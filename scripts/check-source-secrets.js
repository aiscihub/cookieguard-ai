import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile, stat } from 'node:fs/promises';

// High-confidence credential formats only. This complements the sentinel tests;
// it does not certify absence of every possible secret or scan ignored files.
const patterns = [
  /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/,
  /\bgh[pousr]_[A-Za-z0-9]{36,}\b/,
  /\bgithub_pat_[A-Za-z0-9_]{50,}\b/,
  /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/,
  /\bxox[baprs]-[0-9A-Za-z-]{20,}\b/,
];
const { stdout } = await promisify(execFile)('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], { maxBuffer: 4 * 1024 * 1024 });
let checked = 0;
for (const path of stdout.split('\0').filter(Boolean)) {
  let info;
  try { info = await stat(path); } catch (error) { if (error.code === 'ENOENT') continue; throw error; }
  if (!info.isFile()) continue;
  const data = await readFile(path);
  if (patterns.some(pattern => pattern.test(data.toString('utf8')))) {
    throw new Error('Potential credential found in source. Match details withheld; review before release.');
  }
  checked++;
}
process.stdout.write(`Source credential check: ${checked} files checked; no supported credential patterns found.\n`);
