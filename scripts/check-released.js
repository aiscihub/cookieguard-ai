// Release gate: a release must not advertise operations that exist only on main.
// CI runs the release gate on every change, so this applies only once a release is
// being prepared, i.e. when the package version differs from the published one
// recorded in packages/cli/src/capabilities.js.
import { readFile } from 'node:fs/promises';
import { capabilities } from 'cookieguard-ci';

const { version } = JSON.parse(await readFile(new URL('../packages/cli/package.json', import.meta.url), 'utf8'));
const document = capabilities();
const published = document.integrations.find(integration => integration.id === 'cli').version;
const pending = document.operations.filter(operation => operation.availability !== 'released').map(operation => operation.id);

if (version === published) {
  process.stdout.write(`Development build of published ${version}; unreleased operations: ${pending.join(', ') || 'none'}.\n`);
} else if (pending.length) {
  process.stderr.write(`Preparing ${version}, but these operations are still unreleased: ${pending.join(', ')}. `
    + 'Mark them released, with the published versions, before publishing.\n');
  process.exitCode = 1;
} else process.stdout.write(`Preparing ${version}; all advertised operations are released.\n`);
