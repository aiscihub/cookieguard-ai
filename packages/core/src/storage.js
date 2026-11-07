import { AuditError, limitArray, originOf, textField } from './safety.js';

// Web Storage (localStorage and sessionStorage) is readable by every script on
// the origin, so a session or access token kept there is exposed to XSS the same
// way a cookie without HttpOnly is. Adapters read entries in the browser and call
// storageObservation() with the value; only the value-free result leaves.

export const AREAS = Object.freeze(['local', 'session']);
export const TOKEN_KINDS = Object.freeze(['jwt', 'token-in-json', 'token-key', 'configured']);
const MAX_VALUE = 65536;
const TOKEN_FIELD = /^(?:access_?token|id_?token|refresh_?token|auth_?token|session_?token|session_?id|bearer|jwt|token)$/i;
const TOKEN_KEY = /(?:^|[^a-z])(?:token|jwt|auth|session|sid|bearer|credential|access|refresh)s?(?:$|[^a-z])/i;
const OPAQUE = /^[A-Za-z0-9._~+/=-]{16,4096}$/;

function base64UrlJson(segment) {
  try {
    const text = Buffer.from(segment.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8');
    const value = JSON.parse(text);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch { return null; }
}

function isJwt(value) {
  const parts = value.split('.');
  if (parts.length !== 3 || !/^[A-Za-z0-9_-]{10,}$/.test(parts[0]) || !/^[A-Za-z0-9_-]{2,}$/.test(parts[1])
    || !/^[A-Za-z0-9_-]*$/.test(parts[2])) return false;
  const header = base64UrlJson(parts[0]);
  return Boolean(header && typeof header.alg === 'string');
}

function jsonHasToken(value, depth = 0) {
  if (depth > 3 || !value || typeof value !== 'object') return false;
  for (const [field, inner] of Object.entries(value).slice(0, 200)) {
    if (typeof inner === 'string' && TOKEN_FIELD.test(field) && (isJwt(inner) || OPAQUE.test(inner))) return true;
    if (inner && typeof inner === 'object' && jsonHasToken(inner, depth + 1)) return true;
  }
  return false;
}

// camelCase keys such as accessToken become access_Token for the boundary test.
const words = key => key.replace(/([a-z0-9])([A-Z])/g, '$1_$2');

/** Returns the kind of token a Web Storage entry appears to hold, or null. The value is never retained. */
export function classifyStorageEntry(key, value) {
  if (typeof key !== 'string' || typeof value !== 'string' || value.length > MAX_VALUE) return null;
  const trimmed = value.trim();
  if (isJwt(trimmed)) return 'jwt';
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try { if (jsonHasToken(JSON.parse(trimmed))) return 'token-in-json'; } catch { /* not JSON */ }
    return null;
  }
  if (TOKEN_KEY.test(words(key)) && OPAQUE.test(trimmed) && /\d/.test(trimmed) && /[A-Za-z]/.test(trimmed)) return 'token-key';
  return null;
}

/** A storage key is reported only after removing the value and anything that looks like an identifier or secret. */
export function safeStorageKey(key, value = '') {
  // Long runs with digits (client ids, API keys, user ids) or very long runs are masked; words are kept.
  return textField(key, '', value).slice(0, 256)
    .replace(/[A-Za-z0-9_-]{16,}/g, run => (/\d/.test(run) || run.length >= 40 ? '[redacted]' : run));
}

/**
 * Builds a value-free storage observation, or null when the entry does not look
 * like a token and its key is not one of the configured authStorageKeys.
 */
export function storageObservation(entry, policy = {}) {
  if (!entry || typeof entry !== 'object' || !AREAS.includes(entry.area) || typeof entry.key !== 'string') throw new AuditError('INPUT');
  const configured = Array.isArray(policy.authStorageKeys) && policy.authStorageKeys.includes(entry.key);
  const token = classifyStorageEntry(entry.key, entry.value) ?? (configured ? 'configured' : null);
  if (!token) return null;
  // A configured key is the developer's own name and is reported as given.
  const key = configured ? textField(entry.key, '', typeof entry.value === 'string' ? entry.value : '') : safeStorageKey(entry.key, entry.value);
  return { schemaVersion: 1, origin: originOf(entry.origin), area: entry.area, key, token, configured };
}

/** Rebuilds a storage observation field by field. */
export function cleanStorageObservation(input) {
  if (!input || input.schemaVersion !== 1 || !AREAS.includes(input.area) || !TOKEN_KINDS.includes(input.token)
    || typeof input.key !== 'string' || typeof input.configured !== 'boolean') throw new AuditError('INPUT');
  return { schemaVersion: 1, origin: originOf(input.origin), area: input.area, key: textField(input.key).slice(0, 256),
    token: input.token, configured: input.configured };
}

export function cleanStorage(input) {
  return limitArray(input ?? [], 1000).map(cleanStorageObservation);
}
