import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { checkSkill } from '../scripts/check-skill.js';

const write = async (root, name, frontmatter, body = '# Skill\n') => {
  const directory = join(root, name);
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, 'SKILL.md'), `---\n${frontmatter}\n---\n${body}`);
  return directory;
};

test('the CookieGuard skill follows the Agent Skills specification and links resolve', async () => {
  const result = await checkSkill('skills/cookieguard');
  assert.deepEqual(result.errors, []);
  assert.equal(result.name, 'cookieguard');
  const text = await readFile('skills/cookieguard/SKILL.md', 'utf8');
  // Install commands in the skill must use released versions that exist today.
  for (const [, version] of text.matchAll(/@aiscihub\/cookieguard-[a-z]+@(\S+?)[`\s]/g)) assert.equal(version, '0.1.0');
  for (const [, version] of text.matchAll(/cookieguard-ci@(\S+?)[`\s]/g)) assert.equal(version, '0.1.0');
  const marketplace = JSON.parse(await readFile('.claude-plugin/marketplace.json', 'utf8'));
  assert.equal(marketplace.plugins[0].source, './skills/cookieguard');
});

test('the checker rejects specification violations', async () => {
  const root = await mkdtemp(join(tmpdir(), 'cookieguard-skill-'));
  try {
    const cases = [
      ['Bad-Name', 'name: Bad-Name\ndescription: x', /name: 1-64/],
      ['a--b', 'name: a--b\ndescription: x', /name: 1-64/],
      ['mismatch', 'name: other\ndescription: x', /parent directory/],
      ['long', `name: long\ndescription: ${'x'.repeat(1025)}`, /description/],
      ['empty', 'name: empty\ndescription: ', /description/],
      ['unknown', 'name: unknown\ndescription: x\nversion: 1', /Unknown field: version/],
      ['compat', `name: compat\ndescription: x\ncompatibility: ${'x'.repeat(501)}`, /compatibility/],
      ['link', 'name: link\ndescription: x', /Broken link: references\/missing.md/, '[x](references/missing.md)\n'],
      ['escape', 'name: escape\ndescription: x', /leaves the skill directory/, '[x](../outside.md)\n'],
    ];
    for (const [name, frontmatter, pattern, body] of cases) {
      const { errors } = await checkSkill(await write(root, name, frontmatter, body));
      assert.match(errors.join('; '), pattern, name);
    }
    await assert.rejects(checkSkill(await write(root, 'nested', 'name: nested\n  deep: x')), /Unsupported/);
  } finally { await rm(root, { recursive: true, force: true }); }
});
