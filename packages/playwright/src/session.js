import { AuditError, probeLocation, probeUrl, summarizeSession } from '@aiscihub/cookieguard-core';

// Opt-in session probe. It keeps the values of the configured authentication
// cookies in memory only, sends them only to the configured probe URL on an
// allowed origin, and hands core a timeline in which every value is an opaque id.

const MAX_PROBES_LIMIT = 200;

export function sessionProbeConfig(input, origins, policy) {
  if (input === undefined || input === null) return null;
  if (typeof input !== 'object' || Array.isArray(input)
    || Object.keys(input).some(key => !['url', 'requireLogout', 'maxProbes', 'timeoutMs'].includes(key))) throw new AuditError('CONFIG');
  // Without exact authentication-cookie names there is nothing to replay.
  if (!policy.authCookies.length) throw new AuditError('CONFIG');
  const maxProbes = input.maxProbes ?? 50;
  const timeoutMs = input.timeoutMs ?? 5000;
  if ((input.requireLogout !== undefined && typeof input.requireLogout !== 'boolean')
    || !Number.isInteger(maxProbes) || maxProbes < 2 || maxProbes > MAX_PROBES_LIMIT
    || !Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30000) throw new AuditError('CONFIG');
  return { url: probeUrl(input.url, origins), requireLogout: input.requireLogout === true, maxProbes, timeoutMs,
    names: policy.authCookies };
}

const keyOf = cookie => JSON.stringify([cookie.origin, cookie.name, cookie.domain, cookie.path]);

function applies(cookie, url) {
  const host = url.hostname.toLowerCase();
  const domainMatch = host === cookie.domain || host.endsWith(`.${cookie.domain}`);
  const path = cookie.path.endsWith('/') ? cookie.path : `${cookie.path}/`;
  return cookie.origin === url.origin && domainMatch && (url.pathname === cookie.path || url.pathname.startsWith(path));
}

export function createSessionProbe(config, fetchImpl = globalThis.fetch) {
  const url = new URL(config.url);
  const jar = new Map(); // key -> { cookie, value, id }
  const events = [];
  const pending = new Set();
  const replays = [];
  let next = 0, sent = 0, truncated = false, anonymous = null;

  async function request(entries) {
    const headers = { 'user-agent': 'CookieGuard-session-probe' };
    if (entries.length) headers.cookie = entries.map(entry => `${entry.cookie.name}=${entry.value}`).join('; ');
    try {
      const response = await fetchImpl(url.href, { method: 'GET', headers, redirect: 'manual',
        signal: AbortSignal.timeout(config.timeoutMs) });
      const result = { status: response.status, location: probeLocation(response.headers.get('location'), url.href) };
      try { await response.body?.cancel(); } catch { /* the body is never read */ }
      return result;
    } catch { return { error: true }; }
  }

  function probe(phase, entries = [...jar.values()].filter(entry => applies(entry.cookie, url))) {
    if (!entries.length) return;
    if (sent >= config.maxProbes) { truncated = true; return; }
    sent++;
    // The event takes its place in the timeline when the request starts.
    const event = { type: 'probe', phase, values: entries.map(entry => ({ cookie: entry.cookie, valueId: entry.id })), result: null };
    events.push(event);
    // Sent immediately, alongside the one anonymous request, so the probe reflects
    // the session as issued rather than after the workflow's next step.
    anonymous ??= request([]);
    const work = (async () => { event.result = await request(entries); })();
    pending.add(work);
    void work.finally(() => pending.delete(work));
  }

  return {
    /** Called for each Set-Cookie of a configured authentication cookie, with the value and the request method. */
    setCookie(observation, value, method) {
      if (!config.names.includes(observation.name) || !observation.origin) return;
      const cookie = { name: observation.name, domain: observation.domain, path: observation.path, origin: observation.origin };
      const key = keyOf(cookie);
      const current = jar.get(key);
      if (observation.deleted) {
        if (!current) return;
        const snapshot = [...jar.values()].filter(entry => applies(entry.cookie, url));
        events.push({ type: 'deleted', cookie, valueId: current.id });
        jar.delete(key);
        replays.push(snapshot);
        return;
      }
      if (current?.value === value) return;
      const id = `v${++next}`;
      jar.set(key, { cookie, value, id });
      events.push({ type: 'issued', cookie, valueId: id, method: typeof method === 'string' ? method.toUpperCase() : null });
      probe('issued');
    },
    navigation() { probe('navigation'); },
    async finish() {
      await Promise.all([...pending]);
      probe('final');
      for (const snapshot of replays) probe('replay', snapshot);
      await Promise.all([...pending]);
      anonymous ??= request([]);
      const timeline = { url: url.href, anonymous: await anonymous, truncated, requireLogout: config.requireLogout,
        events: events.map(event => (event.type === 'probe' ? { ...event, result: event.result ?? { error: true } } : event)) };
      this.clear();
      return summarizeSession(timeline);
    },
    clear() { jar.clear(); replays.length = 0; },
  };
}
