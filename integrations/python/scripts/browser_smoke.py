"""Bounded, step-by-step smoke check of the browser stack, for CI diagnostics.

    python scripts/browser_smoke.py

Each step has its own timeout and prints a marker, so a hang or crash names
the step. No credentials or cookies are involved: it only opens the login page.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

for key, value in (('ANONYMIZED_TELEMETRY', 'false'), ('BROWSER_USE_CLOUD_SYNC', 'false')):
	os.environ.setdefault(key, value)


def mark(step: str, started: float) -> None:
	print(f'[smoke] {step} ({time.monotonic() - started:.1f}s)', flush=True)


async def bounded(step: str, awaitable, seconds: float):
	started = time.monotonic()
	print(f'[smoke] {step} ...', flush=True)
	result = await asyncio.wait_for(awaitable, seconds)
	mark(f'{step}: ok', started)
	return result


async def main() -> int:
	from browser_use import BrowserProfile, BrowserSession, Tools
	from browser_use.browser.watchdogs.local_browser_watchdog import LocalBrowserWatchdog

	from cookieguard import CookieGuardAudit
	from cookieguard._engine import node_major, resolve_node
	from cookieguard.browser_use.demo.app import DemoApp

	print(f'[smoke] python {sys.version.split()[0]} on {sys.platform}', flush=True)
	print(f'[smoke] browser chosen by Browser Use: {LocalBrowserWatchdog._find_installed_browser_path()}', flush=True)
	print(f'[smoke] node {resolve_node()} major {await node_major(resolve_node())}', flush=True)
	with DemoApp('secure') as app:
		session = BrowserSession(browser_profile=BrowserProfile(
			headless=True, keep_alive=True, enable_default_extensions=False, user_data_dir=None))
		try:
			await bounded('BrowserSession.start', session.start(), 60)
			version = await bounded('Browser.getVersion', session.cdp_client.send.Browser.getVersion(), 10)
			print(f'[smoke] browser product: {version.get("product")}', flush=True)
			audit = CookieGuardAudit(allowed_origins=[app.origin], auth_cookies=['session_id'])
			tools = Tools()
			audit.register_tools(tools)
			await bounded('audit.start (engine + CDP observer)', audit.start(session), 30)
			result = await bounded('navigate to demo login', tools.registry.execute_action(
				'navigate', {'url': f'{app.origin}/login'}, browser_session=session), 30)
			print(f'[smoke] navigate error: {result.error}', flush=True)
			audit_result = await bounded('audit.finish', audit.finish(), 30)
			print(f'[smoke] audit status without a login: {audit_result.status} (INCOMPLETE expected)', flush=True)
		finally:
			await bounded('BrowserSession.kill', session.kill(), 30)
	print('[smoke] done', flush=True)
	return 0


if __name__ == '__main__':
	sys.exit(asyncio.run(main()))
