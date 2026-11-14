import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from '@playwright/test';
import { getDomain } from 'tldts';
import { args, die, normalizeName, readJSON, ROOT, sha, writeAtomic, writeJSON } from './common.mjs';
import { acceptApi, cleanDomain, declaration, matchDeclaration, valueShape } from './cmp.mjs';
import { PrivacyGuard, PrivacyRejection, structural } from './privacy.mjs';
import { checkRobots, requestErrorStatus } from './robots.mjs';

const engine = createRequire(import.meta.url)(resolve(ROOT, 'packages/core/vendor/engine.cjs'));
const registrable = host => getDomain(cleanDomain(host), { allowPrivateDomains: true }) || cleanDomain(host);
export async function oneSite(browser, item, frame, guard) {
  let context, deadline;
  let stage = 'browser', expired = false, blockedStatus = null;
  let visited = false, robotsStatus = 'not-checked', cmp = 'none';
  const disconnected = () => browser.isConnected?.() === false;
  const counts = { observedCookies: 0, unmatchedDeclarations: 0, duplicateObservations: 0 };
  const result = status => ({ ...item, status: disconnected() ? 'browser-error' : status,
    robotsStatus, visited, cmp, counts, rows: [] });
  try {
    context = await browser.newContext({ ignoreHTTPSErrors: false, serviceWorkers: 'block',
      userAgent: 'Mozilla/5.0 (compatible; CookieGuardResearch/1.0; +https://github.com/aiscihub/cookieguard-ai)' });
    deadline = setTimeout(() => { expired = true; void context.close().catch(() => {}); }, 30000);
    stage = 'robots';
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
    stage = 'browser';
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
      if (disconnected() || !root.startsWith('https:') || expired || documentResponded || blockedStatus || requestErrorStatus(error) === 'tls-error') throw error;
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
    const observation = result(rows.length ? 'usable' : 'no-matched-labeled-cookie');
    return { ...observation, rows: observation.status === 'usable' ? rows : [] };
  } catch (error) {
    if (error instanceof PrivacyRejection) throw error;
    return result(expired ? 'timeout' : stage === 'browser' ? 'browser-error' : blockedStatus || stage + '-failed');
  } finally {
    // Never log browser exceptions or save browser state, traces, HAR, or screenshots.
    try { if (context) guard.observe(await context.cookies()); }
    catch (error) { if (error instanceof PrivacyRejection) throw error; }
    finally {
      clearTimeout(deadline);
      await context?.close().catch(() => {});
    }
  }
}
export function resumeInput(frame, shard, frameSha256, plan, attemptsBytes, rowsBytes) {
  const sites = frame.frame.filter(site => site.shard === shard);
  const attempts = JSON.parse(attemptsBytes), rows = String(rowsBytes).split('\n').filter(Boolean).map(line => JSON.parse(line));
  if (plan.shard !== shard || plan.frameSha256 !== frameSha256 || !Number.isInteger(plan.recorded) ||
      !Number.isInteger(plan.visitedPrefix) || plan.visitedPrefix < plan.recorded || plan.visitedPrefix > sites.length ||
      sha(attemptsBytes) !== plan.keptAttemptsSha256 || sha(rowsBytes) !== plan.keptRowsSha256 ||
      attempts.length !== plan.recorded || rows.length !== plan.rows || !structural({ attempts, rows }) ||
      JSON.stringify(plan.remainingSiteIds) !== JSON.stringify(sites.slice(plan.visitedPrefix).map(s => s.siteId)) ||
      attempts.some((a, i) => ['siteId', 'domain', 'rank', 'shard'].some(k => a[k] !== sites[i][k])) ||
      !['passed', 'structuralPassed', 'crossScanPassed'].every(k => plan.keptPrivacy[k] === true) ||
      plan.resume.keptPrefix !== plan.recorded || plan.resume.visitedPrefix !== plan.visitedPrefix ||
      plan.resume.sourceRun !== plan.sourceRun || plan.resume.keptRowsSha256 !== plan.keptRowsSha256 ||
      plan.resume.keptAttemptsSha256 !== plan.keptAttemptsSha256) throw new Error('invalid-resume-input');
  return { proof: plan.resume, attempts, rows };
}
const skippedAttempt = site => ({ ...site, status: 'visited-not-recorded', visited: false,
  robotsStatus: 'not-checked', cmp: 'none', counts: { observedCookies: 0, unmatchedDeclarations: 0, duplicateObservations: 0 } });

// Storage and browser adapters let failure paths run entirely in memory in tests.
export async function crawlShard({ frame, shard, frameSha256, engineSha256, storage,
  launch = () => chromium.launch({ headless: true }), visit = oneSite, guard = new PrivacyGuard(),
  progress = record => console.log(JSON.stringify(record)), resume = null }) {
  const total = frame.shards, allSites = frame.frame.filter(site => site.shard === shard);
  const prefix = resume?.proof.visitedPrefix || 0, sites = allSites.slice(prefix);
  // Reserve outside cleanup: an existing shard must never be overwritten or revisited.
  storage.start({ shard, month: frame.month });
  const attempts = resume ? [...resume.attempts, ...allSites.slice(resume.proof.keptPrefix, prefix).map(skippedAttempt)] : [];
  const rows = resume ? [...resume.rows] : [];
  const oldRows = rows.length, visited = allSites.slice(0, prefix).map(site => site.siteId);
  const ledger = () => ({ schemaVersion: 1, shard, frameSha256, siteIds: visited });
  let browser, reasonCode = 'io-error';
  try {
    // Preserve the inherited prefix even if a resume is cancelled before its first new batch.
    storage.json('visited.json', ledger());
    if (resume) {
      reasonCode = 'privacy-rejected';
      const inherited = { schemaVersion: 1, shard, frameSha256, engineSha256, featureNames: engine.FEATURE_NAMES,
        attempts, rows, privacy: guard.receipt(), resume: resume.proof };
      guard.check(inherited);
      reasonCode = 'io-error';
      storage.json('checkpoint.json', inherited);
    }
    for (let offset = 0; offset < sites.length; offset += 4) {
      // Persist intent before launching a browser or calling any site. A failed ledger write
      // prevents that batch from starting. These frame IDs survive every fail-closed cleanup.
      reasonCode = 'io-error';
      visited.push(...sites.slice(offset, offset + 4).map(site => site.siteId));
      storage.json('visited.json', ledger());
      reasonCode = 'browser-error';
      if (!browser || browser.isConnected?.() === false) {
        await browser?.close().catch(() => {});
        browser = await launch();
      }
      // Wait for every context to finish, including on privacy rejection, before cleanup.
      const settled = await Promise.allSettled(sites.slice(offset, offset + 4).map(site => visit(browser, site, frame, guard)));
      const rejected = settled.filter(entry => entry.status === 'rejected');
      if (rejected.length) {
        if (rejected.some(entry => entry.reason instanceof PrivacyRejection)) reasonCode = 'privacy-rejected';
        throw new Error('batch-failed');
      }
      for (const { value: entry } of settled) {
        rows.push(...entry.rows);
        const { rows: discarded, ...attempt } = entry;
        attempts.push(attempt);
      }
      // Retain the same guard across browser relaunches and cross-scan all batches.
      reasonCode = 'privacy-rejected';
      guard.check({ attempts, rows });
      const checkpoint = { schemaVersion: 1, shard, frameSha256, engineSha256, featureNames: engine.FEATURE_NAMES,
        attempts, rows, privacy: guard.receipt(), ...(resume ? { resume: resume.proof } : {}) };
      guard.check(checkpoint);
      reasonCode = 'io-error';
      // The single atomic snapshot survives cancellation between the two export writes.
      storage.json('checkpoint.json', checkpoint);
      storage.write('cookies.jsonl', rows.map(row => JSON.stringify(row)).join('\n') + (rows.length ? '\n' : ''));
      storage.json('attempts.json', attempts);
      progress({ shard, completed: attempts.length, planned: allSites.length, rows: rows.length });
    }
    if (!sites.length) {
      reasonCode = 'privacy-rejected';
      guard.check({ attempts, rows });
      reasonCode = 'io-error';
      storage.json('visited.json', ledger());
      storage.write('cookies.jsonl', rows.map(row => JSON.stringify(row)).join('\n') + (rows.length ? '\n' : ''));
      storage.json('attempts.json', attempts);
    }
    reasonCode = 'io-error';
    const receipt = {
      schemaVersion: 1, shard, of: total, month: frame.month, dryRun: frame.dryRun,
      frameSha256, sites: allSites.length, attempted: attempts.length,
      usableSites: attempts.filter(x => x.status === 'usable').length,
      visitedSites: attempts.filter(x => x.visited).length, rows: rows.length,
      rowsSha256: sha(storage.read('cookies.jsonl')), attemptsSha256: sha(storage.read('attempts.json')),
      engineSha256, featureNames: engine.FEATURE_NAMES, privacy: guard.receipt(), finishedAt: new Date().toISOString(),
      visitedSha256: sha(storage.read('visited.json')),
      ...(resume ? { resume: resume.proof, newPart: { attempted: sites.length, rows: rows.length - oldRows, privacy: guard.receipt() } } : {})
    };
    reasonCode = 'privacy-rejected';
    guard.check(receipt);
    reasonCode = 'io-error';
    storage.json('receipt.json', receipt);
    storage.json('upload-ready.json', { passed: true });
    return receipt;
  } catch {
    try {
      // Persist the failed disposition before cleanup. Cancellation during cleanup must
      // not let the artifact stager restore a checkpoint the privacy guard rejected.
      storage.json('receipt.json', { schemaVersion: 1, shard, of: total, month: frame.month,
        frameSha256, privacy: { passed: false }, status: 'failed-closed', reasonCode,
        ...(resume ? { resume: resume.proof, newPart: { attempted: visited.length - prefix, rows: 0, privacy: { passed: false } } } : {}) });
      for (const name of ['cookies.jsonl', 'attempts.json', 'checkpoint.json', 'upload-ready.json']) {
        storage.remove(name);
        storage.remove(name + '.tmp');
      }
      storage.json('upload-ready.json', { passed: true });
    } catch { /* No raw I/O exception; artifact staging exports only the ledger and failure receipt. */ }
    throw new Error('shard-failed-closed');
  } finally { await browser?.close().catch(() => {}); }
}

export async function main() {
  const a = args({ shard: { type: 'string' }, of: { type: 'string' },
    frame: { type: 'string', default: 'refresh/.work/run/frame.json' },
    out: { type: 'string', default: 'refresh/.work/run/shards' },
    browser: { type: 'string' }, 'resume-input': { type: 'string' } });
  const frame = readJSON(a.frame), shard = Number(a.shard), total = Number(a.of);
  if (!Number.isInteger(shard) || shard < 1 || shard > total || total !== frame.shards) throw new Error('invalid-shard');
  const frameSha256 = sha(readFileSync(a.frame));
  const resume = a['resume-input'] ? resumeInput(frame, shard, frameSha256,
    readJSON(resolve(a['resume-input'], 'plan.json')), readFileSync(resolve(a['resume-input'], 'kept-attempts.json')),
    readFileSync(resolve(a['resume-input'], 'kept-cookies.jsonl'))) : null;
  const out = resolve(a.out, 'shard-' + shard);
  mkdirSync(out, { recursive: true });
  const storage = {
    start: record => writeFileSync(resolve(out, 'started.json'), JSON.stringify(record) + '\n', { flag: 'wx', mode: 0o600 }),
    write: (name, data) => writeAtomic(resolve(out, name), data),
    json: (name, data) => writeJSON(resolve(out, name), data),
    read: name => readFileSync(resolve(out, name)),
    remove: name => rmSync(resolve(out, name), { force: true }),
  };
  return crawlShard({ frame, shard, frameSha256, resume,
    engineSha256: sha(readFileSync(resolve(ROOT, 'packages/core/vendor/engine.cjs'))), storage,
    launch: () => chromium.launch({ headless: true, ...(a.browser ? { executablePath: a.browser } : {}) }) });
}
if (import.meta.url === pathToFileURL(process.argv[1] || '').href) main().catch(die);
