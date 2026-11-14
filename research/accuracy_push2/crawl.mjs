#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '../..');
const require = createRequire(import.meta.url);
const { chromium } = require(join(ROOT, 'waicy_2026/local_apps_test/node_modules/@playwright/test'));
const engine = require(join(ROOT, 'waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/vendor/engine.cjs'));
const { getDomain } = require(join(ROOT, 'waicy_2026/cookieblock_test/raw/runtime/node_modules/tldts'));

const INPUT = join(HERE, 'inputs/tranco-947N2-top20000.csv');
const OUT = process.env.CG_OUT || join(HERE, 'fresh_test');
const SPLIT = JSON.parse(readFileSync(join(ROOT, 'waicy_2026/retrain_test/split.json'), 'utf8'));
const VALIDATION = JSON.parse(readFileSync(join(ROOT, 'waicy_2026/accuracy_push/validation_split.json'), 'utf8'));
const BROWSER = join(ROOT, 'waicy_2026/local_apps_test/browsers/chromium-1254/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/158.0.0.0 Safari/537.36';
const MAX_RANK = Number(process.env.CG_MAX_RANK || 20000);
const STOP_USABLE = Number(process.env.CG_STOP_USABLE || 1000);
const CHUNK = 100;
const UUID = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
const OT_HOSTS = new Set(['cdn.cookielaw.org', 'cmp-cdn.cookielaw.org', 'optanon.blob.core.windows.net',
  'cookie-cdn.cookiepro.com', 'cookiepro.blob.core.windows.net', 'cdn-ukwest.onetrust.com']);
const sha = value => createHash('sha256').update(value).digest('hex');
const cleanDomain = value => String(value || '').toLowerCase().replace(/^\.+/, '').replace(/\.$/, '');
const registrable = value => getDomain(cleanDomain(value), { allowPrivateDomains: true }) || cleanDomain(value);

function atomic(path, text) {
  const temporary = `${path}.tmp`;
  writeFileSync(temporary, text);
  renameSync(temporary, path);
}

function normalizeName(value) {
  const pieces = String(value).trim().toLowerCase().split(/([_.-])/);
  return pieces.map(piece => {
    if (/^[_.-]$/.test(piece)) return piece;
    const mixed = piece.length >= 6 && /[a-z]/.test(piece) && /[0-9]/.test(piece);
    const hex = piece.length >= 8 && /^[0-9a-f]+$/.test(piece) && /[a-f]/.test(piece);
    return mixed || hex ? '#' : piece;
  }).join('').replace(/\d+/g, '0');
}

function valueShape(value) {
  const text = String(value ?? '');
  let characterSet = 'other';
  if (!text) characterSet = 'empty';
  else if (/^\d+$/.test(text)) characterSet = 'digits';
  else if (/^[0-9a-f]+$/i.test(text)) characterSet = 'hex';
  else if (/^[a-z0-9]+$/i.test(text)) characterSet = 'alphanumeric';
  else if (/^[a-z0-9+/=_-]+$/i.test(text)) characterSet = 'base64/base64url';
  return { length: text.length, characterSet };
}

function binaryCategory(name) {
  const text = String(name || '');
  if (/(^ads.*|.*\s+ads.*|Ad Selection|advertising|advertise|targeting|sale of personal data|marketing|tracking|tracker|fingerprint)/i.test(text)) return { label: 1, category: 'advertising' };
  if (/(necessary|essential|required)/i.test(text)) return { label: 0, category: 'necessary' };
  if (/(measurement|analytic|anonym|research|performance)/i.test(text)) return { label: 1, category: 'analytics' };
  if (/(functional|preference|security|secure)/i.test(text)) return { label: 0, category: 'functional' };
  return null;
}

function declaredCookie(name, domain, label, category, groupId, method) {
  return { name: String(name || ''), domain: cleanDomain(domain), label, category, groupId: String(groupId || ''), method };
}

function parseCookiebot(text) {
  const groups = [
    ['Necessary', 0, 'necessary'], ['Preference', 0, 'preference'],
    ['Statistics', 1, 'statistics'], ['Advertising', 1, 'advertising']
  ];
  const output = [];
  for (const [suffix, label, category] of groups) {
    const match = text.match(new RegExp(`CookieConsentDialog\\.cookieTable${suffix}\\s*=\\s*(\\[[\\s\\S]*?\\]);`));
    if (!match) continue;
    let rows;
    try { rows = JSON.parse(match[1]); } catch { continue; }
    for (const row of rows) {
      if (Array.isArray(row) && row[0]) output.push(declaredCookie(row[0], row[1], label, category, suffix, 'cookiebot-array'));
    }
  }
  return output;
}

function parseOneTrustRuleset(payload) {
  const output = [];
  for (const group of payload?.DomainData?.Groups || []) {
    const mapped = binaryCategory(group.GroupName);
    if (!mapped) continue;
    const id = group.OptanonGroupId || group.CustomGroupId || group.GroupId || group.GroupName;
    for (const cookie of group.FirstPartyCookies || []) {
      if (cookie.Name) output.push(declaredCookie(cookie.Name, cookie.Host, mapped.label, mapped.category, id, 'onetrust-json'));
    }
    for (const host of group.Hosts || []) {
      for (const cookie of host.Cookies || []) {
        if (cookie.Name) output.push(declaredCookie(cookie.Name, cookie.Host || host.Host, mapped.label, mapped.category, id, 'onetrust-json'));
      }
    }
  }
  return output;
}

async function fetchText(context, url, referer) {
  const response = await context.request.get(url, { headers: { Referer: referer }, timeout: 7000 });
  if (!response.ok()) throw new Error(`declaration-http-${response.status()}`);
  return response.text();
}

async function declaration(context, page, homeHost, scripts) {
  let cbid = scripts.map(item => item.cbid).find(value => new RegExp(`^${UUID}$`).test(value || ''));
  for (const item of scripts) {
    const found = String(item.src || '').match(new RegExp(`consent\\.cookiebot\\.com/(${UUID})/cc\\.js|[?&]cbid=(${UUID})`));
    if (!cbid && found) cbid = found[1] || found[2];
  }
  if (cbid) {
    const endpoint = `https://consent.cookiebot.com/${cbid}/cc.js?referer=${encodeURIComponent(homeHost)}`;
    const declared = parseCookiebot(await fetchText(context, endpoint, page.url()));
    return { family: 'cookiebot', declared };
  }

  const ot = scripts.find(item => {
    try { return OT_HOSTS.has(new URL(item.src).hostname) && (item.ddid || /\/consent\//.test(item.src)); } catch { return false; }
  });
  if (!ot) return null;
  const parsed = new URL(ot.src);
  const source = `${parsed.protocol}//${parsed.host}`;
  const ddid = ot.ddid;
  if (!ddid) return { family: 'onetrust', declared: [] };
  const config = JSON.parse(await fetchText(context, `${source}/consent/${ddid}/${ddid}.json`, page.url()));
  const rulesets = (config.RuleSet || []).filter(rule => Object.values(rule.LanguageSwitcherPlaceholder || {}).some(value => ['en', 'en-GB', 'en-US'].includes(value)));
  for (const rule of rulesets) {
    for (const language of ['en', 'en-gb', 'en-us']) {
      try {
        const body = JSON.parse(await fetchText(context, `${source}/consent/${ddid}/${rule.Id}/${language}.json`, page.url()));
        const declared = parseOneTrustRuleset(body);
        if (declared.length) return { family: 'onetrust', declared };
      } catch { /* prescribed language fallback */ }
    }
  }
  return { family: 'onetrust', declared: [] };
}

function matchDeclaration(cookie, declarations) {
  const observedDomain = cleanDomain(cookie.domain);
  const matches = declarations.filter(item => item.name === cookie.name && (!item.domain || observedDomain === item.domain || observedDomain.endsWith(`.${item.domain}`)));
  if (!matches.length) return null;
  return matches.sort((a, b) => b.label - a.label)[0];
}

async function acceptApi(page, family) {
  if (family === 'cookiebot') {
    await page.waitForFunction(() => typeof window.Cookiebot?.submitCustomConsent === 'function', null, { timeout: 4000 }).catch(() => {});
    return page.evaluate(() => {
      if (typeof window.Cookiebot?.submitCustomConsent !== 'function') return false;
      window.Cookiebot.submitCustomConsent(true, true, true);
      return true;
    });
  }
  await page.waitForFunction(() => typeof window.OneTrust?.AllowAll === 'function' || typeof window.Optanon?.AllowAll === 'function', null, { timeout: 4000 }).catch(() => {});
  return page.evaluate(() => {
    if (typeof window.OneTrust?.AllowAll === 'function') { window.OneTrust.AllowAll(); return true; }
    if (typeof window.Optanon?.AllowAll === 'function') { window.Optanon.AllowAll(); return true; }
    return false;
  });
}

async function oneSite(browser, rank, domain, retainedValues) {
  const siteId = sha(`947N2:${rank}:${domain}`);
  const context = await browser.newContext({ userAgent: USER_AGENT, ignoreHTTPSErrors: false });
  let page;
  let stage = 'navigation';
  let timedOut = false;
  const counts = { observedCookies: 0, duplicateObservations: 0, unmatchedDeclarations: 0, oldNameDrops: 0 };
  const deadline = setTimeout(() => { timedOut = true; context.close().catch(() => {}); }, 30000);
  try {
    page = await context.newPage();
    page.setDefaultTimeout(7000);
    let response;
    try { response = await page.goto(`https://${domain}/`, { waitUntil: 'domcontentloaded', timeout: 12000 }); }
    catch { response = await page.goto(`http://${domain}/`, { waitUntil: 'domcontentloaded', timeout: 12000 }); }
    if (!response) return { rank, siteId, status: 'navigation-failed', rows: [] };
    const pageSignal = (await page.locator('body').innerText({ timeout: 2000 }).catch(() => '')).slice(0, 4000).toLowerCase();
    if (/(captcha|access denied|verify you are human|unusual traffic|checking your browser|temporarily blocked)/.test(pageSignal)) {
      return { rank, siteId, status: 'blocked', rows: [] };
    }
    const scripts = await page.locator('script').evaluateAll(nodes => nodes.map(node => ({
      src: node.src || '', cbid: node.getAttribute('data-cbid') || '', ddid: node.getAttribute('data-domain-script') || ''
    })));
    stage = 'declaration';
    const found = await declaration(context, page, new URL(page.url()).hostname, scripts);
    if (!found) return { rank, siteId, status: 'no-supported-cmp', rows: [] };
    if (!found.declared.length) return { rank, siteId, family: found.family, status: 'no-usable-declaration', rows: [] };
    stage = 'consent-api';
    if (!await acceptApi(page, found.family)) return { rank, siteId, family: found.family, status: 'consent-api-missing', rows: [] };
    await page.waitForTimeout(500);
    stage = 'reload';
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 });
    await page.waitForTimeout(5000);
    const now = Math.floor(Date.now() / 1000);
    const cookies = await context.cookies();
    counts.observedCookies = cookies.length;
    const seen = new Set();
    const rows = [];
    for (const cookie of cookies) {
      const key = `${cookie.name}\u0000${cleanDomain(cookie.domain)}\u0000${cookie.path}`;
      if (seen.has(key)) { counts.duplicateObservations++; continue; }
      seen.add(key);
      if (String(cookie.value).length >= 8) retainedValues.add(String(cookie.value));
      const matched = matchDeclaration(cookie, found.declared);
      if (!matched) { counts.unmatchedDeclarations++; continue; }
      const normalizedName = normalizeName(cookie.name);
      if (SPLIT[normalizedName] === 'train' || VALIDATION.assignments?.[normalizedName]) { counts.oldNameDrops++; continue; }
      const mapped = { name: cookie.name, value: cookie.value, domain: cookie.domain, path: cookie.path,
        secure: cookie.secure, httpOnly: cookie.httpOnly, sameSite: cookie.sameSite,
        expirationDate: cookie.expires > 0 ? cookie.expires : undefined };
      const extracted = engine.extractFeatures(mapped, { currentDomain: registrable(domain) });
      rows.push({ rank, siteId, cmp: found.family, category: matched.category, groupId: matched.groupId,
        name: cookie.name, normalizedName, domain: cleanDomain(cookie.domain), path: cookie.path,
        label: matched.label, secure: !!cookie.secure, httpOnly: !!cookie.httpOnly,
        sameSite: cookie.sameSite || 'unspecified', hostOnly: !String(cookie.domain).startsWith('.'),
        session: !(cookie.expires > 0), lifetimeSeconds: cookie.expires > 0 ? Math.max(0, cookie.expires - now) : null,
        valueShape: valueShape(cookie.value), features: engine.FEATURE_NAMES.map(name => Number(extracted[name] || 0)),
        declarationMatch: matched.method });
    }
    return { rank, siteId, family: found.family, status: rows.length ? 'usable' : 'no-matched-fresh-cookie', counts, rows };
  } catch (error) {
    return { rank, siteId, status: timedOut ? 'timeout' : stage === 'navigation' ? 'navigation-failed' : `${stage}-failed`, errorType: error?.name || 'Error', counts, rows: [] };
  } finally {
    clearTimeout(deadline);
    await context.close().catch(() => {});
  }
}

async function withDeadline(browser, rank, domain, values) {
  return oneSite(browser, rank, domain, values);
}

function existingState() {
  const attempts = [];
  for (let start = 1; start <= MAX_RANK; start += CHUNK) {
    const path = join(OUT, `attempts-${String(start).padStart(5, '0')}.json`);
    if (!existsSync(path)) break;
    attempts.push(...JSON.parse(readFileSync(path, 'utf8')).attempts);
  }
  return attempts;
}

mkdirSync(OUT, { recursive: true });
if (engine.FEATURE_NAMES.length !== 38) throw new Error('feature schema is not 38 columns');
const domains = readFileSync(INPUT, 'utf8').trim().split(/\r?\n/).map(line => line.split(',', 2));
const browser = await chromium.launch({ executablePath: BROWSER, headless: true });
const retainedValues = new Set();
const prior = existingState();
let usable = prior.filter(row => row.status === 'usable').length;
let nextRank = prior.length + 1;

for (let start = nextRank; start <= Math.min(MAX_RANK, domains.length) && usable < STOP_USABLE; start += CHUNK) {
  const stop = Math.min(start + CHUNK - 1, MAX_RANK, domains.length);
  const chunkAttempts = [];
  const partial = join(OUT, `rows-${String(start).padStart(5, '0')}.jsonl.partial`);
  atomic(partial, '');
  for (let cursor = start; cursor <= stop && usable < STOP_USABLE; cursor += 4) {
    const batch = [];
    for (let rank = cursor; rank <= Math.min(cursor + 3, stop); rank++) {
      const [listedRank, domain] = domains[rank - 1];
      if (Number(listedRank) !== rank) throw new Error(`rank mismatch at ${rank}`);
      batch.push(withDeadline(browser, rank, domain, retainedValues));
    }
    const results = await Promise.all(batch);
    chunkAttempts.push(...results.map(result => ({ rank: result.rank, siteId: result.siteId, family: result.family || null,
      status: result.status, errorType: result.errorType || null, keptCookies: result.rows.length,
      counts: result.counts || { observedCookies: 0, duplicateObservations: 0, unmatchedDeclarations: 0, oldNameDrops: 0 } })));
    usable += results.filter(result => result.status === 'usable').length;
    const rows = results.flatMap(result => result.rows);
    if (rows.length) {
      const existing = readFileSync(partial, 'utf8');
      writeFileSync(partial, existing + rows.map(row => JSON.stringify(row)).join('\n') + '\n');
    }
  }
  const finalRows = join(OUT, `rows-${String(start).padStart(5, '0')}.jsonl`);
  renameSync(partial, finalRows);
  atomic(join(OUT, `attempts-${String(start).padStart(5, '0')}.json`), `${JSON.stringify({ schemaVersion: 1, start, stop, attempts: chunkAttempts }, null, 2)}\n`);
  console.log(JSON.stringify({ start, stop, usable, retainedValues: retainedValues.size }));
}

await browser.close();
const allAttempts = existingState();
const statusCounts = {};
const dropCounts = { observedCookies: 0, duplicateObservations: 0, unmatchedDeclarations: 0, oldNameDrops: 0 };
for (const row of allAttempts) statusCounts[row.status] = (statusCounts[row.status] || 0) + 1;
for (const row of allAttempts) for (const key of Object.keys(dropCounts)) dropCounts[key] += Number(row.counts?.[key] || 0);
const rowFiles = [];
for (let start = 1; start <= allAttempts.length; start += CHUNK) {
  const name = `rows-${String(start).padStart(5, '0')}.jsonl`;
  const path = join(OUT, name);
  if (existsSync(path)) rowFiles.push({ file: name, sha256: sha(readFileSync(path)), bytes: readFileSync(path).length });
}
const names = new Set();
let records = 0;
for (const item of rowFiles) {
  const text = readFileSync(join(OUT, item.file), 'utf8').trim();
  if (!text) continue;
  for (const line of text.split('\n')) { names.add(JSON.parse(line).normalizedName); records++; }
}
atomic(join(OUT, 'schema.json'), `${JSON.stringify({ schemaVersion: 1, featureNames: engine.FEATURE_NAMES, userAgent: USER_AGENT }, null, 2)}\n`);
atomic(join(OUT, 'manifest.json'), `${JSON.stringify({ schemaVersion: 1, listId: '947N2', attemptedRanks: allAttempts.length,
  usableSites: allAttempts.filter(row => row.status === 'usable').length, records, normalizedNames: names.size,
  statusCounts, dropCounts, rowFiles, completedAt: new Date().toISOString() }, null, 2)}\n`);
console.log(JSON.stringify({ done: true, attemptedRanks: allAttempts.length, usableSites: usable, records, normalizedNames: names.size, statusCounts, dropCounts }, null, 2));
