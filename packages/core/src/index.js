export { AuditError, safeError } from './safety.js';
export { normalizeCookie, normalizeCookies, normalizeLegacyResults, parseSetCookie, classifyCookie, extractCookieFeatures, FEATURE_NAMES } from './normalize.js';
export { evaluateCookiePolicy, validatePolicy, assertCookiePolicy, exitCode, RULES } from './policy.js';
export { formatJson, formatText, formatMarkdown } from './report.js';
export { readEvidence, isEvidenceReport } from './evidence.js';
export { summarizeSession, cleanSession, probeUrl, probeLocation } from './session.js';
export { classifyStorageEntry, storageObservation, safeStorageKey } from './storage.js';
export { explain, ruleCatalog, statusCatalog, EXPLAIN_IDS, ERROR_CODES, ISSUE_CODES } from './catalog.js';
