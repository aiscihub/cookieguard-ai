import { AuditError, normalizeCookie, parseSetCookie, evaluateCookiePolicy, validatePolicy, storageObservation } from '@aiscihub/cookieguard-core';
import { sessionProbeConfig, createSessionProbe } from './session.js';
import { reportUsage } from '@aiscihub/cookieguard-core/usage';
import manifest from '../package.json' with { type: 'json' };

const STORAGE_TIMEOUT_MS = 5000;
const MAX_STORAGE_ENTRIES = 1000;

function allowedOrigins(values) {
  if (!Array.isArray(values) || !values.length || values.length > 20) throw new AuditError('CONFIG');
  return [...new Set(values.map(value => {
    try {
      const url = new URL(value);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error();
      return url.origin;
    } catch { throw new AuditError('CONFIG'); }
  }))];
}

const COOKIE_NAME = /^\s*[!#$%&'*+.^_`|~0-9a-z-]+\s*=/i;
function namelessSetCookie(value) {
  return typeof value === 'string' && value.length <= 16384 && !/[\r\n\0]/.test(value) && !/,\s*[^;,\s=]+\s*=/.test(value)
    && !COOKIE_NAME.test(value.split(';', 1)[0]);
}

function sameScope(a, b) { return a.name === b.name && a.domain === b.domain && a.path === b.path; }
function agrees(header, cookie) {
  return sameScope(header, cookie) && header.secure === cookie.secure && header.httpOnly === cookie.httpOnly
    && (!['lax', 'strict', 'none'].includes(header.sameSite.declared) || header.sameSite.declared === cookie.sameSite.effective)
    && (header.expiresAt === null ? cookie.expiresAt === null : cookie.expiresAt !== null && Math.abs(header.expiresAt - cookie.expiresAt) < 3);
}

export function startCookieAudit(context, options) {
  const origins = allowedOrigins(options?.origins);
  const policy = validatePolicy(options.policy ?? {});
  const timeoutMs = options.timeoutMs ?? 120000;
  const maxObservations = options.maxObservations ?? 1000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 600000
    || !Number.isInteger(maxObservations) || maxObservations < 1 || maxObservations > 1000) throw new AuditError('CONFIG');
  if (options.classifier && (options.classifier.mode !== 'onnx' || typeof options.classifier.classify !== 'function')) throw new AuditError('CONFIG');
  const usageMetrics = options.usageMetrics;
  if (usageMetrics !== undefined && usageMetrics !== null && typeof usageMetrics !== 'boolean') throw new AuditError('CONFIG');
  if (options.storage !== undefined && typeof options.storage !== 'boolean') throw new AuditError('CONFIG');
  const sessionConfig = sessionProbeConfig(options.sessionProbe, origins, policy);
  const session = sessionConfig ? createSessionProbe(sessionConfig) : null;
  const observations = [];
  const pending = new Set();
  let complete = true, disposed = false, responseCount = 0, collectionPromise;
  const onClose = () => { complete = false; detach(); };
  const onResponse = response => {
    if (disposed) return;
    let url;
    try { url = new URL(response.url()); } catch { return; }
    if (!origins.includes(url.origin)) return;
    if (++responseCount > 1000 || pending.size >= 64) { complete = false; detach(); return; }
    const work = (async () => {
      try {
        if (response.fromServiceWorker?.()) complete = false;
        let method = null, navigation = false;
        try {
          const request = response.request?.();
          method = request?.method?.() ?? null;
          navigation = request?.isNavigationRequest?.() === true;
        } catch { /* a request the adapter cannot inspect is treated as unknown */ }
        const headers = await response.headersArray();
        if (headers.length > 1000) throw new AuditError('COLLECT');
        for (const header of headers) {
          if (header.name.toLowerCase() !== 'set-cookie') continue;
          if (observations.length >= maxObservations) throw new AuditError('COLLECT');
          let observation;
          try { observation = parseSetCookie(header.value, url.href); } catch (error) {
            // A line without a valid cookie name cannot set a configured authentication
            // cookie; skip it instead of discarding the rest of the evidence.
            if (namelessSetCookie(header.value)) continue;
            throw error;
          }
          if (session) {
            // The value stays in the session probe's memory; the observation itself is value-free.
            const pair = header.value.split(';', 1)[0];
            session.setCookie(observation, pair.slice(pair.indexOf('=') + 1).trim(), method);
          }
          if (options.classifier) {
            // The value exists only for this awaited inference. It is never retained.
            const pair = header.value.split(';', 1)[0];
            const input = { name: observation.name, value: pair.slice(pair.indexOf('=') + 1).trim(),
              domain: observation.domain, path: observation.path, secure: observation.secure,
              httpOnly: observation.httpOnly, sameSite: observation.sameSite.declared,
              expirationDate: observation.expiresAt, hostOnly: observation.hostOnly };
            observation.triage = await options.classifier.classify(input);
          }
          observations.push(observation);
        }
        if (session && navigation) session.navigation();
        // Supplementary evidence: a store that cannot be read mid-workflow (for example
        // a replayed CDP context) leaves completeness to the final read.
        try { await snapshotStore(url.origin); } catch { /* best effort */ }
      } catch { complete = false; }
    })();
    pending.add(work);
    void work.finally(() => pending.delete(work));
  };
  // Configured authentication cookies can leave the store before collection (logout)
  // or never appear in a header (set by page script). Keep the last value-free store
  // observation of each one, taken after every response on an allowed origin.
  const lastSeen = new Map();
  async function snapshotStore(origin) {
    if (!policy.authCookies.length || typeof context.cookies !== 'function') return;
    const cookies = await context.cookies(origin);
    if (!Array.isArray(cookies)) return;
    const host = new URL(origin).hostname;
    for (const cookie of cookies) {
      if (!policy.authCookies.includes(cookie.name)) continue;
      const domain = cookie.domain.replace(/^\./, '').toLowerCase();
      if (!(host === domain || (cookie.domain.startsWith('.') && host.endsWith(`.${domain}`)))) continue;
      const observation = normalizeCookie(cookie, { source: 'browser', origin });
      if (cookie.partitionKey) observation.confidence = 'uncertain';
      if (lastSeen.size < maxObservations) lastSeen.set(JSON.stringify([origin, observation.name, observation.domain, observation.path]), observation);
    }
  }
  const timer = setTimeout(() => { complete = false; detach(); }, timeoutMs);
  timer.unref?.();
  function detach() {
    disposed = true;
    clearTimeout(timer);
    context.off('response', onResponse);
    context.off('close', onClose);
  }
  context.on('response', onResponse);
  context.on('close', onClose);

  async function readStorage(storagePolicy) {
    const entries = [];
    const bounded = promise => {
      let timer;
      return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new AuditError('COLLECT')), STORAGE_TIMEOUT_MS); })])
        .finally(() => clearTimeout(timer));
    };
    const state = await bounded(context.storageState());
    for (const item of state?.origins ?? []) {
      if (!origins.includes(item.origin)) continue;
      for (const { name, value } of item.localStorage ?? []) entries.push({ origin: item.origin, area: 'local', key: name, value });
    }
    for (const page of context.pages()) {
      let origin;
      try { origin = new URL(page.url()).origin; } catch { continue; }
      if (!origins.includes(origin)) continue;
      const items = await bounded(page.evaluate(limit => {
        // Runs in the page: Web Storage is only reachable from page script.
        const { sessionStorage } = globalThis;
        const out = [];
        for (let i = 0; i < sessionStorage.length && i < limit; i++) { const key = sessionStorage.key(i); out.push([key, sessionStorage.getItem(key)]); }
        return out;
      }, MAX_STORAGE_ENTRIES));
      for (const [key, value] of items) entries.push({ origin, area: 'session', key: String(key), value: String(value ?? '') });
    }
    if (entries.length > MAX_STORAGE_ENTRIES) throw new AuditError('COLLECT');
    // Values are classified here and dropped; only value-free observations remain.
    const result = new Map();
    for (const entry of entries) {
      const observation = storageObservation(entry, storagePolicy);
      if (observation) result.set(JSON.stringify([observation.origin, observation.area, observation.key]), observation);
    }
    entries.length = 0;
    return [...result.values()];
  }

  async function collectOnce(storagePolicy) {
    reportUsage({ package: manifest.name, version: manifest.version, integration: 'playwright', enabled: usageMetrics ?? undefined });
    detach();
    let waitTimer;
    try {
      await Promise.race([
        Promise.all([...pending]),
        new Promise((_, reject) => { waitTimer = setTimeout(() => reject(new AuditError('COLLECT')), 5000); }),
      ]);
    } catch { complete = false; }
    finally { clearTimeout(waitTimer); }
    const browserObservations = [];
    try {
      // No URLs filter: include path-scoped cookies too, then restrict domains below.
      const cookies = await Promise.race([
        context.cookies(),
        new Promise((_, reject) => { waitTimer = setTimeout(() => reject(new AuditError('COLLECT')), 5000); }),
      ]);
      if (!Array.isArray(cookies) || cookies.length > maxObservations) throw new AuditError('COLLECT');
      for (const cookie of cookies) {
        // Browsers store a nameless line as a cookie with an empty name; it cannot be a configured one.
        if (cookie.name === '') continue;
        const domain = cookie.domain.replace(/^\./, '').toLowerCase();
        const matchingOrigins = origins.filter(origin => {
          const host = new URL(origin).hostname;
          return host === domain || (cookie.domain.startsWith('.') && host.endsWith(`.${domain}`));
        });
        for (const origin of matchingOrigins) {
          if (browserObservations.length + observations.length >= maxObservations) throw new AuditError('COLLECT');
          const triage = options.classifier ? await options.classifier.classify(cookie) : undefined;
          const observation = normalizeCookie(cookie, { source: 'browser', origin, triage });
          if (cookie.partitionKey) observation.confidence = 'uncertain';
          browserObservations.push(observation);
        }
      }
      // Configured cookies seen earlier but gone now, with no header that set them (for
      // example, set by page script): evaluate their last store state.
      for (const [key, observation] of lastSeen) {
        if (browserObservations.some(c => JSON.stringify([c.origin, c.name, c.domain, c.path]) === key)) continue;
        if (observations.some(h => !h.deleted && JSON.stringify([h.origin, h.name, h.domain, h.path]) === key)) continue;
        if (browserObservations.length + observations.length >= maxObservations) throw new AuditError('COLLECT');
        browserObservations.push(observation);
      }
    } catch { complete = false; }
    finally { clearTimeout(waitTimer); }
    lastSeen.clear();
    const result = observations.map(header => {
      const matches = browserObservations.filter(cookie => cookie.origin === header.origin && agrees(header, cookie));
      // Multiple header instructions or partitioned scopes cannot prove which
      // instruction produced the current cookie. Preserve separate evidence.
      const unique = observations.filter(other => other.origin === header.origin && sameScope(header, other)).length === 1;
      const matched = unique && matches.length === 1 && header.confidence === 'observed' && matches[0].confidence === 'observed';
      return { ...header, sameSite: { ...header.sameSite, effective: matched ? matches[0].sameSite.effective : null },
        storeStatus: matched ? 'present' : 'not-observed' };
    });
    for (const cookie of browserObservations) {
      if (!result.some(header => header.origin === cookie.origin && header.storeStatus === 'present' && agrees(header, cookie))) result.push(cookie);
    }
    observations.length = 0;
    let sessionSummary = null;
    if (session) {
      try { sessionSummary = await session.finish(); } catch { complete = false; session.clear(); }
    }
    let storage = [];
    if (options.storage !== false && typeof context.pages === 'function' && typeof context.storageState === 'function') {
      try { storage = await readStorage(storagePolicy); } catch { complete = false; }
    }
    return { observations: result, complete, mode: 'browser', target: origins.length === 1 ? origins[0] : undefined,
      session: sessionSummary, storage };
  }
  function collect(storagePolicy = policy) {
    collectionPromise ??= collectOnce(validatePolicy(storagePolicy));
    return collectionPromise;
  }
  return {
    collect,
    async evaluate(overridePolicy = policy, evaluationOptions = {}) {
      const collection = await collect(overridePolicy);
      return evaluateCookiePolicy(collection.observations, overridePolicy, { ...evaluationOptions, ...collection });
    },
    dispose() { complete = false; detach(); observations.length = 0; lastSeen.clear(); session?.clear(); },
  };
}

export async function auditPage(page, options = {}) {
  let origin;
  try { origin = new URL(page.url()).origin; } catch { throw new AuditError('CONFIG'); }
  const collector = startCookieAudit(page.context(), { ...options, origins: options.origins ?? [origin] });
  return collector.evaluate();
}

export { evaluateCookiePolicy, assertCookiePolicy } from '@aiscihub/cookieguard-core';
export { cookieGuardFixtures, checkId, EVIDENCE_INTEGRATION } from './fixture.js';
