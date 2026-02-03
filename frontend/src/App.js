import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [cookies, setCookies] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const json = JSON.parse(e.target.result);
          setCookies(Array.isArray(json) ? json : json.cookies || []);
          setError(null);
        } catch (err) {
          setError('Invalid JSON file. Please upload a valid cookie export.');
        }
      };
      reader.readAsText(file);
    }
  };

  const loadDemoData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('/api/demo');
      setCookies(response.data.cookies);
      setActiveTab('review');
    } catch (err) {
      setError('Failed to load demo data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const analyzeCookies = async () => {
    if (cookies.length === 0) {
      setError('No cookies to analyze');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await axios.post('/api/analyze', { cookies });
      setResults(response.data);
      setActiveTab('results');
    } catch (err) {
      setError('Analysis failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const exportReport = async () => {
    if (!results) return;
    
    try {
      const response = await axios.post('/api/export-report', {
        results: results.results,
        summary_stats: results.summary_stats,
        timestamp: new Date().toISOString()
      });
      
      const blob = new Blob([response.data.report], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'cookieguard-report.txt';
      a.click();
    } catch (err) {
      setError('Export failed: ' + err.message);
    }
  };

  const getSeverityColor = (severity) => {
    const colors = {
      critical: '#dc2626',
      high: '#ea580c',
      medium: '#f59e0b',
      low: '#84cc16',
      info: '#3b82f6'
    };
    return colors[severity] || '#6b7280';
  };

  const getSeverityBadge = (severity) => {
    return (
      <span 
        className="severity-badge" 
        style={{ backgroundColor: getSeverityColor(severity) }}
      >
        {severity.toUpperCase()}
      </span>
    );
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <h1>🍪 CookieGuard AI</h1>
          <p className="subtitle">Detecting Security-Critical Cookie Misuse</p>
        </div>
      </header>

      <div className="container">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
          >
            Upload Cookies
          </button>
          <button 
            className={`tab ${activeTab === 'review' ? 'active' : ''}`}
            onClick={() => setActiveTab('review')}
            disabled={cookies.length === 0}
          >
            Review ({cookies.length})
          </button>
          <button 
            className={`tab ${activeTab === 'results' ? 'active' : ''}`}
            onClick={() => setActiveTab('results')}
            disabled={!results}
          >
            Results
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            ⚠️ {error}
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="tab-content">
            <div className="upload-section">
              <h2>Get Started</h2>
              <p>Upload your cookies or try the demo to see CookieGuard AI in action.</p>
              
              <div className="upload-options">
                <div className="upload-box">
                  <h3>📁 Upload Cookie Data</h3>
                  <p>Export cookies from your browser as JSON</p>
                  <input 
                    type="file" 
                    accept=".json" 
                    onChange={handleFileUpload}
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="button button-primary">
                    Choose File
                  </label>
                </div>

                <div className="upload-box">
                  <h3>🎬 Try Demo</h3>
                  <p>Load example cookies with security issues</p>
                  <button 
                    className="button button-secondary" 
                    onClick={loadDemoData}
                    disabled={loading}
                  >
                    {loading ? 'Loading...' : 'Load Demo'}
                  </button>
                </div>
              </div>

              <div className="info-box">
                <h3>How to Export Cookies</h3>
                <ol>
                  <li>Install a cookie export extension (e.g., "Cookie Editor")</li>
                  <li>Visit the website you want to analyze</li>
                  <li>Export all cookies as JSON</li>
                  <li>Upload the file here</li>
                </ol>
                <p><strong>Privacy Note:</strong> All analysis happens locally. No data is sent to external servers.</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'review' && (
          <div className="tab-content">
            <h2>Review Cookies</h2>
            <p>Loaded {cookies.length} cookie(s). Click "Analyze" to detect security issues.</p>
            
            <button 
              className="button button-primary button-large" 
              onClick={analyzeCookies}
              disabled={loading}
            >
              {loading ? 'Analyzing...' : '🔍 Analyze Cookies'}
            </button>

            <div className="cookie-list">
              {cookies.slice(0, 10).map((cookie, idx) => (
                <div key={idx} className="cookie-item">
                  <strong>{cookie.name}</strong>
                  <span className="cookie-domain">{cookie.domain}</span>
                </div>
              ))}
              {cookies.length > 10 && (
                <div className="cookie-item">
                  <em>... and {cookies.length - 10} more</em>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'results' && results && (
          <div className="tab-content">
            <div className="results-header">
              <h2>Security Analysis Results</h2>
              <button className="button button-secondary" onClick={exportReport}>
                📄 Export Report
              </button>
            </div>

            <div className="summary-stats">
              <div className="stat-card">
                <div className="stat-value">{results.summary_stats.total_cookies}</div>
                <div className="stat-label">Total Cookies</div>
              </div>
              <div className="stat-card critical">
                <div className="stat-value">{results.summary_stats.critical}</div>
                <div className="stat-label">Critical</div>
              </div>
              <div className="stat-card high">
                <div className="stat-value">{results.summary_stats.high}</div>
                <div className="stat-label">High Risk</div>
              </div>
              <div className="stat-card medium">
                <div className="stat-value">{results.summary_stats.medium}</div>
                <div className="stat-label">Medium</div>
              </div>
            </div>

            <div className="results-list">
              {results.results.map((result, idx) => (
                <div key={idx} className="result-card">
                  <div className="result-header">
                    <div>
                      <h3>{result.cookie_name}</h3>
                      <p className="cookie-domain">{result.cookie_domain}</p>
                    </div>
                    {getSeverityBadge(result.risk_assessment.severity)}
                  </div>

                  <div className="ml-classification">
                    <strong>AI Classification:</strong> {result.ml_classification.type}
                    <span className="confidence">
                      {(result.ml_classification.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>

                  <p className="summary">{result.summary}</p>

                  {result.issues.length > 0 && (
                    <div className="issues">
                      <strong>Security Issues:</strong>
                      {result.issues.map((issue, issueIdx) => (
                        <div key={issueIdx} className="issue">
                          {getSeverityBadge(issue.severity)}
                          <div className="issue-content">
                            <div className="issue-title">{issue.title}</div>
                            <div className="issue-description">{issue.description}</div>
                            <div className="issue-impact">
                              <strong>Impact:</strong> {issue.impact}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {result.recommendations.length > 0 && (
                    <div className="recommendations">
                      <strong>Recommendations:</strong>
                      <ul>
                        {result.recommendations.map((rec, recIdx) => (
                          <li key={recIdx}>{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <footer className="app-footer">
        <p>CookieGuard AI - Girls Who Code AI Challenge 2025</p>
        <p>Protecting digital identity through AI-powered cookie security analysis</p>
      </footer>
    </div>
  );
}

export default App;
