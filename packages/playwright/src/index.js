import { AuditError, normalizeCookie, parseSetCookie, evaluateCookiePolicy, validatePolicy } from '@aiscihub/cookieguard-core';

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
        const headers = await response.headersArray();
        if (headers.length > 1000) throw new AuditError('COLLECT');
        for (const header of headers) {
          if (header.name.toLowerCase() !== 'set-cookie') continue;
          if (observations.length >= maxObservations) throw new AuditError('COLLECT');
          const observation = parseSetCookie(header.value, url.href);
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
      } catch { complete = false; }
    })();
    pending.add(work);
    void work.finally(() => pending.delete(work));
  };
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

  async function collectOnce() {
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
    } catch { complete = false; }
    finally { clearTimeout(waitTimer); }
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
    return { observations: result, complete, mode: 'browser', target: origins.length === 1 ? origins[0] : undefined };
  }
  function collect() {
    collectionPromise ??= collectOnce();
    return collectionPromise;
  }
  return {
    collect,
    async evaluate(overridePolicy = policy, evaluationOptions = {}) {
      const collection = await collect();
      return evaluateCookiePolicy(collection.observations, overridePolicy, { ...evaluationOptions, ...collection });
    },
    dispose() { complete = false; detach(); observations.length = 0; },
  };
}

export async function auditPage(page, options = {}) {
  let origin;
  try { origin = new URL(page.url()).origin; } catch { throw new AuditError('CONFIG'); }
  const collector = startCookieAudit(page.context(), { ...options, origins: options.origins ?? [origin] });
  return collector.evaluate();
}

export { evaluateCookiePolicy, assertCookiePolicy } from '@aiscihub/cookieguard-core';
