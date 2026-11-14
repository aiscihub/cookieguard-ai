// Offline integration driver: all visits are pure functions over .example sites.
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { crawlShard, resumeInput } from '../crawl.mjs';
import { readJSON, ROOT, sha, writeAtomic, writeJSON } from '../common.mjs';

const run = resolve(process.argv[2]);
const frame = readJSON(resolve(run, 'frame.json')), plan = readJSON(resolve(run, 'resume-plan.json'));
assert.ok(frame.frame.every(s => s.domain.endsWith('.example')));
const visited = [];
for (const item of plan.shards.filter(s => s.remaining)) {
  const folder = resolve(run, 'resume-inputs/shard-' + item.shard), output = resolve(run, 'shards/shard-' + item.shard);
  mkdirSync(output, { recursive: true });
  const resume = resumeInput(frame, item.shard, plan.frameSha256, readJSON(resolve(folder, 'plan.json')),
    readFileSync(resolve(folder, 'kept-attempts.json')), readFileSync(resolve(folder, 'kept-cookies.jsonl')));
  await crawlShard({ frame, shard: item.shard, frameSha256: plan.frameSha256,
    engineSha256: sha(readFileSync(resolve(ROOT, 'packages/core/vendor/engine.cjs'))), resume,
    storage: {
      start: record => writeFileSync(resolve(output, 'started.json'), JSON.stringify(record), { flag: 'wx' }),
      write: (name, data) => writeAtomic(resolve(output, name), data), json: (name, data) => writeJSON(resolve(output, name), data),
      read: name => readFileSync(resolve(output, name)), remove: name => rmSync(resolve(output, name), { force: true }),
    },
    launch: async () => ({ close: async () => {}, isConnected: () => true }), progress: () => {},
    visit: async (_, site) => {
      visited.push(site.siteId);
      return { ...site, status: 'usable', visited: true, robotsStatus: 'allowed', cmp: 'cookiebot', rows: [{
        crawl: 'monthly', rank: site.rank, cmp: 'cookiebot', declaredCategory: 'statistics', declaredGroup: 'statistics',
        name: 'resumed_metric', normalizedName: 'resumed_metric', domain: site.domain, path: '/', label: 'tracker',
        secure: true, httpOnly: false, sameSite: 'Lax', hostOnly: true, session: true, lifetimeSeconds: null,
        valueLength: 0, valueCharacterSet: 'other', declarationMatch: 'exact', features: Array(38).fill(0),
        crawlDate: '2026-11-14T00:00:00Z', trancoListId: frame.trancoListId,
      }] };
    },
  });
}
assert.deepEqual(visited, plan.shards.flatMap(s => s.remainingSiteIds));
console.log(JSON.stringify({ fakeVisits: visited.length, publicVisits: 0 }));
