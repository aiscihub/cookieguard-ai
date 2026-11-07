import { RULES } from './policy.js';
import { messages } from './safety.js';

// Machine-readable explanations for every rule, incomplete reason, error code,
// and status that CookieGuard can return. Static text only: never cookie data.
const SECURE_EXAMPLE = 'Set-Cookie: session_id=<opaque>; Path=/; Secure; HttpOnly; SameSite=Lax';
const CONFIRMED = 'The cookie is a confirmed authentication cookie (an exact configured authCookies name or validated authEvidence) and the attribute was observed';

const RULE_DETAILS = Object.freeze({
  CG001: { checks: 'HttpOnly', confirmedWhen: `${CONFIRMED} without HttpOnly.`,
    reviewWhen: 'A cookie that only heuristics suggest is authentication-related lacks HttpOnly.' },
  CG002: { checks: 'Secure', confirmedWhen: `${CONFIRMED} without Secure.`,
    reviewWhen: 'A cookie that only heuristics suggest is authentication-related lacks Secure.' },
  CG003: { checks: 'SameSite', confirmedWhen: `${CONFIRMED} with a declared SameSite value outside allowedSameSite, or with no declaration while requireExplicitSameSite is set.`,
    reviewWhen: 'The same condition on a cookie whose authentication role is unconfirmed.' },
  CG004: { checks: 'Domain scope', confirmedWhen: `${CONFIRMED} with a Domain attribute while requireHostOnly is set.`,
    reviewWhen: 'A Domain attribute without requireHostOnly, or on a cookie whose role is unconfirmed.' },
  CG005: { checks: 'Client lifetime', confirmedWhen: `${CONFIRMED} with a remaining lifetime above maxLifetimeDays.`,
    reviewWhen: 'The same condition on a cookie whose authentication role is unconfirmed.' },
  CG006: { checks: '__Host- and __Secure- prefixes', confirmedWhen: `${CONFIRMED} in a Set-Cookie header that violates its prefix requirements.`,
    reviewWhen: 'The same header violation on a cookie whose authentication role is unconfirmed.' },
  CG007: { checks: 'Baseline regression', confirmedWhen: 'A comparable baseline shows that a confirmed authentication cookie lost Secure, HttpOnly, host-only scope, a Lax/Strict SameSite declaration, or its lifetime limit.',
    reviewWhen: 'Never; incomparable baselines produce no CG007 findings.' },
  CG008: { checks: 'Authentication identity', confirmedWhen: 'Never; this is always a review item.',
    reviewWhen: 'A cookie looks like authentication to the uncalibrated classifier, or its role is unknown, and it was not configured.' },
  CG009: { checks: 'Evidence quality', confirmedWhen: 'Never; this is always a review item.',
    reviewWhen: 'Attributes, the SameSite declaration, or browser acceptance are unknown or ambiguous.' },
  CG010: { checks: 'Session rotation at login (session probe)', confirmedWhen: 'With a session probe configured, a configured authentication cookie value issued by a GET response was unauthenticated at the probe URL and later authenticated, without a new value being issued.',
    reviewWhen: 'The same evidence for a cookie that is not a configured authentication cookie.' },
  CG011: { checks: 'Session revocation at logout (session probe)', confirmedWhen: 'With a session probe configured, a configured authentication cookie that was authenticated was deleted (logout), and replaying its previous value to the probe URL was still authenticated.',
    reviewWhen: 'The same evidence for a cookie that is not a configured authentication cookie.' },
  CG012: { checks: 'Tokens in localStorage or sessionStorage', confirmedWhen: 'A configured authStorageKeys entry was present in Web Storage on an allowed origin.',
    reviewWhen: 'A Web Storage value looks like a token (a JWT, a token field in JSON, or a token-like value under a token-like key) and its key is not configured.' },
});

const ISSUES = Object.freeze({
  'collection-incomplete': { title: 'Collection did not complete',
    meaning: 'The collector stopped early, hit a limit, or produced provisional evidence.',
    fix: 'Start collection before the login, let the workflow finish, then evaluate once. Provisional agent checks never satisfy policy.' },
  'no-cookies-observed': { title: 'No cookies observed',
    meaning: 'The audited response or workflow set no cookies.',
    fix: 'Audit the endpoint or login workflow that creates the session, and start collection before it runs.' },
  'expected-auth-cookie-not-observed': { title: 'Configured authentication cookie not observed',
    meaning: 'At least one configured authCookies name was not set during the audit.',
    fix: 'Check the exact cookie name and audit the response or workflow that issues the session cookie.' },
  'validated-auth-cookie-not-observed': { title: 'Validated authentication cookie not observed',
    meaning: 'A cookie listed in authEvidence was not observed with the same name, domain, path, and origin.',
    fix: 'Update authEvidence or audit the workflow that issues that scoped cookie.' },
  'session-check-inconclusive': { title: 'Session checks could not decide',
    meaning: 'A session probe was configured, but rotation or logout could not be determined: the probe URL answered anonymous requests with 2xx, probes failed, the limit was reached, or a configured authentication cookie was never observed authenticated.',
    fix: 'Use a probe URL that answers anonymous requests with 401, 403, or a redirect and authenticated ones with 2xx, start collection before the first visit, and let the login finish before evaluating.' },
  'logout-not-observed': { title: 'Logout was required but not observed',
    meaning: 'requireLogout was set, but no configured authentication cookie was deleted after being authenticated.',
    fix: 'Include the logout step in the audited workflow, or drop requireLogout when the workflow does not log out.' },
  'scan-not-completed': { title: 'Audit did not complete',
    meaning: 'An error stopped the audit before a decision; see error.code.',
    fix: 'Explain the error code, correct the cause, and rerun. Do not treat the run as passed.' },
});

const ERROR_FIXES = Object.freeze({
  CONFIG: 'Check command arguments, policy values, and configuration keys.',
  INPUT: 'Supply a JSON cookie array, a legacy result, or a sanitized CookieGuard report under 1 MiB and 1000 observations.',
  TARGET: 'Use an http(s) URL without credentials, query, or fragment on loopback or an explicitly authorized origin.',
  NETWORK: 'Start the application, check the status code, TLS, and timeout, then retry.',
  REDIRECT: 'Audit the final same-origin URL; redirects may not leave the original origin or exceed five hops.',
  COLLECT: 'Create a new collector before the workflow and retry.',
  MODEL: 'Fix the ONNX runtime, model, or metadata, or omit the explicit classifier.',
  OUTPUT: 'Check the destination directory and permissions.',
  BASELINE: 'Use a previous JSON report from the same target, mode, and policy.',
  EVIDENCE: 'Enable evidenceDir in the server configuration and write the sanitized report there with a plain .json file name.',
  BUSY: 'Wait for the running audit to finish, then retry.',
});

const STATUSES = Object.freeze({
  passed: { label: 'PASS', exitCode: 0, meaning: 'The audit completed with no confirmed violations at or above failOn. It covers only the configured checks and does not prove application security.' },
  failed: { label: 'FAIL', exitCode: 1, meaning: 'Confirmed authentication-cookie policy violations at or above failOn were observed.' },
  incomplete: { label: 'INCOMPLETE', exitCode: 2, meaning: 'Evidence was missing or the audit could not complete. Never a pass.' },
});

export const ERROR_CODES = Object.freeze(Object.keys(ERROR_FIXES));
export const ISSUE_CODES = Object.freeze(Object.keys(ISSUES));
export const STATUS_CODES = Object.freeze(Object.keys(STATUSES));

export function ruleCatalog() {
  return Object.entries(RULES).map(([ruleId, rule]) => ({ ruleId, title: rule.title, severity: rule.severity,
    checks: RULE_DETAILS[ruleId].checks, confirmedWhen: RULE_DETAILS[ruleId].confirmedWhen,
    reviewWhen: RULE_DETAILS[ruleId].reviewWhen, why: rule.why, fix: rule.fix }));
}

export function statusCatalog() {
  return STATUS_CODES.map(status => ({ status, ...STATUSES[status] }));
}

/** Returns a fresh explanation object, or null when the identifier is unknown. */
export function explain(id) {
  if (typeof id !== 'string') return null;
  if (Object.hasOwn(RULES, id)) {
    const rule = ruleCatalog().find(entry => entry.ruleId === id);
    return { id, kind: 'rule', title: rule.title, severity: rule.severity, meaning: rule.why,
      confirmedWhen: rule.confirmedWhen, reviewWhen: rule.reviewWhen, fix: rule.fix, secureExample: SECURE_EXAMPLE };
  }
  if (Object.hasOwn(ISSUES, id)) return { id, kind: 'issue', status: 'incomplete', ...ISSUES[id] };
  if (Object.hasOwn(ERROR_FIXES, id)) {
    return { id, kind: 'error', status: 'incomplete',
      title: `${id} error`, meaning: messages[id] ?? 'The MCP server is already running an audit.', fix: ERROR_FIXES[id] };
  }
  if (Object.hasOwn(STATUSES, id)) return { id, kind: 'status', title: STATUSES[id].label, ...STATUSES[id] };
  return null;
}

export const EXPLAIN_IDS = Object.freeze([...Object.keys(RULES), ...ISSUE_CODES, ...ERROR_CODES, ...STATUS_CODES]);
