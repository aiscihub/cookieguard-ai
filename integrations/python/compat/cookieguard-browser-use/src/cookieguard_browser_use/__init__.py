"""Compatibility module for code written against cookieguard-browser-use 0.1.

CookieGuard's Browser Use integration now lives in ``cookieguard.browser_use``. This
module re-exports its public API, so ``from cookieguard_browser_use import
CookieGuardAudit`` returns the same objects. New code should import from
``cookieguard``.
"""

from cookieguard.browser_use import (
	ACTION_DESCRIPTION,
	DEFAULT_ACTION_NAME,
	AuditResult,
	CookieGuardAudit,
	CookieGuardError,
	CookiePolicyError,
	Finding,
)

__version__ = '0.2.0'
__all__ = [
	'ACTION_DESCRIPTION',
	'AuditResult',
	'CookieGuardAudit',
	'CookieGuardError',
	'CookiePolicyError',
	'DEFAULT_ACTION_NAME',
	'Finding',
	'__version__',
]
