import { createHash } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '../..');
const RAW = join(ROOT, 'waicy_2026/cookieblock_test/raw/06_Training_Data/tranco_05May_20210510_201615.json');
const OLD = join(ROOT, 'waicy_2026/retrain_test/features');
const SPLIT = JSON.parse(readFileSync(join(ROOT, 'waicy_2026/retrain_test/split.json'), 'utf8'));
const OUT = join(HERE, 'features');
const LOCKS = join(HERE, 'locks.txt');
const CHUNK = 10000;
const sha = data => createHash('sha256').update(data).digest('hex');
const require = createRequire(import.meta.url);
const engine = require(join(ROOT, 'waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/vendor/engine.cjs'));
const { getDomain } = require(join(ROOT, 'waicy_2026/cookieblock_test/raw/runtime/node_modules/tldts'));
const core = await import(join(ROOT, 'waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/src/index.js'));

function clean(value) { return String(value || '').toLowerCase().replace(/^\.+/, '').replace(/\.$/, ''); }
function reg(value) { const v = clean(value); return getDomain(v, { allowPrivateDomains: true }) || v; }
function host(value) { try { return new URL(value).hostname; } catch { return clean(value); } }
function sameSite(value) {
  const v = String(value || '').toLowerCase();
  return v === 'no_restriction' ? 'none' : ['strict', 'lax', 'none'].includes(v) ? v : '';
}
function shape(value) {
  const v = String(value ?? '');
  if (!v) return 'empty';
  if (/^\d+$/.test(v)) return 'digits';
  if (/^[0-9a-f]+$/i.test(v)) return 'hex';
  if (/^[a-z0-9]+$/i.test(v)) return 'alphanumeric';
  if (/^[a-z0-9+/=_-]+$/i.test(v)) return 'base64/base64url';
  return 'other';
}
function cookie(record, observation, now) {
  const lifetime = Math.max(0, Number(observation.expiry) || 0);
  return { name: String(record.name || ''), value: String(observation.value ?? ''), domain: String(record.domain || ''),
    path: record.path || '/', secure: observation.secure === true, httpOnly: observation.http_only === true,
    sameSite: sameSite(observation.same_site), hostOnly: observation.host_only === true,
    expirationDate: observation.session === true ? undefined : now + lifetime };
}
function normalizeName(input) {
  return String(input).trim().toLowerCase().split(/([_.-])/).map(piece => {
    if (/^[_.-]$/.test(piece)) return piece;
    const mixed = piece.length >= 6 && /[a-z]/.test(piece) && /[0-9]/.test(piece);
    const hex = piece.length >= 8 && /^[0-9a-f]+$/.test(piece) && /[a-f]/.test(piece);
    return mixed || hex ? '#' : piece;
  }).join('').replace(/\d+/g, '0');
}
function lock(line) { appendFileSync(LOCKS, `${line}\n`); }

mkdirSync(OUT, { recursive: true });
if (engine.FEATURE_NAMES.length !== 38 || JSON.stringify(engine.FEATURE_NAMES) !== JSON.stringify(core.FEATURE_NAMES)) throw new Error('feature schema mismatch');
const schemaPath = join(OUT, 'feature_names.json');
if (!existsSync(schemaPath)) writeFileSync(schemaPath, `${JSON.stringify({ schemaVersion: 2, featureNames: engine.FEATURE_NAMES }, null, 2)}\n`);
const records = Object.values(JSON.parse(readFileSync(RAW, 'utf8')));
const oldRows = new Map();
for (let c = 0; c < Math.ceil(records.length / CHUNK); c++) {
  const oldPath = join(OLD, `chunk-${String(c).padStart(3, '0')}.jsonl`);
  for (const line of readFileSync(oldPath, 'utf8').trim().split('\n')) { const row = JSON.parse(line); oldRows.set(row.recordIndex, row); }
}
const trainIndices = records.map((r, i) => SPLIT[normalizeName(r.name)] === 'train' ? i : -1).filter(i => i >= 0);
const sanityIndices = JSON.parse(readFileSync(join(HERE, 'sanity_indices.json'), 'utf8'));
if (sanityIndices.seed !== 2026111003 || sanityIndices.indices.length !== 1000 || sanityIndices.indices.some(index => !trainIndices.includes(index))) throw new Error('invalid sanity sample');
const sanitySet = new Set(sanityIndices.indices);
let emptyCompared = 0, emptyMismatches = 0, contextCompared = 0, contextMatches = 0, thirdParty = 0;
const now = Math.floor(Date.now() / 1000);
for (let c = 0; c < Math.ceil(records.length / CHUNK); c++) {
  const path = join(OUT, `chunk-${String(c).padStart(3, '0')}.jsonl`);
  if (existsSync(path)) continue;
  const lines = [];
  const start = c * CHUNK, end = Math.min(records.length, start + CHUNK);
  for (let index = start; index < end; index++) {
    const record = records[index], observation = record.variable_data[0], mapped = cookie(record, observation, now);
    const currentDomain = reg(host(record.first_party_domain));
    const context = engine.extractFeatures(mapped, { currentDomain });
    const normalizedName = normalizeName(record.name);
    const old = oldRows.get(index);
    if (!old || old.normalizedName !== normalizedName) throw new Error(`old feature mismatch ${index}`);
    if (sanitySet.has(index)) {
      const direct = engine.extractFeatures(mapped, {}), wrapped = core.extractCookieFeatures(mapped);
      emptyCompared++;
      if (engine.FEATURE_NAMES.some(name => Number(direct[name] || 0) !== Number(wrapped[name] || 0))) emptyMismatches++;
    }
    if (SPLIT[normalizedName] === 'train') {
      const expected = old.websiteId.endsWith(':0') ? 1 : 0;
      const actual = Number(context.f_third_party_context || 0);
      contextCompared++; contextMatches += actual === expected ? 1 : 0; thirdParty += actual;
    }
    lines.push(JSON.stringify({ recordIndex: index, websiteId: old.websiteId, lowercaseName: old.lowercaseName,
      normalizedName, domain: String(record.domain || ''), label: record.label,
      features: engine.FEATURE_NAMES.map(name => Number(context[name] || 0)), thirdParty: !!context.f_third_party_context,
      secure: mapped.secure, httpOnly: mapped.httpOnly, sameSite: mapped.sameSite || 'unspecified',
      lifetimeDays: observation.session === true ? null : Math.max(0, Number(observation.expiry) || 0) / 86400,
      valueShape: { length: mapped.value.length, characterSet: shape(mapped.value) } }));
  }
  const text = `${lines.join('\n')}\n`, tmp = `${path}.tmp`;
  writeFileSync(tmp, text); renameSync(tmp, path);
  lock(`${sha(text)}  features/${path.split('/').pop()}`);
  console.log(JSON.stringify({ chunk: c, rows: end - start }));
}
const sanity = { schemaVersion: 1, emptyContext: { seed: 2026111003, records: emptyCompared, mismatches: emptyMismatches, passed: emptyCompared === 1000 && emptyMismatches === 0 },
  contextAgreement: { trainingRecords: contextCompared, matches: contextMatches, agreement: contextMatches / contextCompared,
    thirdPartyRecords: thirdParty, thirdPartyShare: thirdParty / contextCompared, passed: contextMatches / contextCompared >= .99 } };
writeFileSync(join(HERE, 'sanity_checks.json'), `${JSON.stringify(sanity, null, 2)}\n`);
if (!sanity.emptyContext.passed || !sanity.contextAgreement.passed) throw new Error(`sanity check failed ${JSON.stringify(sanity)}`);
console.log(JSON.stringify(sanity));
