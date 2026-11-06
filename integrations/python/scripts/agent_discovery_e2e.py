"""End-to-end: Browser Use login evidence, audited through the CookieGuard MCP server.

1. A real Browser Use Agent (scripted model, real Chromium) signs in to the local
   demo app; ``CookieGuardAudit`` writes a sanitized result for each scenario.
2. An MCP client using the official *Python* MCP SDK starts the Node MCP server,
   reads its capabilities, selects the browser-session integration, and audits the
   evidence files. It also checks missing, malformed, and out-of-scope inputs.
3. A synthetic session-token canary must not appear in any file or MCP response.

Run from integrations/python: ``.venv/bin/python scripts/agent_discovery_e2e.py``.
Needs Node.js 24+ and ``npm ci`` at the repository root. Exit code 0 means every
expected outcome was observed.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cookieguard.browser_use.demo.scripted import ScriptedLoginModel, run_scenario

ROOT = Path(__file__).resolve().parents[3]
MCP_BIN = ROOT / 'packages' / 'mcp' / 'bin' / 'cookieguard-mcp.js'
CANARY = f'CGBU_CANARY_{secrets.token_hex(12)}'


class NeverLogsIn(ScriptedLoginModel):
	"""An agent that claims success without signing in: no session is ever created."""

	def _decide(self, messages, text):
		return {'evaluation_previous_goal': 'ok', 'memory': 'ok', 'next_goal': 'done',
			'action': [{'done': {'text': 'Logged in.', 'success': True}}]}


def check(condition: bool, label: str) -> None:
	print(f'{"ok  " if condition else "FAIL"} {label}')
	if not condition:
		raise SystemExit(1)


def clean(text: str, label: str) -> None:
	if CANARY in text:
		print(f'FAIL secret canary leaked: {label}')
		raise SystemExit(1)


async def collect(evidence: Path) -> list[str]:
	origins: set[str] = set()
	for name, mode, model in (('insecure-login', 'insecure', None), ('secure-login', 'secure', None),
			('no-session', 'secure', NeverLogsIn('http://127.0.0.1:1'))):
		outcome = await run_scenario(mode, model=model, token_factory=lambda: CANARY)
		path = outcome.result.write_json(evidence / f'{name}.json')
		clean(path.read_text(), path.name)
		report = outcome.result.report
		origins.update(o for o in [report['target'], *(c['observation']['origin'] for c in report['cookies'])] if o)
		print(f'Browser Use {name}: login {"succeeded" if outcome.login_succeeded else "not performed"}; '
			f'local result {outcome.result.status}; wrote {path.name}')
	(evidence / 'malformed.json').write_text('{"schemaVersion": 1, "integration": "cookieguard-browser-use"')
	return sorted(origins)


async def audit(evidence: Path, origins: list[str], config_path: Path) -> None:
	config_path.write_text(json.dumps({'allowedOrigins': origins, 'policy': {'authCookies': ['session_id']},
		'evidenceDir': str(evidence)}))
	node = shutil.which('node')
	check(node is not None, 'Node.js is on PATH')
	params = StdioServerParameters(command=node, args=[str(MCP_BIN), '--config', str(config_path)])
	async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
		await session.initialize()

		async def call(name: str, arguments: dict) -> dict:
			response = await session.call_tool(name, arguments)
			clean(response.model_dump_json(), name)
			payload = response.structured_content
			check(payload == json.loads(response.content[0].text), f'{name}: structured and text results match')
			return {'isError': response.is_error, **payload}

		tools = sorted(tool.name for tool in (await session.list_tools()).tools)
		check('cookieguard_capabilities' in tools and 'cookieguard_audit' in tools, f'discovered tools: {", ".join(tools)}')
		capabilities = await call('cookieguard_capabilities', {})
		check(capabilities['configuration']['evidenceFiles'], 'server accepts evidence files from its configured directory')
		# Selection: the workflow needs a real login, which HTTP header scans cannot do.
		check(any('cannot log in' in item for item in capabilities['limitations']), 'capabilities state that header scans cannot log in')
		chosen = next(i for i in capabilities['integrations'] if i['id'] == 'browser-use')
		print(f'Selected integration: {chosen["package"]} {chosen["version"]} for an authenticated browser workflow')

		insecure = await call('cookieguard_audit', {'evidenceFile': 'insecure-login.json'})
		cg001 = [f for f in insecure['findings'] if f['ruleId'] == 'CG001']
		check(insecure['status'] == 'failed' and insecure['exitCode'] == 1 and not insecure['isError'], 'insecure login: FAIL (exitCode 1)')
		check(bool(cg001) and cg001[0]['status'] == 'confirmed' and cg001[0]['cookieName'] == 'session_id',
			'insecure login: CG001 Missing HttpOnly is a confirmed finding on session_id')
		check(insecure['provenance'] == {'source': 'evidence-file', 'producer': 'cookieguard-browser-use', 'observedByServer': False},
			'insecure login: provenance names the Browser Use evidence file')
		explained = await call('cookieguard_explain', {'id': 'CG001'})
		print(f'  Fix: {explained["explanation"]["fix"]}')

		secure = await call('cookieguard_audit', {'evidenceFile': 'secure-login.json'})
		check(secure['status'] == 'passed' and secure['exitCode'] == 0 and secure['summary']['confirmedViolations'] == 0,
			'secure login: PASS (exitCode 0) with no confirmed violations')

		missing_session = await call('cookieguard_audit', {'evidenceFile': 'no-session.json'})
		check(missing_session['status'] == 'incomplete' and 'expected-auth-cookie-not-observed' in missing_session['issues'],
			'unavailable session: INCOMPLETE (expected-auth-cookie-not-observed), not a pass')
		for arguments, code, label in (
			({'evidenceFile': 'missing.json'}, 'EVIDENCE', 'missing evidence file'),
			({'evidenceFile': 'malformed.json'}, 'INPUT', 'malformed evidence file'),
			({'evidenceFile': '../cookieguard.json'}, 'EVIDENCE', 'path outside the evidence directory'),
			({'url': 'http://127.0.0.1:1/login'}, 'TARGET', 'URL on an unconfigured origin'),
			({'url': f'{origins[0]}/login', 'evidenceFile': 'secure-login.json'}, 'CONFIG', 'ambiguous arguments'),
		):
			result = await call('cookieguard_audit', arguments)
			check(result['isError'] and result['status'] == 'incomplete' and result['error']['code'] == code,
				f'{label}: INCOMPLETE with error {code}')


async def main() -> int:
	with tempfile.TemporaryDirectory(prefix='cookieguard-e2e-') as temp:
		evidence = Path(temp) / 'evidence'
		evidence.mkdir()
		origins = await collect(evidence)
		await audit(evidence, origins, Path(temp) / 'cookieguard.json')
	print('Agent discovery end-to-end passed; the session-token canary never appeared in evidence or MCP output.')
	return 0


if __name__ == '__main__':
	sys.exit(asyncio.run(main()))
