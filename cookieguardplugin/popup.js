// popup.js - CookieGuard with Backend Integration

let currentDomain = '';
let beforeLoginCookies = null;
let afterLoginCookies = null;
let analysisResults = null;
let lastExtractedCookies = null; // Store for export

// Configuration - Change this to enable backend
const CONFIG = {
  useBackend: true, // Set to true to use Flask backend
  backendURL: 'http://localhost:5000', // Your Flask API URL (port 5000!)
  analysisMode: 'backend' // 'local' or 'backend'
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Try to get current tab domain (may fail on chrome:// pages)
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url && !tab.url.startsWith('chrome://')) {
      const url = new URL(tab.url);
      currentDomain = url.hostname;
    } else {
      currentDomain = 'demo-mode';
    }
  } catch (e) {
    currentDomain = 'demo-mode';
  }
  
  document.getElementById('domain-name').textContent = currentDomain;
  
  // Event listeners
  document.getElementById('scan-btn').addEventListener('click', handleDemoScan);
  document.getElementById('login-scan-btn').addEventListener('click', showLoginFlow);
  document.getElementById('back-btn').addEventListener('click', showMainView);
  document.getElementById('login-back-btn').addEventListener('click', showMainView);
  document.getElementById('export-btn').addEventListener('click', exportReport);
  
  // NEW: Demo and Export/Import buttons
  const demoBtn = document.getElementById('demo-btn');
  if (demoBtn) demoBtn.addEventListener('click', handleDemoScan);
  
  const exportCookiesBtn = document.getElementById('export-cookies-btn');
  if (exportCookiesBtn) exportCookiesBtn.addEventListener('click', exportCookiesAsJson);
  
  const importCookiesBtn = document.getElementById('import-cookies-btn');
  if (importCookiesBtn) importCookiesBtn.addEventListener('click', () => {
    document.getElementById('import-file-input').click();
  });
  
  const importFileInput = document.getElementById('import-file-input');
  if (importFileInput) importFileInput.addEventListener('change', importCookiesFromJson);
  
  // Login flow buttons
  document.getElementById('capture-before-btn')?.addEventListener('click', captureBeforeLogin);
  document.getElementById('capture-after-btn')?.addEventListener('click', captureAfterLogin);
  
  // Check backend availability if enabled
  if (CONFIG.useBackend) {
    checkBackendHealth();
  }
  
  // Show backend status
  updateBackendStatus();
});

// === BACKEND STATUS DISPLAY ===

function updateBackendStatus() {
  const statusEl = document.getElementById('backend-status');
  if (statusEl) {
    statusEl.textContent = CONFIG.analysisMode === 'backend' ? '🟢 Backend connected' : '🟡 Local mode';
  }
}

// === VIEW MANAGEMENT ===

function showMainView() {
  document.getElementById('main-view').style.display = 'block';
  document.getElementById('loading-view').style.display = 'none';
  document.getElementById('results-view').style.display = 'none';
  document.getElementById('login-flow-view').style.display = 'none';
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
}

function showLoginFlow() {
  document.getElementById('main-view').style.display = 'none';
  document.getElementById('loading-view').style.display = 'none';
  document.getElementById('results-view').style.display = 'none';
  document.getElementById('login-flow-view').style.display = 'block';
  
  beforeLoginCookies = null;
  afterLoginCookies = null;
  document.getElementById('step-1').classList.add('active');
  document.getElementById('step-2').classList.remove('active', 'completed');
  document.getElementById('step-3').classList.remove('active', 'completed');
  document.getElementById('capture-before-btn').disabled = false;
  document.getElementById('capture-after-btn').disabled = true;
}

// === BACKEND HEALTH CHECK ===

async function checkBackendHealth() {
  try {
    const response = await fetch(`${CONFIG.backendURL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000) // 2 second timeout
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('✓ Backend available:', data);
      CONFIG.analysisMode = 'backend';
    } else {
      console.log('⚠️ Backend not responding, using local analysis');
      CONFIG.analysisMode = 'local';
    }
  } catch (error) {
    console.log('⚠️ Backend not available, using local analysis');
    CONFIG.analysisMode = 'local';
  }
  updateBackendStatus();
}

// === DEMO MODE ===

async function handleDemoScan() {
  showLoadingView();
  console.log('🎮 Running demo scan...');

  try {
    // Step 1: Get demo cookies from backend
    console.log('Step 1: Fetching demo cookies...');
    const demoResponse = await fetch(`${CONFIG.backendURL}/api/demo`);
    const demoData = await demoResponse.json();
    console.log('Demo data:', demoData);

    const cookies = demoData.cookies || [];
    if (cookies.length === 0) {
      throw new Error('No demo cookies returned');
    }

    // Step 2: Send to analyze endpoint
    console.log('Step 2: Analyzing cookies...');
    const analyzeResponse = await fetch(`${CONFIG.backendURL}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookies: cookies })
    });
    const analyzeData = await analyzeResponse.json();
    console.log('Analyze data:', analyzeData);

    if (analyzeData.error) {
      throw new Error(analyzeData.error);
    }

    // Step 3: Display results directly
    currentDomain = 'demo-mode';
    document.getElementById('domain-name').textContent = 'Demo Mode';

    // Simple display
    const summary = analyzeData.summary_stats || { total: cookies.length, critical: 0, high: 0, medium: 0, low: 0 };
    document.getElementById('risk-summary').innerHTML = `
      <div class="stat critical">
        <div class="stat-num">${summary.critical || 0}</div>
        <div class="stat-label">Critical</div>
      </div>
      <div class="stat high">
        <div class="stat-num">${summary.high || 0}</div>
        <div class="stat-label">High</div>
      </div>
      <div class="stat medium">
        <div class="stat-num">${summary.medium || 0}</div>
        <div class="stat-label">Medium</div>
      </div>
      <div class="stat low">
        <div class="stat-num">${summary.low || 0}</div>
        <div class="stat-label">Low</div>
      </div>
    `;

    // Display cookie results
    const listDiv = document.getElementById('cookie-list');
    listDiv.innerHTML = '';

    (analyzeData.results || []).forEach(result => {
      const severity = result.risk_assessment?.severity || 'low';
      const cookieName = result.cookie_name || 'Unknown';
      const cookieType = result.ml_classification?.type || 'unknown';
      const confidence = result.ml_classification?.confidence || 0;
      const issues = result.issues || [];

      const card = document.createElement('div');
      card.className = `cookie-card ${severity}`;
      card.innerHTML = `
        <div class="cookie-header">
          <div class="cookie-name">${cookieName}</div>
          <div class="cookie-type ${cookieType === 'authentication' ? 'auth' : ''}">${cookieType}</div>
        </div>
        ${issues.length > 0 ? `<div class="issues">${issues.map(i => `<div class="issue">⚠ ${i.title}</div>`).join('')}</div>` : ''}
        <div class="confidence">
          Confidence: ${(confidence * 100).toFixed(0)}%
          <div class="conf-bar">
            <div class="conf-fill" style="width: ${confidence * 100}%"></div>
          </div>
        </div>
      `;
      listDiv.appendChild(card);
    });

    showResultsView();

  } catch (error) {
    console.error('Demo error:', error);
    alert('Demo failed: ' + error.message);
    showMainView();
  }
}

// === EXPORT COOKIES AS JSON ===

async function exportCookiesAsJson() {
  try {
    let cookiesToExport;

    // Use last extracted cookies if available, otherwise try to get from current domain
    if (lastExtractedCookies && lastExtractedCookies.length > 0) {
      cookiesToExport = lastExtractedCookies;
    } else {
      cookiesToExport = await getCookiesForDomain(currentDomain);
    }

    if (!cookiesToExport || cookiesToExport.length === 0) {
      // If still no cookies, get ALL cookies
      cookiesToExport = await chrome.cookies.getAll({});
    }

    console.log(`Exporting ${cookiesToExport.length} cookies`);

    const exportData = {
      exported_at: new Date().toISOString(),
      domain: currentDomain,
      total_cookies: cookiesToExport.length,
      cookies: cookiesToExport.map(c => ({
        name: c.name,
        value: c.value || '',
        domain: c.domain,
        path: c.path || '/',
        secure: c.secure || false,
        httpOnly: c.httpOnly || false,
        sameSite: c.sameSite || null,
        expirationDate: c.expirationDate || null,
        hostOnly: c.hostOnly || false,
        session: c.session || false
      }))
    };

    const jsonString = JSON.stringify(exportData, null, 2);

    // Create download
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cookies_${currentDomain}_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    alert(`✓ Exported ${cookiesToExport.length} cookies!\n\nYou can upload this JSON to the backend UI for analysis.`);

  } catch (error) {
    console.error('Export error:', error);
    alert('Export failed: ' + error.message);
  }
}

// === IMPORT COOKIES FROM JSON ===

async function importCookiesFromJson(event) {
  const file = event.target.files[0];
  if (!file) return;

  showLoadingView();

  try {
    const text = await file.text();
    const data = JSON.parse(text);

    let cookies;
    if (data.cookies && Array.isArray(data.cookies)) {
      cookies = data.cookies;
    } else if (Array.isArray(data)) {
      cookies = data;
    } else {
      throw new Error('Invalid JSON format. Expected { cookies: [...] } or [...]');
    }

    console.log(`Imported ${cookies.length} cookies from file`);
    lastExtractedCookies = cookies;
    currentDomain = data.domain || 'imported';
    document.getElementById('domain-name').textContent = `Imported: ${file.name}`;

    // Analyze imported cookies
    let results;
    if (CONFIG.analysisMode === 'backend') {
      results = await analyzeWithBackend(cookies, { behavioral: false });
    } else {
      results = await analyzeLocally(cookies, { behavioral: false });
    }

    if (!results || !results.cookies) {
      throw new Error('Invalid response from analysis');
    }

    analysisResults = results;
    displayResults(results);
    showResultsView();

  } catch (error) {
    console.error('Import error:', error);
    alert('Import failed: ' + error.message);
    showMainView();
  }

  // Reset file input
  event.target.value = '';
}

// === QUICK SCAN (Main feature) ===

async function handleQuickScan() {
  showLoadingView();

  try {
    const cookies = await getCookiesForDomain(currentDomain);

    console.log(`Found ${cookies.length} cookies for ${currentDomain}:`, cookies);

    // Check if any cookies were found
    if (cookies.length === 0) {
      alert(`No cookies found for ${currentDomain}.\n\nTry visiting the site and logging in first.`);
      showMainView();
      return;
    }

    // Choose analysis method
    let results;
    if (CONFIG.analysisMode === 'backend') {
      results = await analyzeWithBackend(cookies, { behavioral: false });
    } else {
      results = await analyzeLocally(cookies, { behavioral: false });
    }

    // Validate results
    if (!results || !results.cookies) {
      throw new Error('Invalid response from analysis');
    }

    analysisResults = results;
    displayResults(results);
    showResultsView();

  } catch (error) {
    console.error('Scan error:', error);
    alert('Scan failed: ' + error.message);
    showMainView();
  }
}

// === LOGIN-AWARE SCAN ===

async function captureBeforeLogin() {
  const btn = document.getElementById('capture-before-btn');
  btn.disabled = true;
  btn.textContent = 'Capturing...';

  try {
    beforeLoginCookies = await getCookiesForDomain(currentDomain);

    document.getElementById('step-1').classList.remove('active');
    document.getElementById('step-1').classList.add('completed');
    document.getElementById('step-2').classList.add('active');

    btn.textContent = `✓ Captured ${beforeLoginCookies.length} cookies`;
    document.getElementById('capture-after-btn').disabled = false;

  } catch (error) {
    alert('Capture failed: ' + error.message);
    btn.disabled = false;
    btn.textContent = 'Capture Before Login';
  }
}

async function captureAfterLogin() {
  const btn = document.getElementById('capture-after-btn');
  btn.disabled = true;
  btn.textContent = 'Analyzing...';

  try {
    afterLoginCookies = await getCookiesForDomain(currentDomain);

    document.getElementById('step-2').classList.remove('active');
    document.getElementById('step-2').classList.add('completed');
    document.getElementById('step-3').classList.add('active');

    const newCookies = identifyNewCookies(beforeLoginCookies, afterLoginCookies);

    // Enhanced analysis with behavioral signals
    let results;
    if (CONFIG.analysisMode === 'backend') {
      results = await analyzeWithBackend(afterLoginCookies, {
        behavioral: true,
        newCookieNames: newCookies.map(c => c.name),
        beforeSnapshot: beforeLoginCookies
      });
    } else {
      results = await analyzeLocally(afterLoginCookies, {
        behavioral: true,
        newCookieNames: newCookies.map(c => c.name),
        beforeSnapshot: beforeLoginCookies
      });
    }

    analysisResults = results;
    displayResults(results);
    showResultsView();

  } catch (error) {
    alert('Analysis failed: ' + error.message);
    btn.disabled = false;
    btn.textContent = 'Capture After Login';
  }
}

function identifyNewCookies(before, after) {
  const beforeNames = new Set(before.map(c => c.name));
  return after.filter(c => !beforeNames.has(c.name));
}

// === COOKIE EXTRACTION ===

async function getCookiesForDomain(domain) {
  const allCookies = await chrome.cookies.getAll({});

  return allCookies.filter(cookie => {
    const cookieDomain = cookie.domain.startsWith('.')
      ? cookie.domain.substring(1)
      : cookie.domain;
    return domain.endsWith(cookieDomain) || cookieDomain.endsWith(domain);
  });
}

// === BACKEND ANALYSIS ===

async function analyzeWithBackend(cookies, options = {}) {
  console.log('🌐 Using backend analysis...');
  console.log(`Sending ${cookies.length} cookies to backend`);

  try {
    // Format cookies for backend API
    const payload = {
      cookies: cookies.map(c => ({
        name: c.name,
        value: c.value,
        domain: c.domain,
        path: c.path,
        secure: c.secure,
        httpOnly: c.httpOnly,
        sameSite: c.sameSite || null,
        expirationDate: c.expirationDate || null,
        hostOnly: c.hostOnly,
        session: c.session
      })),
      options: options
    };

    console.log('Payload:', JSON.stringify(payload, null, 2));

    const response = await fetch(`${CONFIG.backendURL}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    // Get response body for error details
    const data = await response.json();

    if (!response.ok) {
      console.error('Backend error response:', data);
      throw new Error(data.error || `Backend error: ${response.status}`);
    }

    console.log('Backend response:', data);

    // Validate response has required fields
    if (!data.results || !Array.isArray(data.results)) {
      throw new Error('Invalid backend response: missing results array');
    }

    // Transform backend response to match local format
    return {
      cookies: data.results.map(result => {
        // Find original cookie data to include full details
        const originalCookie = cookies.find(c => c.name === result.cookie_name) || {};

        return {
          cookie: {
            name: result.cookie_name || 'unknown',
            domain: result.cookie_domain || originalCookie.domain || '',
            path: originalCookie.path || '/',
            secure: originalCookie.secure || false,
            httpOnly: originalCookie.httpOnly || false,
            sameSite: originalCookie.sameSite || null,
            ...originalCookie
          },
          classification: result.ml_classification || { type: 'unknown', confidence: 0, probabilities: {} },
          risk: result.risk_assessment || { score: 0, severity: 'low', issues: [] },
          features: result.features || {}
        };
      }),
      summary: data.summary_stats || generateDefaultSummary()
    };

  } catch (error) {
    console.error('Backend analysis failed:', error);
    console.log('⚠️ Falling back to local analysis');
    return analyzeLocally(cookies, options);
  }
}

// === LOCAL ANALYSIS (Fallback) ===

async function analyzeLocally(cookies, options = {}) {
  console.log('💻 Using local analysis...');

  const results = [];

  for (const cookie of cookies) {
    const features = extractFeatures(cookie, options);
    const classification = classifyCookie(features);
    const risk = calculateRiskScore(cookie, classification, options);

    results.push({
      cookie: cookie,
      classification: classification,
      risk: risk,
      features: features
    });
  }

  results.sort((a, b) => b.risk.score - a.risk.score);

  return {
    cookies: results,
    summary: generateSummary(results)
  };
}

// === FEATURE EXTRACTION (Local) ===

function extractFeatures(cookie, options) {
  return {
    has_secure: cookie.secure ? 1 : 0,
    has_httponly: cookie.httpOnly ? 1 : 0,
    has_samesite: cookie.sameSite ? 1 : 0,
    samesite_level: getSameSiteLevel(cookie.sameSite),
    is_session: !cookie.expirationDate,
    expiry_days: getExpiryDays(cookie.expirationDate),
    domain_is_wildcard: cookie.domain.startsWith('.') ? 1 : 0,
    domain_depth: cookie.domain.split('.').length,
    path_is_root: cookie.path === '/' ? 1 : 0,
    name_matches_auth: matchesAuthPattern(cookie.name) ? 1 : 0,
    name_matches_tracking: matchesTrackingPattern(cookie.name) ? 1 : 0,
    name_matches_preference: matchesPreferencePattern(cookie.name) ? 1 : 0,
    value_length: cookie.value.length,
    value_looks_like_jwt: cookie.value.split('.').length === 3 ? 1 : 0,
    value_entropy: estimateEntropy(cookie.value),
    appears_after_login: options.newCookieNames?.includes(cookie.name) ? 1 : 0
  };
}

function getSameSiteLevel(sameSite) {
  if (sameSite === 'strict') return 2;
  if (sameSite === 'lax') return 1;
  return 0;
}

function getExpiryDays(expirationDate) {
  if (!expirationDate) return 0;
  const now = Date.now() / 1000;
  const days = (expirationDate - now) / 86400;
  return Math.max(0, Math.min(days, 365));
}

function matchesAuthPattern(name) {
  const patterns = /session|sess|auth|token|login|user|jwt|bearer|sid|ssid/i;
  return patterns.test(name);
}

function matchesTrackingPattern(name) {
  const patterns = /^_ga|^_gid|analytics|tracking|^utm|facebook|doubleclick/i;
  return patterns.test(name);
}

function matchesPreferencePattern(name) {
  const patterns = /lang|locale|theme|timezone|currency|consent|preferences|settings/i;
  return patterns.test(name);
}

function estimateEntropy(value) {
  const chars = new Set(value);
  return Math.min(chars.size / value.length, 1) * 5;
}

// === LOCAL ML CLASSIFICATION ===

function classifyCookie(features) {
  let authScore = 0;
  let trackingScore = 0;
  let preferenceScore = 0;

  if (features.name_matches_auth) authScore += 0.5;
  if (features.has_httponly) authScore += 0.3;
  if (features.value_looks_like_jwt) authScore += 0.4;
  if (features.appears_after_login) authScore += 0.6;
  if (features.is_session) authScore += 0.2;

  if (features.name_matches_tracking) trackingScore += 0.8;
  if (!features.has_httponly && !features.has_secure) trackingScore += 0.2;
  if (features.expiry_days > 180) trackingScore += 0.3;

  if (features.name_matches_preference) preferenceScore += 0.7;
  if (features.value_length < 20) preferenceScore += 0.2;

  const total = authScore + trackingScore + preferenceScore;
  if (total === 0) {
    return {
      type: 'other',
      confidence: 0.5,
      probabilities: {
        authentication: 0.25,
        tracking: 0.25,
        preference: 0.25,
        other: 0.25
      }
    };
  }

  const probs = {
    authentication: authScore / total,
    tracking: trackingScore / total,
    preference: preferenceScore / total,
    other: 0.1
  };

  const winner = Object.entries(probs).reduce((a, b) => a[1] > b[1] ? a : b);

  return {
    type: winner[0],
    confidence: winner[1],
    probabilities: probs
  };
}

// === RISK SCORING ===

function calculateRiskScore(cookie, classification, options) {
  let score = 0;
  const issues = [];
  let severity = 'low';

  const isAuth = classification.type === 'authentication' ||
                 classification.probabilities.authentication > 0.3;

  if (isAuth) {
    if (!cookie.httpOnly) {
      score += 40;
      severity = 'critical';
      issues.push({
        severity: 'critical',
        title: 'Missing HttpOnly Flag',
        description: 'Authentication cookie can be accessed by JavaScript, vulnerable to XSS attacks.'
      });
    }

    if (!cookie.secure) {
      score += 25;
      if (severity !== 'critical') severity = 'high';
      issues.push({
        severity: 'high',
        title: 'Missing Secure Flag',
        description: 'Cookie can be sent over unencrypted HTTP connections.'
      });
    }

    if (!cookie.sameSite || cookie.sameSite === 'none') {
      score += 20;
      if (severity === 'low') severity = 'high';
      issues.push({
        severity: 'high',
        title: 'Missing SameSite Protection',
        description: 'Vulnerable to cross-site request forgery (CSRF) attacks.'
      });
    }

    if (cookie.expirationDate) {
      const days = getExpiryDays(cookie.expirationDate);
      if (days > 30) {
        score += 10;
        if (severity === 'low') severity = 'medium';
        issues.push({
          severity: 'medium',
          title: 'Long-Lived Session',
          description: `Expires in ${Math.round(days)} days. Extended exposure if stolen.`
        });
      }
    }

    if (cookie.domain.startsWith('.')) {
      score += 15;
      if (severity === 'low') severity = 'medium';
      issues.push({
        severity: 'medium',
        title: 'Broad Domain Scope',
        description: 'Accessible to all subdomains. Increases attack surface.'
      });
    }
  }

  return {
    score: score,
    severity: severity,
    issues: issues
  };
}

// === RESULTS DISPLAY ===

function displayResults(results) {
  const summary = results.summary;
  const summaryDiv = document.getElementById('risk-summary');
  summaryDiv.innerHTML = `
    <div class="risk-badge risk-badge-critical">
      <span class="risk-count">${summary.critical || 0}</span>
      <span class="risk-label">Critical</span>
    </div>
    <div class="risk-badge risk-badge-high">
      <span class="risk-count">${summary.high || 0}</span>
      <span class="risk-label">High</span>
    </div>
    <div class="risk-badge risk-badge-medium">
      <span class="risk-count">${summary.medium || 0}</span>
      <span class="risk-label">Medium</span>
    </div>
    <div class="risk-badge risk-badge-low">
      <span class="risk-count">${summary.low || 0}</span>
      <span class="risk-label">Low</span>
    </div>
  `;

  const listDiv = document.getElementById('cookie-list');
  listDiv.innerHTML = '';

  results.cookies.forEach(item => {
    const card = createCookieCard(item);
    listDiv.appendChild(card);
  });
}

function createCookieCard(item) {
  const div = document.createElement('div');
  div.className = `cookie-card ${item.risk.severity}`;

  const typeClass = item.classification.type === 'authentication' ? 'auth' : '';

  let issuesHTML = '';
  if (item.risk.issues.length > 0) {
    issuesHTML = '<div class="cookie-issues">';
    item.risk.issues.forEach(issue => {
      issuesHTML += `<div class="issue">${issue.title}</div>`;
    });
    issuesHTML += '</div>';
  }

  div.innerHTML = `
    <div class="cookie-header">
      <div class="cookie-name">${escapeHtml(item.cookie.name)}</div>
      <div class="cookie-type ${typeClass}">${item.classification.type}</div>
    </div>
    ${issuesHTML}
    <div class="confidence">
      AI Confidence: ${(item.classification.confidence * 100).toFixed(0)}%
      <div class="confidence-bar">
        <div class="confidence-fill" style="width: ${item.classification.confidence * 100}%"></div>
      </div>
    </div>
  `;

  div.addEventListener('click', () => showCookieDetails(item));

  return div;
}

function showCookieDetails(item) {
  const details = `
Cookie: ${item.cookie.name}
Domain: ${item.cookie.domain}
Path: ${item.cookie.path}

Security Flags:
  Secure: ${item.cookie.secure ? '✓' : '✗'}
  HttpOnly: ${item.cookie.httpOnly ? '✓' : '✗'}
  SameSite: ${item.cookie.sameSite || 'None'}

Classification:
  Type: ${item.classification.type}
  Confidence: ${(item.classification.confidence * 100).toFixed(1)}%

Risk Score: ${item.risk.score}/100
Severity: ${item.risk.severity.toUpperCase()}

Issues Found:
${item.risk.issues.map(i => `• ${i.title}: ${i.description}`).join('\n')}

Analysis Mode: ${CONFIG.analysisMode === 'backend' ? 'Backend API' : 'Local Processing'}
  `;

  alert(details);
}

function generateSummary(results) {
  const summary = {
    total: results.length,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0
  };

  results.forEach(r => {
    summary[r.risk.severity]++;
  });

  return summary;
}

function generateDefaultSummary() {
  return {
    total: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0
  };
}

// === EXPORT REPORT ===

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
Analysis Mode: ${CONFIG.analysisMode === 'backend' ? 'Backend API' : 'Local Processing'}

SUMMARY
-------
Total Cookies: ${summary.total}
Critical: ${summary.critical}
High: ${summary.high}
Medium: ${summary.medium}
Low: ${summary.low}

DETAILED FINDINGS
-----------------
${analysisResults.cookies.map((item, i) => `
${i + 1}. ${item.cookie.name} (${item.cookie.domain})
   Type: ${item.classification.type} (${(item.classification.confidence * 100).toFixed(0)}% confidence)
   Severity: ${item.risk.severity.toUpperCase()}
   Score: ${item.risk.score}/100

   Issues:
${item.risk.issues.map(issue => `   • ${issue.title}: ${issue.description}`).join('\n')}
`).join('\n')}

==============================
Generated by CookieGuard AI
Privacy-first cookie security scanner
${CONFIG.analysisMode === 'backend' ? 'Backend analysis via Flask API' : 'Local browser analysis'}
  `.trim();

  navigator.clipboard.writeText(report).then(() => {
    alert('✓ Report copied to clipboard!');
  }).catch(err => {
    alert('Failed to copy report: ' + err.message);
  });
}

// === UTILITIES ===

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}