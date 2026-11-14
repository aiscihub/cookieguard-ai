import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { args, die, monthSeed, ROOT, sha, writeAtomic, writeJSON } from './common.mjs';

export function parseRanking(csv) {
  const items = [], ranks = new Set(), seen = new Set();
  let invalidDomainRows = 0;
  for (const line of csv.trim().split(/\r?\n/)) {
    const [rankText, raw] = line.split(',');
    const rank = Number(rankText), domain = String(raw || '').trim().toLowerCase();
    if (!Number.isInteger(rank) || rank < 1 || rank > 100000) continue;
    if (ranks.has(rank)) throw new Error('duplicate-rank');
    ranks.add(rank);
    // Tranco includes wildcard placeholders; they are not visitable domains.
    // Punycode TLDs remain eligible.
    if (!/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$/.test(domain)) { invalidDomainRows++; continue; }
    if (seen.has(domain)) throw new Error('duplicate-domain');
    seen.add(domain);
    items.push({ rank, domain });
  }
  if (ranks.size !== 100000) throw new Error('incomplete-ranking');
  return { items, invalidDomainRows };
}
export function selectFrame(csv, excluded, count, seed) {
  const eligible = parseRanking(csv).items.filter(item => !excluded.has(item.domain));
  if (eligible.length < count) throw new Error('insufficient-eligible-domains');
  // SHA-256 counter stream, rejection sampling, Fisher-Yates: no modulo bias.
  let counter = 0;
  function draw(n) {
    const limit = Math.floor(2 ** 32 / n) * n;
    let value;
    do { value = parseInt(sha(String(seed) + ':' + counter++).slice(0, 8), 16); } while (value >= limit);
    return value % n;
  }
  for (let i = eligible.length - 1; i > 0; i--) {
    const j = draw(i + 1);
    [eligible[i], eligible[j]] = [eligible[j], eligible[i]];
  }
  return eligible.slice(0, count);
}
async function fetchText(url) {
  const r = await fetch(url, { signal: AbortSignal.timeout(60000), redirect: 'error' });
  if (!r.ok) throw new Error('ranking-download-failed');
  return r.text();
}
export async function main() {
  const a = args({
    month: { type: 'string' }, sites: { type: 'string', default: '10000' },
    shards: { type: 'string', default: '16' }, out: { type: 'string', default: 'refresh/.work/run' },
    state: { type: 'string', default: 'refresh/state/crawled_domains.txt' },
    csv: { type: 'string' }, 'list-id': { type: 'string' }, 'dry-run': { type: 'boolean', default: false }
  });
  const month = a.month || new Date().toISOString().slice(0, 7), seed = monthSeed(month);
  const sites = Number(a.sites), shards = Number(a.shards), out = resolve(a.out);
  if (!Number.isInteger(sites) || sites < 1 || sites > 10000 ||
      !Number.isInteger(shards) || shards < 1 || shards > 16 || shards > sites) throw new Error('invalid-size');
  if (existsSync(resolve(out, 'frame.json'))) throw new Error('frame-already-frozen');
  const excludedText = readFileSync(resolve(a.state), 'utf8');
  const excluded = new Set(excludedText.trim().split(/\r?\n/).filter(Boolean));
  if (excluded.size < 20000) throw new Error('missing-initial-exclusions');
  let listId = a['list-id'], csv;
  if (a.csv) {
    if (!listId) throw new Error('list-id-required');
    csv = readFileSync(resolve(a.csv), 'utf8');
  } else {
    const meta = JSON.parse(await fetchText('https://tranco-list.eu/api/lists/date/latest'));
    if (!meta.available || meta.failed || !/^[A-Z0-9]{4,12}$/.test(meta.list_id)) throw new Error('ranking-unavailable');
    listId = meta.list_id;
    csv = await fetchText('https://tranco-list.eu/download/' + listId + '/100000');
  }
  if (!/^[A-Z0-9]{4,12}$/.test(listId)) throw new Error('invalid-list-id');
  const frame = selectFrame(csv, excluded, sites, seed).map((site, i) => ({
    ...site, siteId: sha(listId + ':' + site.rank + ':' + site.domain), shard: i % shards + 1
  }));
  writeAtomic(resolve(out, 'ranking.csv'), csv);
  writeAtomic(resolve(out, 'exclusions.txt'), [...excluded].sort().join('\n') + '\n');
  const payload = {
    schemaVersion: 1, month, seed, sites, shards, dryRun: a['dry-run'],
    createdAt: new Date().toISOString(), trancoListId: listId,
    trancoSha256: sha(csv), exclusionsSha256: sha(excludedText), excludedDomains: excluded.size,
    invalidDomainRows: parseRanking(csv).invalidDomainRows,
    sampling: 'uniform without replacement; SHA-256 counter rejection Fisher-Yates; ranks 1-100000',
    frame
  };
  writeJSON(resolve(out, 'frame.json'), payload);
  for (let i = 1; i <= shards; i++) writeJSON(resolve(out, 'shard-' + i + '.json'), {
    frameSha256: sha(readFileSync(resolve(out, 'frame.json'))), shard: i, of: shards,
    sites: frame.filter(site => site.shard === i)
  });
  console.log(JSON.stringify({ stage: 'frame', sites, shards, listId, seed }));
}
if (import.meta.url === pathToFileURL(process.argv[1] || '').href) main().catch(die);
