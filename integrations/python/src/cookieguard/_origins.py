"""Authorized-origin handling. Origins restrict evidence collection; they are never expanded."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from ._errors import CookieGuardError

MAX_ORIGINS = 20
_DEFAULT_PORTS = {'http': 80, 'https': 443}


def _split(value: str):
	if not isinstance(value, str) or len(value) > 2048 or not value.isascii():
		return None
	try:
		url = urlsplit(value)
		port = url.port
	except ValueError:
		return None
	if url.scheme not in _DEFAULT_PORTS or not url.hostname or url.username is not None or url.password is not None:
		return None
	return url, port


def origin_of(value: str) -> str | None:
	"""Serialize a URL's origin like the WHATWG URL parser for ASCII HTTP(S) URLs, or return None."""
	parts = _split(value)
	if parts is None:
		return None
	url, port = parts
	host = url.hostname.lower()
	if ':' in host:
		host = f'[{host}]'
	if port is not None and port != _DEFAULT_PORTS[url.scheme]:
		return f'{url.scheme}://{host}:{port}'
	return f'{url.scheme}://{host}'


def is_loopback(origin: str) -> bool:
	host = urlsplit(origin).hostname or ''
	if host == 'localhost':
		return True
	try:
		return ipaddress.ip_address(host).is_loopback
	except ValueError:
		return False


def host_of(origin: str) -> str:
	return (urlsplit(origin).hostname or '').lower()


def validate_origins(values, allow_nonlocal: bool) -> tuple[str, ...]:
	"""Return exact, deduplicated origins. Paths, queries, fragments, and credentials are rejected."""
	if isinstance(values, str) or not isinstance(values, (list, tuple)) or not values or len(values) > MAX_ORIGINS:
		raise CookieGuardError('CONFIG')
	if not isinstance(allow_nonlocal, bool):
		raise CookieGuardError('CONFIG')
	result: list[str] = []
	for value in values:
		parts = _split(value)
		if parts is None or parts[0].path not in ('', '/') or parts[0].query or parts[0].fragment or value.endswith(('?', '#')):
			raise CookieGuardError('CONFIG')
		origin = origin_of(value)
		if origin is None:
			raise CookieGuardError('CONFIG')
		if not allow_nonlocal and not is_loopback(origin):
			raise CookieGuardError('TARGET')
		if origin not in result:
			result.append(origin)
	return tuple(result)


def cookie_matches_origins(domain: object, origins: tuple[str, ...]) -> bool:
	"""Same host matching as the CookieGuard collector: exact host, or a Domain cookie's subdomains."""
	if not isinstance(domain, str):
		return False
	bare = domain.removeprefix('.').lower()
	for origin in origins:
		host = host_of(origin)
		if host == bare or (domain.startswith('.') and host.endswith(f'.{bare}')):
			return True
	return False
