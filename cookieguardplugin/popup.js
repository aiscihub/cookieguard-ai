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


// Configuration
const CONFIG = {
  useBackend: true,
  backendURL: 'http://localhost:5000',
  demoSiteURL: 'http://localhost:8000',
  analysisMode: 'backend'
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
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
  document.getElementById('scan-btn').addEventListener('click', handleScan);
  document.getElementById('login-scan-btn').addEventListener('click', showLoginFlow);
  document.getElementById('back-btn').addEventListener('click', showMainView);
  document.getElementById('login-back-btn').addEventListener('click', showMainView);
  document.getElementById('export-btn').addEventListener('click', exportReport);
  document.getElementById('export-cookies-btn')?.addEventListener('click', exportCookiesAsJson);

  // Modal actions (reduce false positives)
  document.getElementById('btn-mark-not-auth')?.addEventListener('click', markCurrentCookieNotAuth);
  document.getElementById('btn-ignore-cookie')?.addEventListener('click', ignoreCurrentCookie);

  // Login flow buttons
  document.getElementById('capture-before-btn')?.addEventListener('click', captureBeforeLogin);
  document.getElementById('capture-after-btn')?.addEventListener('click', captureAfterLogin);

  // Check backend availability
  if (CONFIG.useBackend) {
    await checkBackendHealth();
  }

  await loadUserPrefs();
  updateBackendStatus();

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

function showLoginFlow() {
  document.getElementById('main-view').style.display = 'none';
  document.getElementById('loading-view').style.display = 'none';
  document.getElementById('results-view').style.display = 'none';
  document.getElementById('login-flow-view').style.display = 'block';
  document.getElementById('login-domain').textContent = currentDomain;

  beforeLoginCookies = null;
  afterLoginCookies = null;
  document.getElementById('step-1').classList.add('active');
  document.getElementById('step-2').classList.remove('active', 'completed');
  document.getElementById('step-3').classList.remove('active', 'completed');
  document.getElementById('capture-before-btn').disabled = false;
  document.getElementById('capture-after-btn').disabled = true;
}

// === BACKEND STATUS ===

function updateBackendStatus() {
  const statusEl = document.getElementById('backend-status');
  if (statusEl) {
    if (CONFIG.analysisMode === 'backend') {
      statusEl.textContent = '✓ Backend Connected';
      statusEl.className = 'connected';
    } else {
      statusEl.textContent = '⚡ Local Mode';
      statusEl.className = 'local';
    }
  }
}

async function checkBackendHealth() {
  try {
    const response = await fetch(`${CONFIG.backendURL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000)
    });

    if (response.ok) {
      CONFIG.analysisMode = 'backend';
      console.log('✓ Backend available');
      return true;
    } else {
      CONFIG.analysisMode = 'local';
      return false;
    }
  } catch (error) {
    CONFIG.analysisMode = 'local';
    console.log('⚠️ Backend not available, using local analysis');
    return false;
  }
}

// === DEMO SITE INDICATOR ===

function showDemoSiteIndicator() {
  const header = document.querySelector('.header');
  const indicator = document.createElement('div');
  indicator.style.cssText = `
    background: #e6fffa;
    border: 1px solid #319795;
    border-radius: 6px;
    padding: 8px;
    margin-top: 8px;
    font-size: 10px;
    color: #234e52;
    text-align: center;
  `;
  indicator.innerHTML = '<strong>🎯 Demo Site Detected</strong><br>Ready to test scenarios A/B/C/D';
  header.appendChild(indicator);
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
    alert('Scan failed: ' + error.message + '\n\nCheck:\n1. Backend is running (port 5000)\n2. Console for errors (F12)');
    showMainView();
  }
}

// === LOGIN FLOW ===

async function captureBeforeLogin() {
  try {
    console.log('Capturing before-login cookies...');
    beforeLoginCookies = await chrome.cookies.getAll({ domain: currentDomain });

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
    afterLoginCookies = await chrome.cookies.getAll({ domain: currentDomain });

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
  console.log(`Analyzing ${cookies.length} cookies, mode: ${CONFIG.analysisMode}`);

  if (CONFIG.analysisMode === 'backend') {
    return await analyzeWithBackend(cookies, context);
  } else {
    return await analyzeLocally(cookies, context);
  }
}

async function analyzeWithBackend(cookies, context) {
  try {
    console.log('Sending to backend:', `${CONFIG.backendURL}/api/analyze`);

    const requestBody = {
      domain: currentDomain,
      cookies: cookies.map(c => ({
        name: c.name,
        domain: c.domain,
        path: c.path,
        secure: c.secure,
        httpOnly: c.httpOnly,
        sameSite: c.sameSite,
        expirationDate: c.expirationDate,
        hostOnly: c.hostOnly,
        value: c.value
      })),
      context: context
    };

    console.log('Request body:', requestBody);

    const response = await fetch(`${CONFIG.backendURL}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });

    console.log('Backend response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend error:', errorText);
      throw new Error(`Backend returned ${response.status}: ${errorText}`);
    }

    const data = await response.json();
    console.log('Backend response data:', data);

    if (!data.results) {
      throw new Error('Backend returned no results');
    }

    // Store results
    analysisResults = {
      cookies: (() => {
        // Map raw cookies by (name,domain,path) for lookup
        const cookieIndex = new Map();
        cookies.forEach(c => {
          const key = `${c.name}||${c.domain}||${c.path}`;
          cookieIndex.set(key, c);
        });

        return (data.results || []).map((r) => {
          // Prefer backend-normalized attributes for display (single source of truth)
          const attrs = r.cookie_attributes || {};
          const name = r.cookie_name || attrs.name || '(unknown)';
          const domain = attrs.domain ?? r.cookie_domain;
          const path = attrs.path ?? '/';

          const key = `${name}||${domain}||${path}`;
          const raw = cookieIndex.get(key);

          const displayCookie = {
            name,
            domain,
            path,
            secure: attrs.secure ?? raw?.secure,
            httpOnly: attrs.httpOnly ?? raw?.httpOnly,
            sameSite: attrs.sameSite ?? raw?.sameSite,
            expirationDate: attrs.expirationDate ?? raw?.expirationDate,
            hostOnly: attrs.hostOnly ?? raw?.hostOnly
          };

          return {
            cookie: displayCookie,
            classification: r.ml_classification,
            risk: {
              score: r.risk_assessment?.score ?? 0,
              severity: r.risk_assessment?.severity ?? 'info',
              issues: r.issues || []
            },
            summary: r.summary,
            recommendations: r.recommendations || []
          };
        });
      })(),
      summary: data.summary_stats,
      context: context
    };

    console.log('Analysis results:', analysisResults);
    return analysisResults;

  } catch (error) {
    console.error('Backend analysis failed:', error);
    console.log('Falling back to local analysis');
    return await analyzeLocally(cookies, context);
  }
}

async function analyzeLocally(cookies, context) {
  console.log('Using local analysis');

  // Simple local classification
  const results = cookies.map(cookie => {
    const classification = classifyLocally(cookie);
    const risk = calculateRiskLocally(cookie, classification);

    return {
      cookie: cookie,
      classification: classification,
      risk: risk,
      summary: `${cookie.name} classified as ${classification.type}`,
      recommendations: generateRecommendations(cookie, risk)
    };
  });

  // Sort by risk
  results.sort((a, b) => b.risk.score - a.risk.score);

  const summary = {
    total_cookies: cookies.length,
    critical: results.filter(r => r.risk.severity === 'critical').length,
    high: results.filter(r => r.risk.severity === 'high').length,
    medium: results.filter(r => r.risk.severity === 'medium').length,
    low: results.filter(r => r.risk.severity === 'low').length,
    info: results.filter(r => r.risk.severity === 'info').length
  };

  analysisResults = {
    cookies: results,
    summary: summary,
    context: context
  };

  console.log('Local analysis results:', analysisResults);
  return analysisResults;
}

function classifyLocally(cookie) {
  const name = cookie.name.toLowerCase();

  // Auth patterns
  if (name.includes('session') || name.includes('auth') || name.includes('token') ||
      name.includes('login') || name === 'sessionid' || name === 'jsessionid') {
    return {
      type: 'authentication',
      confidence: 0.85,
      probabilities: { authentication: 0.85, tracking: 0.05, preference: 0.05, other: 0.05 }
    };
  }

  // Tracking patterns
  if (name.startsWith('_ga') || name.startsWith('_gid') || name.includes('analytics')) {
    return {
      type: 'tracking',
      confidence: 0.90,
      probabilities: { authentication: 0.02, tracking: 0.90, preference: 0.03, other: 0.05 }
    };
  }

  // Preference patterns
  if (name.includes('pref') || name.includes('theme') || name.includes('lang')) {
    return {
      type: 'preference',
      confidence: 0.75,
      probabilities: { authentication: 0.05, tracking: 0.10, preference: 0.75, other: 0.10 }
    };
  }

  return {
    type: 'other',
    confidence: 0.60,
    probabilities: { authentication: 0.10, tracking: 0.15, preference: 0.15, other: 0.60 }
  };
}

function calculateRiskLocally(cookie, classification) {
  let score = 0;
  const issues = [];

  const isAuth = classification.type === 'authentication';

  if (isAuth) {
    if (!cookie.httpOnly) {
      score += 40;
      issues.push({
        severity: 'critical',
        title: 'Missing HttpOnly Flag',
        description: 'Cookie accessible via JavaScript - vulnerable to XSS attacks'
      });
    }

    if (!cookie.secure) {
      score += 25;
      issues.push({
        severity: 'high',
        title: 'Missing Secure Flag',
        description: 'Cookie sent over HTTP - vulnerable to network interception'
      });
    }

    if (!cookie.sameSite || cookie.sameSite === 'none') {
      score += 20;
      issues.push({
        severity: 'high',
        title: 'Missing SameSite Protection',
        description: 'Vulnerable to cross-site request forgery (CSRF) attacks'
      });
    }

    if (cookie.expirationDate) {
      const days = (cookie.expirationDate * 1000 - Date.now()) / (1000 * 60 * 60 * 24);
      if (days > 30) {
        score += 10;
        issues.push({
          severity: 'medium',
          title: 'Long-Lived Session',
          description: `Expires in ${Math.round(days)} days`
        });
      }
    }
  }

  let severity = 'low';
  if (score >= 50) severity = 'critical';
  else if (score >= 30) severity = 'high';
  else if (score >= 15) severity = 'medium';
  else if (score > 0) severity = 'low';
  else severity = 'info';

  return { score, severity, issues };
}

function generateRecommendations(cookie, risk) {
  const recommendations = [];

  for (const issue of risk.issues) {
    if (issue.title.includes('HttpOnly')) {
      recommendations.push('Set HttpOnly flag to prevent JavaScript access');
    } else if (issue.title.includes('Secure')) {
      recommendations.push('Set Secure flag to require HTTPS');
    } else if (issue.title.includes('SameSite')) {
      recommendations.push('Set SameSite=Lax or Strict to prevent CSRF');
    } else if (issue.title.includes('Long-Lived')) {
      recommendations.push('Reduce expiration time for session cookies');
    }
  }

  return recommendations;
}

// === RESULTS DISPLAY ===

function displayResults(results) {
  if (!results || !results.summary) {
    console.error('Invalid results:', results);
    alert('Error: Invalid analysis results');
    showMainView();
    return;
  }

  // Show login event badge if detected
  if (results.context?.loginEvent || loginEventDetected) {
    const badge = document.getElementById('login-event-badge');
    badge.style.display = 'block';

    const details = document.getElementById('event-details');
    const changedCount = results.context?.changedCookies?.length || 0;
    details.textContent = `${changedCount} cookie(s) changed during login`;

    loginEventDetected = false; // Reset
  } else {
    document.getElementById('login-event-badge').style.display = 'none';
  }

  // Show before/after comparison if we have previous analysis
  if (previousAnalysis && previousAnalysis.summary) {
    showComparison(previousAnalysis, results);
  } else {
    document.getElementById('comparison-view').style.display = 'none';
  }


  // Apply user overrides / ignore list
  const visibleCookies = (results.cookies || [])
    .map(c => applyUserOverrides(c))
    .filter(c => !isIgnored(c));

  // Recompute summary using "effective severity" to reduce noisy false positives in UI
  const derivedSummary = {
    total_cookies: visibleCookies.length,
    critical: 0, high: 0, medium: 0, low: 0, info: 0
  };

  visibleCookies.forEach(item => {
    const s = getEffectiveSeverity(item);
    if (derivedSummary[s] !== undefined) derivedSummary[s] += 1;
  });

  // Display summary
  document.getElementById('risk-summary').innerHTML = `
    <div class="stat critical">
      <div class="stat-num">${derivedSummary.critical}</div>
      <div class="stat-label">Critical</div>
    </div>
    <div class="stat high">
      <div class="stat-num">${derivedSummary.high}</div>
      <div class="stat-label">High</div>
    </div>
    <div class="stat medium">
      <div class="stat-num">${derivedSummary.medium}</div>
      <div class="stat-label">Medium</div>
    </div>
    <div class="stat low">
      <div class="stat-num">${derivedSummary.low}</div>
      <div class="stat-label">Low</div>
    </div>
  `;

  // Display cookies
  const listDiv = document.getElementById('cookie-list');
  listDiv.innerHTML = '';

  if (visibleCookies.length > 0) {
    visibleCookies.sort((a, b) => (b.risk?.score || 0) - (a.risk?.score || 0));
    visibleCookies.forEach(item => {
      const card = createCookieCard(item);
      listDiv.appendChild(card);
    });
  } else {
    listDiv.innerHTML = '<div style="text-align:center;padding:20px;color:#666;">No cookies to display (ignored or none found)</div>';
  }


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
  const reviewPill = item._needsReview ? '<span class="pill review">Review</span>' : '';

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

  bodyEl.innerHTML = detailsHTML;
  modal.classList.add('active');
}

function closeModal() {
  document.getElementById('cookie-modal').classList.remove('active');
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
Analysis Mode: ${CONFIG.analysisMode === 'backend' ? 'Backend AI' : 'Local Processing'}

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
    const allCookies = await chrome.cookies.getAll({});

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
  try {
    const data = await chrome.storage.local.get(['cookieguard_prefs_v1']);
    if (data && data.cookieguard_prefs_v1) {
      userPrefs = data.cookieguard_prefs_v1;
    }
  } catch (e) {
    console.warn('Failed to load user prefs', e);
  }
}

async function saveUserPrefs() {
  try {
    await chrome.storage.local.set({ cookieguard_prefs_v1: userPrefs });
  } catch (e) {
    console.warn('Failed to save user prefs', e);
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

  // Login-aware signal (if available)
  const changed = analysisResults?.context?.changedCookies || [];
  if (changed.includes(item.cookie?.name)) {
    chips.push({ text: 'Changed during login', kind: 'primary' });
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

  // Cap
  return chips.slice(0, UI_CONFIG.maxEvidenceChips);
}


// === UTILITIES ===

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
  const modal = document.getElementById('cookie-modal');
  if (e.target === modal) {
    closeModal();
  }
});