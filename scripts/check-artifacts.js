import { readdir, readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { assertNoSentinels } from './lib/leakage.js';

let checked = 0;
async function inspect(directory) {
  let entries;
  try { entries = await readdir(directory, { withFileTypes: true }); }
  catch (error) { if (error.code === 'ENOENT') return; throw error; }
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await inspect(path);
    else if (entry.isFile()) {
      const contents = await readFile(path);
      checked++;
      assertNoSentinels(contents);
    }
  }
}
for (const directory of ['artifacts', 'test-results', 'examples/playwright/test-results']) await inspect(directory);
for (const path of process.argv.slice(2)) {
  // Explicit Action output paths must exist; a missing artifact is a failed gate.
  if ((await stat(path)).isDirectory()) await inspect(path);
  else { assertNoSentinels(await readFile(path)); checked++; }
}
if (!checked) throw new Error('No artifacts found to check. Run benchmark and tests first.');
process.stdout.write(`Leakage check: ${checked} generated files inspected; no sentinel values found.\n`);
