// Stage only durable, verified shard artifacts after success, failure, or cancellation.
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { args, die, readJSON, sha } from './common.mjs';
import { structural } from './privacy.mjs';

export function artifactFiles(files, outcome, frame, frameSha256, shard) {
  if (!files.has('started.json')) return new Map();
  const read = name => JSON.parse(files.get(name));
  const output = new Map();
  const json = (name, data) => output.set(name, JSON.stringify(data) + '\n');
  const sites = frame.frame.filter(s => s.shard === shard).map(s => s.siteId);
  const ledger = files.has('visited.json') ? read('visited.json') : { schemaVersion: 1, shard, frameSha256, siteIds: [] };
  if (ledger.shard !== shard || ledger.frameSha256 !== frameSha256 || !Array.isArray(ledger.siteIds) ||
      JSON.stringify(ledger.siteIds) !== JSON.stringify(sites.slice(0, ledger.siteIds.length))) throw new Error('invalid-ledger');
  json('started.json', { shard, month: frame.month });
  json('visited.json', { schemaVersion: 1, shard, frameSha256, siteIds: ledger.siteIds });
  const receipt = files.has('receipt.json') ? read('receipt.json') : null;
  if (receipt?.status === 'failed-closed' || outcome === 'failure') {
    const reasonCode = ['privacy-rejected', 'browser-error', 'io-error'].includes(receipt?.reasonCode) ? receipt.reasonCode : 'io-error';
    json('receipt.json', { schemaVersion: 1, shard, of: frame.shards, month: frame.month, frameSha256,
      status: 'failed-closed', reasonCode, privacy: { passed: false },
      ...(receipt?.resume && structural(receipt.resume) ? { resume: receipt.resume,
        newPart: { attempted: receipt.newPart.attempted, rows: 0, privacy: { passed: false } } } : {}) });
  } else if (outcome === 'success') {
    if (!receipt || !structural(receipt) || !['passed', 'structuralPassed', 'crossScanPassed'].every(k => receipt.privacy[k] === true) ||
        receipt.rowsSha256 !== sha(files.get('cookies.jsonl')) || receipt.attemptsSha256 !== sha(files.get('attempts.json'))) {
      throw new Error('invalid-final-shard');
    }
    // Keep the original ledger bytes: the final receipt hashes them.
    output.set('visited.json', files.get('visited.json'));
    for (const name of ['receipt.json', 'cookies.jsonl', 'attempts.json']) output.set(name, files.get(name));
  } else if (outcome === 'cancelled' && files.has('checkpoint.json')) {
    const checkpoint = read('checkpoint.json');
    if (!structural(checkpoint) || checkpoint.frameSha256 !== frameSha256 || checkpoint.shard !== shard ||
        !['passed', 'structuralPassed', 'crossScanPassed'].every(k => checkpoint.privacy[k] === true) ||
        checkpoint.attempts.length > ledger.siteIds.length) throw new Error('invalid-checkpoint');
    output.set('checkpoint.json', files.get('checkpoint.json'));
  }
  return output;
}

export function main() {
  const a = args({ source: { type: 'string' }, out: { type: 'string' }, outcome: { type: 'string' },
    shard: { type: 'string' }, frame: { type: 'string', default: 'refresh/.work/run/frame.json' } });
  if (!existsSync(a.source) || !existsSync(a.frame)) return;
  const files = new Map(readdirSync(a.source).filter(name => ['started.json', 'visited.json', 'receipt.json',
    'checkpoint.json', 'attempts.json', 'cookies.jsonl'].includes(name)).map(name => [name, readFileSync(resolve(a.source, name))]));
  const output = artifactFiles(files, a.outcome, readJSON(a.frame), sha(readFileSync(a.frame)), Number(a.shard));
  if (!output.size) return;
  if (existsSync(a.out)) throw new Error('artifact-already-exists');
  mkdirSync(a.out, { recursive: true });
  for (const [name, data] of output) writeFileSync(resolve(a.out, name), data, { mode: 0o600 });
}
if (import.meta.url === pathToFileURL(process.argv[1] || '').href) Promise.resolve().then(main).catch(die);
