import { readFile, writeFile, mkdir } from 'node:fs/promises';

// Reviewed license expressions in the locked dependency graph. A new expression
// requires review rather than silently widening the public-beta release gate.
const reviewed = new Set(['MIT', 'Apache-2.0', 'ISC', 'BSD-2-Clause', 'BSD-3-Clause', 'BlueOak-1.0.0', '(MIT OR CC0-1.0)']);
const lock = JSON.parse(await readFile('package-lock.json', 'utf8'));
const inventory = Object.entries(lock.packages).filter(([, pkg]) => !pkg.link).map(([path, pkg]) => ({
  package: path || lock.name, version: pkg.version, license: pkg.license,
}));
if (inventory.some(pkg => !reviewed.has(pkg.license))) {
  throw new Error('Dependency license inventory changed or is incomplete; maintainer review is required.');
}
await mkdir('artifacts', { recursive: true });
await writeFile('artifacts/dependency-licenses.json', JSON.stringify({ reviewedExpressions: [...reviewed].sort(), packages: inventory }, null, 2) + '\n');
process.stdout.write(`License gate: ${inventory.length} locked package entries use reviewed license expressions.\n`);
