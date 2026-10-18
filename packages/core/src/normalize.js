import engine from '../vendor/engine.cjs';
import { AuditError, classes, limitArray, originOf, sameSite, textField } from './safety.js';

const sources = ['header', 'browser', 'fixture', 'legacy'];
const bool = value => typeof value === 'boolean' ? value : null;
const finite = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
const labels = ['ambiguous-attributes', 'invalid-domain', 'invalid-path', 'invalid-expiry', 'partitioned', 'invalid-samesite'];

export function extractCookieFeatures(cookie) {
  if (!cookie || typeof cookie !== 'object') throw new AuditError('INPUT');
  if (typeof cookie.value === 'string' && cookie.value.length > 16384) throw new AuditError('INPUT');
  // Only the original model's numeric feature output crosses this boundary.
  return engine.extractFeatures({
    name: textField(cookie.name), value: typeof cookie.value === 'string' ? cookie.value : '',
    domain: textField(cookie.domain), path: textField(cookie.path, '/'),
    secure: cookie.secure === true, httpOnly: cookie.httpOnly === true,
    sameSite: sameSite(cookie.sameSite) || '',
    expirationDate: finite(cookie.expirationDate ?? cookie.expires) > 0 ? (cookie.expirationDate ?? cookie.expires) : undefined,
    hostOnly: bool(cookie.hostOnly) ?? undefined,
  });
}

export const FEATURE_NAMES = Object.freeze([...engine.FEATURE_NAMES]);

export function classifyCookie(cookie) {
  const classification = engine.classifyRuleBased(extractCookieFeatures(cookie));
  return { mode: 'rule', label: classification.type, score: classification.confidence,
    origin: 'extension-rule-heuristic' };
}

export function cleanTriage(triage) {
  if (!triage || !['rule', 'onnx'].includes(triage.mode) || !classes.includes(triage.label)
    || !Number.isFinite(triage.score) || triage.score < 0 || triage.score > 1) throw new AuditError('INPUT');
  return { mode: triage.mode, label: triage.label, score: Math.round(triage.score * 1e6) / 1e6,
    origin: triage.mode === 'onnx' ? 'extension-onnx-uncalibrated' : 'extension-rule-heuristic' };
}

export function normalizeCookie(input, options = {}) {
  if (!input || typeof input !== 'object' || typeof input.name !== 'string' || !input.name || input.name.length > 256) throw new AuditError('INPUT');
  const source = options.source ?? 'fixture';
  if (!sources.includes(source) || source === 'header') throw new AuditError('CONFIG');
  const now = options.now ?? Date.now();
  if (!Number.isFinite(now)) throw new AuditError('CONFIG');
  const secret = typeof input.value === 'string' ? input.value : '';
  const expires = finite(input.expires ?? input.expirationDate);
  const expiresAt = expires !== null && expires > 0 ? expires : null;
  return {
    schemaVersion: 1,
    name: textField(input.name, '', secret),
    domain: textField(input.domain, '', secret).replace(/^\./, '').toLowerCase(),
    path: textField(input.path, '/', secret),
    secure: bool(input.secure), httpOnly: bool(input.httpOnly),
    hostOnly: bool(input.hostOnly) ?? (typeof input.domain === 'string' && input.domain.startsWith('.') ? false : null),
    sameSite: { declared: 'unknown', effective: sameSite(input.sameSite) },
    expiresAt, lifetimeSeconds: expiresAt === null ? null : Math.max(0, expiresAt - now / 1000),
    deleted: expiresAt !== null && expiresAt <= now / 1000,
    source, origin: options.origin ? textField(originOf(options.origin), '', secret) : null,
    confidence: 'observed', header: null,
    storeStatus: source === 'browser' ? 'present' : 'unverified',
    triage: cleanTriage(options.triage ?? classifyCookie(input)),
  };
}

function defaultPath(path) {
  const end = path.lastIndexOf('/');
  return end <= 0 ? '/' : path.slice(0, end);
}

export function parseSetCookie(header, responseUrl, options = {}) {
  if (typeof header !== 'string' || header.length > 16384 || /[\r\n\0]/.test(header)
    || /,\s*[^;,\s=]+\s*=/.test(header)) throw new AuditError('INPUT');
  const origin = originOf(responseUrl);
  const url = new URL(responseUrl);
  const now = options.now ?? Date.now();
  if (!Number.isFinite(now)) throw new AuditError('CONFIG');
  const parts = header.split(';');
  const pair = parts.shift();
  const equals = pair.indexOf('=');
  const name = pair.slice(0, equals).trim();
  if (equals < 1 || !/^[!#$%&'*+.^_`|~0-9a-z-]+$/i.test(name) || name.length > 256) throw new AuditError('INPUT');
  const value = pair.slice(equals + 1).trim();
  const attrs = new Map();
  const warnings = new Set();
  for (const part of parts) {
    if (!part.trim()) continue;
    const i = part.indexOf('=');
    const key = (i < 0 ? part : part.slice(0, i)).trim().toLowerCase();
    const val = i < 0 ? null : part.slice(i + 1).trim();
    if (attrs.has(key)) warnings.add('ambiguous-attributes');
    attrs.set(key, val);
    if (['secure', 'httponly', 'partitioned'].includes(key) && val !== null) warnings.add('ambiguous-attributes');
  }
  const host = url.hostname.toLowerCase();
  const domain = attrs.has('domain') ? (attrs.get('domain') || '').replace(/^\./, '').toLowerCase() : host;
  if (!domain || !/^[a-z0-9.:[\]-]+$/i.test(domain) || !(host === domain || host.endsWith(`.${domain}`))) warnings.add('invalid-domain');
  const declaredPath = attrs.get('path');
  const path = declaredPath?.startsWith('/') ? declaredPath : defaultPath(url.pathname);
  if (attrs.has('path') && !declaredPath?.startsWith('/')) warnings.add('invalid-path');
  const rawSameSite = attrs.get('samesite')?.toLowerCase();
  const declared = attrs.has('samesite') ? (['strict', 'lax', 'none'].includes(rawSameSite) ? rawSameSite : 'invalid') : 'absent';
  if (declared === 'invalid') warnings.add('invalid-samesite');
  if (attrs.has('partitioned')) warnings.add('partitioned');
  let expiresAt = null;
  let lifetimeSeconds = null;
  if (attrs.has('expires')) {
    const date = Date.parse(attrs.get('expires'));
    if (Number.isFinite(date)) { expiresAt = date / 1000; lifetimeSeconds = Math.max(0, expiresAt - now / 1000); }
    else warnings.add('invalid-expiry');
  }
  // Max-Age takes precedence, including deletion instructions.
  if (attrs.has('max-age')) {
    const maxAge = attrs.get('max-age');
    if (/^-?\d+$/.test(maxAge || '') && Number.isSafeInteger(Number(maxAge))) {
      lifetimeSeconds = Math.max(0, Number(maxAge));
      expiresAt = now / 1000 + lifetimeSeconds;
      warnings.delete('invalid-expiry');
    } else warnings.add('invalid-expiry');
  }
  const secure = attrs.has('secure');
  const httpOnly = attrs.has('httponly');
  const hostOnly = !attrs.has('domain');
  // Chromium permits Secure cookies on trustworthy loopback HTTP origins.
  const trustworthy = url.protocol === 'https:' || host === 'localhost' || host === '[::1]' || /^127(?:\.\d{1,3}){3}$/.test(host);
  let prefixValid = null;
  if (name.startsWith('__Host-')) prefixValid = secure && hostOnly && declaredPath === '/' && trustworthy;
  else if (name.startsWith('__Secure-')) prefixValid = secure && trustworthy;
  const triage = cleanTriage(options.triage ?? classifyCookie({ name, value, domain, path, secure, httpOnly,
    sameSite: declared, expirationDate: expiresAt, hostOnly }));
  return {
    schemaVersion: 1, name: textField(name, '', value), domain: textField(domain, '', value), path: textField(path, '/', value),
    secure, httpOnly, hostOnly, sameSite: { declared, effective: null },
    expiresAt, lifetimeSeconds, deleted: expiresAt !== null && expiresAt <= now / 1000,
    source: 'header', origin: textField(origin, '', value), confidence: warnings.size ? 'uncertain' : 'observed',
    header: { prefixValid, scheme: url.protocol.slice(0, -1), warnings: [...warnings].sort() },
    storeStatus: 'unverified', triage,
  };
}

export function normalizeCookies(inputs, options = {}) {
  return limitArray(inputs).map(input => normalizeCookie(input, options));
}

export function normalizeLegacyResults(results, options = {}) {
  if (!results || typeof results !== 'object') throw new AuditError('INPUT');
  // Deliberately ignore nested context, explanations, errors, and old risk claims.
  return limitArray(results.cookies).map(entry => normalizeCookie(entry.cookie ?? entry, { ...options, source: 'legacy' }));
}

// Reconstruct rather than serialize caller-owned objects, including nested data.
export function cleanObservation(input) {
  if (!input || input.schemaVersion !== 1 || !sources.includes(input.source)
    || typeof input.name !== 'string' || !input.name || typeof input.domain !== 'string'
    || typeof input.path !== 'string' || !['observed', 'uncertain'].includes(input.confidence)) throw new AuditError('INPUT');
  const declared = input.sameSite?.declared;
  if (![...['strict', 'lax', 'none'], 'absent', 'invalid', 'unknown'].includes(declared)) throw new AuditError('INPUT');
  return {
    schemaVersion: 1, name: textField(input.name), domain: textField(input.domain), path: textField(input.path),
    secure: bool(input.secure), httpOnly: bool(input.httpOnly), hostOnly: bool(input.hostOnly),
    sameSite: { declared: input.source === 'header' ? declared : 'unknown', effective: sameSite(input.sameSite?.effective) },
    expiresAt: finite(input.expiresAt), lifetimeSeconds: finite(input.lifetimeSeconds), deleted: input.deleted === true,
    source: input.source, origin: input.origin ? originOf(input.origin) : null, confidence: input.confidence,
    header: input.source === 'header' && input.header ? {
      prefixValid: bool(input.header.prefixValid), scheme: input.header.scheme === 'https' ? 'https' : 'http',
      warnings: limitArray(input.header.warnings ?? [], 20).filter(warning => labels.includes(warning)),
    } : null,
    storeStatus: ['present', 'not-observed', 'unverified'].includes(input.storeStatus) ? input.storeStatus : 'unverified',
    triage: cleanTriage(input.triage),
  };
}
