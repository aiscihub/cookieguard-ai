// Checks skills/*/SKILL.md against the Agent Skills specification
// (https://agentskills.io/specification): frontmatter fields and limits, the
// name/directory match, body size, and that every relative link resolves.
// The frontmatter parser is deliberately strict: only `key: value` lines and
// one level of `metadata` string entries are accepted.
import { readdir, readFile, stat } from 'node:fs/promises';
import { join, dirname, resolve, relative } from 'node:path';

const ALLOWED = new Set(['name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools']);

export function parseFrontmatter(text) {
  const match = /^---\n([\s\S]*?)\n---\n/.exec(text);
  if (!match) throw new Error('SKILL.md must start with YAML frontmatter delimited by ---');
  const fields = {};
  let map = null;
  for (const line of match[1].split('\n')) {
    const nested = /^ {2}([A-Za-z0-9_.-]+): (.+)$/.exec(line);
    if (nested && map) { map[nested[1]] = nested[2].replace(/^"(.*)"$/, '$1'); continue; }
    const top = /^([a-z-]+):(?: (.*))?$/.exec(line);
    if (!top) throw new Error(`Unsupported frontmatter line: ${line.slice(0, 40)}`);
    if (Object.hasOwn(fields, top[1])) throw new Error(`Duplicate field: ${top[1]}`);
    if (top[2] === undefined) { map = fields[top[1]] = {}; continue; }
    map = null;
    fields[top[1]] = top[2].replace(/^"(.*)"$/, '$1');
  }
  return { fields, body: text.slice(match[0].length) };
}

export async function checkSkill(directory) {
  const errors = [];
  const text = await readFile(join(directory, 'SKILL.md'), 'utf8');
  const { fields, body } = parseFrontmatter(text);
  for (const key of Object.keys(fields)) if (!ALLOWED.has(key)) errors.push(`Unknown field: ${key}`);
  const { name, description, compatibility, metadata } = fields;
  if (typeof name !== 'string' || name.length < 1 || name.length > 64 || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(name)) {
    errors.push('name: 1-64 lowercase letters, digits, and single hyphens, not at either end');
  }
  if (name !== directory.split('/').pop()) errors.push('name must match the parent directory name');
  if (typeof description !== 'string' || !description.trim() || description.length > 1024) errors.push('description: 1-1024 characters');
  if (compatibility !== undefined && (typeof compatibility !== 'string' || !compatibility || compatibility.length > 500)) errors.push('compatibility: 1-500 characters');
  if (metadata !== undefined && (typeof metadata !== 'object' || Object.values(metadata).some(v => typeof v !== 'string'))) errors.push('metadata: string-to-string map');
  if (body.split('\n').length > 500) errors.push('Body should stay under 500 lines');
  // Rough token estimate: the spec recommends under 5000 tokens for the body.
  if (body.length / 4 > 5000) errors.push('Body should stay under about 5000 tokens');
  // Every relative link in every Markdown file must stay inside the skill and resolve,
  // so the folder works when distributed on its own.
  const documents = (await readdir(directory, { recursive: true, withFileTypes: true }))
    .filter(entry => entry.isFile() && entry.name.endsWith('.md')).map(entry => join(entry.parentPath, entry.name));
  for (const document of documents) {
    const content = document.endsWith('SKILL.md') ? body : await readFile(document, 'utf8');
    for (const [, target] of content.matchAll(/\]\(([^)#\s]+)(?:#[^)]*)?\)/g)) {
      if (/^[a-z]+:/i.test(target)) continue;
      const path = resolve(dirname(document), target);
      const label = document.endsWith('SKILL.md') ? target : `${relative(directory, document)} -> ${target}`;
      if (relative(directory, path).startsWith('..')) errors.push(`Link leaves the skill directory: ${label}`);
      else await stat(path).catch(() => errors.push(`Broken link: ${label}`));
    }
  }
  return { name, description, errors };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const root = resolve(dirname(new URL(import.meta.url).pathname), '../skills');
  let failed = false;
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const { name, description, errors } = await checkSkill(join(root, entry.name));
    failed ||= errors.length > 0;
    process.stdout.write(errors.length ? `${entry.name}: ${errors.join('; ')}\n` : `${name}: valid (${description.length}-character description)\n`);
  }
  process.exitCode = failed ? 1 : 0;
}
