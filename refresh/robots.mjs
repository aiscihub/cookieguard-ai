export function rootAllowed(text) {
  const groups = [];
  let agents = [], rules = [], seenRule = false;
  const flush = () => { if (agents.length) groups.push({ agents, rules }); agents = []; rules = []; seenRule = false; };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/#.*/, '').trim();
    const match = /^([^:]+):\s*(.*)$/.exec(line);
    if (!match) continue;
    const key = match[1].trim().toLowerCase(), val = match[2].trim();
    if (key === 'user-agent') {
      if (seenRule) flush();
      agents.push(val.toLowerCase());
    } else if (agents.length && ['allow', 'disallow'].includes(key)) {
      seenRule = true;
      if (val) rules.push({ allow: key === 'allow', path: val });
    }
  }
  flush();
  const matching = groups.filter(g => g.agents.includes('*')).flatMap(g => g.rules).filter(rule => {
    const expr = '^' + rule.path.split('*').map(p => p.replace(/[.*+?^{}()|[\]\\]/g, '\\$&')).join('.*').replace(/\\\$$/, '$');
    return new RegExp(expr).test('/');
  }).sort((a, b) => b.path.replace(/\*/g, '').length - a.path.replace(/\*/g, '').length || Number(b.allow) - Number(a.allow));
  return matching.length === 0 || matching[0].allow;
}
export const ROBOTS_STATUSES = Object.freeze([
  'allowed', 'disallowed', 'absent-4xx', 'server-error', 'network-error', 'redirect-limit', 'too-large',
  'unreachable', 'tls-error'
]);
export function requestErrorStatus(error) {
  // Inspect the message in memory only. Never return, log, or persist it.
  const message = String(error?.message ?? error ?? '');
  // TLS takes precedence over a timeout/reset mentioned in the same error.
  if (/\b(?:ERR_(?:TLS|SSL|CERT)[A-Z_]*|CERT_[A-Z_]+|DEPTH_ZERO_SELF_SIGNED_CERT|SELF_SIGNED_CERT_IN_CHAIN|UNABLE_TO_VERIFY_LEAF_SIGNATURE|UNABLE_TO_GET_ISSUER_CERT(?:_LOCALLY)?)\b|\b(?:TLS|SSL)_[A-Z_]+\b|\b(?:TLS|SSL) (?:error|handshake|connection|protocol|alert|routines|failure|certificate)|\bcertificate (?:error|verify|verification|has|is|expired|invalid|unknown|signed)|\b(?:self[- ]signed|invalid|expired|untrusted) certificate|\bunable to (?:verify|get)[^\n]*certificate/i.test(message)) return 'tls-error';
  if (/\b(?:ENOTFOUND|EAI_[A-Z_]+|ECONNREFUSED|ECONNRESET|ECONNABORTED|EHOSTUNREACH|ENETUNREACH|ENETDOWN|EHOSTDOWN|ETIMEDOUT|ESOCKETTIMEDOUT|ERR_NAME_NOT_RESOLVED|ERR_DNS_[A-Z_]+|ERR_CONNECTION_(?:REFUSED|RESET|ABORTED|CLOSED|TIMED_OUT|FAILED)|ERR_ADDRESS_UNREACHABLE|ERR_INTERNET_DISCONNECTED|ERR_TIMED_OUT)\b|\bDNS (?:failure|error)|\bconnection (?:refused|reset|unreachable|closed)|\b(?:network|host) is unreachable|no route to host|socket hang up|timeout|timed out|name or service not known|nodename nor servname provided/i.test(message)) return 'unreachable';
  return 'network-error';
}
export async function checkRobots(context, origin) {
  const failure = status => ({ allowed: false, status });
  const deadline = Date.now() + 5000, seen = new Set();
  let url = origin + '/robots.txt';
  try {
    // RFC 9309: follow up to five redirects, including redirects across hosts.
    // Fetch explicitly so loops and the redirect limit get a fixed status code.
    for (let redirects = 0; redirects <= 5; redirects++) {
      if (seen.has(url)) return failure('redirect-limit');
      seen.add(url);
      const remaining = deadline - Date.now();
      if (remaining <= 0) return failure('unreachable');
      const response = await context.request.get(url, { timeout: remaining, maxRedirects: 0 });
      try {
        const status = response.status();
        const body = await response.text();
        if (Buffer.byteLength(body, 'utf8') > 500 * 1024) return failure('too-large');
        if ([301, 302, 303, 307, 308].includes(status)) {
          if (redirects === 5) return failure('redirect-limit');
          const location = response.headers().location;
          if (!location) return failure('network-error');
          const next = new URL(location, url);
          if (!['https:', 'http:'].includes(next.protocol)) return failure('network-error');
          next.hash = '';
          url = next.href;
          continue;
        }
        if (status >= 400 && status < 500) return { allowed: true, status: 'absent-4xx' };
        if (status >= 500 && status < 600) return failure('server-error');
        if (status < 200 || status >= 300) return failure('network-error');
        const allowed = rootAllowed(body);
        return { allowed, status: allowed ? 'allowed' : 'disallowed' };
      } finally {
        await response.dispose?.().catch(() => {});
      }
    }
    return failure('redirect-limit');
  } catch (error) { return failure(requestErrorStatus(error)); }
}
