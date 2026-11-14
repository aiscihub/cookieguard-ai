import assert from 'node:assert/strict';
import test from 'node:test';
import { crawlShard, oneSite, resumeInput } from '../crawl.mjs';
import { PrivacyGuard, PrivacyRejection } from '../privacy.mjs';
import { artifactFiles } from '../seal.mjs';
import { sha } from '../common.mjs';
import { siteBrowser } from './fakes.mjs';

function fixture(count = 8) {
  const files = new Map(), progress = [];
  const frame = { month: '2026-11', shards: 1, dryRun: true, trancoListId: 'FIXTURE',
    frame: Array.from({ length: count }, (_, i) => ({ shard: 1, rank: i + 1,
      siteId: 'fixture-' + (i + 1), domain: 'site' + (i + 1) + '.example' })) };
  const storage = {
    start(record) {
      if (files.has('started.json')) throw new Error('already-started');
      files.set('started.json', JSON.stringify(record));
    },
    write: (name, data) => files.set(name, data),
    json: (name, data) => files.set(name, JSON.stringify(data)),
    read: name => files.get(name),
    remove: name => files.delete(name),
  };
  const browser = { ...siteBrowser().browser, close: async () => {}, isConnected: () => true };
  return { files, storage, frame, progress, browser, options: { frame, shard: 1, storage,
    frameSha256: 'a'.repeat(64), engineSha256: 'b'.repeat(64), launch: async () => browser,
    progress: record => progress.push(record) } };
}

test('newContext failure is one attempted browser-error with no exception contents', async () => {
  const f = fixture(1);
  f.browser.newContext = async () => { throw new Error('private-exception-sentinel'); };
  await crawlShard(f.options);
  const attempts = JSON.parse(f.files.get('attempts.json'));
  assert.equal(attempts.length, 1);
  assert.equal(attempts[0].status, 'browser-error');
  assert.equal(attempts[0].robotsStatus, 'not-checked');
  assert.equal(attempts[0].visited, false);
  assert.equal(JSON.parse(f.files.get('receipt.json')).attempted, 1);
  assert.ok(![...f.files.values()].join('').includes('private-exception-sentinel'));
});

test('disconnected browser relaunches once and never repeats the affected sites', async () => {
  const f = fixture(), attempted = [];
  let connected = true, launches = 0;
  const dead = { isConnected: () => connected, close: async () => {}, async newContext() {
    connected = false;
    throw new Error('private-browser-sentinel');
  } };
  await crawlShard({ ...f.options, launch: async () => ++launches === 1 ? dead : f.browser,
    visit: async (browser, item, frame, guard) => {
      attempted.push(item.siteId);
      return oneSite(browser, item, frame, guard);
    } });
  const observations = JSON.parse(f.files.get('attempts.json'));
  assert.equal(launches, 2);
  assert.equal(new Set(attempted).size, 8);
  assert.equal(attempted.length, 8);
  assert.deepEqual(observations.slice(0, 4).map(x => x.status), Array(4).fill('browser-error'));
  assert.deepEqual(observations.slice(4).map(x => x.status), Array(4).fill('no-supported-cmp'));
  assert.equal(JSON.parse(f.files.get('receipt.json')).attempted, 8);
});

for (const reason of ['privacy-rejected', 'browser-error', 'io-error']) {
  test('failed receipt records only the fixed ' + reason + ' reason', async () => {
    const f = fixture();
    if (reason === 'browser-error') f.options.launch = async () => { throw new Error('private-exception-sentinel'); };
    if (reason === 'io-error') f.storage.write = () => {
      f.files.set('cookies.jsonl.tmp', 'private-exception-sentinel');
      throw new Error('private-exception-sentinel');
    };
    if (reason === 'privacy-rejected') {
      f.options.guard = new PrivacyGuard();
      f.options.visit = async (browser, item, frame, guard) => {
        const result = await oneSite(browser, item, frame, guard);
        if (item.rank <= 4) result.diagnostic = 'private-cookie-sentinel';
        else guard.observe([{ value: 'private-cookie-sentinel' }]);
        return result;
      };
    }
    await assert.rejects(crawlShard(f.options), { message: 'shard-failed-closed' });
    const receipt = JSON.parse(f.files.get('receipt.json'));
    assert.equal(receipt.reasonCode, reason);
    assert.equal(receipt.status, 'failed-closed');
    assert.equal(receipt.privacy.passed, false);
    assert.deepEqual([...f.files.keys()].sort(), ['receipt.json', 'started.json', 'upload-ready.json', 'visited.json']);
    assert.ok(![...f.files.values(), JSON.stringify(f.progress)].join('').includes('sentinel'));
  });
}

test('privacy rejection stops after a settled batch and never starts the next one', async () => {
  const f = fixture(12), called = [];
  await assert.rejects(crawlShard({ ...f.options, visit: async (_, item) => {
    called.push(item.rank);
    if (item.rank === 1) throw new PrivacyRejection();
    await Promise.resolve();
    return { ...item, rows: [] };
  } }), { message: 'shard-failed-closed' });
  assert.deepEqual(called, [1, 2, 3, 4]);
  assert.equal(JSON.parse(f.files.get('receipt.json')).reasonCode, 'privacy-rejected');
});

test('cleanup failure leaves no upload marker and does not expose exception text', async () => {
  const f = fixture();
  f.options.guard = { check() { throw new PrivacyRejection(); } };
  f.options.visit = async (_, item) => ({ ...item, rows: [] });
  f.storage.remove = () => { throw new Error('private-io-sentinel'); };
  await assert.rejects(crawlShard(f.options), { message: 'shard-failed-closed' });
  assert.equal(f.files.has('upload-ready.json'), false);
  assert.ok(![...f.files.values()].join('').includes('sentinel'));
  assert.equal(JSON.parse(f.files.get('receipt.json')).reasonCode, 'privacy-rejected');
  f.files.set('checkpoint.json', 'unexportable-fixture');
  const artifact = artifactFiles(f.files, 'cancelled', f.frame, f.options.frameSha256, 1);
  assert.equal(artifact.has('checkpoint.json'), false);
  assert.equal(JSON.parse(artifact.get('receipt.json')).reasonCode, 'privacy-rejected');
});

test('existing start marker prevents a repeat without deleting previous output', async () => {
  const f = fixture();
  await crawlShard(f.options);
  const before = [...f.files.entries()];
  await assert.rejects(crawlShard(f.options), { message: 'already-started' });
  assert.deepEqual([...f.files.entries()], before);
});

test('resume skips kept and in-flight sites and records a distinct new-part privacy result', async () => {
  const f = fixture(12), called = [];
  const attempts = f.frame.frame.slice(0, 4).map(site => ({ ...site, status: 'no-supported-cmp',
    visited: true, robotsStatus: 'allowed', cmp: 'none' }));
  const a = JSON.stringify(attempts), r = '';
  const privacy = { passed: true, structuralPassed: true, crossScanPassed: true };
  const proof = { sourceRun: '123', keptPrefix: 4, visitedPrefix: 8,
    keptAttemptsSha256: sha(a), keptRowsSha256: sha(r), keptPrivacy: privacy };
  const plan = { shard: 1, frameSha256: f.options.frameSha256, sourceRun: '123', recorded: 4, rows: 0,
    visitedPrefix: 8, remainingSiteIds: f.frame.frame.slice(8).map(s => s.siteId),
    keptAttemptsSha256: sha(a), keptRowsSha256: sha(r), keptPrivacy: privacy, resume: proof };
  const resume = resumeInput(f.frame, 1, f.options.frameSha256, plan, a, r);
  const receipt = await crawlShard({ ...f.options, resume, visit: async (browser, site, frame, guard) => {
    const ledger = JSON.parse(f.files.get('visited.json'));
    assert.ok(ledger.siteIds.includes(site.siteId));
    called.push(site.siteId);
    return oneSite(browser, site, frame, guard);
  } });
  assert.deepEqual(called, plan.remainingSiteIds);
  const output = JSON.parse(f.files.get('attempts.json'));
  assert.deepEqual(output.slice(0, 4), attempts);
  assert.deepEqual(output.slice(4, 8).map(a => a.status), Array(4).fill('visited-not-recorded'));
  assert.equal(receipt.attempted, 12);
  assert.equal(receipt.resume.sourceRun, '123');
  assert.equal(receipt.newPart.attempted, 4);
  assert.equal(receipt.newPart.privacy.crossScanPassed, true);
  assert.throws(() => resumeInput(f.frame, 1, f.options.frameSha256, plan, a + ' ', r), /invalid-resume-input/);
  const failed = fixture(12);
  await assert.rejects(crawlShard({ ...failed.options, resume, launch: async () => { throw new Error('fixture'); } }), /shard-failed-closed/);
  const failedReceipt = JSON.parse(failed.files.get('receipt.json'));
  assert.deepEqual(failedReceipt.resume, proof);
  assert.equal(failedReceipt.newPart.privacy.passed, false);
  const artifact = artifactFiles(failed.files, 'failure', failed.frame, failed.options.frameSha256, 1);
  assert.deepEqual(JSON.parse(artifact.get('receipt.json')).resume, proof);

});

test('ledger is durable before launching and survives privacy fail-closed', async () => {
  const f = fixture(12);
  const guard = new PrivacyGuard();
  let visits = 0;
  await assert.rejects(crawlShard({ ...f.options, guard, launch: async () => {
    assert.equal(JSON.parse(f.files.get('visited.json')).siteIds.length, 4);
    return f.browser;
  }, visit: async (_, site) => {
    visits++;
    assert.ok(JSON.parse(f.files.get('visited.json')).siteIds.includes(site.siteId));
    return { ...site, status: 'no-supported-cmp', robotsStatus: 'allowed', visited: true, cmp: 'none',
      rows: [], forbidden: { value: 'fixture' } };
  } }), /shard-failed-closed/);
  assert.equal(visits, 4);
  assert.deepEqual(JSON.parse(f.files.get('visited.json')).siteIds, f.frame.frame.slice(0, 4).map(s => s.siteId));
  assert.equal(f.files.has('checkpoint.json'), false);
  assert.equal(JSON.parse(f.files.get('receipt.json')).reasonCode, 'privacy-rejected');
});

test('a failed ledger write prevents browser launch and every site visit', async () => {
  const f = fixture();
  const json = f.storage.json;
  f.storage.json = (name, data) => { if (name === 'visited.json') throw new Error('fixture-disk-failure'); json(name, data); };
  let launches = 0, visits = 0;
  await assert.rejects(crawlShard({ ...f.options, launch: async () => { launches++; }, visit: async () => { visits++; } }), /shard-failed-closed/);
  assert.equal(launches, 0); assert.equal(visits, 0);
  assert.equal(JSON.parse(f.files.get('receipt.json')).reasonCode, 'io-error');
});

test('cancelled artifact keeps only the atomic checkpoint and ledger, ignoring torn exports', async () => {
  const f = fixture(), snapshots = [], json = f.storage.json;
  f.storage.json = (name, data) => { if (name === 'checkpoint.json') snapshots.push(JSON.stringify(data)); json(name, data); };
  await crawlShard(f.options);
  f.files.delete('receipt.json');
  f.files.set('checkpoint.json', snapshots[0]);
  f.files.set('attempts.json', 'in-flight-private-sentinel');
  f.files.set('cookies.jsonl', 'in-flight-private-sentinel');
  const artifact = artifactFiles(f.files, 'cancelled', f.frame, f.options.frameSha256, 1);
  assert.deepEqual([...artifact.keys()].sort(), ['checkpoint.json', 'started.json', 'visited.json']);
  assert.equal(JSON.parse(artifact.get('checkpoint.json')).attempts.length, 4);
  assert.equal(JSON.parse(artifact.get('visited.json')).siteIds.length, 8);
  assert.ok(![...artifact.values()].join('').includes('sentinel'));
});

test('failed artifact preserves the visited ledger and drops all payloads even after cleanup errors', async () => {
  const f = fixture();
  await crawlShard(f.options);
  const artifact = artifactFiles(f.files, 'failure', f.frame, f.options.frameSha256, 1);
  assert.deepEqual([...artifact.keys()].sort(), ['receipt.json', 'started.json', 'visited.json']);
  assert.equal(JSON.parse(artifact.get('receipt.json')).status, 'failed-closed');
  assert.equal(JSON.parse(artifact.get('visited.json')).siteIds.length, 8);
});
