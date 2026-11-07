// Release gate: every operation the capabilities document advertises must be
// marked released, so published instructions never point at main-only features.
import { capabilities } from 'cookieguard-ci';

const pending = capabilities().operations.filter(operation => operation.availability !== 'released');
if (pending.length) {
  process.stderr.write(`Unreleased operations: ${pending.map(operation => operation.id).join(', ')}. Publish them and mark them released first.\n`);
  process.exitCode = 1;
} else process.stdout.write('All advertised operations are released.\n');
