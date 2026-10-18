import { AuditError, levels, limitArray, originOf, sameSites, textField } from './safety.js';
import { cleanObservation } from './normalize.js';

export const RULES = Object.freeze({
  CG001: { title: 'Missing HttpOnly', severity: 'high', why: 'If accepted, a cookie without HttpOnly can be read by JavaScript. This increases token exposure if script execution is compromised; it does not demonstrate XSS.', fix: 'Set HttpOnly on the authentication cookie at the server.' },
  CG002: { title: 'Missing Secure', severity: 'high', why: 'The cookie is not restricted to HTTPS transport. This is a configuration exposure, not proof of interception.', fix: 'Set Secure and serve the application over HTTPS.' },
  CG003: { title: 'SameSite declaration violates policy', severity: 'medium', why: 'The declared cross-site behavior does not meet the configured policy. SameSite alone does not establish CSRF protection or vulnerability.', fix: 'Use an allowed SameSite value, or explicitly adjust the policy for a reviewed cross-site flow with separate CSRF defenses.' },
  CG004: { title: 'Domain sharing requires review', severity: 'medium', why: 'A Domain attribute shares the cookie with matching subdomains. This does not establish subdomain compromise or takeover.', fix: 'Omit Domain when subdomain sharing is unnecessary; use a valid __Host- cookie where practical.' },
  CG005: { title: 'Authentication-cookie lifetime exceeds policy', severity: 'medium', why: 'A longer client lifetime extends potential exposure. Server-side session expiry and revocation are not measured.', fix: 'Reduce Max-Age or Expires to the configured maximum and enforce server-side session expiry.' },
  CG006: { title: 'Invalid security prefix declaration', severity: 'high', why: 'The observed header violates __Host- or __Secure- requirements. Browsers may reject it; this does not prove an insecure cookie was accepted.', fix: 'Use HTTPS and Secure for both prefixes; __Host- also requires an explicit Path=/ and no Domain.' },
  CG007: { title: 'Authentication-cookie protection regressed', severity: 'high', why: 'Comparable observations show a previously enabled protection was removed.', fix: 'Restore the previous protection or review and document the intentional policy change.' },
  CG008: { title: 'Authentication role is unconfirmed', severity: 'info', why: 'Classifier outputs are triage signals, not validated probabilities of an authentication role.', fix: 'Identify the actual session cookie in your login test and configure its exact name or validated scoped evidence.' },
  CG009: { title: 'Cookie evidence requires review', severity: 'info', why: 'Some attributes, declarations, or browser acceptance are unknown or ambiguous.', fix: 'Start collection before login and inspect the server cookie configuration. Do not infer declarations from browser defaults.' },
});

export function validatePolicy(policy = {}) {
  if (!policy || typeof policy !== 'object' || Array.isArray(policy)) throw new AuditError('CONFIG');
  const allowedKeys = ['authCookies', 'authEvidence', 'failOn', 'allowedSameSite', 'requireExplicitSameSite', 'requireHostOnly', 'maxLifetimeDays'];
  if (Object.keys(policy).some(key => !allowedKeys.includes(key))) throw new AuditError('CONFIG');
  const names = limitArray(policy.authCookies ?? [], 100);
  if (names.some(name => typeof name !== 'string' || !/^[!#$%&'*+.^_`|~0-9a-z-]{1,256}$/i.test(name))) throw new AuditError('CONFIG');
  const failOn = policy.failOn ?? 'high';
  const allowedSameSite = policy.allowedSameSite ?? ['lax', 'strict'];
  const maxLifetimeDays = policy.maxLifetimeDays ?? 30;
  if (!Object.hasOwn(levels, failOn) || !Array.isArray(allowedSameSite) || !allowedSameSite.length
    || allowedSameSite.some(value => !sameSites.includes(value))
    || !Number.isFinite(maxLifetimeDays) || maxLifetimeDays <= 0 || maxLifetimeDays > 36500) throw new AuditError('CONFIG');
  for (const key of ['requireExplicitSameSite', 'requireHostOnly']) {
    if (policy[key] !== undefined && typeof policy[key] !== 'boolean') throw new AuditError('CONFIG');
  }
  const authEvidence = limitArray(policy.authEvidence ?? [], 100).map(evidence => {
    if (!evidence || evidence.validation !== 'server-session-validated' || typeof evidence.name !== 'string'
      || !evidence.name || typeof evidence.domain !== 'string' || !evidence.domain
      || typeof evidence.path !== 'string' || !evidence.path.startsWith('/')) throw new AuditError('CONFIG');
    return { name: textField(evidence.name), domain: textField(evidence.domain).replace(/^\./, '').toLowerCase(),
      path: textField(evidence.path), origin: originOf(evidence.origin), validation: 'server-session-validated' };
  });
  return { authCookies: [...new Set(names)].sort(), authEvidence, failOn,
    allowedSameSite: [...new Set(allowedSameSite)].sort(), maxLifetimeDays,
    requireExplicitSameSite: policy.requireExplicitSameSite ?? false,
    requireHostOnly: policy.requireHostOnly ?? false };
}

function identityOf(cookie, policy) {
  if (policy.authCookies.includes(cookie.name)) return { status: 'confirmed', basis: 'developer-name' };
  if (policy.authEvidence.some(e => e.name === cookie.name && e.domain === cookie.domain && e.path === cookie.path && e.origin === cookie.origin)) {
    return { status: 'confirmed', basis: 'validated-auth-flow' };
  }
  if (cookie.triage.label === 'authentication') return { status: 'candidate', basis: cookie.triage.origin };
  if (cookie.triage.label === 'other') return { status: 'unknown', basis: cookie.triage.origin };
  return { status: 'non-auth-candidate', basis: cookie.triage.origin };
}

export function cookieKey(cookie) {
  return JSON.stringify([cookie.origin, cookie.name, cookie.domain, cookie.path]);
}

function evidenceOf(cookie, identity, changes = []) {
  return { source: cookie.source, identityBasis: identity.basis, secure: cookie.secure, httpOnly: cookie.httpOnly,
    hostOnly: cookie.hostOnly, declaredSameSite: cookie.sameSite.declared, effectiveSameSite: cookie.sameSite.effective,
    remainingLifetimeDays: cookie.lifetimeSeconds === null ? null : Math.round(cookie.lifetimeSeconds / 86400 * 1000) / 1000,
    storeStatus: cookie.storeStatus, headerWarnings: cookie.header?.warnings ?? [], changes };
}

const reportCache = new WeakMap();
export function trustedReport(report) {
  const canonical = reportCache.get(report);
  if (!canonical) throw new AuditError('INPUT');
  return canonical;
}

export function evaluateCookiePolicy(observations, policyInput = {}, options = {}) {
  const policy = validatePolicy(policyInput);
  const cookies = limitArray(observations).map(cleanObservation).sort((a, b) => {
    const x = cookieKey(a) + a.source + JSON.stringify(a);
    const y = cookieKey(b) + b.source + JSON.stringify(b);
    return x < y ? -1 : x > y ? 1 : 0;
  });
  const target = options.target ? originOf(options.target) : null;
  const mode = options.mode ?? 'fixture';
  if (!['http', 'browser', 'fixture'].includes(mode)) throw new AuditError('CONFIG');
  const issues = [];
  if (options.complete === false) issues.push('collection-incomplete');
  if (!cookies.length) issues.push('no-cookies-observed');
  if (policy.authCookies.some(name => !cookies.some(cookie => cookie.name === name && !cookie.deleted))) issues.push('expected-auth-cookie-not-observed');
  if (policy.authEvidence.some(e => !cookies.some(cookie => !cookie.deleted && cookieKey(cookie) === cookieKey(e)))) issues.push('validated-auth-cookie-not-observed');
  const findings = [];
  const add = (id, cookie, identity, confirmed, changes) => {
    const rule = RULES[id];
    findings.push({ ruleId: id, severity: rule.severity, status: confirmed ? 'confirmed' : 'review',
      cookie: { name: cookie.name, domain: cookie.domain, path: cookie.path, origin: cookie.origin },
      title: rule.title, evidence: evidenceOf(cookie, identity, changes), why: rule.why, fix: rule.fix });
  };
  const entries = cookies.map(cookie => ({ observation: cookie, identity: identityOf(cookie, policy) }));
  for (const { observation: cookie, identity } of entries) {
    if (cookie.deleted) continue;
    const confirmed = identity.status === 'confirmed' && cookie.confidence === 'observed';
    const couldBeAuth = ['confirmed', 'candidate', 'unknown'].includes(identity.status);
    if (['candidate', 'unknown'].includes(identity.status)) add('CG008', cookie, identity, false);
    if (couldBeAuth) {
      if (cookie.httpOnly === false) add('CG001', cookie, identity, confirmed);
      if (cookie.secure === false) add('CG002', cookie, identity, confirmed);
      if ((sameSites.includes(cookie.sameSite.declared) && !policy.allowedSameSite.includes(cookie.sameSite.declared))
        || (policy.requireExplicitSameSite && cookie.sameSite.declared === 'absent')) add('CG003', cookie, identity, confirmed);
      if (cookie.hostOnly === false) add('CG004', cookie, identity, confirmed && policy.requireHostOnly);
      if (cookie.lifetimeSeconds !== null && cookie.lifetimeSeconds > policy.maxLifetimeDays * 86400) add('CG005', cookie, identity, confirmed);
      if (cookie.sameSite.declared === 'unknown' || cookie.sameSite.declared === 'absent'
        || cookie.confidence === 'uncertain' || cookie.secure === null || cookie.httpOnly === null
        || (policy.requireHostOnly && cookie.hostOnly === null) || cookie.storeStatus === 'not-observed') add('CG009', cookie, identity, false);
    }
    if (cookie.header?.prefixValid === false) add('CG006', cookie, identity, confirmed);
  }

  const comparison = { status: 'not-requested', comparedCookies: 0 };
  if (options.baseline !== undefined) {
    const baseline = options.baseline;
    if (!baseline || baseline.schemaVersion !== 1 || !['passed', 'failed', 'incomplete'].includes(baseline.status)
      || !Array.isArray(baseline.cookies) || baseline.cookies.length > 1000
      || !baseline.policy) throw new AuditError('BASELINE');
    comparison.status = 'not-comparable';
    if (baseline.status !== 'incomplete' && baseline.target === target && baseline.mode === mode
      && JSON.stringify(validatePolicy(baseline.policy)) === JSON.stringify(policy)) {
      comparison.status = 'comparable';
      for (const { observation: current, identity } of entries) {
        if (identity.status !== 'confirmed' || current.deleted || current.confidence !== 'observed') continue;
        const matches = baseline.cookies.filter(entry => cookieKey(entry.observation ?? {}) === cookieKey(current)
          && entry.observation?.source === current.source);
        if (matches.length !== 1 || entries.filter(entry => cookieKey(entry.observation) === cookieKey(current) && entry.observation.source === current.source).length !== 1) continue;
        const previous = cleanObservation(matches[0].observation);
        if (identityOf(previous, policy).status !== 'confirmed' || previous.deleted || previous.confidence !== 'observed'
          || previous.storeStatus !== current.storeStatus) continue;
        comparison.comparedCookies++;
        const changes = ['secure', 'httpOnly'].filter(flag => previous[flag] === true && current[flag] === false);
        if (['lax', 'strict'].includes(previous.sameSite.declared) && current.sameSite.declared === 'none') changes.push('sameSite');
        if (previous.hostOnly === true && current.hostOnly === false) changes.push('hostOnly');
        if (previous.lifetimeSeconds !== null && current.lifetimeSeconds !== null
          && previous.lifetimeSeconds <= policy.maxLifetimeDays * 86400 && current.lifetimeSeconds > policy.maxLifetimeDays * 86400) changes.push('lifetime');
        if (changes.length) add('CG007', current, identity, true, changes);
      }
    }
  }

  const uniqueFindings = [...new Map(findings.map(f => [JSON.stringify(f), f])).values()];
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  uniqueFindings.sort((a, b) => levels[b.severity] - levels[a.severity] || compare(a.ruleId, b.ruleId) || compare(cookieKey(a.cookie), cookieKey(b.cookie)));
  const failed = uniqueFindings.filter(f => f.status === 'confirmed' && levels[f.severity] >= levels[policy.failOn]).length;
  const uniqueEntries = [...new Map(entries.filter(e => !e.observation.deleted).map(e => [cookieKey(e.observation), e])).values()];
  const status = issues.length ? 'incomplete' : failed ? 'failed' : 'passed';
  const report = { schemaVersion: 1, toolVersion: '0.1.0', mode, target, status,
    classificationModes: [...new Set(cookies.map(cookie => cookie.triage.mode))].sort(),
    policy, summary: { cookies: uniqueEntries.length, observations: cookies.length,
      confirmedAuth: uniqueEntries.filter(e => e.identity.status === 'confirmed').length,
      candidateAuth: uniqueEntries.filter(e => e.identity.status === 'candidate').length,
      unknownIdentity: uniqueEntries.filter(e => e.identity.status === 'unknown').length,
      confirmedViolations: uniqueFindings.filter(f => f.status === 'confirmed').length,
      failures: failed, reviewItems: uniqueFindings.filter(f => f.status === 'review').length },
    issues, limitations: [
      'Configuration audit only; no exploit or server-session validation is performed.',
      'Rule and ONNX classification are uncalibrated triage; only developer evidence confirms authentication identity.',
      ...(mode === 'http' ? ['HTTP headers only: no JavaScript, login workflow, or browser-acceptance check.'] : []),
      ...(cookies.some(c => c.sameSite.declared === 'unknown') ? ['Browser or fixture effective SameSite does not establish the original declaration.'] : []),
      ...(comparison.status === 'not-comparable' ? ['Baseline cannot be compared with this target, policy, or observation mode.'] : []),
    ], comparison, cookies: entries, findings: uniqueFindings };
  // Renderers use an immutable private copy, even if callers mutate a report.
  reportCache.set(report, structuredClone(report));
  return report;
}

export function exitCode(report) {
  const status = trustedReport(report).status;
  return status === 'incomplete' ? 2 : status === 'failed' ? 1 : 0;
}

export function assertCookiePolicy(report) {
  const code = exitCode(report);
  if (code) {
    const error = new Error(code === 2 ? 'CookieGuard audit incomplete.' : 'CookieGuard confirmed cookie policy violations.');
    error.name = 'CookiePolicyError';
    error.exitCode = code;
    throw error;
  }
}
