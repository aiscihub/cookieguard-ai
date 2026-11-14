import { request } from 'node:https';
import { parentPort } from 'node:worker_threads';

const DEADLINE_MS = 500;
const MAX_PENDING = 16;
const queue = [];
let busy = false;

function deliver({ id, region, body }) {
  let req;
  let finished = false;
  let timer;
  const done = () => {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    try { req?.destroy(); } catch { /* Ignore transport failure. */ }
    try { parentPort.postMessage(id); } catch { /* Parent may have exited. */ }
    busy = false;
    next();
  };
  timer = setTimeout(done, DEADLINE_MS);
  try {
    req = request({
      protocol: 'https:',
      hostname: region === 'eu' ? 'eu.i.posthog.com' : 'us.i.posthog.com',
      port: 443,
      path: '/i/v0/e/',
      method: 'POST',
      rejectUnauthorized: true,
      agent: false,
      maxHeaderSize: 8192,
      headers: { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) },
    }, response => {
      response.on('error', done);
      response.once('end', done);
      response.once('aborted', done);
      response.resume();
    });
    req.on('error', done);
    req.end(body);
  } catch { done(); }
}

function next() {
  if (busy || queue.length === 0) return;
  busy = true;
  deliver(queue.shift());
}

parentPort?.on('message', message => {
  if (!message || typeof message !== 'object') return;
  const { id, region, body } = message;
  if (!Number.isSafeInteger(id) || id < 1 || (region !== 'us' && region !== 'eu') || typeof body !== 'string' || body.length > 2048) return;
  if (queue.length + Number(busy) >= MAX_PENDING) {
    parentPort.postMessage(id);
    return;
  }
  queue.push({ id, region, body });
  next();
});
