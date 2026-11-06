import { ruleCatalog, statusCatalog, ERROR_CODES, ISSUE_CODES } from '@aiscihub/cookieguard-core';
import manifest from '../package.json' with { type: 'json' };

const REPO = 'https://github.com/aiscihub/cookieguard-ai';
const RAW = 'https://raw.githubusercontent.com/aiscihub/cookieguard-ai/main';
// Versions that are actually published. Operations marked "unreleased" exist on
// the main branch only and need a source checkout until the next release.
const PUBLISHED = Object.freeze({ cli: '0.1.0', core: '0.1.0', playwright: '0.1.0', mcp: '0.1.0', browserUse: '0.1.0' });

/** The stable, versioned description of what CookieGuard can do. Static data only. */
export function capabilities() {
  return {
    $schema: `${RAW}/schemas/capabilities.schema.json`,
    schemaVersion: 1,
    tool: { id: 'cookieguard', name: 'CookieGuard', version: manifest.version, license: 'MIT',
      repository: REPO, documentation: `${REPO}#readme`, capabilitiesUrl: `${RAW}/cookieguard.capabilities.json` },
    summary: 'Evidence-based audit of authentication-cookie configuration (HttpOnly, Secure, SameSite, Domain scope, lifetime, and __Host-/__Secure- prefixes) for applications you are authorized to test. Returns PASS, FAIL, or INCOMPLETE with rule IDs and fixes, and never returns cookie values.',
    useWhen: [
      'Adding a session-cookie check to a login test, AI browser-agent workflow, or CI pipeline for your own application.',
      'Verifying that a Browser Use or Playwright login creates an HttpOnly, Secure, SameSite-restricted session cookie.',
      'Giving an MCP client a bounded, policy-fixed way to audit Set-Cookie headers on configured origins.',
    ],
    doNotUseWhen: [
      'Testing websites you do not own or are not authorized to test.',
      'Proving exploitability, XSS, CSRF, or server-side session security; CookieGuard audits configuration only.',
      'Reading, exporting, or replaying cookie values or browser profiles.',
    ],
    integrations: [
      { id: 'browser-use', kind: 'python-package', registry: 'pypi', package: 'cookieguard-browser-use', version: PUBLISHED.browserUse,
        install: 'pip install cookieguard-browser-use', entryPoint: 'cookieguard_browser_use.CookieGuardAudit',
        requires: ['Python 3.11-3.13', 'Node.js 24+', 'browser-use 0.13.14 (>=0.13.14,<0.14)', 'Chrome or Chromium'],
        tested: ['Linux, Python 3.11-3.13, Chromium 156', 'macOS, Python 3.12, Chrome 156'],
        documentation: `${REPO}/tree/main/integrations/browser-use` },
      { id: 'playwright', kind: 'npm-package', registry: 'npm', package: '@aiscihub/cookieguard-playwright', version: PUBLISHED.playwright,
        install: 'npm install --save-dev @aiscihub/cookieguard-playwright@0.1.0', entryPoint: 'startCookieAudit',
        requires: ['Node.js 24+', '@playwright/test'], tested: ['Linux (CI) and macOS arm64 (local), Node.js 24, Chromium'],
        documentation: `${REPO}/blob/main/docs/CI_GUIDE.md#quick-start-playwright` },
      { id: 'cli', kind: 'npm-package', registry: 'npm', package: 'cookieguard-ci', version: PUBLISHED.cli,
        install: 'npx --yes cookieguard-ci@0.1.0 scan http://127.0.0.1:3000/ --auth-cookie session_id --format json',
        entryPoint: 'cookieguard-ci', requires: ['Node.js 24+'], tested: ['Linux (CI) and macOS arm64 (local), Node.js 24'],
        documentation: `${REPO}/blob/main/docs/CI_GUIDE.md#quick-start-cli` },
      { id: 'github-action', kind: 'github-action', package: 'aiscihub/cookieguard-ai/action', version: 'ci-v0.1.0',
        install: 'uses: aiscihub/cookieguard-ai/action@12a09fe322b135ac2a5aec45cae1f880b717575f # ci-v0.1.0',
        entryPoint: 'action/action.yml', requires: ['GitHub-hosted or self-hosted runner with Node.js 24 setup'],
        tested: ['ubuntu-latest'], documentation: `${REPO}/blob/main/docs/CI_GUIDE.md#quick-start-github-actions` },
      { id: 'mcp', kind: 'mcp-server', registry: 'npm', package: '@aiscihub/cookieguard-mcp', version: PUBLISHED.mcp,
        mcpRegistryName: 'io.github.aiscihub/cookieguard', transport: 'stdio',
        install: 'npx --yes @aiscihub/cookieguard-mcp@0.1.0 --config /absolute/path/cookieguard.json',
        entryPoint: 'cookieguard-mcp', requires: ['Node.js 24+', 'A startup JSON configuration with allowedOrigins'],
        tested: ['Official MCP SDK client on Linux (Node.js 24) and macOS (Node.js 26)'],
        documentation: `${REPO}/tree/main/packages/mcp` },
      { id: 'agent-skill', kind: 'agent-skill', package: 'skills/cookieguard', version: 'unreleased',
        install: 'Copy skills/cookieguard into your agent skills directory, or add the repository as a Claude Code plugin marketplace.',
        entryPoint: 'skills/cookieguard/SKILL.md', requires: ['An agent that supports Agent Skills (SKILL.md)'],
        tested: ['Claude Code 2.1'], documentation: `${REPO}/tree/main/skills/cookieguard` },
    ],
    operations: [
      { id: 'audit-browser-session', availability: 'released', surfaces: ['browser-use', 'playwright'],
        description: 'Audit cookies created while your own test code drives an authorized browser workflow, such as a login.',
        inputs: ['Exact allowed origins', 'Authentication-cookie names (required to confirm failures)', 'Optional policy settings'],
        permissions: ['Your test code owns the browser session; the collector starts before the workflow and observes only allowed origins'],
        evidence: ['server-declaration', 'browser-observation'], network: 'None beyond the workflow the browser already performs.' },
      { id: 'audit-http-headers', availability: 'released', surfaces: ['cli', 'github-action', 'mcp'],
        description: 'Send one GET request (plus same-origin redirects) and audit the Set-Cookie headers.',
        inputs: ['URL on loopback or an explicitly allowed origin, without credentials, query, or fragment'],
        permissions: ['Loopback by default; nonlocal origins need --allow-origin; the MCP server needs an exact startup allowlist'],
        evidence: ['server-declaration'], network: 'GET without cookies or authorization headers; bodies are discarded.' },
      { id: 'audit-evidence-file', availability: 'unreleased', surfaces: ['cli', 'mcp'],
        description: 'Re-evaluate a sanitized CookieGuard JSON report or Browser Use result under the current policy.',
        inputs: ['cookieguard-ci scan --input FILE', 'MCP cookieguard_audit {"evidenceFile": "name.json"} inside the configured evidenceDir'],
        permissions: ['Local file read only; the MCP server reads only plain .json names inside its startup evidenceDir'],
        evidence: ['supplied-evidence'], network: 'None.' },
      { id: 'agent-provisional-check', availability: 'released', surfaces: ['browser-use'],
        description: 'Optional read-only cookieguard_audit action an agent can call mid-run. Provisional; it cannot satisfy policy.',
        inputs: ['None from the agent'], permissions: ['Registered by developer code with audit.register_tools(tools)'],
        evidence: ['browser-observation'], network: 'None.' },
      { id: 'explain', availability: 'unreleased', surfaces: ['cli', 'mcp'],
        description: 'Explain a rule ID, incomplete reason, error code, or status without any cookie data.',
        inputs: ['cookieguard-ci explain CG001 --json', 'MCP cookieguard_explain {"id": "CG001"}'], permissions: [],
        evidence: [], network: 'None.' },
      { id: 'capabilities', availability: 'unreleased', surfaces: ['cli', 'mcp'],
        description: 'Return this document.', inputs: ['cookieguard-ci capabilities --json', 'MCP cookieguard_capabilities {}'],
        permissions: [], evidence: [], network: 'None.' },
    ],
    checks: ruleCatalog().map(({ ruleId, title, severity, checks, confirmedWhen, reviewWhen, fix }) =>
      ({ ruleId, title, severity, checks, confirmedWhen, reviewWhen, fix })),
    results: {
      statuses: statusCatalog(),
      failOnLevels: ['info', 'low', 'medium', 'high', 'critical'], defaultFailOn: 'high',
      findingStatuses: [
        { status: 'confirmed', meaning: 'Observed violation on a cookie whose authentication role was confirmed by developer configuration or validated evidence. Can fail a run.' },
        { status: 'review', meaning: 'Heuristic or uncertain finding (classifier-only identity, unknown attributes, or ambiguous evidence). Never fails a run.' },
      ],
      evidenceSources: [
        { source: 'header', category: 'server-declaration', meaning: 'Parsed from an observed Set-Cookie header.' },
        { source: 'browser', category: 'browser-observation', meaning: 'Read from browser cookie-store metadata; cannot show the original SameSite declaration.' },
        { source: 'fixture', category: 'fixture', meaning: 'Supplied cookie metadata, such as a JSON cookie array.' },
        { source: 'legacy', category: 'legacy-import', meaning: 'Imported from a legacy extension result.' },
      ],
      identityBases: ['developer-name', 'validated-auth-flow', 'extension-rule-heuristic', 'extension-onnx-uncalibrated'],
      issueCodes: [...ISSUE_CODES], errorCodes: [...ERROR_CODES],
      schemas: { capabilities: `${RAW}/schemas/capabilities.schema.json`, report: `${RAW}/schemas/report.schema.json`,
        mcpAuditResult: `${RAW}/schemas/mcp-audit-result.schema.json`, explanation: `${RAW}/schemas/explanation.schema.json`,
        cliError: `${RAW}/schemas/cli-error.schema.json` },
      exitCodes: { 0: 'passed', 1: 'failed', 2: 'incomplete or error' },
    },
    privacy: [
      'Cookie values are never written to results, reports, logs, or MCP responses.',
      'No telemetry, accounts, or remote services. The engine runs locally.',
      'HTTP scans send no cookies or authorization headers and discard response bodies.',
      'CookieGuard never asks for, stores, or replays credentials or session tokens.',
      'MCP responses withhold observed cookie names, domains, and paths unless a name is a configured authentication cookie.',
    ],
    authorization: [
      'Audit only applications you own or are authorized to test.',
      'Loopback targets by default; every nonlocal origin must be explicitly allowed. Private non-loopback addresses and remote IPv6 are rejected in HTTP scans.',
      'The MCP server fixes its allowed origins, policy, and evidence directory at startup; tool arguments cannot change them.',
    ],
    evidenceRequirements: [
      'Configure the exact authentication-cookie names. Without them, findings stay in review and authentication rules cannot fail a run.',
      'Start browser collection before the login and evaluate after the workflow completes.',
      'Audit the response or workflow that actually sets the session cookie; otherwise the result is INCOMPLETE.',
      'SameSite declarations need Set-Cookie header evidence; browser-store evidence leaves them unknown.',
    ],
    limitations: [
      'Configuration audit only: no exploit, XSS, CSRF, or server-side session validation.',
      'A PASS covers only the configured checks and observed cookies.',
      'HTTP header scans cannot log in or execute JavaScript.',
      'Browser verification is Chromium-family only; Windows and Browser Use cloud browsers are untested.',
      'Classifier outputs are uncalibrated triage and never confirm authentication identity.',
      'Exposing a tool cannot force an agent to call it; enforce results in tests or CI.',
    ],
  };
}
