"""Fixed-message errors. Exception text never contains input, values, or URLs."""

from __future__ import annotations

_MESSAGES = {
	'CONFIG': 'Invalid CookieGuard configuration. See the cookieguard-browser-use documentation.',
	'TARGET': 'An audited origin is outside the authorized boundary. Nonlocal origins need allow_nonlocal_origins=True.',
	'KEEP_ALIVE': (
		'Browser Use closes the browser after Agent.run() unless keep_alive=True, so CookieGuard could not '
		'read the final cookie state. Create the BrowserSession with keep_alive=True and kill it after audit.finish().'
	),
	'SESSION': 'Start the Browser Use BrowserSession before starting the CookieGuard audit.',
	'STATE': 'The CookieGuard audit is not in a valid state for this call. Start a new audit for another workflow.',
	'ENGINE': 'The local CookieGuard engine could not run. Check that Node.js 24+ is installed and the package is complete.',
	'COLLECT': 'Browser cookie collection could not complete. Start a new audit and retry.',
	'OUTPUT': 'Could not produce or write the sanitized report. Unsafe output, if any, was withheld.',
	'INPUT': 'Invalid or oversized cookie evidence. Raw input has been withheld.',
	'BASELINE': 'Baseline is invalid or incompatible with this audit.',
}
# Engine codes emitted by @aiscihub/cookieguard-core's AuditError.
_ENGINE_CODES = {'CONFIG', 'INPUT', 'COLLECT', 'BASELINE', 'OUTPUT', 'TARGET'}


class CookieGuardError(Exception):
	"""A CookieGuard tool or configuration error. Treat as an incomplete audit (exit code 2)."""

	exit_code = 2

	def __init__(self, code: str = 'INPUT') -> None:
		self.code = code if code in _MESSAGES else 'INPUT'
		super().__init__(f'CookieGuard {self.code}: {_MESSAGES[self.code]}')


def engine_error(code: object) -> CookieGuardError:
	return CookieGuardError(code if isinstance(code, str) and code in _ENGINE_CODES else 'ENGINE')


class CookiePolicyError(AssertionError):
	"""Raised by AuditResult.assert_policy() for FAIL (exit 1) or INCOMPLETE (exit 2) results."""

	def __init__(self, message: str, *, status: str, exit_code: int) -> None:
		super().__init__(message)
		self.status = status
		self.exit_code = exit_code
