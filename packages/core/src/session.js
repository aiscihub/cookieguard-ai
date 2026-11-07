import { AuditError, limitArray, originOf, textField } from './safety.js';

// Session checks replay the observed session against one protected URL that the
// developer configured. Adapters do the network I/O and keep cookie values in
// memory; they report a value-free timeline in which each value is an opaque id.
// This module decides, from that timeline alone, whether the session identifier
// was rotated at login and whether it still worked after logout.

const SAFE_METHODS = Object.freeze(['GET', 'HEAD']);
const PHASES = Object.freeze(['issued', 'navigation', 'final', 'replay']);
export const ROTATION = Object.freeze(['rotated', 'not-rotated', 'inconclusive']);
export const LOGOUT = Object.freeze(['not-observed', 'revoked', 'still-valid', 'inconclusive']);
const PROBE_STATUS = Object.freeze(['ok', 'inconclusive']);
const PROBE_REASONS = Object.freeze(['probe-error', 'unprotected-url', 'probe-limit', 'no-authenticated-state']);

const valueId = value => {
  if (typeof value !== 'string' || !/^v\d{1,6}$/.test(value)) throw new AuditError('INPUT');
  return value;
};
const method = value => (typeof value === 'string' && /^[A-Z]{1,16}$/.test(value) ? value : null);

function cleanCookie(cookie) {
  if (!cookie || typeof cookie.name !== 'string' || !cookie.name || typeof cookie.domain !== 'string'
    || typeof cookie.path !== 'string') throw new AuditError('INPUT');
  return { name: textField(cookie.name), domain: textField(cookie.domain), path: textField(cookie.path),
    origin: originOf(cookie.origin) };
}

const keyOf = cookie => JSON.stringify([cookie.origin, cookie.name, cookie.domain, cookie.path]);

function cleanResult(result) {
  if (!result || typeof result !== 'object') throw new AuditError('INPUT');
  if (result.error === true) return { error: true };
  if (!Number.isInteger(result.status) || result.status < 100 || result.status > 599) throw new AuditError('INPUT');
  // Only a redirect's path is compared; queries and fragments never reach the timeline.
  const location = typeof result.location === 'string' && result.location.startsWith('/') ? textField(result.location).slice(0, 512) : null;
  return { status: result.status, location };
}

/** Builds the location field adapters report: the redirect target's path only. */
export function probeLocation(location, base) {
  if (typeof location !== 'string' || !location) return null;
  try { return new URL(location, base).pathname; } catch { return null; }
}

/** Validates a probe URL: an absolute http(s) URL on one of the allowed origins, without credentials, query, or fragment. */
export function probeUrl(value, origins) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash
      || !origins.includes(url.origin)) throw new Error();
    return url.href;
  } catch { throw new AuditError('CONFIG'); }
}

function classify(result, anonymous) {
  if (result.error || anonymous.error) return 'error';
  if (result.status === anonymous.status && result.location === anonymous.location) return 'unauthenticated';
  if (result.status >= 200 && result.status < 300) return 'authenticated';
  return 'unknown';
}

/**
 * Summarizes a value-free session timeline:
 *   { url, anonymous: {status, location} | {error: true}, truncated, events: [
 *       { type: 'issued', cookie, valueId, method },
 *       { type: 'deleted', cookie, valueId },
 *       { type: 'probe', phase, values: [{ cookie, valueId }], result } ] }
 * Returns { probe, cookies } where each cookie has a rotation and a logout outcome.
 */
export function summarizeSession(timeline) {
  if (!timeline || typeof timeline !== 'object') throw new AuditError('INPUT');
  const url = typeof timeline.url === 'string' ? new URL(timeline.url).href : null;
  if (!url) throw new AuditError('INPUT');
  originOf(url);
  const anonymous = cleanResult(timeline.anonymous);
  const events = limitArray(timeline.events, 2000);
  let reason = null;
  if (anonymous.error) reason = 'probe-error';
  else if (anonymous.status >= 200 && anonymous.status < 300) reason = 'unprotected-url';
  else if (timeline.truncated === true) reason = 'probe-limit';

  const cookies = new Map();
  const entry = cookie => {
    const key = keyOf(cookie);
    if (!cookies.has(key)) cookies.set(key, { cookie, values: new Map(), deletions: [] });
    return cookies.get(key);
  };
  let probes = 0, probeErrors = 0;
  events.forEach((event, index) => {
    if (!event || typeof event !== 'object') throw new AuditError('INPUT');
    if (event.type === 'issued') {
      const target = entry(cleanCookie(event.cookie));
      const id = valueId(event.valueId);
      if (!target.values.has(id)) target.values.set(id, { method: method(event.method), states: [], deletedAt: null });
    } else if (event.type === 'deleted') {
      const target = entry(cleanCookie(event.cookie));
      const value = target.values.get(valueId(event.valueId));
      if (value && value.deletedAt === null) { value.deletedAt = index; target.deletions.push(event.valueId); }
    } else if (event.type === 'probe') {
      if (!PHASES.includes(event.phase)) throw new AuditError('INPUT');
      const result = cleanResult(event.result);
      const state = classify(result, anonymous);
      probes++;
      if (state === 'error') probeErrors++;
      for (const item of limitArray(event.values, 100)) {
        const target = entry(cleanCookie(item.cookie));
        const value = target.values.get(valueId(item.valueId));
        if (value) value.states.push({ phase: event.phase, state, index });
      }
    } else throw new AuditError('INPUT');
  });
  if (!reason && probes && probeErrors === probes) reason = 'probe-error';

  const results = [];
  for (const { cookie, values, deletions } of cookies.values()) {
    let rotation = 'inconclusive', logout = 'not-observed';
    if (!reason) {
      const live = [...values.values()].map(value => ({ ...value,
        states: value.states.filter(s => s.phase !== 'replay' && (value.deletedAt === null || s.index < value.deletedAt)) }));
      const fixated = live.some(value => SAFE_METHODS.includes(value.method)
        && value.states[0]?.state === 'unauthenticated' && value.states.some(s => s.state === 'authenticated'));
      const authenticated = live.filter(value => value.states.some(s => s.state === 'authenticated'));
      if (fixated) rotation = 'not-rotated';
      else if (authenticated.length && authenticated.every(value => value.states[0].state === 'authenticated')) rotation = 'rotated';

      const outcomes = deletions.map(id => {
        const value = values.get(id);
        const before = value.states.filter(s => s.phase !== 'replay' && s.index < value.deletedAt);
        if (!before.some(s => s.state === 'authenticated')) return null;
        const replay = value.states.filter(s => s.phase === 'replay' && s.index > value.deletedAt).at(-1);
        if (replay?.state === 'authenticated') return 'still-valid';
        if (replay?.state === 'unauthenticated') return 'revoked';
        return 'inconclusive';
      }).filter(Boolean);
      if (outcomes.includes('still-valid')) logout = 'still-valid';
      else if (outcomes.includes('inconclusive')) logout = 'inconclusive';
      else if (outcomes.includes('revoked')) logout = 'revoked';
    }
    results.push({ ...cookie, rotation, logout });
  }
  if (!reason && results.length && results.every(cookie => cookie.rotation === 'inconclusive')) reason = 'no-authenticated-state';
  results.sort((a, b) => (keyOf(a) < keyOf(b) ? -1 : keyOf(a) > keyOf(b) ? 1 : 0));
  return cleanSession({ probe: { url, anonymousStatus: anonymous.error ? null : anonymous.status,
    status: reason ? 'inconclusive' : 'ok', reason, probes, requireLogout: timeline.requireLogout === true }, cookies: results });
}

/** Rebuilds a session summary field by field; used for evaluation and supplied evidence files. */
export function cleanSession(input) {
  if (input === null || input === undefined) return null;
  if (!input || typeof input !== 'object' || !input.probe) throw new AuditError('INPUT');
  const probe = input.probe;
  if (typeof probe.url !== 'string' || !PROBE_STATUS.includes(probe.status)
    || (probe.reason !== null && !PROBE_REASONS.includes(probe.reason))
    || (probe.anonymousStatus !== null && !Number.isInteger(probe.anonymousStatus))
    || !Number.isInteger(probe.probes) || probe.probes < 0) throw new AuditError('INPUT');
  const url = new URL(probe.url);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new AuditError('INPUT');
  return {
    probe: { url: url.href, anonymousStatus: probe.anonymousStatus, status: probe.status, reason: probe.reason,
      probes: probe.probes, requireLogout: probe.requireLogout === true },
    cookies: limitArray(input.cookies, 100).map(cookie => {
      if (!ROTATION.includes(cookie?.rotation) || !LOGOUT.includes(cookie?.logout)) throw new AuditError('INPUT');
      return { ...cleanCookie(cookie), rotation: cookie.rotation, logout: cookie.logout };
    }),
  };
}
