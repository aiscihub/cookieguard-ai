"""CookieGuard + a Browser Use agent logging in to a local demo app.

    python examples/agent_login.py --mode insecure                       # scripted, no API key
    ANTHROPIC_API_KEY=... python examples/agent_login.py --provider anthropic --mode insecure
    BROWSER_USE_API_KEY=... python examples/agent_login.py --provider browser-use --mode secure
    OPENAI_API_KEY=... python examples/agent_login.py --provider openai --model <model-id> --mode secure

Exit code: 0 PASS, 1 confirmed policy FAIL, 2 INCOMPLETE. With --mode insecure the
login succeeds and the exit code is 1: the agent reaching the account page does
not make the session cookie secure.

Model providers receive the task, page content, and CookieGuard's sanitized tool
output. Credentials stay in Browser Use's sensitive_data and are typed as
placeholders; cookie values never reach the model. The app is loopback-only.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Browser Use telemetry would send the task, visited URLs, actions, and final answer.
os.environ.setdefault('ANONYMIZED_TELEMETRY', 'false')
os.environ.setdefault('BROWSER_USE_CLOUD_SYNC', 'false')

from browser_use import Agent, BrowserProfile, BrowserSession, Tools  # noqa: E402

from cookieguard_browser_use import CookieGuardAudit, CookiePolicyError  # noqa: E402
from cookieguard_browser_use.demo.app import DEMO_PASSWORD, DEMO_USERNAME, DemoApp  # noqa: E402
from cookieguard_browser_use.demo.scripted import TASK, ScriptedLoginModel  # noqa: E402

KEYS = {'anthropic': 'ANTHROPIC_API_KEY', 'openai': 'OPENAI_API_KEY', 'browser-use': 'BROWSER_USE_API_KEY'}


def make_llm(provider: str, model: str | None, origin: str):
	if provider == 'scripted':
		return ScriptedLoginModel(origin)  # Deterministic stand-in; not an AI model.
	if not os.environ.get(KEYS[provider]):
		raise SystemExit(f'{KEYS[provider]} is not set; use --provider scripted to run without a model.')
	if provider == 'anthropic':
		from browser_use import ChatAnthropic
		# Adaptive thinking makes browser-use 0.13 send tool_choice "auto"; current
		# Claude models reject the forced tool_choice it would otherwise send.
		return ChatAnthropic(model=model or 'claude-opus-5-5', thinking={'type': 'adaptive'})
	if provider == 'browser-use':
		from browser_use import ChatBrowserUse
		return ChatBrowserUse(**({'model': model} if model else {}))
	if not model:
		raise SystemExit('--model is required for --provider openai.')
	from browser_use import ChatOpenAI
	return ChatOpenAI(model=model)


async def main(args: argparse.Namespace) -> int:
	with DemoApp(args.mode) as app:
		# 1. Configure the audit: exact authorized origins and the known session cookie.
		audit = CookieGuardAudit(allowed_origins=[app.origin], auth_cookies=['session_id'], fail_on='high')
		# keep_alive=True: Agent.run() would otherwise close the browser before audit.finish().
		session = BrowserSession(browser_profile=BrowserProfile(
			headless=not args.headed, keep_alive=True, enable_default_extensions=False,
			allowed_domains=audit.browser_allowed_domains()))
		tools = Tools()
		audit.register_tools(tools)  # Optional: lets the agent request a sanitized provisional check.
		try:
			# 2. Start the browser, then evidence collection, before the login.
			await session.start()
			await audit.start(session)
			# 3-4. The agent performs the authorized login and workflow.
			agent = Agent(
				task=TASK.format(origin=app.origin), llm=make_llm(args.provider, args.model, app.origin),
				browser_session=session, tools=tools, use_vision=False,
				sensitive_data={audit.browser_allowed_domains()[0]: {'login_user': DEMO_USERNAME, 'login_password': DEMO_PASSWORD}})
			history = await agent.run(max_steps=12)
			# 5. Evaluate with the CookieGuard engine, independent of what the agent concluded.
			result = await audit.finish()
		finally:
			await audit.close()
			await session.kill()
		print(f'\nAgent final answer: {history.final_result()}')
		print(f'Server-side logins: {app.logins}\n')
		print(result.summary)
		result.write_json(f'cookieguard-{args.mode}.json')
	# 6. Enforce. In pytest, just call result.assert_policy().
	try:
		result.assert_policy()
	except CookiePolicyError as error:
		print(error)
	return result.exit_code


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Browser Use agent login audited by CookieGuard.')
	parser.add_argument('--mode', choices=['insecure', 'secure'], default='insecure')
	parser.add_argument('--provider', choices=['scripted', *KEYS], default='scripted')
	parser.add_argument('--model', help='model id for the selected provider')
	parser.add_argument('--headed', action='store_true')
	sys.exit(asyncio.run(main(parser.parse_args())))
