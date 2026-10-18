import http from 'node:http';
import https from 'node:https';
import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';
import { AuditError, parseSetCookie } from '@aiscihub/cookieguard-core';

function parseTarget(value) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash
      || url.href.length > 2048 || !url.hostname) throw new Error();
    return url;
  } catch { throw new AuditError('TARGET'); }
}

function loopback(host) {
  return host === 'localhost' || host === '[::1]' || (isIP(host) === 4 && host.startsWith('127.'));
}

function publicIPv4(address) {
  if (isIP(address) !== 4) return false;
  const [a, b] = address.split('.').map(Number);
  return !(a === 0 || a === 10 || a === 127 || a >= 224 || (a === 100 && b >= 64 && b <= 127)
    || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && [0, 168].includes(b))
    || (a === 198 && [18, 19, 51].includes(b)) || (a === 203 && b === 0));
}

export function validateTarget(target, allowOrigins = []) {
  const url = parseTarget(target);
  if (!Array.isArray(allowOrigins) || allowOrigins.length > 20) throw new AuditError('CONFIG');
  const allowed = allowOrigins.map(value => {
    const candidate = parseTarget(value);
    if (candidate.pathname !== '/') throw new AuditError('CONFIG');
    return candidate.origin;
  });
  if (!loopback(url.hostname) && !allowed.includes(url.origin)) throw new AuditError('TARGET');
  return url;
}

async function resolvePinned(url) {
  const host = url.hostname;
  if (host === 'localhost') return { address: '127.0.0.1', family: 4 };
  if (host === '[::1]') return { address: '::1', family: 6 };
  if (isIP(host) === 4) {
    if (!loopback(host) && !publicIPv4(host)) throw new AuditError('TARGET');
    return { address: host, family: 4 };
  }
  // Remote IPv6 and internal DNS targets are intentionally unsupported in v0.1.
  if (host.startsWith('[')) throw new AuditError('TARGET');
  let addresses;
  try { addresses = await lookup(host, { all: true, family: 4 }); }
  catch { throw new AuditError('NETWORK'); }
  if (!addresses.length || addresses.some(entry => !publicIPv4(entry.address))) throw new AuditError('TARGET');
  return addresses[0];
}

function getHeaders(url, address, signal) {
  return new Promise((resolve, reject) => {
    const transport = url.protocol === 'https:' ? https : http;
    const request = transport.request(url, {
      method: 'GET', agent: false, signal, maxHeaderSize: 32768,
      headers: { 'user-agent': 'CookieGuard-CI/0.1.0', accept: '*/*', connection: 'close' },
      lookup: (_hostname, options, callback) => {
        if (options.all) callback(null, [address]);
        else callback(null, address.address, address.family);
      },
    }, response => {
      const result = { status: response.statusCode, location: response.headers.location,
        headers: response.headers['set-cookie'] ?? [] };
      response.destroy(); // Bodies are never collected or executed.
      resolve(result);
    });
    request.on('error', () => reject(new AuditError('NETWORK')));
    request.end();
  });
}

export async function scanUrl(target, options = {}) {
  const initial = validateTarget(target, options.allowOrigins ?? []);
  const timeoutMs = options.timeoutMs ?? 10000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 60000) throw new AuditError('CONFIG');
  const controller = new AbortController();
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => { controller.abort(); reject(new AuditError('NETWORK')); }, timeoutMs);
  });
  try {
    return await Promise.race([deadline, (async () => {
      const address = await resolvePinned(initial);
      const observations = [];
      let url = initial;
      for (let redirects = 0; redirects <= 5; redirects++) {
        if (controller.signal.aborted) throw new AuditError('NETWORK');
        const result = await getHeaders(url, address, controller.signal);
        if (result.headers.length + observations.length > 1000) throw new AuditError('INPUT');
        for (const header of result.headers) observations.push(parseSetCookie(header, url.href));
        if ([301, 302, 303, 307, 308].includes(result.status)) {
          if (!result.location || redirects === 5) throw new AuditError('REDIRECT');
          try { url = parseTarget(new URL(result.location, url).href); }
          catch { throw new AuditError('REDIRECT'); }
          if (url.origin !== initial.origin) throw new AuditError('REDIRECT');
          continue;
        }
        if (result.status < 200 || result.status >= 300) throw new AuditError('NETWORK');
        return { observations, target: initial.origin, mode: 'http', complete: true };
      }
      throw new AuditError('REDIRECT');
    })()]);
  } finally { clearTimeout(timer); controller.abort(); }
}
