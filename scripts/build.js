import { mkdir, copyFile, readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const packages = await readdir(resolve(root, 'packages'));
await mkdir(resolve(root, 'packages/core/vendor'), { recursive: true });
await copyFile(resolve(root, 'extension-standalone/engine.js'), resolve(root, 'packages/core/vendor/engine.cjs'));
for (const name of packages) {
  await copyFile(resolve(root, 'LICENSE'), resolve(root, `packages/${name}/LICENSE`));
  const manifest = JSON.parse(await readFile(resolve(root, `packages/${name}/package.json`), 'utf8'));
  for (const entry of Object.values(manifest.exports ?? {})) {
    await import(new URL(`../packages/${name}/${entry.import}`, import.meta.url));
  }
}
process.stdout.write('Build: canonical engine, package licenses, and exports verified.\n');
