"""CookieGuard: authentication-cookie policy checks for AI browser agents and tests.

The shared core (results, errors, origin checks, and the local CookieGuard engine)
lives in this package. Each integration is a subpackage; today that is
``cookieguard.browser_use``. Its main names are also available here, loaded on first
use, so ``from cookieguard import CookieGuardAudit`` works.
"""

from __future__ import annotations

from typing import Any

from ._errors import CookieGuardError, CookiePolicyError
from ._result import AuditResult, Finding

__version__ = '0.2.0'

# Integration names, imported only when first used so the core never requires an
# integration's dependencies.
_INTEGRATION_NAMES = {
	'CookieGuardAudit': 'browser_use',
	'ACTION_DESCRIPTION': 'browser_use',
	'DEFAULT_ACTION_NAME': 'browser_use',
}

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


def __getattr__(name: str) -> Any:
	if name in _INTEGRATION_NAMES:
		from importlib import import_module

		value = getattr(import_module(f'.{_INTEGRATION_NAMES[name]}', __name__), name)
		globals()[name] = value
		return value
	raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__() -> list[str]:
	return sorted(set(globals()) | set(__all__))
