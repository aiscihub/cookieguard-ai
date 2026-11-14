// Port of the frozen name_knowledge crawler's declaration and consent logic.
export const cleanDomain = text => String(text || '').toLowerCase().replace(/^\.+/, '').replace(/\.$/, '');
const UUID = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
const OT_HOSTS = new Set(['cdn.cookielaw.org', 'cmp-cdn.cookielaw.org', 'optanon.blob.core.windows.net',
  'cookie-cdn.cookiepro.com', 'cookiepro.blob.core.windows.net', 'cdn-ukwest.onetrust.com']);
export function binaryCategory(name, id) {
  if (id === 'C0001') return { label: 'not-tracker', category: 'necessary' };
  if (id === 'C0002') return { label: 'tracker', category: 'analytics' };
  if (id === 'C0003') return { label: 'not-tracker', category: 'functional' };
  if (id === 'C0004' || id === 'C0005') return { label: 'tracker', category: 'advertising' };
  const text = String(name || '');
  if (/(^ads.*|.*\s+ads.*|Ad Selection|advertising|advertise|targeting|sale of personal data|marketing|tracking|tracker|fingerprint)/i.test(text)) return { label: 'tracker', category: 'advertising' };
  if (/(necessary|essential|required)/i.test(text)) return { label: 'not-tracker', category: 'necessary' };
  if (/(measurement|analytic|anonym|research|performance)/i.test(text)) return { label: 'tracker', category: 'analytics' };
  if (/(functional|preference|security|secure)/i.test(text)) return { label: 'not-tracker', category: 'functional' };
  return null;
}
const declared = (name, domain, mapping, group, method) => ({
  name: String(name || ''), domain: cleanDomain(domain), ...mapping, group: String(group || ''), method
});
export function parseCookiebot(text) {
  const rows = [];
  for (const [suffix, label, category] of [
    ['Necessary', 'not-tracker', 'necessary'], ['Preference', 'not-tracker', 'preference'],
    ['Statistics', 'tracker', 'statistics'], ['Advertising', 'tracker', 'advertising']
  ]) {
    const match = text.match(new RegExp('CookieConsentDialog\\.cookieTable' + suffix + '\\s*=\\s*(\\[[\\s\\S]*?\\]);'));
    if (!match) continue;
    try { for (const row of JSON.parse(match[1])) if (Array.isArray(row) && row[0]) rows.push(declared(row[0], row[1], { label, category }, suffix, 'cookiebot-array')); } catch { /* unsupported declaration */ }
  }
  return rows;
}
export function parseOneTrust(payload) {
  const rows = [];
  for (const group of payload?.DomainData?.Groups || []) {
    const id = group.OptanonGroupId || group.CustomGroupId || group.GroupId || group.GroupName;
    const mapping = binaryCategory(group.GroupName, id);
    if (!mapping) continue;
    for (const c of group.FirstPartyCookies || []) if (c.Name) rows.push(declared(c.Name, c.Host, mapping, id, 'onetrust-json'));
    for (const host of group.Hosts || []) for (const c of host.Cookies || []) if (c.Name) rows.push(declared(c.Name, c.Host || host.Host, mapping, id, 'onetrust-json'));
  }
  return rows;
}
export async function fetchText(context, url, referer) {
  const response = await context.request.get(url, { headers: { Referer: referer }, timeout: 7000, maxRedirects: 20 });
  try {
    if (!response.ok()) throw new Error('declaration-unavailable');
    const body = await response.text();
    if (Buffer.byteLength(body, 'utf8') > 5000000) throw new Error('declaration-too-large');
    return body;
  } finally {
    await response.dispose?.().catch(() => {});
  }
}
export async function declaration(context, page, onFamily = () => {}) {
  const scripts = await page.locator('script').evaluateAll(nodes => nodes.map(n => ({
    src: n.src || '', cbid: n.getAttribute('data-cbid') || '', ddid: n.getAttribute('data-domain-script') || ''
  })));
  let cbid = scripts.map(x => x.cbid).find(x => new RegExp('^' + UUID + '$').test(x));
  for (const script of scripts) {
    const match = script.src.match(new RegExp('consent\\.cookiebot\\.com/(' + UUID + ')/cc\\.js|[?&]cbid=(' + UUID + ')'));
    if (!cbid && match) cbid = match[1] || match[2];
  }
  if (cbid) {
    onFamily('cookiebot');
    return { family: 'cookiebot', declared: parseCookiebot(await fetchText(context,
      'https://consent.cookiebot.com/' + cbid + '/cc.js?referer=' + encodeURIComponent(new URL(page.url()).hostname), page.url())) };
  }
  const ot = scripts.find(x => { try { return OT_HOSTS.has(new URL(x.src).hostname) && x.ddid; } catch { return false; } });
  if (!ot) return null;
  onFamily('onetrust');
  if (!new RegExp('^' + UUID + '(?:-test)?$').test(ot.ddid)) return { family: 'onetrust', declared: [] };
  const source = new URL(ot.src).origin + '/consent/' + ot.ddid + '/';
  const config = JSON.parse(await fetchText(context, source + ot.ddid + '.json', page.url()));
  for (const rule of (config.RuleSet || []).filter(r => Object.values(r.LanguageSwitcherPlaceholder || {}).some(v => ['en', 'en-GB', 'en-US'].includes(v)))) {
    if (!new RegExp('^' + UUID + '$').test(rule.Id)) continue;
    for (const lang of ['en', 'en-gb', 'en-us']) {
      try {
        const rows = parseOneTrust(JSON.parse(await fetchText(context, source + rule.Id + '/' + lang + '.json', page.url())));
        if (rows.length) return { family: 'onetrust', declared: rows };
      } catch { /* next language, bounded by site deadline */ }
    }
  }
  return { family: 'onetrust', declared: [] };
}
export function matchDeclaration(cookie, declarations) {
  const domain = cleanDomain(cookie.domain);
  return declarations.filter(row => row.name === cookie.name &&
    (!row.domain || domain === row.domain || domain.endsWith('.' + row.domain)))
    .sort((a, b) => Number(b.label === 'tracker') - Number(a.label === 'tracker'))[0] || null;
}
export async function acceptApi(page, family) {
  if (family === 'cookiebot') {
    await page.waitForFunction(() => typeof window.Cookiebot?.submitCustomConsent === 'function', null, { timeout: 4000 }).catch(() => {});
    return page.evaluate(() => {
      if (typeof window.Cookiebot?.submitCustomConsent !== 'function') return false;
      window.Cookiebot.submitCustomConsent(true, true, true); return true;
    });
  }
  await page.waitForFunction(() => typeof window.OneTrust?.AllowAll === 'function' || typeof window.Optanon?.AllowAll === 'function', null, { timeout: 4000 }).catch(() => {});
  return page.evaluate(() => {
    const api = typeof window.OneTrust?.AllowAll === 'function' ? window.OneTrust : window.Optanon;
    if (typeof api?.AllowAll !== 'function') return false;
    return new Promise(resolve => {
      const done = () => { clearTimeout(timer); window.removeEventListener('OneTrustGroupsUpdated', done); resolve(true); };
      const timer = setTimeout(() => { window.removeEventListener('OneTrustGroupsUpdated', done); resolve(false); }, 4000);
      window.addEventListener('OneTrustGroupsUpdated', done); api.AllowAll();
    });
  });
}
export function valueShape(input) {
  const text = String(input || '');
  let characterSet = 'other';
  if (!text) characterSet = 'empty';
  else if (/^\d+$/.test(text)) characterSet = 'digits';
  else if (/^[0-9a-f]+$/i.test(text)) characterSet = 'hex';
  else if (/^[a-z0-9]+$/i.test(text)) characterSet = 'alphanumeric';
  else if (/^[a-z0-9+/=_-]+$/i.test(text)) characterSet = 'base64/base64url';
  return { valueLength: text.length, valueCharacterSet: characterSet };
}
