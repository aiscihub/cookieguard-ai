// Approach B's CI gate: every required check must have a PASS verdict file.
// Usage: node ci/security-gate.mjs sign-in-and-out [more ids]
import { readFileSync } from 'node:fs';

let code = 0;
for (const id of process.argv.slice(2)) {
  let result;
  try { result = JSON.parse(readFileSync(`security-results/${id}.json`, 'utf8')); }
  catch { result = { status: 'INCOMPLETE', missing: ['no verdict file: the check did not run'] }; }
  if (!['PASS', 'FAIL', 'INCOMPLETE'].includes(result.status)) result = { status: 'INCOMPLETE', missing: ['invalid verdict file'] };
  console.log(`[${result.status}] ${id} ${[...(result.failures ?? []), ...(result.missing ?? [])].join('; ')}`);
  if (result.status === 'FAIL') code = 1;
  else if (result.status === 'INCOMPLETE' && code === 0) code = 2;
}
if (process.argv.length < 3) { console.log('No checks required.'); code = 2; }
process.exit(code);
