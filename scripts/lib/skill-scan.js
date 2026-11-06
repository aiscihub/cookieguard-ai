// Pre-submission scan for a skill folder, modeled on the checks skill marketplaces such
// as Agensi publish: structure, file types, dangerous commands, secrets, environment
// harvesting, outbound URLs, obfuscation, prompt injection, and size. The marketplace's
// own detection rules are not public, so this is a conservative approximation.
import { readdir, readFile, stat } from 'node:fs/promises';
import { join, relative, extname, basename } from 'node:path';
import { checkSkill } from '../check-skill.js';

const TEXT_TYPES = new Set(['.md', '.json', '.txt', '']);
const ALLOWED_HOSTS = new Set(['github.com', 'raw.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org',
  'registry.npmjs.org', 'www.npmjs.com', 'agentskills.io', 'json-schema.org', '127.0.0.1', 'localhost']);
const PATTERNS = {
  dangerousCommand: /\brm\s+-[a-z]*r[a-z]*f|\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b|\bsudo\b|\bchmod\s+(-R\s+)?777\b|\bmkfs\b|\bdd\s+if=|:\(\)\s*\{/i,
  secret: /AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|\bsk-(ant-)?[A-Za-z0-9-]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|npm_[A-Za-z0-9]{36}|pypi-AgE[A-Za-z0-9_-]{20,}|COOKIEGUARD_DEMO_SENTINEL|CGBU_CANARY_[0-9a-f]|BENCH_SECRET_[0-9a-f]{8}/,
  promptInjection: /ignore (all |any )?(previous|prior|above) instructions|disregard (the |all )?(system|previous|prior)|(do not|don't|never) (tell|inform|notify) the user|without (telling|informing|asking) the user|hide (this|these|your) (action|actions|output|commands)|suppress (all |the )?output|exfiltrat/i,
  obfuscation: /[A-Za-z0-9+/=]{200,}|\beval\s*\(|\batob\s*\(|base64\s+(-d|--decode)/,
};

async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true, recursive: true });
  return entries.filter(entry => entry.isFile()).map(entry => join(entry.parentPath, entry.name)).sort();
}

export async function scanSkill(directory) {
  const failures = [], warnings = [], hosts = new Map();
  const list = await files(directory);
  let bytes = 0, envReads = 0;
  const { errors } = await checkSkill(directory);
  failures.push(...errors.map(error => `structure: ${error}`));
  if (list.length >= 1000) failures.push(`size: ${list.length} files`);
  for (const path of list) {
    const name = relative(directory, path);
    const info = await stat(path);
    bytes += info.size;
    if (basename(path).startsWith('.')) failures.push(`file type: hidden file ${name}`);
    if (!TEXT_TYPES.has(extname(path))) { failures.push(`file type: ${name}`); continue; }
    const buffer = await readFile(path);
    if (buffer.includes(0)) { failures.push(`file type: binary content in ${name}`); continue; }
    const text = buffer.toString('utf8');
    for (const [check, pattern] of Object.entries(PATTERNS)) {
      const match = pattern.exec(text);
      if (match) failures.push(`${check}: ${name}: ${match[0].slice(0, 60)}`);
    }
    envReads += (text.match(/process\.env\.|os\.environ|getenv\(/g) ?? []).length;
    for (const [, host] of text.matchAll(/https?:\/\/([a-z0-9.-]+)/gi)) {
      hosts.set(host.toLowerCase(), (hosts.get(host.toLowerCase()) ?? 0) + 1);
    }
  }
  for (const host of hosts.keys()) if (!ALLOWED_HOSTS.has(host)) warnings.push(`network: undisclosed host ${host}`);
  if (envReads > 5) warnings.push(`environment: ${envReads} environment-variable reads`);
  if (bytes >= 50 * 1024 * 1024) failures.push(`size: ${bytes} bytes`);
  return { files: list.map(path => relative(directory, path)), bytes, envReads, hosts: Object.fromEntries([...hosts].sort()), failures, warnings };
}
