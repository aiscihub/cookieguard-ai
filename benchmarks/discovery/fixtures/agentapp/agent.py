"""Browser Use agent that signs in to the Acme staging app.

Usage: python app.py & ANTHROPIC_API_KEY=... python agent.py
"""

import asyncio
import os

from browser_use import Agent, BrowserProfile, BrowserSession
from browser_use.llm import ChatAnthropic

ORIGIN = os.environ.get('ACME_ORIGIN', 'http://127.0.0.1:{{PORT}}')


async def main() -> None:
    session = BrowserSession(browser_profile=BrowserProfile(headless=True, allowed_domains=['127.0.0.1']))
    agent = Agent(
        task=f'Go to {ORIGIN}/login and sign in with username <secret>user</secret> and password <secret>password</secret>. '
             'Stop when the dashboard says Login succeeded.',
        llm=ChatAnthropic(model='claude-sonnet-5-5'),
        browser_session=session,
        sensitive_data={ORIGIN: {'user': 'demo', 'password': os.environ.get('ACME_PASSWORD', 'demo123')}},
    )
    await agent.run(max_steps=10)


if __name__ == '__main__':
    asyncio.run(main())
