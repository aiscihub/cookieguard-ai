import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { startCookieAudit } from '@cookieguard/playwright';
import { exitCode, formatJson } from '@cookieguard/core';

const TOKEN = 'SENTINEL_SESSION_NEVER_SERIALIZE_84af20';
class Context extends EventEmitter {
  constructor(cookies = []) { super(); this.store = cookies; }
  async cookies() { return this.store; }
}
const cookie = { name: 'session_id', value: TOKEN, domain: 'app.test', path: '/private', secure: true, httpOnly: true, sameSite: 'Lax', expires: -1 };
const response = (header, url = 'https://app.test/login') => ({ url: () => url, headersArray: async () => [{ name: 'Set-Cookie', value: header }] });

test('collector scopes store cookies, keeps path cookies, and detaches on collection', async () => {
  const context = new Context([cookie, { ...cookie, domain: 'unrelated.test' }]);
  const collector = startCookieAudit(context, { origins: ['https://app.test'] });
  context.emit('response', response(`session_id=${TOKEN}; Path=/private; Secure; HttpOnly; SameSite=Lax`));
  context.emit('response', response(`outside=${TOKEN}`, 'https://unrelated.test'));
  const report = await collector.evaluate({ authCookies: ['session_id'] });
  assert.equal(report.cookies.length, 1);
  assert.equal(report.cookies[0].observation.storeStatus, 'present');
  assert.equal(context.listenerCount('response'), 0);
  assert.equal(formatJson(report).includes(TOKEN), false);
});
test('header failures and browser exceptions become incomplete without raw errors', async () => {
  for (const failure of ['header', 'store']) {
    const context = new Context([cookie]);
    const collector = startCookieAudit(context, { origins: ['https://app.test'] });
    if (failure === 'header') context.emit('response', { url: () => 'https://app.test', headersArray: async () => { throw new Error(TOKEN); } });
    else context.cookies = async () => { throw new Error(TOKEN); };
    const report = await collector.evaluate();
    assert.equal(exitCode(report), 2); assert.equal(formatJson(report).includes(TOKEN), false);
  }
});
test('bounded collection and conflicting/replaced headers cannot invent declaration matching', async () => {
  const context = new Context([cookie]);
  const collector = startCookieAudit(context, { origins: ['https://app.test'] });
  context.emit('response', response(`session_id=${TOKEN}; Path=/private; Secure; HttpOnly; SameSite=Lax`));
  context.emit('response', response(`session_id=${TOKEN}; Path=/private; Secure; HttpOnly; SameSite=Strict`));
  const report = await collector.evaluate();
  assert.equal(report.cookies.filter(e => e.observation.source === 'browser')[0].observation.sameSite.declared, 'unknown');
  const limited = startCookieAudit(context, { origins: ['https://app.test'], maxObservations: 1 });
  context.emit('response', response(`a=${TOKEN}`));
  context.emit('response', response(`b=${TOKEN}`));
  assert.equal(exitCode(await limited.evaluate()), 2);
});
test('closed context and expired collection are incomplete', async () => {
  const context = new Context([cookie]);
  const closed = startCookieAudit(context, { origins: ['https://app.test'] });
  context.emit('close');
  assert.equal(exitCode(await closed.evaluate()), 2);
  const expired = startCookieAudit(context, { origins: ['https://app.test'], timeoutMs: 100 });
  await new Promise(resolve => setTimeout(resolve, 120));
  assert.equal(exitCode(await expired.evaluate()), 2);
});
