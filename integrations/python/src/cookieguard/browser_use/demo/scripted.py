"""Deterministic Browser Use run of the demo login, with no AI model.

``ScriptedLoginModel`` implements Browser Use's ``BaseChatModel`` protocol and
returns fixed actions based on the browser state the real ``Agent`` sends it.
It is a stand-in for an LLM so the real Agent loop, Tools registry, browser
actions, and CookieGuard integration can be tested without a paid model. It is
not an AI model and makes no network calls.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

for _key, _value in (('ANONYMIZED_TELEMETRY', 'false'), ('BROWSER_USE_CLOUD_SYNC', 'false')):
	os.environ.setdefault(_key, _value)

from .app import DEMO_PASSWORD, DEMO_USERNAME, SESSION_COOKIE, DemoApp  # noqa: E402

TASK = ('Sign in to the local demo app at {origin}/login with username <secret>login_user</secret> and password '
	'<secret>login_password</secret>. When the account page confirms the sign-in, call cookieguard_audit, '
	'then finish and report its status.')


def _section(text: str, tag: str) -> str:
	match = re.search(rf'<{tag}>(.*?)</{tag}>', text, re.S)
	return match.group(1) if match else ''


def _text(message: Any) -> str:
	content = getattr(message, 'content', '')
	if isinstance(content, str):
		return content
	parts = []
	for part in content or []:
		parts.append(getattr(part, 'text', '') or '')
	return '\n'.join(parts)


class ScriptedLoginModel:
	"""A fixed, non-AI policy for the demo login page. Implements BaseChatModel."""

	_verified_api_keys = True
	model = 'cookieguard-scripted-login'

	def __init__(self, origin: str, *, call_audit_tool: bool = True) -> None:
		self.origin = origin
		self.call_audit_tool = call_audit_tool
		self.calls = 0
		self.observed_messages: list[str] = []

	@property
	def provider(self) -> str:
		return 'scripted'

	@property
	def name(self) -> str:
		return self.model

	@property
	def model_name(self) -> str:
		return self.model

	async def ainvoke(self, messages: list[Any], output_format: type | None = None, **kwargs: Any):
		from browser_use.llm.views import ChatInvokeCompletion

		self.calls += 1
		text = '\n'.join(_text(message) for message in messages)
		self.observed_messages.append(text)
		if output_format is None:
			return ChatInvokeCompletion(completion='ok', usage=None)
		return ChatInvokeCompletion(completion=output_format.model_validate(self._decide(messages, text)), usage=None)

	def _decide(self, messages: list[Any], text: str) -> dict[str, Any]:
		latest = _text(messages[-1]) if messages else text
		state, history = _section(latest, 'browser_state'), _section(latest, 'agent_history')
		brain = {'evaluation_previous_goal': 'Scripted step.', 'memory': 'Scripted demo login.', 'next_goal': ''}
		if 'CookieGuard provisional check' in history or 'CookieGuard audit is not active' in history:
			status = re.search(r'Status: (PASS|FAIL|INCOMPLETE)', history)
			report = f'Logged in. CookieGuard provisional status: {status.group(1) if status else "unknown"}.'
			return {**brain, 'next_goal': 'Finish', 'action': [{'done': {'text': report, 'success': True}}]}
		if 'Login succeeded' in state:
			if self.call_audit_tool:
				return {**brain, 'next_goal': 'Run CookieGuard', 'action': [{'cookieguard_audit': {}}]}
			return {**brain, 'next_goal': 'Finish', 'action': [{'done': {'text': 'Logged in.', 'success': True}}]}
		username = re.search(r'\[(\d+)\]<input id=username', state)
		password = re.search(r'\[(\d+)\]<input type=password', state)
		submit = re.search(r'\[(\d+)\]<button type=submit', state)
		if username and password and submit:
			return {**brain, 'next_goal': 'Sign in', 'action': [
				{'input': {'index': int(username.group(1)), 'text': '<secret>login_user</secret>'}},
				{'input': {'index': int(password.group(1)), 'text': '<secret>login_password</secret>'}},
				{'click': {'index': int(submit.group(1))}},
			]}
		return {**brain, 'next_goal': 'Open login', 'action': [{'navigate': {'url': f'{self.origin}/login'}}]}


@dataclass
class DemoOutcome:
	mode: str
	login_succeeded: bool
	agent_called_audit: bool
	agent_final_text: str | None
	result: Any  # cookieguard.AuditResult


async def run_scenario(mode: str, *, headless: bool = True, call_audit_tool: bool = True, capture_headers: bool = True,
	token_factory=None, model: Any = None) -> DemoOutcome:
	"""Run the demo login through a real Browser Use Agent, then the CookieGuard audit."""
	from browser_use import Agent, BrowserProfile, BrowserSession, Tools

	from .. import CookieGuardAudit

	with DemoApp(mode, token_factory=token_factory) as app:
		audit = CookieGuardAudit(allowed_origins=[app.origin], auth_cookies=[SESSION_COOKIE], fail_on='high',
			capture_headers=capture_headers)
		session = BrowserSession(browser_profile=BrowserProfile(
			headless=headless, keep_alive=True, enable_default_extensions=False,
			allowed_domains=audit.browser_allowed_domains(), user_data_dir=None))
		tools = Tools()
		audit.register_tools(tools)
		llm = model or ScriptedLoginModel(app.origin, call_audit_tool=call_audit_tool)
		try:
			await session.start()
			await audit.start(session)
			agent = Agent(
				task=TASK.format(origin=app.origin), llm=llm, browser_session=session, tools=tools,
				sensitive_data={audit.browser_allowed_domains()[0]: {'login_user': DEMO_USERNAME, 'login_password': DEMO_PASSWORD}},
				use_vision=False, use_judge=False, calculate_cost=False, max_actions_per_step=4)
			history = await agent.run(max_steps=8)
			result = await audit.finish()
		finally:
			await audit.close()
			await session.kill()
		called = any(
			action and 'cookieguard_audit' in action
			for step in history.model_actions() for action in [step])
		return DemoOutcome(mode=mode, login_succeeded=app.logins > 0, agent_called_audit=called,
			agent_final_text=history.final_result(), result=result)
