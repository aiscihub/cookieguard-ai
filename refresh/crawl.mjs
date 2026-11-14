import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from '@playwright/test';
import { getDomain } from 'tldts';
import { args, die, normalizeName, readJSON, ROOT, sha, writeAtomic, writeJSON } from './common.mjs';
import { acceptApi, cleanDomain, declaration, matchDeclaration, valueShape } from './cmp.mjs';
import { PrivacyGuard } from './privacy.mjs';
import { checkRobots, requestErrorStatus } from './robots.mjs';

const engine = createRequire(import.meta.url)(resolve(ROOT, 'packages/core/vendor/engine.cjs'));
const registrable = host => getDomain(cleanDomain(host), { allowPrivateDomains: true }) || cleanDomain(host);
export async function oneSite(browser, item, frame, guard) {
  const context = await browser.newContext({ ignoreHTTPSErrors: false, serviceWorkers: 'block',
    userAgent: 'Mozilla/5.0 (compatible; CookieGuardResearch/1.0; +https://github.com/aiscihub/cookieguard-ai)' });
  let stage = 'robots', expired = false, blockedStatus = null;
  let visited = false, robotsStatus = 'network-error', cmp = 'none';
  const deadline = setTimeout(() => { expired = true; void context.close().catch(() => {}); }, 30000);
  const counts = { observedCookies: 0, unmatchedDeclarations: 0, duplicateObservations: 0 };
  const result = status => ({ ...item, status, robotsStatus, visited, cmp, counts, rows: [] });
  try {
    const robots = new Map();
    async function permitted(origin) {
      if (!robots.has(origin)) robots.set(origin, await checkRobots(context, origin));
      const decision = robots.get(origin);
      robotsStatus = decision.status;
      return decision;
    }
    let root = 'https://' + item.domain;
    let initial = await permitted(root);
    if (!initial.allowed && initial.status === 'unreachable' && !expired) {
      root = 'http://' + item.domain;
      initial = await permitted(root);
    }
    if (!initial.allowed) return result(initial.status === 'disallowed' ? 'robots-disallowed' : 'robots-unavailable');
    const page = await context.newPage();
    page.setDefaultTimeout(7000);
    await page.route('**/*', async route => {
      const request = route.request();
      if (request.isNavigationRequest() && request.frame() === page.mainFrame()) {
        try {
          const url = new URL(request.url());
          if (!['http:', 'https:'].includes(url.protocol) || registrable(url.hostname) !== registrable(item.domain)) {
            blockedStatus = 'redirect-outside-frame'; return route.abort();
          }
          const decision = await permitted(url.origin);
          if (!decision.allowed) {
            blockedStatus = decision.status === 'disallowed' ? 'robots-disallowed' : 'robots-unavailable';
            return route.abort();
          }
        } catch { return route.abort(); }
      }
      return route.continue().catch(() => {});
    });
    stage = 'navigation';
    let documentResponded = false;
    page.on('response', response => {
      if (response.request().isNavigationRequest() && response.frame() === page.mainFrame()) documentResponded = true;
    });
    let response;
    visited = true; // Robots permitted this origin and document navigation is starting.
    try {
      response = await page.goto(root + '/', { waitUntil: 'domcontentloaded', timeout: 12000 });
    } catch (error) {
      // Match the frozen crawler; do not retry a responding, blocked, or invalid-TLS site.
      if (!root.startsWith('https:') || expired || documentResponded || blockedStatus || requestErrorStatus(error) === 'tls-error') throw error;
      const httpRoot = 'http://' + item.domain;
      const httpRobots = await permitted(httpRoot);
      if (!httpRobots.allowed) return result(httpRobots.status === 'disallowed' ? 'robots-disallowed' : 'robots-unavailable');
      response = await page.goto(httpRoot + '/', { waitUntil: 'domcontentloaded', timeout: 12000 });
    }
    if (!response) return result('navigation-failed');
    if ([401, 403, 429].includes(response.status())) return result('blocked');
    guard.observe(await context.cookies());
    const signal = (await page.locator('body').innerText({ timeout: 2000 }).catch(() => '')).slice(0, 4000);
    if (/(captcha|access denied|verify you are human|unusual traffic|checking your browser|temporarily blocked)/i.test(signal)) return result('blocked');
    stage = 'declaration';
    const found = await declaration(context, page, family => { cmp = family; });
    if (!found) return result('no-supported-cmp');
    if (!found.declared.length) return result('no-usable-declaration');
    stage = 'consent-api';
    if (!await acceptApi(page, found.family)) return result('consent-api-missing');
    stage = 'reload';
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 });
    await page.waitForTimeout(5000);
    const cookies = await context.cookies(), now = Date.now() / 1000, seen = new Set(), rows = [];
    guard.observe(cookies);
    counts.observedCookies = cookies.length;
    for (const cookie of cookies) {
      const identity = cookie.name + '\0' + cleanDomain(cookie.domain) + '\0' + cookie.path;
      if (seen.has(identity)) { counts.duplicateObservations++; continue; }
      seen.add(identity);
      const matched = matchDeclaration(cookie, found.declared);
      if (!matched) { counts.unmatchedDeclarations++; continue; }
      const mapped = { ...cookie, hostOnly: !cookie.domain.startsWith('.'),
        expirationDate: cookie.expires > 0 ? cookie.expires : undefined };
      const features = engine.extractFeatures(mapped, { currentDomain: registrable(item.domain) });
      rows.push({
        crawl: 'monthly', rank: item.rank, cmp: found.family,
        declaredCategory: matched.category, declaredGroup: matched.group,
        name: cookie.name, normalizedName: normalizeName(cookie.name), domain: cleanDomain(cookie.domain),
        path: cookie.path, label: matched.label, secure: cookie.secure, httpOnly: cookie.httpOnly,
        sameSite: cookie.sameSite || 'unspecified', hostOnly: mapped.hostOnly, session: !(cookie.expires > 0),
        lifetimeSeconds: cookie.expires > 0 ? Math.max(0, cookie.expires - now) : null,
        ...valueShape(cookie.value), declarationMatch: matched.method,
        features: engine.FEATURE_NAMES.map(name => Number(features[name] || 0)),
        crawlDate: new Date(now * 1000).toISOString(), trancoListId: frame.trancoListId
      });
    }
    return { ...result(rows.length ? 'usable' : 'no-matched-labeled-cookie'), rows };
  } catch {
    return result(expired ? 'timeout' : blockedStatus || stage + '-failed');
  } finally {
    // Never log browser exceptions or save browser state, traces, HAR, or screenshots.
    try { guard.observe(await context.cookies()); } catch { /* deadline closed context */ }
    clearTimeout(deadline);
    await context.close().catch(() => {});
  }
}
export async function main() {
  const a = args({ shard: { type: 'string' }, of: { type: 'string' },
    frame: { type: 'string', default: 'refresh/.work/run/frame.json' },
    out: { type: 'string', default: 'refresh/.work/run/shards' },
    browser: { type: 'string' } });
  const frame = readJSON(a.frame), shard = Number(a.shard), total = Number(a.of);
  if (!Number.isInteger(shard) || shard < 1 || shard > total || total !== frame.shards) throw new Error('invalid-shard');
  const sites = frame.frame.filter(site => site.shard === shard), out = resolve(a.out, 'shard-' + shard);
  mkdirSync(out, { recursive: true });
  // A started shard cannot be rerun: even a crashed visit counts as attempted.
  writeFileSync(resolve(out, 'started.json'), JSON.stringify({ shard, month: frame.month }) + '\n', { flag: 'wx', mode: 0o600 });
  const guard = new PrivacyGuard(), attempts = [], rows = [];
  let browser;
  try {
    browser = await chromium.launch({ headless: true, ...(a.browser ? { executablePath: a.browser } : {}) });
    for (let offset = 0; offset < sites.length; offset += 4) {
      const batch = await Promise.all(sites.slice(offset, offset + 4).map(site => oneSite(browser, site, frame, guard)));
      for (const entry of batch) {
        rows.push(...entry.rows);
        const { rows: discarded, ...attempt } = entry;
        attempts.push(attempt);
      }
      // Cross-scan all earlier and current batches against every retained in-memory string.
      guard.check({ attempts, rows });
      writeAtomic(resolve(out, 'cookies.jsonl'), rows.map(row => JSON.stringify(row)).join('\n') + (rows.length ? '\n' : ''));
      writeJSON(resolve(out, 'attempts.json'), attempts);
      console.log(JSON.stringify({ shard, completed: attempts.length, planned: sites.length, rows: rows.length }));
    }
    const receipt = {
      schemaVersion: 1, shard, of: total, month: frame.month, dryRun: frame.dryRun,
      frameSha256: sha(readFileSync(a.frame)), sites: sites.length, attempted: attempts.length,
      usableSites: attempts.filter(x => x.status === 'usable').length,
      visitedSites: attempts.filter(x => x.visited).length, rows: rows.length,
      rowsSha256: sha(readFileSync(resolve(out, 'cookies.jsonl'))),
      attemptsSha256: sha(readFileSync(resolve(out, 'attempts.json'))),
      engineSha256: sha(readFileSync(resolve(ROOT, 'packages/core/vendor/engine.cjs'))),
      featureNames: engine.FEATURE_NAMES, privacy: guard.receipt(), finishedAt: new Date().toISOString()
    };
    guard.check(receipt);
    writeJSON(resolve(out, 'receipt.json'), receipt);
  } catch {
    for (const name of ['cookies.jsonl', 'attempts.json', 'receipt.json']) rmSync(resolve(out, name), { force: true });
    writeJSON(resolve(out, 'receipt.json'), { schemaVersion: 1, shard, of: total, month: frame.month,
      frameSha256: sha(readFileSync(a.frame)), privacy: { passed: false }, status: 'failed-closed' });
    throw new Error('shard-failed-closed');
  } finally { await browser?.close().catch(() => {}); }
}
if (import.meta.url === pathToFileURL(process.argv[1] || '').href) main().catch(die);
