// CookieGuard for Browser Use: local evaluation bridge.
//
// The Python adapter streams value-bearing CDP evidence to this process over a
// stdin pipe (never argv, files, or the network). This bridge feeds it to the
// published CookieGuard collector and policy engine without modification, then
// returns only sanitized core reports on stdout. It never logs or echoes input.
// Python runs it with Node's permission model: read-only access to this
// directory, and no writes, child processes, workers, or addons.
import { EventEmitter } from 'node:events';
import { setImmediate as tick } from 'node:timers/promises';
import { startCookieAudit } from '@aiscihub/cookieguard-playwright';
import { AuditError, safeError, evaluateCookiePolicy, formatJson, formatText, exitCode } from '@aiscihub/cookieguard-core';

const PROTOCOL = 1;
const MAX_LINE = 4 * 1024 * 1024;
const MAX_MESSAGES = 20000;
const MAX_LINES_PER_RESPONSE = 200;
const MAX_STORE_COOKIES = 1000;
const SAME_SITE = Object.freeze({ strict: 'Strict', lax: 'Lax', none: 'None' });

// Structural stand-in for a Playwright BrowserContext. The collector only uses
// on/off('response'|'close') and cookies(); CDP evidence is replayed through them.
class EvidenceContext extends EventEmitter {
  #store = null;
  setStore(cookies) { this.#store = cookies; }
  async cookies() {
    if (!this.#store) throw new AuditError('COLLECT');
    return this.#store;
  }
}

const isText = (value, max) => typeof value === 'string' && value.length <= max;

function responseOf(message) {
  if (!isText(message.url, 8192) || !Array.isArray(message.setCookie)
    || message.setCookie.length > MAX_LINES_PER_RESPONSE
    || message.setCookie.some(line => typeof line !== 'string')) throw new AuditError('INPUT');
  const headers = message.setCookie.map(value => ({ name: 'set-cookie', value }));
  const url = message.url;
  const fromServiceWorker = message.fromServiceWorker === true;
  return { url: () => url, headersArray: async () => headers, fromServiceWorker: () => fromServiceWorker };
}

// Allowlist CDP Storage.getCookies fields into the Playwright cookie shape.
function storeOf(cookies) {
  if (cookies === null) return null;
  if (!Array.isArray(cookies) || cookies.length > MAX_STORE_COOKIES) throw new AuditError('INPUT');
  return cookies.map(cookie => {
    if (!cookie || typeof cookie !== 'object' || !isText(cookie.name, 256) || !cookie.name
      || !isText(cookie.value ?? '', 16384) || !isText(cookie.domain, 1024) || !isText(cookie.path, 1024)
      || !Number.isFinite(cookie.expires) || typeof cookie.httpOnly !== 'boolean'
      || typeof cookie.secure !== 'boolean') throw new AuditError('INPUT');
    const sameSite = typeof cookie.sameSite === 'string' ? SAME_SITE[cookie.sameSite.toLowerCase()] : undefined;
    return {
      name: cookie.name, value: cookie.value ?? '', domain: cookie.domain, path: cookie.path,
      expires: cookie.expires, httpOnly: cookie.httpOnly, secure: cookie.secure,
      ...(sameSite ? { sameSite } : {}), ...(cookie.partitioned === true ? { partitionKey: 'partitioned' } : {}),
    };
  });
}

function reportMessage(id, report, extra = {}) {
  return { type: 'report', id, exitCode: exitCode(report), report: JSON.parse(formatJson(report)), text: formatText(report), ...extra };
}

const state = { context: null, collector: null, config: null, requireHeaderEvidence: false, dead: false, finished: false };
let queue = Promise.resolve();
let received = 0;
let buffer = '';

function send(message) { process.stdout.write(JSON.stringify(message) + '\n'); }

function fatal(error) {
  if (state.dead) return;
  state.dead = true;
  state.collector?.dispose();
  buffer = '';
  process.stdin.pause();
  // Only a fixed AuditError code leaves the process; never input or messages.
  process.stdout.write(JSON.stringify({ type: 'error', code: safeError(error).code, fatal: true }) + '\n',
    () => process.exit(2));
}

function started() {
  if (!state.collector || state.finished) throw new AuditError('CONFIG');
}

async function handle(message) {
  if (!message || typeof message !== 'object' || message.protocol !== PROTOCOL) throw new AuditError('INPUT');
  switch (message.type) {
    case 'start': {
      if (state.collector) throw new AuditError('CONFIG');
      const keys = ['protocol', 'type', 'origins', 'policy', 'timeoutMs', 'requireHeaderEvidence'];
      if (Object.keys(message).some(key => !keys.includes(key)) || typeof message.requireHeaderEvidence !== 'boolean') throw new AuditError('CONFIG');
      state.config = { origins: message.origins, policy: message.policy ?? {}, timeoutMs: message.timeoutMs };
      state.requireHeaderEvidence = message.requireHeaderEvidence;
      state.context = new EvidenceContext();
      // The collector validates origins, policy, and limits with core rules.
      state.collector = startCookieAudit(state.context, state.config);
      send({ type: 'ready', protocol: PROTOCOL });
      return;
    }
    case 'response':
      started();
      state.context.emit('response', responseOf(message));
      // Let the collector finish its asynchronous header read before the next
      // event, so its pending-read bound measures real concurrency.
      await tick();
      return;
    case 'close':
      started();
      state.context.emit('close');
      return;
    case 'snapshot': {
      started();
      // Provisional store-only evaluation in a separate collector. The live
      // header collection is unaffected and cannot be stopped from here.
      const context = new EvidenceContext();
      context.setStore(storeOf(message.cookies));
      const collector = startCookieAudit(context, { origins: state.config.origins, policy: state.config.policy, timeoutMs: 10000 });
      try { send(reportMessage(message.id, await collector.evaluate())); }
      finally { collector.dispose(); }
      return;
    }
    case 'finish': {
      started();
      state.context.setStore(storeOf(message.cookies));
      const collection = await state.collector.collect();
      const options = { ...collection, ...(message.baseline === undefined ? {} : { baseline: message.baseline }) };
      let report = evaluateCookiePolicy(collection.observations, state.config.policy, options);
      let headerEvidenceMissing = [];
      if (state.requireHeaderEvidence && report.status === 'passed') {
        // Store state cannot establish what the server declared. When the
        // developer requires declarations, an otherwise passing audit without a
        // Set-Cookie observation for each expected cookie is incomplete.
        const expected = [...new Set([...report.policy.authCookies, ...report.policy.authEvidence.map(e => e.name)])];
        headerEvidenceMissing = expected.filter(name => !collection.observations
          .some(observation => observation.name === name && observation.source === 'header' && !observation.deleted));
        if (headerEvidenceMissing.length) report = evaluateCookiePolicy(collection.observations, state.config.policy, { ...options, complete: false });
      }
      state.finished = true;
      send(reportMessage(message.id, report, { headerEvidenceMissing }));
      return;
    }
    default:
      throw new AuditError('INPUT');
  }
}

async function dispatch(line) {
  if (state.dead) return;
  let message;
  try { message = JSON.parse(line); } catch { fatal(new AuditError('INPUT')); return; }
  try { await handle(message); }
  catch (error) {
    if (message?.type === 'snapshot' && !state.dead) send({ type: 'error', id: message.id, code: safeError(error).code, fatal: false });
    else fatal(error);
  }
}

process.on('uncaughtException', () => fatal(new AuditError('INPUT')));
process.on('unhandledRejection', () => fatal(new AuditError('INPUT')));
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  if (state.dead) return;
  buffer += chunk;
  let index;
  while ((index = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, index);
    buffer = buffer.slice(index + 1);
    if (!line.trim()) continue;
    if (++received > MAX_MESSAGES) { fatal(new AuditError('INPUT')); return; }
    queue = queue.then(() => dispatch(line));
  }
  if (buffer.length > MAX_LINE) { buffer = ''; fatal(new AuditError('INPUT')); }
});
process.stdin.on('end', () => {
  void queue.then(() => { buffer = ''; state.collector?.dispose(); });
});
