import assert from 'node:assert/strict';
import test from 'node:test';
import { crawlShard, oneSite } from '../crawl.mjs';
import { PrivacyGuard, PrivacyRejection } from '../privacy.mjs';
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
    assert.deepEqual([...f.files.keys()].sort(), ['receipt.json', 'started.json', 'upload-ready.json']);
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
});

test('existing start marker prevents a repeat without deleting previous output', async () => {
  const f = fixture();
  await crawlShard(f.options);
  const before = [...f.files.entries()];
  await assert.rejects(crawlShard(f.options), { message: 'already-started' });
  assert.deepEqual([...f.files.entries()], before);
});
