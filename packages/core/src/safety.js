const messages = Object.freeze({
  CONFIG: 'Invalid CookieGuard configuration. See --help or the API documentation.',
  INPUT: 'Invalid or oversized cookie input. Raw input has been withheld.',
  TARGET: 'Target is outside the authorized HTTP(S) scan boundary.',
  NETWORK: 'HTTP scan could not complete. Check connectivity, TLS, status, and timeout.',
  REDIRECT: 'Redirect exceeded the scan boundary or redirect limit.',
  COLLECT: 'Browser cookie collection could not complete. Start a new collector and retry.',
  MODEL: 'Explicit ONNX classification failed. Check the runtime, model, and metadata; no fallback was used.',
  OUTPUT: 'Could not write the sanitized report. Check the destination and permissions.',
  BASELINE: 'Baseline is invalid or incompatible with this audit.',
});

export class AuditError extends Error {
  constructor(code = 'INPUT') {
    super(messages[code] || messages.INPUT);
    this.name = 'AuditError';
    this.code = Object.hasOwn(messages, code) ? code : 'INPUT';
  }
}

export function safeError(error) {
  // Never trust exception.message, cause, stack, network headers, or paths.
  return new AuditError(error instanceof AuditError ? error.code : 'INPUT');
}

export function textField(value, fallback = '', secret = '') {
  if (typeof value !== 'string') return fallback;
  let result = value.slice(0, 1024).replace(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, '?');
  if (secret && (secret.length >= 8 || result === secret)) result = result.split(secret).join('[redacted]');
  return result;
}

export function originOf(value) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error();
    return url.origin;
  } catch { throw new AuditError('INPUT'); }
}

export const classes = Object.freeze(['authentication', 'other', 'preference', 'tracking']);
export const sameSites = Object.freeze(['strict', 'lax', 'none']);
export const levels = Object.freeze({ info: 0, low: 1, medium: 2, high: 3, critical: 4 });

export function sameSite(value) {
  if (typeof value !== 'string') return null;
  const normalized = value.toLowerCase() === 'no_restriction' ? 'none' : value.toLowerCase();
  return sameSites.includes(normalized) ? normalized : null;
}

export function limitArray(value, max = 1000) {
  if (!Array.isArray(value) || value.length > max) throw new AuditError('INPUT');
  return value;
}
