// popup.js - CookieGuard AI Enhanced with Better Loading States
// Supports: Login detection, Before/After comparison, Demo scenarios

let currentDomain = '';
let beforeLoginCookies = null;
let afterLoginCookies = null;
let analysisResults = null;
let previousAnalysis = null;
let loginEventDetected = false;
let isScanning = false; // Prevent double-scanning


let userPrefs = { overrides: {}, ignored: {} };
let currentModalItem = null;

const UI_CONFIG = {
  reviewConfidenceThreshold: 0.75,  // below this, downgrade critical/high to "Review"
  maxEvidenceChips: 3
};


// Configuration — fully self-contained, no backend needed
const CONFIG = {
  useBackend: false,
  analysisMode: 'local'
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  try {
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.url && !tab.url.startsWith('chrome://')) {
        const url = new URL(tab.url);
        currentDomain = url.hostname;
      } else {
        currentDomain = 'demo-mode';
      }
    } else {
      currentDomain = 'demo-mode';
    }
  } catch (e) {
    currentDomain = 'demo-mode';
  }

  document.getElementById('domain-name').textContent = currentDomain;

  // Event listeners
  document.getElementById('scan-btn').addEventListener('click', handleScan);

  // Model info button
  document.getElementById('results-model-btn')
    ?.addEventListener('click', openModelModal);

  // Back button
  document.getElementById('back-btn')
    ?.addEventListener('click', showMainView);

  // Panel open/close
  document.getElementById('open-explain-panel')
    ?.addEventListener('click', () => openPanel('explain-panel'));
  document.getElementById('open-protect-panel')
    ?.addEventListener('click', () => openPanel('protect-panel'));
  document.getElementById('close-explain-panel')
    ?.addEventListener('click', () => closePanel('explain-panel'));
  document.getElementById('close-protect-panel')
    ?.addEventListener('click', () => closePanel('protect-panel'));

  // Close panels by tapping backdrop
  document.getElementById('explain-panel')
    ?.addEventListener('click', e => { if (e.target === document.getElementById('explain-panel')) closePanel('explain-panel'); });
  document.getElementById('protect-panel')
    ?.addEventListener('click', e => { if (e.target === document.getElementById('protect-panel')) closePanel('protect-panel'); });

  // Handle review button clicks in explain panel (event delegation)
  document.getElementById('explain-panel')?.addEventListener('click', handleExplainPanelButtonClick);

  // Login back button
  document.getElementById('login-back-btn')
    ?.addEventListener('click', showMainView);

  // Modal actions (reduce false positives)
  document.getElementById('btn-mark-not-auth')?.addEventListener('click', markCurrentCookieNotAuth);
  document.getElementById('btn-ignore-cookie')?.addEventListener('click', ignoreCurrentCookie);
  document.getElementById('cookie-modal-close-btn')?.addEventListener('click', closeModal);

  // Login flow buttons
  document.getElementById('capture-before-btn')?.addEventListener('click', captureBeforeLogin);
  document.getElementById('capture-after-btn')?.addEventListener('click', captureAfterLogin);

  // Model modal close button
  document.getElementById('model-modal-close-btn')?.addEventListener('click', closeModelModal);

  // Preload ONNX model, then update status
  if (window.CookieGuardEngine) {
    try {
      await window.CookieGuardEngine.loadModel();
      console.log('[CookieGuard] Model loaded successfully');
    } catch (e) {
      console.warn('[CookieGuard] Model preload failed:', e.message);
    }
  }

  await loadUserPrefs();
  updateBackendStatus();

  // Session dashboard
  await loadSessionDashboard();

  // Educational tip carousel
  initTipCarousel();
  document.getElementById('tip-prev')?.addEventListener('click', () => advanceTip(-1));
  document.getElementById('tip-next')?.addEventListener('click', () => advanceTip(1));

  // Check if we're on the demo site
  if (currentDomain.includes('localhost:8000') || currentDomain.includes('127.0.0.1:8000')) {
    showDemoSiteIndicator();
  }
});

// === VIEW MANAGEMENT ===

function showMainView() {
  document.getElementById('main-view').style.display = 'block';
  document.getElementById('loading-view').style.display = 'none';
  document.getElementById('results-view').style.display = 'none';
  document.getElementById('login-flow-view').style.display = 'none';
  isScanning = false; // Reset scanning flag
}

function toggleView(view) {
  document.getElementById('main-view').style.display =
    view === 'main' ? 'block' : 'none';

  document.getElementById('loading-view').style.display =
    view === 'loading' ? 'block' : 'none';

  document.getElementById('results-view').style.display =
    view === 'results' ? 'block' : 'none';

  document.getElementById('login-flow-view').style.display =
    view === 'login' ? 'block' : 'none';
}


function showLoadingView() {
  document.getElementById('main-view').style.display = 'none';
  document.getElementById('loading-view').style.display = 'block';
  document.getElementById('results-view').style.display = 'none';
  document.getElementById('login-flow-view').style.display = 'none';
}

function showResultsView() {
  document.getElementById('main-view').style.display = 'none';
  document.getElementById('loading-view').style.display = 'none';
  document.getElementById('results-view').style.display = 'block';
  document.getElementById('login-flow-view').style.display = 'none';
  document.getElementById('results-domain').textContent = currentDomain;
  isScanning = false; // Reset scanning flag
}

// === MODEL INFO MODAL ===

function openModelModal() {
  const modal = document.getElementById('model-modal');
  if (modal) {
    modal.classList.add('active');
  }
}

function closeModelModal() {
  const modal = document.getElementById('model-modal');
  if (modal) {
    modal.classList.remove('active');
  }
}

// === BACKEND STATUS ===

function updateBackendStatus() {
  const statusEl = document.getElementById('backend-status');
  if (statusEl) {
    // Check if the ONNX model actually loaded (engine tracks this internally)
    const engine = window.CookieGuardEngine;
    const modelReady = engine && engine._isModelLoaded && engine._isModelLoaded();
    statusEl.textContent = modelReady ? 'AI Engine Ready' : 'Rule-Based Mode';
    statusEl.className = modelReady ? 'connected' : 'local';
  }
}

// No backend health check needed — fully self-contained

// === DEMO SITE INDICATOR ===

function showDemoSiteIndicator() {
  const content = document.querySelector('#main-view .content');
  if (!content) return;

  const indicator = document.createElement('div');
  indicator.className = 'demo-indicator';
  indicator.innerHTML = '<strong>🎯 Demo Site Detected</strong><span>Ready to test scenarios A/B/C/D</span>';

  // Insert before the info text
  const infoText = content.querySelector('.info-text');
  if (infoText) {
    content.insertBefore(indicator, infoText);
  } else {
    content.appendChild(indicator);
  }
}

// === MAIN SCAN ===

async function handleScan() {
  // Prevent double-clicking
  if (isScanning) {
    console.log('Scan already in progress, ignoring...');
    return;
  }

  isScanning = true;
  showLoadingView();
  console.log('🔍 Starting scan...');

  try {
    // Check if chrome.cookies is available
    if (typeof chrome === 'undefined' || !chrome.cookies) {
      // Demo mode - create fake cookies for testing
      const cookies = [
        { name: 'session_id', domain: currentDomain, path: '/', secure: false, httpOnly: false, sameSite: 'none', value: 'abc123' },
        { name: 'auth_token', domain: currentDomain, path: '/', secure: true, httpOnly: true, sameSite: 'strict', value: 'xyz789' },
        { name: '_ga', domain: currentDomain, path: '/', secure: false, httpOnly: false, sameSite: 'lax', value: 'GA1.2.123' }
      ];
      console.log('Demo mode: using fake cookies');
      const results = await analyzeCookies(cookies);
      displayResults(results);
      showResultsView();
      return;
    }

    // Get cookies for current domain
    const cookies = await chrome.cookies.getAll({ domain: currentDomain });

    if (cookies.length === 0) {
      alert('No cookies found for this domain.\n\nTry:\n1. Visit a website first\n2. Make sure the site sets cookies\n3. For demo: visit localhost:8000 and click Login');
      showMainView();
      return;
    }

    console.log(`Found ${cookies.length} cookies:`, cookies.map(c => c.name));

    // Store previous analysis for comparison
    if (analysisResults) {
      previousAnalysis = analysisResults;
    }

    // Analyze cookies
    const results = await analyzeCookies(cookies);

    if (!results) {
      throw new Error('Analysis returned no results');
    }

    console.log('Analysis complete:', results);

    // Display results
    displayResults(results);
    showResultsView();

  } catch (error) {
    console.error('Scan error:', error);
    alert('Scan failed: ' + error.message + '\n\nCheck console for errors (F12)');
    showMainView();
  }
}

// === LOGIN FLOW ===

async function captureBeforeLogin() {
  try {
    console.log('Capturing before-login cookies...');

    if (typeof chrome !== 'undefined' && chrome.cookies) {
      beforeLoginCookies = await chrome.cookies.getAll({ domain: currentDomain });
    } else {
      // Demo mode
      beforeLoginCookies = [
        { name: 'visitor_id', domain: currentDomain, path: '/', secure: false, httpOnly: false, value: 'v123' }
      ];
    }

    document.getElementById('step-1').classList.remove('active');
    document.getElementById('step-1').classList.add('completed');
    document.getElementById('step-2').classList.add('active');
    document.getElementById('capture-before-btn').disabled = true;

    // Wait a bit, then enable step 3
    setTimeout(() => {
      document.getElementById('step-2').classList.remove('active');
      document.getElementById('step-2').classList.add('completed');
      document.getElementById('step-3').classList.add('active');
      document.getElementById('capture-after-btn').disabled = false;
    }, 2000);

  } catch (error) {
    console.error('Error capturing before cookies:', error);
    alert('Failed to capture cookies: ' + error.message);
  }
}

async function captureAfterLogin() {
  showLoadingView();

  try {
    console.log('Capturing after-login cookies...');

    if (typeof chrome !== 'undefined' && chrome.cookies) {
      afterLoginCookies = await chrome.cookies.getAll({ domain: currentDomain });
    } else {
      // Demo mode - simulate new cookies after login
      afterLoginCookies = [
        { name: 'visitor_id', domain: currentDomain, path: '/', secure: false, httpOnly: false, value: 'v123' },
        { name: 'session_id', domain: currentDomain, path: '/', secure: false, httpOnly: false, sameSite: 'none', value: 'sess_abc' },
        { name: 'auth_token', domain: currentDomain, path: '/', secure: true, httpOnly: true, sameSite: 'strict', value: 'auth_xyz' }
      ];
    }

    // Detect which cookies changed
    const changedCookies = detectLoginChanges(beforeLoginCookies, afterLoginCookies);

    console.log(`Detected ${changedCookies.length} changed cookies`);

    // Mark as login event
    loginEventDetected = true;

    // Store before analysis for comparison
    if (beforeLoginCookies.length > 0) {
      previousAnalysis = await analyzeCookies(beforeLoginCookies);
    }

    // Analyze new cookies
    const results = await analyzeCookies(afterLoginCookies, {
      loginEvent: true,
      changedCookies: changedCookies.map(c => c.name)
    });

    displayResults(results);
    showResultsView();

  } catch (error) {
    console.error('Error in after-login capture:', error);
    alert('Failed to analyze: ' + error.message);
    showMainView();
  }
}

function detectLoginChanges(before, after) {
  const beforeMap = new Map(before.map(c => [c.name, c]));
  const changed = [];

  for (const cookie of after) {
    const beforeCookie = beforeMap.get(cookie.name);
    if (!beforeCookie || beforeCookie.value !== cookie.value) {
      changed.push(cookie);
    }
  }

  return changed;
}

// === COOKIE ANALYSIS ===

async function analyzeCookies(cookies, context = {}) {
  console.log(`Analyzing ${cookies.length} cookies via CookieGuard Engine`);

  // Build context for the engine
  const engineContext = {
    currentDomain,
    loginEvent: context.loginEvent || false,
    changedCookies: context.changedCookies || [],
    beforeCookieIndex: (context.loginEvent && beforeLoginCookies)
      ? Object.fromEntries(beforeLoginCookies.map(c => [c.name, { present: true }]))
      : {},
  };

  // Run the full engine pipeline (feature extraction → ML/rule classification → risk → explainability → attack sim)
  const engineResult = await window.CookieGuardEngine.analyzeAllCookies(cookies, engineContext);

  // Map engine output to popup.js data shape
  analysisResults = {
    cookies: engineResult.cookies.map(r => ({
      cookie: r.cookie,
      classification: r.classification,
      risk: r.risk,
      summary: `${r.cookie.name} classified as ${r.classification.type} (${r.classification.mode === 'onnx' ? 'ML' : 'rule-based'})`,
      recommendations: r.recommendations || [],
      explanations: r.explanations || null,
      attack_simulation: r.attack_simulation || null,
      behavior_signals: r.behavior_signals || null,
      _needsReview: r._needsReview || false,
    })),
    summary: engineResult.summary,
    context: context,
  };

  console.log('Engine analysis results:', analysisResults);
  return analysisResults;
}

// === RESULTS DISPLAY ===

function displayResults(results) {
  if (!results || !results.summary) {
    console.error('Invalid results:', results);
    alert('Error: Invalid analysis results');
    showMainView();
    return;
  }

  // Login event badge
  if (results.context?.loginEvent || loginEventDetected) {
    document.getElementById('login-event-badge').style.display = 'block';
    document.getElementById('event-details').textContent =
      `${results.context?.changedCookies?.length || 0} cookie(s) changed during login`;
    loginEventDetected = false;
  } else {
    document.getElementById('login-event-badge').style.display = 'none';
  }

  // Apply overrides / ignore
  const visibleCookies = (results.cookies || [])
    .map(c => applyUserOverrides(c))
    .filter(c => !isIgnored(c));

  // ── CARD 1: DIGITAL IDENTITY EXPOSURE ──
  const authCookies = visibleCookies.filter(c => c.classification?.type === 'authentication');
  const highRisk    = visibleCookies.filter(c => {
    const s = getEffectiveSeverity(c);
    return s === 'critical' || s === 'high';
  });

  const idLevel = window.CookieGuardEngine.computeIdentityExposure(authCookies.length, highRisk.length);
  const idCls   = idLevel === 'High' ? 'high' : idLevel === 'Medium' ? 'medium' : 'safe';
  const idInterp = {
    Low:    'No risky login cookies detected.',
    Medium: 'Login cookies detected but security protections are present.',
    High:   'At least one login cookie could expose your session.',
  }[idLevel];

  setCard('id', idCls, idLevel, idInterp,
    authCookies.length, highRisk.length, visibleCookies.length,
    ['Session', 'Cookies'], ['At-Risk', 'Cookies'], ['Total', 'Scanned']);

  // ── CARD 2: TRACKING EXPOSURE ──
  const eng = window.CookieGuardEngine;
  const trackingCookies   = visibleCookies.filter(c => c.classification?.type === 'tracking');
  const thirdPartyDomains = new Set(
    visibleCookies
      .filter(c => c.behavior_signals?.third_party)
      .map(c => (c.cookie?.domain || '').replace(/^\./, ''))
      .filter(Boolean)
  );

  // Build a map: company → cookie names
  const trackerCompanyMap = {};
  const addTracker = (company, cookieName) => {
    if (!trackerCompanyMap[company]) trackerCompanyMap[company] = [];
    if (!trackerCompanyMap[company].includes(cookieName)) trackerCompanyMap[company].push(cookieName);
  };

  // Layer 1: domain-based detection (all cookies)
  visibleCookies.forEach(c => {
    const co = eng.detectTrackerCompany(c.cookie?.domain || '');
    if (co) addTracker(co, c.cookie?.name || '?');
  });

  // Layer 2: cookie name patterns (all cookies, any classification)
  // Covers first-party tracker cookies set under the site's own domain
  const NAME_PATTERNS = [
    // Google Analytics / GTM
    [/^_ga($|_)/i,                    'Google Analytics'],
    [/^_gid$/i,                       'Google Analytics'],
    [/^_gac_/i,                       'Google Analytics'],
    [/^_gtm/i,                        'Google Tag Manager'],
    [/^__utm/i,                       'Google Analytics'],
    [/^_gcl_/i,                       'Google Ads'],
    // Meta / Facebook
    [/^_fbp$/i,                       'Meta'],
    [/^_fbc$/i,                       'Meta'],
    [/^fbm_/i,                        'Meta'],
    [/^fr$/i,                         'Meta'],
    // Amazon
    [/^session-id/i,                  'Amazon'],
    [/^ubid-/i,                       'Amazon'],
    [/^x-amz/i,                       'Amazon'],
    [/^csm-hit$/i,                    'Amazon'],
    [/^i18n-prefs$/i,                 'Amazon'],
    [/^lc-main$/i,                    'Amazon'],
    [/^sp-cdn$/i,                     'Amazon'],
    // Microsoft / Bing
    [/^_clck$/i,                      'Microsoft Clarity'],
    [/^_clsk$/i,                      'Microsoft Clarity'],
    [/^MUID$/i,                       'Microsoft'],
    [/^MR$/i,                         'Microsoft'],
    // TikTok
    [/^_ttp$/i,                       'TikTok'],
    [/^tt_/i,                         'TikTok'],
    // Analytics tools
    [/^amplitude/i,                   'Amplitude'],
    [/^mp_/i,                         'Mixpanel'],
    [/^ajs_/i,                        'Segment'],
    [/^fs_/i,                         'FullStory'],
    [/^_hjid$/i,                      'Hotjar'],
    [/^_hjSession/i,                  'Hotjar'],
    [/^_hjIncluded/i,                 'Hotjar'],
    // LinkedIn
    [/^li_/i,                         'LinkedIn'],
    [/^liap$/i,                       'LinkedIn'],
    [/^bcookie$/i,                    'LinkedIn'],
    // Pinterest
    [/^_pinterest/i,                  'Pinterest'],
    // Criteo
    [/^cto_/i,                        'Criteo'],
    // Generic tracking signals
    [/^_pk_/i,                        'Matomo Analytics'],
    [/^intercom-/i,                   'Intercom'],
    [/^__hstc$/i,                     'HubSpot'],
    [/^hubspotutk$/i,                 'HubSpot'],
    [/^__hssc$/i,                     'HubSpot'],
  ];

  visibleCookies.forEach(c => {
    const name = c.cookie?.name || '';
    for (const [pattern, company] of NAME_PATTERNS) {
      if (pattern.test(name)) {
        addTracker(company, name);
        break; // one company per cookie name loop
      }
    }
  });

  const trackerCompanies = new Set(Object.keys(trackerCompanyMap));

  const trLevel = eng.computeTrackingExposure(trackerCompanies.size, thirdPartyDomains.size);
  const trCls   = trLevel === 'High' ? 'high' : trLevel === 'Medium' ? 'medium' : 'safe';
  const trInterp = {
    Low:    'This site uses minimal tracking technologies.',
    Medium: 'This site uses several third-party trackers.',
    High:   'This site includes multiple tracking systems that may profile your browsing behavior.',
  }[trLevel];

  setCard('tr', trCls, trLevel, trInterp,
    trackingCookies.length, thirdPartyDomains.size, trackerCompanies.size,
    ['Tracking', 'Cookies'], ['3rd-Party', 'Domains'], ['Tracking', 'Companies']);

  // Render company pill list inside Card 2
  renderTrackerPills(trackerCompanyMap, trCls);

  // ── ACTION SUMMARY ──
  const summaryEl = document.getElementById('action-summary');
  if (summaryEl) {
    const isOk = highRisk.length === 0 && trackerCompanies.size === 0;
    if (isOk) {
      summaryEl.className = 'action-summary ok';
      summaryEl.textContent = 'CookieGuard found no high-risk cookies or known trackers on this page.';
    } else {
      const parts = [];
      if (highRisk.length > 0) parts.push(`<strong style="color:#dc2626">${highRisk.length} risky session cookie${highRisk.length > 1 ? 's' : ''}</strong>`);
      if (trackerCompanies.size > 0) parts.push(`<strong style="color:#ca8a04">${trackerCompanies.size} tracking ${trackerCompanies.size > 1 ? 'companies' : 'company'}</strong>`);
      summaryEl.className = 'action-summary';
      summaryEl.innerHTML = `CookieGuard detected ${parts.join(' and ')} on this page.`;
    }
  }

  // ── PANELS ──
  buildExplainPanel(visibleCookies, trackerCompanyMap);
  buildProtectPanel(visibleCookies, authCookies, trackingCookies, thirdPartyDomains, trackerCompanies);

  // ── SESSION STATS ──
  recordSessionScan({
    authCount:    authCookies.length,
    riskCount:    highRisk.length,
    trackerCount: trackerCompanies.size,
    trackerNames: Array.from(trackerCompanies),
  });

  // Populate hidden cookie list (modal still accessible)
  const listDiv = document.getElementById('cookie-list');
  listDiv.innerHTML = '';
  visibleCookies.sort((a, b) => (b.risk?.score || 0) - (a.risk?.score || 0));
  visibleCookies.forEach(item => listDiv.appendChild(createCookieCard(item)));
}

// ── helper: update an exposure card ──
function setCard(prefix, cls, levelText, interpText, m1, m2, m3, l1, l2, l3) {
  const level  = document.getElementById(`${prefix}-level`);
  const stripe = document.getElementById(`${prefix}-stripe`);
  const interp = document.getElementById(`${prefix}-interp`);
  const em1    = document.getElementById(`${prefix}-m1`);
  const em2    = document.getElementById(`${prefix}-m2`);
  const em3    = document.getElementById(`${prefix}-m3`);

  if (level)  { level.textContent = levelText; level.className = `exp-level ${cls}`; }
  if (stripe) { stripe.className = `exp-stripe ${cls}`; }
  if (interp) { interp.textContent = interpText; interp.className = `exp-interp ${cls}`; }
  if (em1)    {
    em1.textContent = m1;
    em1.className   = `exp-metric-n ${m1 > 0 && (cls === 'high' || cls === 'medium') ? (cls === 'high' ? 'danger' : 'warn') : ''}`;
  }
  if (em2)    {
    em2.textContent = m2;
    em2.className   = `exp-metric-n ${m2 > 0 && cls === 'high' ? 'danger' : ''}`;
  }
  if (em3)    { em3.textContent = m3; em3.className = 'exp-metric-n'; }
}

// ── render tracker company pills inside Card 2 ──
function renderTrackerPills(trackerCompanyMap, cls) {
  const container = document.getElementById('tracker-pills-row');
  if (!container) return;

  const companies = Object.keys(trackerCompanyMap);
  if (companies.length === 0) {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'flex';
  container.innerHTML = companies.map(co => {
    const cookies = trackerCompanyMap[co];
    const tipText = cookies.slice(0, 3).join(', ') + (cookies.length > 3 ? '…' : '');
    return `<span class="tracker-pill tracker-pill-${cls}" title="${escapeHtml(tipText)}">${escapeHtml(co)}</span>`;
  }).join('');
}


// (legacy no-op)
function renderIdentityDashboard() {}

// ── EXPLAIN PANEL ──

let explainPanelCookies = []; // Store cookies for review button handlers

function buildExplainPanel(cookies, trackerCompanyMap) {
  const risksEl  = document.getElementById('expl-risks-list');
  const otherEl  = document.getElementById('expl-other-list');
  const actionEl = document.getElementById('expl-action-line');
  const otherSec = document.getElementById('expl-other-sec');
  const trackerSec = document.getElementById('expl-tracker-sec');
  const trackerListEl = document.getElementById('expl-tracker-list');
  if (!risksEl || !otherEl) return;

  // Store cookies globally for button handlers
  explainPanelCookies = cookies;

  const important = cookies.filter(c => {
    const s = getEffectiveSeverity(c);
    return s === 'critical' || s === 'high';
  });
  const other = cookies.filter(c => {
    const s = getEffectiveSeverity(c);
    return s === 'medium' || s === 'low';
  });
  const trackerEntries = Object.entries(trackerCompanyMap || {});

  // Action line
  if (actionEl) {
    if (important.length === 0 && trackerEntries.length === 0) {
      actionEl.textContent = 'CookieGuard found no high-risk cookies or known trackers on this page.';
    } else {
      const parts = [];
      if (important.length > 0) parts.push(`<strong style="color:#dc2626">${important.length} risky session cookie${important.length > 1 ? 's' : ''}</strong>`);
      if (trackerEntries.length > 0) parts.push(`<strong style="color:#ca8a04">${trackerEntries.length} tracking ${trackerEntries.length > 1 ? 'companies' : 'company'}</strong>`);
      actionEl.innerHTML = `CookieGuard detected ${parts.join(' and ')} on this page.`;
    }
  }

  // Most important risks - pass global index
  if (important.length === 0) {
    risksEl.innerHTML = `<div class="expl-empty">✅ No high-risk cookies found.<br>Your login cookies appear well-configured.</div>`;
  } else {
    risksEl.innerHTML = important.slice(0, 5).map((item, i) => {
      const globalIndex = cookies.indexOf(item);
      return explainCard(item, globalIndex);
    }).join('');
  }

  // Other observations
  if (other.length === 0) {
    otherSec.style.display = 'none';
  } else {
    otherSec.style.display = 'block';
    otherEl.innerHTML = other.slice(0, 4).map((item, i) => {
      const globalIndex = cookies.indexOf(item);
      return explainCard(item, globalIndex);
    }).join('');
  }

  // Tracker company breakdown
  if (!trackerSec || !trackerListEl) return;
  if (trackerEntries.length === 0) {
    trackerSec.style.display = 'none';
  } else {
    trackerSec.style.display = 'block';
    trackerListEl.innerHTML = trackerEntries.map(([company, cookieNames]) => {
      const icon = trackerIcon(company);
      const cookieStr = cookieNames.slice(0, 3).map(n => `<code class="tc-cookie">${escapeHtml(n)}</code>`).join(' ');
      const more = cookieNames.length > 3 ? `<span class="tc-more">+${cookieNames.length - 3} more</span>` : '';
      return `
        <div class="tracker-row">
          <div class="tracker-row-top">
            <span class="tracker-ico">${icon}</span>
            <span class="tracker-name">${escapeHtml(company)}</span>
            <span class="tracker-count">${cookieNames.length} cookie${cookieNames.length > 1 ? 's' : ''}</span>
          </div>
          <div class="tracker-cookies">${cookieStr}${more}</div>
        </div>`;
    }).join('');
  }
}

function trackerIcon(company) {
  const map = {
    'Google': '🔍', 'Google Analytics': '🔍',
    'Meta': '👤', 'X/Twitter': '🐦',
    'Amazon': '📦', 'TikTok': '🎵',
    'Microsoft': '🪟', 'Microsoft Clarity': '🪟',
    'LinkedIn': '💼', 'Snap': '👻',
    'Hotjar': '🔥', 'Mixpanel': '📊',
    'Amplitude': '📈', 'Segment': '🔀',
    'Intercom': '💬', 'FullStory': '🎬',
    'Heap': '📋', 'Criteo': '🎯',
    'Outbrain': '📰', 'Taboola': '📰',
  };
  return map[company] || '🕵️';
}

function explainCard(item, index) {
  const sev  = getEffectiveSeverity(item);
  const name = escapeHtml(item.cookie?.name || '(unknown)');
  const type = item.classification?.type || 'other';
  const text = buildHumanExplanation(item);
  const needsReview = item._needsReview || sev === 'critical' || sev === 'high' || sev === 'medium';

  // Only show review actions for auth/tracking cookies with issues
  const showActions = (type === 'authentication' || type === 'tracking') && needsReview;

  const actionsHtml = showActions ? `
    <div class="expl-actions">
      <button class="expl-review-btn not-auth" data-index="${index}" data-action="not-auth">
        ✗ Not Auth
      </button>
      <button class="expl-review-btn ignore" data-index="${index}" data-action="ignore">
        🚫 Ignore
      </button>
      <button class="expl-review-btn" data-index="${index}" data-action="details">
        🔍 Details
      </button>
    </div>` : '';

  return `
    <div class="expl-card" data-cookie-index="${index}">
      <div class="expl-top">
        <div class="expl-dot ${sev}"></div>
        <div class="expl-name">${name}</div>
        <div class="expl-type">${escapeHtml(type)}</div>
      </div>
      <div class="expl-body">${text || 'This cookie has security configuration issues.'}</div>
      ${actionsHtml}
    </div>`;
}

// ── PROTECT PANEL ──

function buildProtectPanel(cookies, authCookies, trackingCookies, thirdPartyDomains, trackerCompanies) {
  const list = document.getElementById('protect-list');
  if (!list) return;

  const tips = [];

  const hasNoHttpOnly = cookies.some(c =>
    c.classification?.type === 'authentication' && !c.cookie?.httpOnly);
  const hasNoSecure = cookies.some(c =>
    c.classification?.type === 'authentication' && !c.cookie?.secure);
  const hasNoSameSite = cookies.some(c => {
    const ss = (c.cookie?.sameSite || '').toLowerCase();
    return c.classification?.type === 'authentication' &&
      (!ss || ss === 'none' || ss === 'no_restriction');
  });
  const hasWildcard = cookies.some(c => (c.cookie?.domain || '').startsWith('.'));

  if (authCookies.length > 0) {
    tips.push({
      icon: '🔐',
      title: 'Enable two-factor authentication',
      desc: 'Even if a login cookie is stolen, 2FA prevents attackers from accessing your account without a second verification step.',
    });
  }
  if (hasNoSecure || hasNoHttpOnly) {
    tips.push({
      icon: '📶',
      title: 'Avoid public Wi-Fi',
      desc: 'Some cookies on this site could be exposed on insecure networks. Use mobile data or a VPN when accessing sensitive accounts.',
    });
  }
  if (hasNoHttpOnly) {
    tips.push({
      icon: '🖥️',
      title: 'Log out after sessions on shared devices',
      desc: 'Login cookies are accessible to scripts. Logging out clears them and reduces exposure risk on shared computers.',
    });
  }
  if (hasNoSameSite) {
    tips.push({
      icon: '🔗',
      title: 'Be cautious with links in emails',
      desc: 'Some cookies here can be sent on cross-site requests. Avoid clicking suspicious links while logged into this site.',
    });
  }
  if (hasWildcard) {
    tips.push({
      icon: '🏠',
      title: 'Log out after each session',
      desc: 'Login cookies are shared across subdomains. Logging out removes them and reduces exposure risk.',
    });
  }
  if (trackingCookies.length > 0) {
    tips.push({
      icon: '🧩',
      title: 'Block trackers',
      desc: `This page includes tracking cookies. Extensions like uBlock Origin or Privacy Badger can block them automatically.`,
    });
  }
  if (thirdPartyDomains.size > 3) {
    tips.push({
      icon: '🌐',
      title: 'Review browser privacy settings',
      desc: `This page connects to ${thirdPartyDomains.size} third-party domains. Enabling "Enhanced Tracking Protection" in Firefox or similar settings in Chrome reduces exposure.`,
    });
  }

  // Always add
  tips.push({
    icon: '🗑️',
    title: 'Clear cookies on shared computers',
    desc: "After using any website on a public or shared computer, clear your browser's cookies to prevent others from accessing your sessions.",
  });

  list.innerHTML = tips.slice(0, 5).map(tip => `
    <div class="tip">
      <div class="tip-icon">${tip.icon}</div>
      <div>
        <div class="tip-title">${escapeHtml(tip.title)}</div>
        <div class="tip-desc">${escapeHtml(tip.desc)}</div>
      </div>
    </div>`).join('');
}

// ── PANEL OPEN / CLOSE ──
function openPanel(id)  { document.getElementById(id)?.classList.add('open'); }
function closePanel(id) { document.getElementById(id)?.classList.remove('open'); }

// ── EXPLAIN PANEL BUTTON HANDLER ──
function handleExplainPanelButtonClick(e) {
  const btn = e.target.closest('.expl-review-btn');
  if (!btn) return;

  const index = parseInt(btn.dataset.index, 10);
  const action = btn.dataset.action;
  const item = explainPanelCookies[index];

  if (!item) return;

  if (action === 'not-auth') {
    // Mark as not authentication cookie
    currentModalItem = item;
    markCurrentCookieNotAuth();
    // Update UI to show feedback
    const card = btn.closest('.expl-card');
    if (card) {
      card.style.opacity = '0.5';
      card.innerHTML = `
        <div class="expl-top">
          <div class="expl-dot info"></div>
          <div class="expl-name">${escapeHtml(item.cookie?.name || '(unknown)')}</div>
          <div class="expl-type" style="background:#dcfce7;color:#166534;">marked not-auth</div>
        </div>
        <div class="expl-body" style="color:#64748b;">This cookie will be excluded from future alerts.</div>
      `;
    }
  } else if (action === 'ignore') {
    // Ignore this cookie
    currentModalItem = item;
    ignoreCurrentCookie();
    // Update UI to show feedback
    const card = btn.closest('.expl-card');
    if (card) {
      card.style.opacity = '0.4';
      card.innerHTML = `
        <div class="expl-top">
          <div class="expl-dot info"></div>
          <div class="expl-name" style="text-decoration:line-through;">${escapeHtml(item.cookie?.name || '(unknown)')}</div>
          <div class="expl-type" style="background:#fef2f2;color:#991b1b;">ignored</div>
        </div>
        <div class="expl-body" style="color:#64748b;">This cookie will be hidden from future scans.</div>
      `;
    }
  } else if (action === 'details') {
    // Open the cookie details modal
    closePanel('explain-panel');
    showCookieDetails(item);
  }
}

// ═══════════════════════════════════════════════════════════════
//  SESSION PRIVACY DASHBOARD
// ═══════════════════════════════════════════════════════════════

const SESSION_KEY = 'cookieguard_session_v1';

async function recordSessionScan({ authCount, riskCount, trackerCount, trackerNames }) {
  try {
    const today = new Date().toDateString();
    const empty = () => ({ date: today, sites: 0, authCookies: 0, riskCookies: 0,
                           trackers: 0, trackerSet: [], domains: [], siteList: [] });

    let stored = empty();
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      const data = await chrome.storage.local.get([SESSION_KEY]);
      stored = (data[SESSION_KEY]?.date === today) ? data[SESSION_KEY] : empty();
    }

    if (!Array.isArray(stored.trackerSet)) stored.trackerSet = [];
    if (!Array.isArray(stored.siteList))   stored.siteList   = [];

    // ── per-site record (upsert by domain) ──
    const existing = stored.siteList.find(s => s.domain === currentDomain);
    if (existing) {
      // update with latest scan values
      existing.riskCount    = riskCount;
      existing.trackerNames = trackerNames || [];
      existing.trackerCount = (trackerNames || []).length;
    } else {
      stored.siteList.push({
        domain:       currentDomain,
        riskCount,
        trackerNames: trackerNames || [],
        trackerCount: (trackerNames || []).length,
      });
    }

    // ── aggregate totals ──
    stored.domains   = stored.siteList.map(s => s.domain);
    stored.sites     = stored.domains.length;
    stored.authCookies += authCount;  // cumulative
    stored.riskCookies  = stored.siteList.reduce((a, s) => a + s.riskCount, 0);

    // unique tracker companies across all sites
    const allTrackers = new Set();
    stored.siteList.forEach(s => s.trackerNames.forEach(n => allTrackers.add(n)));
    stored.trackerSet = Array.from(allTrackers);
    stored.trackers   = stored.trackerSet.length;

    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      await chrome.storage.local.set({ [SESSION_KEY]: stored });
    }
    renderSessionDashboard(stored);
  } catch (e) {
    console.warn('[CookieGuard] Session stats error:', e);
  }
}

async function loadSessionDashboard() {
  try {
    const today = new Date().toDateString();
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      const data = await chrome.storage.local.get([SESSION_KEY]);
      const stored = data[SESSION_KEY];
      if (stored?.date === today) { renderSessionDashboard(stored); return; }
    }
    renderSessionDashboard(null);
  } catch (e) {
    renderSessionDashboard(null);
  }
}

function renderSessionDashboard(stats) {
  const el = document.getElementById('session-dashboard');
  if (!el) return;

  if (!stats || !stats.sites) { el.style.display = 'none'; return; }
  el.style.display = 'block';

  const { sites = 0, authCookies = 0, riskCookies = 0, trackers = 0, siteList = [] } = stats;

  document.getElementById('sd-sites').textContent    = sites;
  document.getElementById('sd-auth').textContent     = authCookies;
  document.getElementById('sd-trackers').textContent = trackers;

  const riskEl = document.getElementById('sd-risk');
  if (riskEl) {
    riskEl.textContent = riskCookies;
    riskEl.className = 'sd-val ' + (riskCookies > 0 ? 'danger' : 'ok');
  }

  const listEl = document.getElementById('sd-site-list');
  if (!listEl) return;

  // Sort: high-risk first, then by tracker count
  const sorted = [...siteList].sort((a, b) =>
    (b.riskCount - a.riskCount) || (b.trackerCount - a.trackerCount)
  );

  const hasAnyFinding = sorted.some(s => s.riskCount > 0 || s.trackerCount > 0);

  listEl.innerHTML = (sorted.length > 0 ? '<div class="sd-list-header">Sites scanned today</div>' : '') +
    sorted.map(site => {
      const level = site.riskCount > 0 ? 'risk' : site.trackerCount > 0 ? 'warn' : 'ok';
      const icon  = level === 'risk' ? '🔴' : level === 'warn' ? '🟡' : '🟢';

      const riskBadge = site.riskCount > 0
        ? '<span class="sd-badge danger">⚠ ' + site.riskCount + ' at-risk</span>' : '';

      // individual company pills
      const shown = site.trackerNames.slice(0, 4);
      const extra = site.trackerNames.length - shown.length;
      const companyPills = shown.map(co => '<span class="sd-co-pill">' + escapeHtml(co) + '</span>').join('');
      const morePill     = extra > 0 ? '<span class="sd-co-more">+' + extra + ' more</span>' : '';
      const noneLabel    = site.trackerCount === 0 && site.riskCount === 0
        ? '<span class="sd-clean">✓ No trackers found</span>' : '';

      const bottomRow = (companyPills || noneLabel)
        ? '<div class="sd-site-companies">' + companyPills + morePill + noneLabel + '</div>'
        : '';

      return '<div class="sd-site-row">' +
        '<div class="sd-site-top">' +
          '<span class="sd-site-icon">' + icon + '</span>' +
          '<span class="sd-site-name">' + escapeHtml(site.domain) + '</span>' +
          riskBadge +
        '</div>' +
        bottomRow +
      '</div>';
    }).join('');
}

// ═══════════════════════════════════════════════════════════════
//  EDUCATIONAL TIP CAROUSEL
// ═══════════════════════════════════════════════════════════════

const EDU_TIPS = [
  {
    icon: '🍪',
    title: 'What are session cookies?',
    text: 'Session cookies keep you logged in. If stolen, an attacker can access your account without ever knowing your password.',
  },
  {
    icon: '🔒',
    title: 'What does HttpOnly mean?',
    text: 'The HttpOnly flag prevents JavaScript from reading a cookie. Without it, a malicious script on a hacked page could steal your login.',
  },
  {
    icon: '📡',
    title: 'What is cross-site tracking?',
    text: 'Companies like Google and Meta embed trackers on millions of websites. This lets them build a profile of your browsing habits across the web.',
  },
  {
    icon: '🛡️',
    title: 'What does the Secure flag do?',
    text: 'The Secure flag ensures cookies are only sent over HTTPS. Without it, your session can be intercepted on public Wi-Fi.',
  },
  {
    icon: '🎯',
    title: 'What is a CSRF attack?',
    text: 'Cross-Site Request Forgery tricks your browser into sending authenticated requests to a site you\'re logged into — without your knowledge.',
  },
  {
    icon: '🔑',
    title: 'Why does 2FA help?',
    text: 'Even if your session cookie is stolen, two-factor authentication adds a second barrier that attackers cannot bypass with cookies alone.',
  },
  {
    icon: '👁',
    title: 'Who tracks you most?',
    text: 'Google, Meta, and Amazon trackers appear on over 70% of popular websites. CookieGuard detects them and shows you which ones are active.',
  },
  {
    icon: '🗑️',
    title: 'When should you clear cookies?',
    text: 'Always clear cookies after using a shared or public computer. Leaving a session cookie behind is like leaving your door unlocked.',
  },
];

let tipIndex = 0;
let tipTimer = null;

function initTipCarousel() {
  tipIndex = Math.floor(Math.random() * EDU_TIPS.length);
  renderTip();

  // Rotate every 8 seconds
  tipTimer = setInterval(() => {
    tipIndex = (tipIndex + 1) % EDU_TIPS.length;
    renderTip();
  }, 8000);
}

function renderTip() {
  const tip  = EDU_TIPS[tipIndex];
  const icon = document.getElementById('tip-icon');
  const title = document.getElementById('tip-title');
  const text  = document.getElementById('tip-text');
  const dots  = document.querySelectorAll('.tip-dot');

  if (icon)  icon.textContent  = tip.icon;
  if (title) title.textContent = tip.title;
  if (text)  text.textContent  = tip.text;

  dots.forEach((d, i) => {
    d.className = 'tip-dot' + (i === tipIndex % Math.min(EDU_TIPS.length, 5) ? ' active' : '');
  });
}

function advanceTip(dir) {
  clearInterval(tipTimer);
  tipIndex = (tipIndex + dir + EDU_TIPS.length) % EDU_TIPS.length;
  renderTip();
  tipTimer = setInterval(() => {
    tipIndex = (tipIndex + 1) % EDU_TIPS.length;
    renderTip();
  }, 8000);
}

function showComparison(before, after) {
  const compView = document.getElementById('comparison-view');

  compView.style.display = 'block';

  // Calculate total risk scores
  const beforeScore = calculateTotalRisk(before);
  const afterScore = calculateTotalRisk(after);

  const beforeEl = document.getElementById('before-score');
  const afterEl = document.getElementById('after-score');

  beforeEl.textContent = beforeScore;
  afterEl.textContent = afterScore;

  // Style based on improvement
  beforeEl.className = 'comparison-value';
  afterEl.className = 'comparison-value';

  if (afterScore < beforeScore) {
    afterEl.classList.add('improved');
  } else if (afterScore > beforeScore) {
    afterEl.classList.add('worse');
  }

  // Show fixed issues
  const fixed = findFixedIssues(before, after);
  if (fixed.length > 0) {
    document.getElementById('fixed-items-section').style.display = 'block';
    const listEl = document.getElementById('fixed-items-list');
    listEl.innerHTML = fixed.map(item =>
      `<div class="fixed-item">${item}</div>`
    ).join('');
  } else {
    document.getElementById('fixed-items-section').style.display = 'none';
  }
}

function calculateTotalRisk(results) {
  return results.cookies.reduce((sum, item) => sum + (item.risk?.score || 0), 0);
}

function findFixedIssues(before, after) {
  const fixed = [];

  // Compare critical/high counts
  const beforeCritical = before.summary.critical || 0;
  const afterCritical = after.summary.critical || 0;
  const beforeHigh = before.summary.high || 0;
  const afterHigh = after.summary.high || 0;

  if (afterCritical < beforeCritical) {
    fixed.push(`${beforeCritical - afterCritical} critical issue(s) resolved`);
  }

  if (afterHigh < beforeHigh) {
    fixed.push(`${beforeHigh - afterHigh} high-risk issue(s) resolved`);
  }

  // Look for specific improvements
  const beforeIssues = new Set();
  const afterIssues = new Set();

  before.cookies.forEach(c => {
    if (c.risk && c.risk.issues) {
      c.risk.issues.forEach(i => beforeIssues.add(i.title));
    }
  });

  after.cookies.forEach(c => {
    if (c.risk && c.risk.issues) {
      c.risk.issues.forEach(i => afterIssues.add(i.title));
    }
  });

  beforeIssues.forEach(issue => {
    if (!afterIssues.has(issue)) {
      fixed.push(issue);
    }
  });

  return fixed;
}


function createCookieCard(item) {
  const div = document.createElement('div');

  const effectiveSeverity = getEffectiveSeverity(item);
  div.className = `cookie-card ${effectiveSeverity}`;

  const typeClass = item.classification.type === 'authentication' ? 'auth' : '';
  const reviewPill = item._needsReview ? '<span class="pill">Review</span>' : '';

  // Top issues (formatted)
  let issuesHTML = '';
  if (item.risk.issues && item.risk.issues.length > 0) {
    issuesHTML = '<div class="issue-list">';
    item.risk.issues.slice(0, 2).forEach(issue => {
      issuesHTML += `<div class="issue">${escapeHtml(formatIssueTitle(issue.title))}</div>`;
    });
    if (item.risk.issues.length > 2) {
      issuesHTML += `<div class="issue">+${item.risk.issues.length - 2} more</div>`;
    }
    issuesHTML += '</div>';
  }

  // Evidence chips
  const evidence = buildEvidence(item);
  const chipsHTML = evidence.length
    ? `<div class="chip-row">${evidence.map(c => `<span class="chip ${c.kind}">${escapeHtml(c.text)}</span>`).join('')}</div>`
    : '';

  const authConfPct = ((item.classification.confidence ?? 0) * 100).toFixed(0);
  const riskScore = item.risk?.score ?? 0;
  const riskLabel = (effectiveSeverity || 'info').toUpperCase();

  div.innerHTML = `
    <div class="cookie-header">
      <div class="cookie-name">${escapeHtml(item.cookie.name)}${reviewPill}</div>
      <div class="cookie-type ${typeClass}">${escapeHtml(item.classification.type)}</div>
    </div>

    <div class="mini-metrics">
      <div>Auth confidence: <strong>${authConfPct}%</strong></div>
      <div>Risk: <strong>${riskLabel}</strong> (${riskScore}/100)</div>
    </div>

    ${issuesHTML}
    ${chipsHTML}

    <div class="confidence">
      Auth confidence
      <div class="conf-bar">
        <div class="conf-fill" style="width: ${authConfPct}%"></div>
      </div>
    </div>
  `;

  div.addEventListener('click', () => showCookieDetails(item));
  return div;
}

function showCookieDetails(item) {
  currentModalItem = item;
  const modal = document.getElementById('cookie-modal');
  const nameEl = document.getElementById('modal-cookie-name');
  const bodyEl = document.getElementById('modal-body');

  nameEl.textContent = item.cookie.name;

  let detailsHTML = `
    <div class="modal-section">
      <div class="modal-section-title">Classification</div>
      <div class="modal-text">
        Type: <strong>${item.classification.type}</strong><br>
        Confidence: <strong>${(item.classification.confidence * 100).toFixed(1)}%</strong>
      </div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">Risk Assessment</div>
      <div class="modal-text">
        Severity: <strong>${item.risk.severity.toUpperCase()}</strong><br>
        Score: <strong>${item.risk.score}/100</strong>
      </div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">Cookie Attributes</div>
      <div class="modal-text">
        Domain: ${item.cookie.domain || '(host-only)'}<br>
        Path: ${item.cookie.path}<br>
        Secure: ${item.cookie.secure ? '✓ Yes' : '✗ No'}<br>
        HttpOnly: ${item.cookie.httpOnly ? '✓ Yes' : '✗ No'}<br>
        SameSite: ${formatSameSite(item.cookie.sameSite)}
      </div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">Evidence</div>
      <div class="modal-text">
        ${buildEvidence(item).map(c => `• ${escapeHtml(c.text)}`).join('<br>') || '• (No additional evidence)'}
        ${item._overrideNote ? `<br><br><em>${escapeHtml(item._overrideNote)}</em>` : ''}
      </div>
    </div>
  `;

  if (item.risk.issues && item.risk.issues.length > 0) {
    detailsHTML += `
      <div class="modal-section">
        <div class="modal-section-title">Security Issues</div>
        <div class="modal-text">
    `;
    item.risk.issues.forEach(issue => {
      detailsHTML += `
        <strong>[${issue.severity.toUpperCase()}] ${escapeHtml(formatIssueTitle(issue.title))}</strong><br>
        ${escapeHtml(issue.description)}<br><br>
      `;
    });
    detailsHTML += '</div></div>';
  }

  if (item.recommendations && item.recommendations.length > 0) {
    detailsHTML += `
      <div class="modal-section">
        <div class="modal-section-title">Recommendations</div>
        <div class="modal-text">
    `;
    item.recommendations.forEach(rec => {
      detailsHTML += `• ${escapeHtml(rec)}<br>`;
    });
    detailsHTML += '</div></div>';
  }

  // ══════════════════════════════════════════════════════════
  // Human Explanation Mode — "Why This Matters"
  // ══════════════════════════════════════════════════════════
  const humanExpl = buildHumanExplanation(item);
  if (humanExpl) {
    detailsHTML += `
      <div class="modal-section">
        <div class="human-explanation">
          <div class="human-explanation-title">💡 Why this matters</div>
          <div class="human-explanation-text">${humanExpl}</div>
        </div>
      </div>
    `;
  }

  // ══════════════════════════════════════════════════════════
  // Personal Protection Recommendations
  // ══════════════════════════════════════════════════════════
  const protectionTips = buildProtectionTips(item);
  if (protectionTips.length > 0) {
    detailsHTML += `
      <div class="modal-section">
        <div class="protection-section">
          <div class="protection-title">🛡️ What you can do</div>
          ${protectionTips.map(tip => `<div class="protection-item">${escapeHtml(tip)}</div>`).join('')}
        </div>
      </div>
    `;
  }

  // ══════════════════════════════════════════════════════════
  // CookieGuard 2.0: "Why the AI flagged this cookie"
  // ══════════════════════════════════════════════════════════
  if (item.explanations) {
    const expl = item.explanations;
    const allSignals = [
      ...(expl.auth_signals || []),
      ...(expl.tracking_signals || []),
    ];

    if (allSignals.length > 0 || (expl.risk_signals && expl.risk_signals.length > 0)) {
      detailsHTML += `
        <div class="modal-section explanation-section">
          <div class="modal-section-title">🧠 Why the AI flagged this cookie</div>
          <div class="modal-text">
      `;

      // Classification signals
      if (allSignals.length > 0) {
        detailsHTML += '<div class="explanation-group"><strong>Classification signals:</strong></div>';
        allSignals.slice(0, 5).forEach(sig => {
          const icon = sig.direction === 'positive' ? '🔵' : '⚪';
          detailsHTML += `<div class="explanation-item">${icon} <strong>${escapeHtml(sig.signal)}</strong></div>`;
          if (sig.detail) {
            detailsHTML += `<div class="explanation-detail">${escapeHtml(sig.detail)}</div>`;
          }
        });
      }

      // Risk exposure signals
      if (expl.risk_signals && expl.risk_signals.length > 0) {
        detailsHTML += '<br><div class="explanation-group"><strong>Risk exposure signals:</strong></div>';
        expl.risk_signals.slice(0, 3).forEach(sig => {
          detailsHTML += `<div class="explanation-item">🔴 <strong>${escapeHtml(sig.signal)}</strong></div>`;
          if (sig.detail) {
            detailsHTML += `<div class="explanation-detail">${escapeHtml(sig.detail)}</div>`;
          }
        });
      }

      // Risk formula
      if (expl.risk_formula) {
        const rf = expl.risk_formula;
        const c = rf.components || {};
        detailsHTML += `
          <br><div class="explanation-group"><strong>Risk formula:</strong></div>
          <div class="risk-formula-box">
            <code>${escapeHtml(rf.formula)}</code><br>
            <span class="formula-values">
              Auth gate: P(auth)=${c.auth_gate?.toFixed(2) || '?'} ${(c.auth_gate || 0) > 0.3 ? '✓ active' : '✗ inactive'}<br>
              Severity: ${c.severity_points || 0} pts ×
              Breadth: ${c.breadth_factor?.toFixed(1) || '1.0'}× ×
              Lifetime: ${c.lifetime_factor?.toFixed(1) || '1.0'}×
              = <strong>${c.estimated_score || 0}/100</strong>
            </span><br>
            <em>${escapeHtml(rf.interpretation || '')}</em>
          </div>
        `;
      }

      detailsHTML += '</div></div>';
    }
  }

  // ══════════════════════════════════════════════════════════
  // CookieGuard 2.0: "Attack Simulation"
  // ══════════════════════════════════════════════════════════
  if (item.attack_simulation && item.attack_simulation.paths && item.attack_simulation.paths.length > 0) {
    const sim = item.attack_simulation;

    detailsHTML += `
      <div class="modal-section attack-sim-section">
        <div class="modal-section-title">⚔️ Attack Simulation</div>
        <div class="modal-text">
          <div class="attack-badges">
    `;

    // Attack path badges
    sim.paths.forEach(path => {
      const badgeClass = path.severity === 'critical' ? 'badge-critical' :
                         path.severity === 'high' ? 'badge-high' :
                         path.severity === 'medium' ? 'badge-medium' : 'badge-low';
      detailsHTML += `<span class="attack-badge ${badgeClass}">${escapeHtml(path.type)}</span>`;
    });

    detailsHTML += `</div>`;

    // Impact summary
    if (sim.impact) {
      detailsHTML += `<div class="attack-impact"><strong>Impact:</strong> ${escapeHtml(sim.impact)}</div>`;
    }

    // Individual paths
    sim.paths.forEach(path => {
      detailsHTML += `
        <div class="attack-path">
          <div class="attack-path-title">${escapeHtml(path.name)} <span class="severity-tag ${path.severity}">[${path.severity.toUpperCase()}]</span></div>
          <div class="attack-path-desc">${escapeHtml(path.description)}</div>
          <div class="attack-path-technique"><strong>Technique:</strong> <code>${escapeHtml(path.technique)}</code></div>
        </div>
      `;
    });

    // Fixes
    if (sim.fixes && sim.fixes.length > 0) {
      detailsHTML += `<br><div class="explanation-group"><strong>🛡️ What you can do:</strong></div>`;
      sim.fixes.forEach(fix => {
        detailsHTML += `
          <div class="fix-item">
            <strong>${escapeHtml(fix.fix)}</strong><br>
            <span class="fix-impact">${escapeHtml(fix.impact)}</span><br>
            <code class="fix-code">${escapeHtml(fix.code)}</code>
            ${fix.site_should_fix ? `<div class="site-fix-note">Site should fix: <code>${escapeHtml(fix.site_should_fix)}</code></div>` : ''}
          </div>
        `;
      });
    }

    // Overall risk
    detailsHTML += `<div class="attack-overall"><strong>Overall:</strong> ${escapeHtml(sim.overall_risk)}</div>`;

    detailsHTML += '</div></div>';
  }

  bodyEl.innerHTML = detailsHTML;
  document.body.style.width = '560px';
  modal.classList.add('active');
}

function closeModal() {
  document.getElementById('cookie-modal').classList.remove('active');
  document.body.style.width = '320px';
}


function markCurrentCookieNotAuth() {
  if (!currentModalItem) return;
  const key = prefKeyForCookie(currentModalItem);
  userPrefs.overrides = userPrefs.overrides || {};
  userPrefs.overrides[key] = 'not_auth';
  saveUserPrefs();
  // Refresh view
  closeModal();
  if (analysisResults) {
    displayResults(analysisResults);
    showResultsView();
  }
}

function ignoreCurrentCookie() {
  if (!currentModalItem) return;
  const key = prefKeyForCookie(currentModalItem);
  userPrefs.ignored = userPrefs.ignored || {};
  userPrefs.ignored[key] = true;
  saveUserPrefs();
  closeModal();
  if (analysisResults) {
    displayResults(analysisResults);
    showResultsView();
  }
}


// === EXPORT ===

function exportReport() {
  if (!analysisResults) {
    alert('No results to export');
    return;
  }

  const summary = analysisResults.summary;

  const report = `
CookieGuard AI Security Report
==============================
Domain: ${currentDomain}
Scan Date: ${new Date().toISOString()}
Analysis Mode: ${window.CookieGuardEngine ? 'AI Engine (ONNX + Rules)' : 'Rule-Based'}

SUMMARY
-------
Total Cookies: ${summary.total_cookies}
Critical: ${summary.critical}
High: ${summary.high}
Medium: ${summary.medium}
Low: ${summary.low}

DETAILED FINDINGS
-----------------
${analysisResults.cookies.map((item, i) => `
${i + 1}. ${item.cookie.name}
   Type: ${item.classification.type} (${(item.classification.confidence * 100).toFixed(0)}% confidence)
   Severity: ${item.risk.severity.toUpperCase()}
   Score: ${item.risk.score}/100

   Issues:
${item.risk.issues.map(issue => `   • ${issue.title}: ${issue.description}`).join('\n')}

   Recommendations:
${item.recommendations.map(rec => `   • ${rec}`).join('\n')}
`).join('\n')}

==============================
Generated by CookieGuard AI
Privacy-first cookie security scanner
  `.trim();

  navigator.clipboard.writeText(report).then(() => {
    alert('✓ Report copied to clipboard!');
  }).catch(err => {
    alert('Failed to copy report: ' + err.message);
  });
}

async function exportCookiesAsJson() {
  try {
    let allCookies;

    if (typeof chrome !== 'undefined' && chrome.cookies) {
      allCookies = await chrome.cookies.getAll({});
    } else {
      // Demo mode
      allCookies = [
        { name: 'demo_cookie', domain: 'demo-mode', path: '/', value: 'demo' }
      ];
    }

    if (allCookies.length === 0) {
      alert('No cookies found!');
      return;
    }

    const exportData = {
      exported_at: new Date().toISOString(),
      domain: currentDomain,
      total_cookies: allCookies.length,
      cookies: allCookies
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cookies_${currentDomain}_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);

  } catch (error) {
    console.error('Export error:', error);
    alert('Export failed: ' + error.message);
  }
}


function formatSameSite(v) {
  if (!v) return 'None';
  const s = String(v).toLowerCase();
  if (s === 'no_restriction') return 'None';
  if (s === 'none') return 'None';
  if (s === 'lax') return 'Lax';
  if (s === 'strict') return 'Strict';
  return v;
}


// === USER PREFS (Overrides / Ignore) ===

async function loadUserPrefs() {
  if (typeof chrome === 'undefined' || !chrome.storage || !chrome.storage.local) {
    return; // Silently skip when not in extension context
  }
  try {
    const data = await chrome.storage.local.get(['cookieguard_prefs_v1']);
    if (data && data.cookieguard_prefs_v1) {
      userPrefs = data.cookieguard_prefs_v1;
    }
  } catch (e) {
    // Silently ignore storage errors
  }
}

async function saveUserPrefs() {
  if (typeof chrome === 'undefined' || !chrome.storage || !chrome.storage.local) {
    return; // Silently skip when not in extension context
  }
  try {
    await chrome.storage.local.set({ cookieguard_prefs_v1: userPrefs });
  } catch (e) {
    // Silently ignore storage errors
  }
}

function prefKeyForCookie(item) {
  const name = item?.cookie?.name || item?.cookie_name || '(unknown)';
  return `${currentDomain}||${name}`;
}

function applyUserOverrides(item) {
  const key = prefKeyForCookie(item);
  const override = userPrefs.overrides?.[key];
  if (override === 'not_auth') {
    // Override classification to reduce false positives
    item.classification = item.classification || {};
    item.classification.type = 'other';
    item.classification.confidence = Math.min(item.classification.confidence ?? 0.6, 0.55);
    item._overrideNote = 'User marked as not auth';
  }
  return item;
}

function isIgnored(item) {
  const key = prefKeyForCookie(item);
  return Boolean(userPrefs.ignored?.[key]);
}

function getEffectiveSeverity(item) {
  const sev = item?.risk?.severity || 'info';
  const conf = item?.classification?.confidence ?? 0.0;

  // Downgrade noisy alerts when auth confidence is low
  if ((sev === 'critical' || sev === 'high') && conf < UI_CONFIG.reviewConfidenceThreshold) {
    item._needsReview = true;
    return 'medium';
  }
  item._needsReview = false;
  return sev;
}

function formatIssueTitle(title) {
  if (!title) return '';
  return title
    .replace(/^Missing\s+/i, 'Risk: ')
    .replace(/\s+Flag$/i, ' not set')
    .replace(/\s+Protection$/i, ' protection weak');
}

function isFirstParty(cookie) {
  const d = (cookie?.domain || '').replace(/^\./, '');
  return d === currentDomain || d.endsWith('.' + currentDomain);
}

function buildEvidence(item) {
  const chips = [];

  // Context chips (first/third party + scope)
  const fp = isFirstParty(item.cookie) ? 'First-party' : 'Third-party';
  chips.push({ text: fp, kind: 'primary' });

  if (item.cookie?.hostOnly) {
    chips.push({ text: 'Host-only scope', kind: 'primary' });
  } else if (item.cookie?.domain && String(item.cookie.domain).startsWith('.')) {
    chips.push({ text: 'Shared across subdomains', kind: 'warn' });
  }

  // Name patterns
  const n = (item.cookie?.name || '').toLowerCase();
  if (/(session|sid|auth|token|login)/.test(n)) {
    chips.push({ text: 'Identity keyword in name', kind: 'primary' });
  }

  // Behavior signals from backend (CookieGuard 2.0)
  if (item.behavior_signals) {
    if (item.behavior_signals.changed_during_login) {
      chips.push({ text: 'Changed during login', kind: 'primary' });
    }
    if (item.behavior_signals.new_after_login) {
      chips.push({ text: 'New after login', kind: 'primary' });
    }
    if (item.behavior_signals.rotated_after_login) {
      chips.push({ text: 'Rotated at login', kind: 'primary' });
    }
    if (item.behavior_signals.third_party) {
      chips.push({ text: 'Third-party context', kind: 'warn' });
    }
  } else {
    // Fallback: check from analysisResults context
    const changed = analysisResults?.context?.changedCookies || [];
    if (changed.includes(item.cookie?.name)) {
      chips.push({ text: 'Changed during login', kind: 'primary' });
    }
  }

  // Misconfig signals
  if (item.risk?.issues?.some(i => (i.title || '').toLowerCase().includes('httponly'))) {
    chips.push({ text: 'XSS exposure risk', kind: 'bad' });
  }
  if (item.risk?.issues?.some(i => (i.title || '').toLowerCase().includes('samesite'))) {
    chips.push({ text: 'Cross-site abuse risk', kind: 'warn' });
  }
  if (item.risk?.issues?.some(i => (i.title || '').toLowerCase().includes('secure'))) {
    chips.push({ text: 'Network interception risk', kind: 'warn' });
  }

  // Attack simulation badge count (2.0)
  if (item.attack_simulation && item.attack_simulation.path_count > 0) {
    chips.push({ text: `${item.attack_simulation.path_count} attack path(s)`, kind: 'bad' });
  }

  // Cap
  return chips.slice(0, UI_CONFIG.maxEvidenceChips + 2); // Allow a couple more for 2.0
}


// === HUMAN EXPLANATION MODE ===

function buildHumanExplanation(item) {
  const cookie = item.cookie;
  const type = item.classification?.type;
  const issues = item.risk?.issues || [];
  const parts = [];

  // What this cookie does
  if (type === 'authentication') {
    parts.push(`This cookie keeps you logged into <strong>${escapeHtml(cookie.domain || 'this website')}</strong>.`);
  } else if (type === 'tracking') {
    parts.push(`This cookie tracks your activity across websites to build an advertising profile.`);
  } else if (type === 'preference') {
    parts.push(`This cookie remembers your settings and preferences on the site.`);
  } else {
    parts.push(`This cookie stores information used by the website during your visit.`);
  }

  // What's wrong in plain English
  const hasHttpOnlyIssue = issues.some(i => (i.title || '').toLowerCase().includes('httponly'));
  const hasSecureIssue = issues.some(i => (i.title || '').toLowerCase().includes('secure'));
  const hasSameSiteIssue = issues.some(i => (i.title || '').toLowerCase().includes('samesite'));
  const hasWildcardIssue = issues.some(i => (i.title || '').toLowerCase().includes('wildcard'));

  if (hasHttpOnlyIssue) {
    parts.push(`Because the <strong>HttpOnly flag is missing</strong>, a malicious script could steal this cookie and access your account without your password.`);
  }
  if (hasSecureIssue) {
    parts.push(`The <strong>Secure flag is missing</strong>, so this cookie can be transmitted over unencrypted connections — making it vulnerable on public WiFi.`);
  }
  if (hasSameSiteIssue) {
    parts.push(`Without <strong>SameSite protection</strong>, another website could trick your browser into sending this cookie to perform actions on your behalf.`);
  }
  if (hasWildcardIssue) {
    parts.push(`This cookie is shared across all subdomains, so a vulnerability on any subdomain could expose your session.`);
  }

  return parts.join(' ');
}

function buildProtectionTips(item) {
  const tips = [];
  const cookie = item.cookie;
  const type = item.classification?.type;
  const severity = item.risk?.severity;
  const issues = item.risk?.issues || [];

  if (type === 'authentication' && (severity === 'critical' || severity === 'high')) {
    tips.push('Log out of sensitive sites when using shared or public computers.');
    tips.push('Avoid using this site on public WiFi without a VPN.');
  }

  if (issues.some(i => (i.title || '').toLowerCase().includes('httponly'))) {
    tips.push('Enable a browser content-security policy extension to limit script access.');
  }

  if (issues.some(i => (i.title || '').toLowerCase().includes('secure'))) {
    tips.push('Always verify you are on HTTPS (🔒 lock icon) before logging in.');
  }

  if (type === 'tracking') {
    tips.push('Consider a browser extension like uBlock Origin to block tracking cookies.');
  }

  // Always add general tips for auth cookies
  if (type === 'authentication') {
    tips.push('Enable two-factor authentication (2FA) on this account for stronger protection.');
    tips.push('Clear cookies after each session on shared devices.');
  }

  return tips.slice(0, 4); // cap at 4 tips
}

// === UTILITIES ===

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
  const cookieModal = document.getElementById('cookie-modal');
  const modelModal = document.getElementById('model-modal');

  if (e.target === cookieModal) {
    closeModal();
  }
  if (e.target === modelModal) {
    closeModelModal();
  }
});