// The scanner never persists the strings it searches for.
const forbidden = /^(?:value|cookieValue|rawValue|authorization|password|api[_-]?key|access[_-]?token|refresh[_-]?token)$/i;
export const credential = /(?:ph[ctx]_[A-Za-z0-9_-]{20,}|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)/;
export function structural(node) {
  if (Array.isArray(node)) return node.every(structural);
  if (node && typeof node === 'object') return Object.entries(node).every(([key, val]) => !forbidden.test(key) && structural(val));
  return typeof node !== 'string' || !credential.test(node);
}
// Aho-Corasick, also used by the frozen crawler's final scan. Scan each field once
// rather than once per retained string; full-size shards can retain many strings.
export function buildMatcher(secrets) {
  const nodes = [{ next: new Map(), fail: 0, outputs: 0 }];
  for (const secret of secrets) {
    if (!secret.length) continue;
    let state = 0;
    for (let i = 0; i < secret.length; i++) {
      const char = secret[i];
      if (!nodes[state].next.has(char)) {
        nodes[state].next.set(char, nodes.length);
        nodes.push({ next: new Map(), fail: 0, outputs: 0 });
      }
      state = nodes[state].next.get(char);
    }
    nodes[state].outputs++;
  }
  const queue = [...nodes[0].next.values()];
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const state = queue[cursor];
    for (const [char, child] of nodes[state].next) {
      queue.push(child);
      let fallback = nodes[state].fail;
      while (fallback && !nodes[fallback].next.has(char)) fallback = nodes[fallback].fail;
      nodes[child].fail = nodes[fallback].next.get(char) ?? 0;
      nodes[child].outputs += nodes[nodes[child].fail].outputs;
    }
  }
  return { count(input) {
    const text = String(input);
    let state = 0, matches = 0;
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      while (state && !nodes[state].next.has(char)) state = nodes[state].fail;
      state = nodes[state].next.get(char) ?? 0;
      matches += nodes[state].outputs;
    }
    return matches;
  } };
}
export function crossScan(node, secrets, field = '', matcher = buildMatcher(secrets)) {
  let bad = 0, metadataCoincidences = 0;
  if (Array.isArray(node)) {
    for (const part of node) {
      const count = crossScan(part, secrets, field, matcher);
      bad += count.bad; metadataCoincidences += count.metadataCoincidences;
    }
  } else if (node && typeof node === 'object') {
    for (const [key, val] of Object.entries(node)) {
      bad += matcher.count(key);
      const count = crossScan(val, secrets, key, matcher);
      bad += count.bad; metadataCoincidences += count.metadataCoincidences;
    }
  } else {
    const matches = matcher.count(node);
    if (matches) {
      // Same exception as the frozen crawler: numeric features and independent
      // cookie names/domains can coincidentally equal a cookie's contents.
      if (typeof node === 'number' || /^(name|normalizedName|domain)$/.test(field)) metadataCoincidences += matches;
      else bad += matches;
    }
  }
  return { bad, metadataCoincidences };
}
export class PrivacyGuard {
  constructor() { this.secrets = new Set(); this.checks = 0; }
  observe(cookies) {
    for (const cookie of cookies) {
      const text = String(cookie.value || '');
      if (text.length >= 8) this.secrets.add(text);
    }
  }
  check(data) {
    this.checks++;
    const result = crossScan(data, this.secrets);
    if (!structural(data) || result.bad) throw new Error('privacy-rejected');
    return result;
  }
  receipt() {
    return { passed: true, structuralPassed: true, crossScanPassed: true, batchChecks: this.checks,
      observedStrings: this.secrets.size, minimumScannedLength: 8,
      shortContentsProtection: 'fixed numeric features and allowlisted metadata; no contents field serialized',
      metadataCoincidencePolicy: 'numeric fields, cookie names and domains are independently observed metadata' };
  }
}
