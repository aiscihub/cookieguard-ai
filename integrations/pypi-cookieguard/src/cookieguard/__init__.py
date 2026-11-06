"""CookieGuard authentication-cookie policy checks.

This distribution installs ``cookieguard-browser-use`` and re-exports its public
API: ``from cookieguard import CookieGuardAudit`` is the same object as
``from cookieguard_browser_use import CookieGuardAudit``. See
https://github.com/aiscihub/cookieguard-ai/tree/main/integrations/browser-use
"""

from cookieguard_browser_use import (
	ACTION_DESCRIPTION,
	DEFAULT_ACTION_NAME,
	AuditResult,
	CookieGuardAudit,
	CookieGuardError,
	CookiePolicyError,
	Finding,
)
from cookieguard_browser_use import __version__ as integration_version

__version__ = '0.1.0'
__all__ = [
	'ACTION_DESCRIPTION',
	'AuditResult',
	'CookieGuardAudit',
	'CookieGuardError',
	'CookiePolicyError',
	'DEFAULT_ACTION_NAME',
	'Finding',
	'__version__',
	'integration_version',
]
