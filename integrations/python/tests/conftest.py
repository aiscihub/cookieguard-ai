"""Shared helpers. Synthetic canaries stand in for session tokens and must never appear in output."""

from __future__ import annotations

import asyncio
import os
import secrets
import traceback
from contextlib import asynccontextmanager

for key, value in (('ANONYMIZED_TELEMETRY', 'false'), ('BROWSER_USE_CLOUD_SYNC', 'false'),
	('BROWSER_USE_DISABLE_EXTENSIONS', '1')):
	os.environ.setdefault(key, value)

import pytest  # noqa: E402

CANARY_PREFIX = 'CGBU_CANARY_'


def pytest_configure(config):
	# Registered here too, so the copied suite runs cleanly outside this project.
	config.addinivalue_line('markers', 'browser: launches a real local Chromium through Browser Use')


def canary() -> str:
	return f'{CANARY_PREFIX}{secrets.token_hex(12)}'


def assert_clean(*texts: object) -> None:
	for text in texts:
		value = text if isinstance(text, str) else repr(text)
		assert CANARY_PREFIX not in value, 'Synthetic secret leaked into output'


def exception_text(error: BaseException) -> str:
	"""Everything a developer could see from an exception: message, repr, chain, traceback."""
	parts = [str(error), repr(error), ''.join(traceback.format_exception(error))]
	seen: set[int] = set()
	current: BaseException | None = error
	while current is not None and id(current) not in seen:
		seen.add(id(current))
		parts += [str(current), repr(current), repr(getattr(current, 'args', ()))]
		current = current.__cause__ or current.__context__
	return '\n'.join(parts)


def run(coroutine, timeout: float = 150):
	"""Run a coroutine with a deadline. Unlike asyncio.run, cleanup is bounded too:
	tasks that ignore cancellation cannot hang the suite (they did when Chrome failed to launch)."""
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	try:
		return loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
	finally:
		pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
		for task in pending:
			task.cancel()
		if pending:
			loop.run_until_complete(asyncio.wait(pending, timeout=10))
		try:
			loop.run_until_complete(asyncio.wait_for(loop.shutdown_asyncgens(), 5))
		except Exception:
			pass
		asyncio.set_event_loop(None)
		loop.close()


@asynccontextmanager
async def browser_session(**profile):
	from browser_use import BrowserProfile, BrowserSession

	options = {'headless': True, 'keep_alive': True, 'enable_default_extensions': False, 'user_data_dir': None}
	options.update(profile)
	session = BrowserSession(browser_profile=BrowserProfile(**options))
	try:
		await session.start()  # Inside try: a failed launch must still be killed.
		yield session
	finally:
		await session.kill()


async def login(tools, session, origin: str, *, password: str | None = None, new_tab: bool = False) -> None:
	"""Log in with Browser Use's own navigate/input/click actions, as an agent would."""
	from cookieguard.browser_use.demo.app import DEMO_PASSWORD, DEMO_USERNAME

	result = await tools.registry.execute_action('navigate', {'url': f'{origin}/login', 'new_tab': new_tab},
		browser_session=session)
	assert not result.error
	state = await session.get_browser_state_summary(include_screenshot=False)
	indices = {}
	for index, node in state.dom_state.selector_map.items():
		attributes = node.attributes or {}
		if attributes.get('id') == 'username':
			indices['username'] = index
		elif attributes.get('type') == 'password':
			indices['password'] = index
		elif node.tag_name == 'button':
			indices['submit'] = index
	assert set(indices) == {'username', 'password', 'submit'}
	for field, text in (('username', DEMO_USERNAME), ('password', password or DEMO_PASSWORD)):
		result = await tools.registry.execute_action('input', {'index': indices[field], 'text': text}, browser_session=session)
		assert not result.error
	result = await tools.registry.execute_action('click', {'index': indices['submit']}, browser_session=session)
	assert not result.error
	for _ in range(50):
		if (await session.get_current_page_url()).endswith('/account'):
			return
		await asyncio.sleep(0.1)
	raise AssertionError('login did not reach /account')


@pytest.fixture
def token():
	return canary()
