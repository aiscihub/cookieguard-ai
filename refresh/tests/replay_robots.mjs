// Checkpoint 1b: synthetic pattern replay. No public network client is used.
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { args, readJSON, writeJSON } from '../common.mjs';
import { oneSite } from '../crawl.mjs';
import { PrivacyGuard } from '../privacy.mjs';
import { response, siteBrowser } from './fakes.mjs';

const options = args({ out: { type: 'string', default: 'refresh/.work/checkpoint-1b/robots-replay.json' } });
const original = readJSON(resolve('refresh/.work/checkpoint-1/releases/2026-11/manifest.json'));
assert.equal(original.statusCounts['robots-unavailable'], 69);
const cases = [];
for (let i = 1; i <= 69; i++) {
  const pattern = ['redirect', '403', '5xx'][(i - 1) % 3];
  const domain = `fixture${i}.example`;
  const fixture = siteBrowser({ robots: url => {
    if (pattern === '403') return response(403);
    if (pattern === '5xx') return response(503);
    return new URL(url).hostname === domain ? response(301, '', `https://www.${domain}/robots.txt`) : response();
  } });
  const result = await oneSite(fixture.browser, { domain, rank: i, shard: 1, siteId: 'fixture-' + i },
                             { trancoListId: 'FIXTURE' }, new PrivacyGuard());
  const expected = pattern === 'redirect' ? 'allowed' : pattern === '403' ? 'absent-4xx' : 'server-error';
  assert.equal(result.robotsStatus, expected);
  assert.equal(result.visited, pattern !== '5xx');
  cases.push({ case: i, pattern, expected, robotsStatus: result.robotsStatus,
               status: result.status, visited: result.visited, cmp: result.cmp, passed: true });
}
const result = {
  kind: 'in-memory synthetic pattern replay', originalRobotsUnavailableCount: 69,
  interpretation: 'Original receipts did not retain HTTP status or redirect history. The 23/23/23 split is a balanced test matrix, not a reconstruction of those sites.',
  publicVisits: 0, publicRequests: 0, originalEvidenceModified: false, cases,
  summary: { cases: 69, correct: 69, redirectsAllowed: 23, forbiddenResponsesAllowed: 23, serverErrorsSkipped: 23 },
};
writeJSON(resolve(options.out), result);
console.log(JSON.stringify({ ...result.summary, publicVisits: 0, publicRequests: 0 }));
