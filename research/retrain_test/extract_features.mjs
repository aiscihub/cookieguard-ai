import { createHash } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '../..');
const INPUT = join(ROOT, 'waicy_2026/cookieblock_test/raw/06_Training_Data/tranco_05May_20210510_201615.json');
const OUT = join(HERE, 'features');
const LOCKS = join(HERE, 'locks.txt');
const CHUNK_SIZE = 10000;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const require = createRequire(import.meta.url);
const { getDomain } = require(join(ROOT, 'waicy_2026/cookieblock_test/raw/runtime/node_modules/tldts'));
const core = await import(join(ROOT, 'waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/src/index.js'));

const EXAMPLES = new Map([
  ['VISITOR_INFO1_LIVE', 'visitor_info0_live'],
  ['_gat_UA-131465162-3', '_gat_ua-0-0'],
  ['_gat_UA-377240-26', '_gat_ua-0-0'],
  ['intercom-id-zy5uzrp0', 'intercom-id-#'],
  ['intercom-session-zy5uzrp0', 'intercom-session-#'],
  ['__csrf_token-1', '__csrf_token-0'],
  ['fsb_total_price_279740', 'fsb_total_price_0'],
  ['AMCVS_D7B27FF452128BAA0A490D4C%40AdobeOrg', 'amcvs_#'],
  ['AMCV_D7B27FF452128BAA0A490D4C%40AdobeOrg', 'amcv_#'],
  ['_gat_gtag_UA_111147133_1', '_gat_gtag_ua_0_0'],
  ['WC_AUTHENTICATION_-1002', 'wc_authentication_-0'],
  ['etf4_session', 'etf0_session'],
  ['TapAd_3WAY_SYNCS', 'tapad_0way_syncs'],
  ['_ga_YKK4GC49SR', '_ga_#'],
  ['_dc_gtm_UA-27781823-16', '_dc_gtm_ua-0-0'],
  ['3060738.3440491', '0.0'],
  ['_sp_id.3d9b', '_sp_id.0d0b'],
  ['tc_tp00', 'tc_tp0'],
  ['tk_r3d', 'tk_r0d'],
  ['yith_wcwl_session_5c27123ef633899817dff8985f9b8dd1', 'yith_wcwl_session_#'],
]);

export function normalizeName(input) {
  const pieces = String(input).trim().toLowerCase().split(/([_.-])/);
  const replaced = pieces.map(piece => {
    if (/^[_.-]$/.test(piece)) return piece;
    const mixed = piece.length >= 6 && /[a-z]/.test(piece) && /[0-9]/.test(piece);
    const hexWithLetter = piece.length >= 8 && /^[0-9a-f]+$/.test(piece) && /[a-f]/.test(piece);
    return mixed || hexWithLetter ? '#' : piece;
  }).join('');
  return replaced.replace(/\d+/g, '0');
}

for (const [input, expected] of EXAMPLES) {
  const actual = normalizeName(input);
  if (actual !== expected) throw new Error(`normalization unit test failed for ${input}: ${actual} != ${expected}`);
}

function sameSite(value) {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'no_restriction') return 'None';
  if (normalized === 'lax') return 'Lax';
  if (normalized === 'strict') return 'Strict';
  return undefined;
}
function cleanDomain(value) { return String(value || '').toLowerCase().replace(/^\.+/, '').replace(/\.$/, ''); }
function registrable(value) { const domain = cleanDomain(value); return getDomain(domain, { allowPrivateDomains: true }) || domain; }
function websiteHost(value) { try { return new URL(value).hostname; } catch { return cleanDomain(value); } }
function websiteId(record) {
  const hash = sha(record.first_party_domain);
  const firstParty = registrable(record.domain) === registrable(websiteHost(record.first_party_domain));
  return `${hash}:${firstParty ? 1 : 0}`;
}
function cookie(record, observation) {
  const lifetime = Math.max(0, Number(observation.expiry) || 0);
  return {
    name: record.name,
    value: observation.value,
    domain: record.domain,
    path: record.path || '/',
    secure: observation.secure === true,
    httpOnly: observation.http_only === true,
    sameSite: sameSite(observation.same_site),
    hostOnly: observation.host_only === true,
    expirationDate: observation.session === true ? undefined : Date.now() / 1000 + lifetime,
  };
}
function lock(entry) { appendFileSync(LOCKS, `${JSON.stringify({ ...entry, at: new Date().toISOString() })}\n`); }

mkdirSync(OUT, { recursive: true });
const metaPath = join(OUT, 'feature_names.json');
if (!existsSync(metaPath)) {
  const text = `${JSON.stringify({ schemaVersion: 1, featureNames: [...core.FEATURE_NAMES], count: core.FEATURE_NAMES.length }, null, 2)}\n`;
  writeFileSync(metaPath, text);
  lock({ event: 'feature_schema', sha256: sha(text), featureCount: core.FEATURE_NAMES.length });
}
if (core.FEATURE_NAMES.length !== 38) throw new Error(`expected 38 features, found ${core.FEATURE_NAMES.length}`);

const records = Object.values(JSON.parse(readFileSync(INPUT, 'utf8')));
const chunks = Math.ceil(records.length / CHUNK_SIZE);
const prior = new Map(readFileSync(LOCKS, 'utf8').split('\n').filter(Boolean).map(JSON.parse).filter(row => row.event === 'feature_chunk').map(row => [row.chunk, row.sha256]));
for (let chunk = 0; chunk < chunks; chunk += 1) {
  const path = join(OUT, `chunk-${String(chunk).padStart(3, '0')}.jsonl`);
  if (existsSync(path)) {
    const actual = sha(readFileSync(path));
    if (prior.get(chunk) !== actual) throw new Error(`feature chunk ${chunk} is not locked or has changed`);
    continue;
  }
  const rows = [];
  const start = chunk * CHUNK_SIZE;
  const end = Math.min(records.length, start + CHUNK_SIZE);
  for (let index = start; index < end; index += 1) {
    const record = records[index];
    const features = core.extractCookieFeatures(cookie(record, record.variable_data[0]));
    rows.push(JSON.stringify({
      recordIndex: index,
      websiteId: websiteId(record),
      lowercaseName: String(record.name).trim().toLowerCase(),
      normalizedName: normalizeName(record.name),
      label: record.label,
      features: core.FEATURE_NAMES.map(name => Number(features[name] || 0)),
    }));
  }
  const text = `${rows.join('\n')}\n`;
  const temporary = `${path}.tmp`;
  writeFileSync(temporary, text);
  renameSync(temporary, path);
  lock({ event: 'feature_chunk', chunk, records: end - start, sha256: sha(text) });
  console.log(JSON.stringify({ chunk, records: end - start }));
}
console.log(JSON.stringify({ complete: true, chunks, records: records.length }));
