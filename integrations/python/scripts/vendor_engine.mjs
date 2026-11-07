// Vendor the CookieGuard npm packages into the Python package as the local engine.
//
//   node scripts/vendor_engine.mjs             # pack this monorepo's workspaces (offline)
//   node scripts/vendor_engine.mjs --registry  # also require byte-identical contents
//                                              # to the published npm release
//   node scripts/vendor_engine.mjs --published # vendor the published npm release itself,
//                                              # for when main has unreleased engine changes
//
// Only the packed npm contents are copied: no hand-maintained fork of the
// engine. The manifest records per-file SHA-256 hashes, which the Python
// adapter verifies before starting Node.
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { join, relative, resolve, sep } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const exec = promisify(execFile);
const here = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(here, '../../..');
const engineDir = resolve(here, '../src/cookieguard/_node');
const packages = [
  { name: '@aiscihub/cookieguard-core', dir: 'cookieguard-core' },
  { name: '@aiscihub/cookieguard-playwright', dir: 'cookieguard-playwright' },
];
// The engine version this Browser Use release pins. Workspaces may be ahead of it.
const ENGINE_VERSION = '0.1.0';
const args = process.argv.slice(2);
if (args.length > 1 || args.some(arg => !['--registry', '--published'].includes(arg))) {
  throw new Error('Usage: node scripts/vendor_engine.mjs [--registry | --published]');
}
const verifyRegistry = args.includes('--registry');
const published = args.includes('--published');

async function files(directory) {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await files(path));
    else if (entry.isFile()) result.push(path);
    else throw new Error('Unexpected file type in package.');
  }
  return result.sort();
}

async function hashes(directory) {
  const result = {};
  for (const path of await files(directory)) {
    result[relative(directory, path).split(sep).join('/')] = createHash('sha256').update(await readFile(path)).digest('hex');
  }
  return result;
}

async function unpack(tarball, destination) {
  await mkdir(destination, { recursive: true });
  await exec('tar', ['-xzf', tarball, '-C', destination]);
  return join(destination, 'package');
}

const temporary = await mkdtemp(join(tmpdir(), 'cookieguard-browser-use-engine-'));
try {
  await mkdir(join(temporary, 'workspace'), { recursive: true });
  await mkdir(join(temporary, 'registry'), { recursive: true });
  let packed;
  if (published) {
    // npm verifies the registry's sha512 integrity while downloading.
    const { stdout } = await exec('npm', ['pack', ...packages.map(p => `${p.name}@${ENGINE_VERSION}`),
      '--registry=https://registry.npmjs.org', '--pack-destination', join(temporary, 'workspace'), '--json'], { cwd: temporary });
    packed = JSON.parse(stdout);
  } else {
    await exec(process.execPath, ['scripts/build.js'], { cwd: root });
    const { stdout } = await exec('npm', ['pack', ...packages.flatMap(p => ['--workspace', p.name]),
      '--pack-destination', join(temporary, 'workspace'), '--json'], { cwd: root });
    packed = JSON.parse(stdout);
  }
  const manifest = { schemaVersion: 1,
    source: published ? 'npm-registry' : verifyRegistry ? 'workspace-verified-against-npm-registry' : 'workspace', packages: [] };
  const modules = join(engineDir, 'node_modules');
  await rm(modules, { recursive: true, force: true });
  for (const pkg of packages) {
    const result = packed.find(entry => entry.name === pkg.name);
    // The pin applies to the published engine. Workspace packs carry the workspace
    // version, which may be ahead of the pin while new engine features are developed.
    const expected = published ? ENGINE_VERSION
      : JSON.parse(await readFile(join(root, 'packages', pkg.dir.replace(/^cookieguard-/, ''), 'package.json'), 'utf8')).version;
    if (!result || result.version !== expected) throw new Error('Unexpected package version.');
    const contents = await unpack(join(temporary, 'workspace', result.filename), join(temporary, 'workspace', pkg.dir));
    const fileHashes = await hashes(contents);
    let registryIntegrity = published ? result.integrity : null;
    if (verifyRegistry) {
      // npm verifies the registry's sha512 integrity while downloading.
      const download = await exec('npm', ['pack', `${pkg.name}@${result.version}`, '--registry=https://registry.npmjs.org',
        '--pack-destination', join(temporary, 'registry'), '--json'], { cwd: temporary });
      const [published] = JSON.parse(download.stdout);
      const registryContents = await unpack(join(temporary, 'registry', published.filename), join(temporary, 'registry', pkg.dir));
      if (JSON.stringify(await hashes(registryContents)) !== JSON.stringify(fileHashes)) {
        throw new Error('Workspace package contents differ from the published npm release.');
      }
      registryIntegrity = published.integrity;
    }
    await cp(contents, join(modules, '@aiscihub', pkg.dir), { recursive: true });
    manifest.packages.push({ name: pkg.name, version: result.version, registryIntegrity,
      files: Object.fromEntries(Object.entries(fileHashes).map(([path, hash]) => [`node_modules/@aiscihub/${pkg.dir}/${path}`, hash])) });
  }
  const bridge = await readFile(join(engineDir, 'bridge.mjs'));
  manifest.bridge = { 'bridge.mjs': createHash('sha256').update(bridge).digest('hex') };
  await writeFile(join(engineDir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  process.stdout.write(`Vendored ${packages.map(p => p.name).join(', ')} (${manifest.source}).\n`);
} finally {
  await rm(temporary, { recursive: true, force: true });
}
