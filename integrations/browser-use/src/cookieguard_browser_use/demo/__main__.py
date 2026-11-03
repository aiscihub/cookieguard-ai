"""Run both demo scenarios: ``python -m cookieguard_browser_use.demo``.

A real Browser Use Agent logs in to a loopback app, driven by a scripted
stand-in model (no AI provider or API key). CookieGuard then enforces the
cookie policy independently. Use ``--headed`` to watch the browser.
Exit code 0 means both scenarios produced the expected CookieGuard results.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .scripted import run_scenario

EXPECTED = {'insecure': 'FAIL', 'secure': 'PASS'}


async def _main(args: argparse.Namespace) -> int:
	ok = True
	for mode in args.modes:
		outcome = await run_scenario(mode, headless=not args.headed)
		result = outcome.result
		print(f'\n=== Scenario: {mode} login ===')
		print(f'Login succeeded: {"yes" if outcome.login_succeeded else "no"}')
		print(f'Agent called cookieguard_audit: {"yes" if outcome.agent_called_audit else "no"}')
		print(result.summary.rstrip())
		print(f'CookieGuard for Browser Use: {result.status} (exit code {result.exit_code}); '
			f'evidence: {result.collection["evidence"]}')
		for finding in result.confirmed_findings:
			print(f'  {finding.rule_id} {finding.severity}: {finding.title}. Why: {finding.explanation}')
		expected = EXPECTED[mode]
		matched = outcome.login_succeeded and result.status == expected
		print(f'Expected {expected}: {"yes" if matched else "NO"}')
		ok = ok and matched
	return 0 if ok else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	# No argparse `choices` here: Python 3.11 rejects an empty nargs='*' list against them.
	parser.add_argument('modes', nargs='*', metavar='MODE', help='insecure and/or secure (default: both)')
	parser.add_argument('--headed', action='store_true', help='show the browser window')
	args = parser.parse_args(argv)
	unknown = [mode for mode in args.modes if mode not in EXPECTED]
	if unknown:
		parser.error(f"unknown mode {unknown[0]!r}; choose from {', '.join(EXPECTED)}")
	args.modes = args.modes or list(EXPECTED)
	return args


def main(argv: list[str] | None = None) -> int:
	return asyncio.run(_main(parse_args(argv)))


if __name__ == '__main__':
	sys.exit(main())
