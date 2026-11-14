import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const usageURL = new URL('../packages/core/src/usage.js', import.meta.url).href;
const configURL = new URL('../packages/core/src/usage-config.js', import.meta.url).href;
const workerURL = new URL('../packages/core/src/usage-worker.js', import.meta.url).href;
const publicToken = `phc_${'A'.repeat(40)}`;
const base = { package: 'cookieguard-ci', version: '0.2.0', integration: 'cli' };

// Replace built-ins only in isolated processes, never through a production hook.
function run(source, env = {}, timeout = 5000) {
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', source], {
    env: { PATH: process.env.PATH, COOKIEGUARD_POSTHOG_PROJECT_TOKEN: publicToken, ...env },
    encoding: 'utf8', timeout,
  });
  assert.equal(result.error, undefined, result.error?.message);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, '', 'Usage metrics must never write to stdout');
  assert.equal(result.stderr, '', 'Usage metrics must never write to stderr');
}

const senderMocks = `
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { syncBuiltinESMExports } from 'node:module';
import workerThreads from 'node:worker_threads';
import crypto from 'node:crypto';
const workers = [];
let constructionFailure = false;
let postFailure = false;
class FakeWorker extends EventEmitter {
  constructor(url, options) {
    super();
    if (constructionFailure) throw new Error('PRIVATE_CONSTRUCTOR_FAILURE');
    this.url = url; this.options = options; this.sent = []; this.unrefs = 0;
    workers.push(this);
  }
  unref() { this.unrefs++; }
  postMessage(message) {
    if (postFailure) throw new Error('PRIVATE_POST_FAILURE');
    this.sent.push(message);
  }
  terminate() { this.terminated = true; return Promise.resolve(0); }
}
workerThreads.Worker = FakeWorker;
syncBuiltinESMExports();
`;

const senderSetup = `${senderMocks}
const { reportUsage, flushUsage } = await import(${JSON.stringify(usageURL)});
const base = ${JSON.stringify(base)};
`;

test('usage import and opt-outs avoid workers, timers, and random identifiers', () => {
  run(`${senderMocks}
    let randomCalls = 0;
    let timerCalls = 0;
    crypto.randomUUID = () => { randomCalls++; throw new Error('unexpected random UUID'); };
    syncBuiltinESMExports();
    globalThis.setTimeout = () => { timerCalls++; throw new Error('unexpected timer'); };
    const { reportUsage, flushUsage } = await import(${JSON.stringify(usageURL)});
    const base = ${JSON.stringify(base)};
    assert.equal(workers.length, 0);
    assert.equal(randomCalls, 0);
    assert.equal(timerCalls, 0);
    assert.equal(await flushUsage(), undefined);
    reportUsage({ ...base, enabled: false });
    for (const value of ['', 'true', 'yes', '2']) {
      process.env.COOKIEGUARD_USAGE_METRICS = value;
      reportUsage(base);
      reportUsage({ ...base, enabled: null });
    }
    process.env.COOKIEGUARD_USAGE_METRICS = '1';
    reportUsage({ ...base, enabled: false });
    for (const value of ['true', 1, {}, []]) reportUsage({ ...base, enabled: value });
    process.env.COOKIEGUARD_USAGE_METRICS = '0';
    for (const enabled of [undefined, null, false, true]) reportUsage({ ...base, enabled });
    process.env.COOKIEGUARD_USAGE_METRICS = '1';
    process.env.DO_NOT_TRACK = '1';
    for (const enabled of [undefined, null, false, true]) reportUsage({ ...base, enabled });
    delete process.env.COOKIEGUARD_USAGE_METRICS;
    reportUsage(base);
    assert.equal(await flushUsage(), undefined);
    assert.equal(workers.length, 0);
    assert.equal(randomCalls, 0);
    assert.equal(timerCalls, 0);
  `);
});

test('usage defaults to one event per invocation with the bundled project configuration', () => {
  run(`${senderSetup}
    delete process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN;
    const { PROJECT_TOKEN, REGION } = await import(${JSON.stringify(configURL)});
    assert.match(PROJECT_TOKEN, /^phc_[A-Za-z0-9_-]{20,200}$/);
    assert.equal(process.env.COOKIEGUARD_USAGE_METRICS, undefined);
    assert.equal(workers.length, 0);
    reportUsage(base);
    assert.equal(workers.length, 1);
    assert.equal(workers[0].sent.length, 1);
    reportUsage({ ...base, enabled: null });
    assert.equal(workers.length, 1);
    assert.equal(workers[0].sent.length, 2);
    const ids = new Set();
    for (const message of workers[0].sent) {
      assert.equal(message.region, REGION);
      const payload = JSON.parse(message.body);
      assert.equal(payload.api_key, PROJECT_TOKEN);
      assert.equal(payload.event, 'cookieguard_invoked');
      ids.add(payload.distinct_id);
      workers[0].emit('message', message.id);
    }
    assert.equal(ids.size, 2);
    assert.equal(await flushUsage(), undefined);
  `);
});

test('usage serializes exact approved fields and fresh UUIDv4 identifiers', () => {
  run(`${senderSetup}
    process.env.PRIVATE_KEY = 'SENTINEL_PRIVATE_ENV';
    const pairs = [
      ['cli', 'cookieguard-ci'], ['github-action', 'cookieguard-ci'],
      ['playwright', '@aiscihub/cookieguard-playwright'],
      ['mcp', '@aiscihub/cookieguard-mcp'], ['core', '@aiscihub/cookieguard-core'],
    ];
    for (const [integration, packageName] of pairs) {
      assert.equal(reportUsage({ ...base, integration, package: packageName,
        cookie: 'SENTINEL_COOKIE', url: 'https://private.example',
        results: { secret: 'SENTINEL_RESULT' }, enabled: true }), undefined);
    }
    assert.equal(workers.length, 1);
    const instance = workers[0];
    assert.equal(instance.unrefs, 1);
    assert.deepEqual(instance.options, { env: {}, execArgv: [], stdout: true, stderr: true });
    assert.equal(instance.url.href, ${JSON.stringify(workerURL)});
    const ids = new Set();
    for (const [index, message] of instance.sent.entries()) {
      assert.deepEqual(Object.keys(message), ['id', 'region', 'body']);
      assert.equal(message.region, 'us');
      const payload = JSON.parse(message.body);
      assert.match(payload.distinct_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      ids.add(payload.distinct_id);
      assert.deepEqual(payload, {
        api_key: ${JSON.stringify(publicToken)}, event: 'cookieguard_invoked', distinct_id: payload.distinct_id,
        properties: { $process_person_profile: false, $geoip_disable: true, $ip: '0.0.0.0',
          schema_version: 1, package: pairs[index][1], package_version: '0.2.0', integration: pairs[index][0] },
      });
      assert.doesNotMatch(message.body, /SENTINEL|private.example/);
      instance.emit('message', message.id);
    }
    assert.equal(ids.size, pairs.length);
    assert.equal(await flushUsage(), undefined);
    process.env.COOKIEGUARD_USAGE_METRICS = '1';
    reportUsage({ ...base, enabled: null });
    assert.equal(instance.sent.length, 6);
    for (const value of ['', 'true', 'yes', '2']) {
      process.env.COOKIEGUARD_USAGE_METRICS = value;
      reportUsage({ ...base, enabled: true });
    }
    assert.equal(instance.sent.length, 10);
  `);
});

test('usage validates public tokens, regions, finite metadata, and hostile inputs', () => {
  run(`${senderSetup}
    for (const candidate of [undefined, null, false, 'x', [],
      new Proxy({}, { get() { throw new Error('PRIVATE_GETTER'); } }),
      { ...base, package: 'other' }, { ...base, integration: 'toString' },
      { ...base, integration: '__proto__' }, { ...base, integration: 'https://attacker.example' },
      { ...base, package: { toString() { throw new Error('PRIVATE_COERCION'); } } },
      ...['', 'v1.0.0', '01.2.3', '1.2', '1.2.3\\n', '1.2.3-01', '1.2.3+secret/x', '1.2.3-' + 'a'.repeat(64)]
        .map(version => ({ ...base, version }))]) {
      assert.doesNotThrow(() => reportUsage(candidate));
    }
    const token = process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN;
    for (const value of ['', 'phx_private_key', 'sk_secret', 'phc_short', 'phc_' + 'a'.repeat(201),
      token + '\\n', token + ';bad', 'https://attacker.example']) {
      process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN = value;
      reportUsage(base);
    }
    process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN = token;
    for (const value of ['EU', '', 'https://attacker.example', 'us.i.posthog.com', 'us\\n']) {
      process.env.COOKIEGUARD_POSTHOG_REGION = value;
      reportUsage(base);
    }
    assert.equal(workers.length, 0);
    process.env.COOKIEGUARD_POSTHOG_REGION = 'eu';
    reportUsage({ ...base, version: '1.2.3-rc.1+build.4' });
    assert.equal(workers.length, 1);
    assert.equal(workers[0].sent[0].region, 'eu');
  `, { COOKIEGUARD_USAGE_METRICS: '1' });
});

test('usage requires a configured project and bounds its queue at 16 events', () => {
  run(`${senderSetup}
    // An empty override disables delivery even when a release bundles a token.
    process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN = '';
    reportUsage(base);
    assert.equal(workers.length, 0);
    process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN = ${JSON.stringify(publicToken)};
    for (let index = 0; index < 100; index++) reportUsage(base);
    assert.equal(workers.length, 1);
    assert.equal(workers[0].sent.length, 16);
    workers[0].emit('message', 99999);
    reportUsage(base);
    assert.equal(workers[0].sent.length, 16);
    workers[0].emit('message', workers[0].sent[0].id);
    reportUsage(base);
    assert.equal(workers[0].sent.length, 17);
  `, { COOKIEGUARD_USAGE_METRICS: '1' });
});

test('usage flush is bounded, acknowledges delivery, and never logs failures', () => {
  run(`${senderSetup}
    constructionFailure = true;
    assert.doesNotThrow(() => reportUsage(base));
    assert.equal(await flushUsage(), undefined);
    constructionFailure = false;
    postFailure = true;
    assert.doesNotThrow(() => reportUsage(base));
    assert.equal(await flushUsage(), undefined);
    assert.equal(workers[0].terminated, true);
    postFailure = false;
    reportUsage(base);
    const instance = workers.at(-1);
    let started = Date.now();
    await flushUsage(20);
    assert.ok(Date.now() - started >= 10);
    assert.ok(Date.now() - started < 500);
    started = Date.now();
    await flushUsage(-1);
    assert.ok(Date.now() - started < 100);
    started = Date.now();
    await flushUsage(1e9);
    assert.ok(Date.now() - started >= 900);
    assert.ok(Date.now() - started < 1600);
    started = Date.now();
    setTimeout(() => instance.emit('message', instance.sent[0].id), 10);
    await flushUsage(500);
    assert.ok(Date.now() - started < 300);
    reportUsage(base);
    const flushing = flushUsage(500);
    instance.emit('error', new Error('PRIVATE_NETWORK_FAILURE'));
    await flushing;
    assert.equal(instance.terminated, true);
    for (const value of [Symbol(), {}, null, '1000', NaN, Infinity]) {
      assert.equal(await flushUsage(value), undefined);
    }
  `, { COOKIEGUARD_USAGE_METRICS: '1' });
});

const transportSetup = `
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { syncBuiltinESMExports } from 'node:module';
import https from 'node:https';
import workerThreads from 'node:worker_threads';
const calls = [];
const acknowledgements = [];
const port = new EventEmitter();
port.postMessage = id => acknowledgements.push(id);
workerThreads.parentPort = port;
let mode = 'success';
https.request = (options, callback) => {
  const req = new EventEmitter();
  req.destroy = () => { req.destroyed = true; };
  calls.push({ options, req });
  if (mode === 'throw') throw new Error('PRIVATE_REQUEST_FAILURE');
  req.end = body => {
    calls.at(-1).body = body;
    if (mode === 'end-throw') throw new Error('PRIVATE_END_FAILURE');
    if (mode === 'network-error') return req.emit('error', new Error('PRIVATE_SOCKET_FAILURE'));
    if (mode === 'stall') return;
    const response = new EventEmitter();
    response.statusCode = mode === 'redirect' ? 302 : 200;
    response.headers = { location: 'https://attacker.example', 'set-cookie': 'private=value' };
    response.resume = () => response.emit(mode === 'response-error' ? 'error' : 'end');
    callback(response);
  };
  return req;
};
syncBuiltinESMExports();
await import(${JSON.stringify(workerURL)});
`;

test('worker uses verified HTTPS and fixed regional hosts without redirects or retries', () => {
  run(`${transportSetup}
    for (const [index, region] of ['us', 'eu'].entries()) {
      mode = index ? 'redirect' : 'success';
      const body = JSON.stringify({ event: 'cookieguard_invoked' });
      port.emit('message', { id: index + 1, region, body });
      assert.equal(calls.length, index + 1);
      assert.equal(calls[index].body, body);
      assert.deepEqual(calls[index].options, {
        protocol: 'https:', hostname: region + '.i.posthog.com', port: 443,
        path: '/i/v0/e/', method: 'POST', rejectUnauthorized: true, agent: false,
        maxHeaderSize: 8192,
        headers: { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) },
      });
      assert.equal(calls[index].req.destroyed, true);
    }
    assert.deepEqual(acknowledgements, [1, 2]);
    for (const message of [null, {}, { id: 3, region: 'https://attacker.example', body: '{}' },
      { id: 3, region: 'us', body: 'a'.repeat(2049) }, { id: -1, region: 'eu', body: '{}' }]) {
      port.emit('message', message);
    }
    assert.equal(calls.length, 2);
  `);
});

test('worker acknowledges errors and a total deadline includes stalled DNS or sockets', () => {
  run(`${transportSetup}
    for (const [index, failure] of ['throw', 'end-throw', 'network-error', 'response-error'].entries()) {
      mode = failure;
      port.emit('message', { id: index + 1, region: 'us', body: '{}' });
    }
    assert.deepEqual(acknowledgements, [1, 2, 3, 4]);
    mode = 'stall';
    const started = Date.now();
    port.emit('message', { id: 5, region: 'us', body: '{}' });
    await new Promise(resolve => setTimeout(resolve, 650));
    assert.deepEqual(acknowledgements, [1, 2, 3, 4, 5]);
    assert.equal(calls.length, 5);
    assert.equal(calls.at(-1).req.destroyed, true);
    assert.ok(Date.now() - started < 1100);
  `);
});

test('worker serializes requests and bounds its queue at 16 events', () => {
  run(`${transportSetup}
    mode = 'stall';
    for (let id = 1; id <= 17; id++) port.emit('message', { id, region: 'us', body: '{}' });
    assert.equal(calls.length, 1);
    assert.deepEqual(acknowledgements, [17]);
    for (let index = 0; index < 16; index++) calls[index].req.emit('error', new Error('PRIVATE_FAILURE'));
    assert.equal(calls.length, 16);
    assert.equal(acknowledgements.length, 17);
    assert.ok(calls.every(call => call.req.destroyed));
  `);
});

test('real workers receive no parent environment or preloads and discard their output', () => {
  const fixture = `
    import { parentPort } from 'node:worker_threads';
    console.log('PRIVATE_WORKER_STDOUT');
    console.error('PRIVATE_WORKER_STDERR');
    parentPort.on('message', message => {
      parentPort.postMessage({ env: process.env, execArgv: process.execArgv });
      parentPort.postMessage(message.id);
    });
  `;
  run(`
    import assert from 'node:assert/strict';
    import { syncBuiltinESMExports } from 'node:module';
    import workerThreads from 'node:worker_threads';
    const OriginalWorker = workerThreads.Worker;
    let observed;
    workerThreads.Worker = class extends OriginalWorker {
      constructor(_url, options) {
        super(new URL(${JSON.stringify(`data:text/javascript,${encodeURIComponent(fixture)}`)}), options);
        this.on('message', message => { if (typeof message === 'object') observed = message; });
      }
    };
    syncBuiltinESMExports();
    const { reportUsage, flushUsage } = await import(${JSON.stringify(usageURL)});
    reportUsage(${JSON.stringify(base)});
    await flushUsage(1000);
    assert.deepEqual(observed, { env: {}, execArgv: [] });
  `, { COOKIEGUARD_USAGE_METRICS: '1', PRIVATE_SECRET: 'SENTINEL_ENV', HTTPS_PROXY: 'https://private.example' });
});

test('queued workers never keep a CLI alive and explicit flush stays bounded', () => {
  const fixture = `import { parentPort } from 'node:worker_threads'; parentPort.on('message', () => {});`;
  for (const flush of ['', 'await flushUsage(30);']) {
    const started = Date.now();
    run(`
      import { syncBuiltinESMExports } from 'node:module';
      import workerThreads from 'node:worker_threads';
      const OriginalWorker = workerThreads.Worker;
      workerThreads.Worker = class extends OriginalWorker {
        constructor(_url, options) {
          super(new URL(${JSON.stringify(`data:text/javascript,${encodeURIComponent(fixture)}`)}), options);
        }
      };
      syncBuiltinESMExports();
      const { reportUsage, flushUsage } = await import(${JSON.stringify(usageURL)});
      for (let index = 0; index < 20; index++) reportUsage(${JSON.stringify(base)});
      ${flush}
    `, { COOKIEGUARD_USAGE_METRICS: '1' }, 2000);
    assert.ok(Date.now() - started < 1500);
  }
});
