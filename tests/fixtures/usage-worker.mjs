import workerThreads from 'node:worker_threads';
import { syncBuiltinESMExports } from 'node:module';
import { EventEmitter } from 'node:events';
import { appendFileSync } from 'node:fs';

const originalWorker = workerThreads.Worker;
export const messages = [];
export const workers = [];
export const transport = { mode: 'success' };

class UsageWorker extends EventEmitter {
  constructor() { super(); workers.push(this); }
  unref() {}
  postMessage(message) {
    messages.push({ worker: this, message });
    if (process.env.CG_TEST_USAGE_CAPTURE) appendFileSync(process.env.CG_TEST_USAGE_CAPTURE, message.body + '\n');
    if (transport.mode === 'throw' || process.env.CG_TEST_USAGE_FAILURE === '1') throw new Error('PRIVATE_TRANSPORT_ERROR_CANARY');
    if (transport.mode === 'success') void Promise.resolve().then(() => this.emit('message', message.id));
  }
  async terminate() {}
}

workerThreads.Worker = UsageWorker;
syncBuiltinESMExports();

export function acknowledgeMessages() {
  for (const { worker, message } of messages) worker.emit('message', message.id);
}

export function restoreWorker() {
  workerThreads.Worker = originalWorker;
  syncBuiltinESMExports();
}
