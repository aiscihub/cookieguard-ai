import { randomUUID } from 'node:crypto';
import { Worker } from 'node:worker_threads';
import { PROJECT_TOKEN, REGION } from './usage-config.js';

const PACKAGES = Object.freeze({
  cli: 'cookieguard-ci',
  playwright: '@aiscihub/cookieguard-playwright',
  mcp: '@aiscihub/cookieguard-mcp',
  'github-action': 'cookieguard-ci',
  core: '@aiscihub/cookieguard-core',
});
const MAX_PENDING = 16;
const MAX_FLUSH_MS = 1000;
const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;
const pending = new Set();
const waiters = new Set();
let worker;
let sequence = 0;

function notifyWaiters() {
  for (const notify of waiters) notify();
}

function failed(instance) {
  if (worker !== instance) return;
  worker = undefined;
  pending.clear();
  notifyWaiters();
  try { instance.terminate().catch(() => {}); } catch { /* Best effort only. */ }
}

function getWorker() {
  if (worker) return worker;
  const instance = new Worker(new URL('./usage-worker.js', import.meta.url), {
    // Do not inherit credentials, preload scripts, proxy settings, or TLS overrides.
    env: {}, execArgv: [], stdout: true, stderr: true,
  });
  worker = instance;
  // Discard captured stdio without reading: reads can ref an internal port
  // after unref(), keeping a short-lived CLI alive. This worker never logs.
  instance.stdout?.destroy();
  instance.stderr?.destroy();
  instance.on('message', id => {
    if (worker !== instance) return;
    pending.delete(id);
    notifyWaiters();
  });
  instance.on('error', () => failed(instance));
  instance.on('exit', () => failed(instance));
  // Install listeners before unref: adding a message listener can ref the port.
  instance.unref();
  return instance;
}

/** Report one invocation unless opted out. All failures are silently ignored. */
export function reportUsage(options) {
  try {
    if (!options || typeof options !== 'object') return;
    const enabled = options.enabled;
    const setting = process.env.COOKIEGUARD_USAGE_METRICS;
    if (enabled === false || setting === '0' || process.env.DO_NOT_TRACK === '1') return;
    if (enabled !== undefined && enabled !== null && typeof enabled !== 'boolean') return;
    if (enabled !== true && setting !== undefined && setting !== '1') return;
    if (pending.size >= MAX_PENDING) return;

    const integration = options.integration;
    const packageName = options.package;
    const version = options.version;
    if (typeof integration !== 'string' || !Object.hasOwn(PACKAGES, integration) || PACKAGES[integration] !== packageName) return;
    if (typeof version !== 'string' || version.length > 64 || version !== version.trim() || !SEMVER.test(version)) return;
    const token = process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN ?? PROJECT_TOKEN;
    const region = process.env.COOKIEGUARD_POSTHOG_REGION ?? REGION;
    if (typeof token !== 'string' || token.length > 204 || token !== token.trim() || !/^phc_[A-Za-z0-9_-]{20,200}$/.test(token)) return;
    if (region !== 'us' && region !== 'eu') return;

    const body = JSON.stringify({
      api_key: token,
      event: 'cookieguard_invoked',
      distinct_id: randomUUID(),
      properties: {
        $process_person_profile: false,
        $geoip_disable: true,
        $ip: '0.0.0.0',
        schema_version: 1,
        package: packageName,
        package_version: version,
        integration,
      },
    });
    const instance = getWorker();
    const id = ++sequence;
    pending.add(id);
    try { instance.postMessage({ id, region, body }); } catch { failed(instance); }
  } catch { /* Telemetry must never affect the caller. */ }
}

/** Wait at most timeoutMs (capped at 1000 ms) for already queued events. */
export function flushUsage(timeoutMs = 250) {
  try {
    if (pending.size === 0) return Promise.resolve();
    const timeout = typeof timeoutMs === 'number' && Number.isFinite(timeoutMs)
      ? Math.max(0, Math.min(MAX_FLUSH_MS, timeoutMs)) : 250;
    if (timeout === 0) return Promise.resolve();
    const snapshot = new Set(pending);
    return new Promise(resolve => {
      let timer;
      const done = () => {
        clearTimeout(timer);
        waiters.delete(check);
        resolve();
      };
      const check = () => {
        if ([...snapshot].every(id => !pending.has(id))) done();
      };
      waiters.add(check);
      // Only an explicit flush keeps the process alive, and only for this bound.
      timer = setTimeout(done, timeout);
      check();
    }).catch(() => {});
  } catch { return Promise.resolve(); }
}
