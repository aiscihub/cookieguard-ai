// Packages skills/cookieguard-browser-auth-security as a reproducible ZIP for skill
// marketplaces (for example Agensi): one top-level folder named after the skill,
// sorted entries, fixed timestamps, DEFLATE via node:zlib. Refuses to package a
// skill that fails the pre-submission scan.
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { deflateRawSync, crc32 } from 'node:zlib';
import { scanSkill } from './lib/skill-scan.js';

const NAME = 'cookieguard-browser-auth-security';
const root = resolve(new URL('..', import.meta.url).pathname);
const source = join(root, 'skills', NAME);
const out = resolve(process.argv[2] ?? join(root, 'artifacts', 'skill'));
const DOS_TIME = 0, DOS_DATE = (2026 - 1980) << 9 | 1 << 5 | 1; // 2026-01-01 00:00

export async function buildZip(directory, prefix) {
  const scan = await scanSkill(directory);
  if (scan.failures.length) throw new Error(`Skill scan failed:\n${scan.failures.join('\n')}`);
  const locals = [], centrals = [];
  let offset = 0;
  for (const file of scan.files) {
    const name = Buffer.from(`${prefix}/${file.split('\\').join('/')}`);
    const data = await readFile(join(directory, file));
    const packed = deflateRawSync(data, { level: 9 });
    const crc = crc32(data);
    const header = Buffer.alloc(30);
    header.writeUInt32LE(0x04034b50, 0); header.writeUInt16LE(20, 4); header.writeUInt16LE(0x0800, 6);
    header.writeUInt16LE(8, 8); header.writeUInt16LE(DOS_TIME, 10); header.writeUInt16LE(DOS_DATE, 12);
    header.writeUInt32LE(crc, 14); header.writeUInt32LE(packed.length, 18); header.writeUInt32LE(data.length, 22);
    header.writeUInt16LE(name.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0); central.writeUInt16LE(0x0314, 4); central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0800, 8); central.writeUInt16LE(8, 10); central.writeUInt16LE(DOS_TIME, 12);
    central.writeUInt16LE(DOS_DATE, 14); central.writeUInt32LE(crc, 16); central.writeUInt32LE(packed.length, 20);
    central.writeUInt32LE(data.length, 24); central.writeUInt16LE(name.length, 28);
    central.writeUInt32LE((0o100644 << 16) >>> 0, 38); central.writeUInt32LE(offset, 42);
    locals.push(header, name, packed);
    centrals.push(central, name);
    offset += header.length + name.length + packed.length;
  }
  const directoryBytes = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(scan.files.length, 8); end.writeUInt16LE(scan.files.length, 10);
  end.writeUInt32LE(directoryBytes.length, 12); end.writeUInt32LE(offset, 16);
  return { zip: Buffer.concat([...locals, directoryBytes, end]), scan };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { zip, scan } = await buildZip(source, NAME);
  await mkdir(out, { recursive: true });
  const path = join(out, `${NAME}.zip`);
  await writeFile(path, zip);
  const sha256 = createHash('sha256').update(zip).digest('hex');
  await writeFile(join(out, `${NAME}.zip.sha256`), `${sha256}  ${NAME}.zip\n`);
  process.stdout.write(`${path}\n${scan.files.length} files, ${zip.length} bytes, sha256 ${sha256}\n`
    + `Hosts: ${Object.keys(scan.hosts).join(', ')}\n`
    + (scan.warnings.length ? `Warnings:\n  ${scan.warnings.join('\n  ')}\n` : 'Warnings: none\n'));
}
