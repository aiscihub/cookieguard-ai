import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

// These are process controls, never included in a release's payload.
process.env.COOKIEGUARD_USAGE_METRICS = '0';
process.env.DO_NOT_TRACK = '1';
process.env.ORT_DISABLE_TELEMETRY = '1';
export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const sha = input => createHash('sha256').update(input).digest('hex');
export const readJSON = path => JSON.parse(readFileSync(path, 'utf8'));
export function writeAtomic(path, text) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path + '.tmp', text, { mode: 0o600 });
  renameSync(path + '.tmp', path);
}
export const writeJSON = (path, data) => writeAtomic(path, JSON.stringify(data, null, 2) + '\n');
export function args(options) { return parseArgs({ options }).values; }
export function monthSeed(month) {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) throw new Error('invalid-month');
  return Number(month.replace('-', ''));
}
export function normalizeName(input) {
  return String(input).trim().toLowerCase().split(/([_.-])/).map(piece => {
    if (/^[_.-]$/.test(piece)) return piece;
    const mixed = piece.length >= 6 && /[a-z]/.test(piece) && /[0-9]/.test(piece);
    const hex = piece.length >= 8 && /^[0-9a-f]+$/.test(piece) && /[a-f]/.test(piece);
    return mixed || hex ? '#' : piece;
  }).join('').replace(/\d+/g, '0');
}
export function die() {
  // Do not print exceptions: network/browser errors can embed cookies or URLs.
  process.stderr.write('Refresh stopped; inspect the sanitized status receipt.\n');
  process.exitCode = 1;
}
