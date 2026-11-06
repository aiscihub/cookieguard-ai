"""CookieGuard for Browser Use agents.

The agent performs the authorized workflow; CookieGuard observes the same
browser over its own CDP connection and the local CookieGuard core engine
decides PASS, FAIL, or INCOMPLETE. The agent cannot override that decision.
"""

from .._errors import CookieGuardError, CookiePolicyError
from .._result import AuditResult, Finding
from ._audit import ACTION_DESCRIPTION, DEFAULT_ACTION_NAME, CookieGuardAudit

__all__ = [
	'ACTION_DESCRIPTION',
	'AuditResult',
	'CookieGuardAudit',
	'CookieGuardError',
	'CookiePolicyError',
	'DEFAULT_ACTION_NAME',
	'Finding',
]
