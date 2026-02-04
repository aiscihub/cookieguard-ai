import React, { useState, useMemo } from 'react';
import './App.css';

// Icons component (keep your existing one)
const Icons = {
  Upload: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  Shield: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  AlertTriangle: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  X: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  Play: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  Info: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
  Globe: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  Tag: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>,
  Download: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  Folder: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>,
  ChevronDown: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>,
  ChevronUp: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="18 15 12 9 6 15"/></svg>,
  Brain: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9.5 2A2.5 2.5 0 0 0 7 4.5v15A2.5 2.5 0 0 0 9.5 22h5a2.5 2.5 0 0 0 2.5-2.5v-15A2.5 2.5 0 0 0 14.5 2h-5z"/><path d="M14 9h4"/><path d="M14 12h4"/><path d="M14 15h4"/></svg>
};

// Model Info Panel Component
const ModelInfoPanel = ({ isVisible, onToggle }) => {
  return (
    <>
      {/* Floating toggle button */}
      <button 
        className={`model-info-toggle-btn ${isVisible ? 'hidden' : ''}`}
        onClick={onToggle}
        title="Show AI Model Details"
      >
        <Icons.Brain />
      </button>

      {/* Sliding panel */}
      <div className={`model-info-panel ${isVisible ? 'visible' : ''}`}>
        <div className="panel-header">
          <h3>🤖 AI Model Details</h3>
          <button className="panel-toggle" onClick={onToggle}>×</button>
        </div>
        
        <div className="panel-content">
          {/* Architecture */}
          <div className="info-section">
            <h4>Architecture</h4>
            <div className="info-grid">
              <div className="info-item">
                <span className="label">Algorithm:</span>
                <span className="value">Random Forest</span>
              </div>
              <div className="info-item">
                <span className="label">Trees:</span>
                <span className="value">100</span>
              </div>
              <div className="info-item">
                <span className="label">Max Depth:</span>
                <span className="value">10</span>
              </div>
              <div className="info-item">
                <span className="label">Features:</span>
                <div>
                  <span className="value highlight">34</span>
                  <span className="badge">↑ from 18</span>
                </div>
              </div>
            </div>
          </div>

          {/* Feature Groups */}
          <div className="info-section">
            <h4>Feature Groups</h4>
            <div className="feature-groups">
              <div className="feature-group">
                <div className="group-header">
                  <span className="group-name">Attributes</span>
                  <span className="group-count">7</span>
                </div>
                <div className="group-details">Security flags, expiry, lifetime</div>
              </div>
              <div className="feature-group">
                <div className="group-header">
                  <span className="group-name">Scope/Exposure</span>
                  <span className="group-count">7</span>
                </div>
                <div className="group-details">Domain, path, cross-site sendability</div>
              </div>
              <div className="feature-group">
                <div className="group-header">
                  <span className="group-name">Lexical/Token</span>
                  <span className="group-count">20</span>
                </div>
                <div className="group-details">Name patterns, value structure, entropy</div>
              </div>
            </div>
          </div>

          {/* Performance */}
          <div className="info-section">
            <h4>Model Performance</h4>
            <div className="metrics-grid">
              <div className="metric">
                <div className="metric-value">100%</div>
                <div className="metric-label">Accuracy</div>
              </div>
              <div className="metric">
                <div className="metric-value">100%</div>
                <div className="metric-label">Precision</div>
              </div>
              <div className="metric">
                <div className="metric-value">100%</div>
                <div className="metric-label">Recall</div>
              </div>
              <div className="metric">
                <div className="metric-value">1.00</div>
                <div className="metric-label">F1-Score</div>
              </div>
            </div>
          </div>

          {/* Enhancements */}
          <div className="info-section">
            <h4>AI Enhancements</h4>
            <div className="enhancements-list">
              <div className="enhancement">
                <span className="check">✓</span>
                <span>Isotonic Calibration</span>
              </div>
              <div className="enhancement">
                <span className="check">✓</span>
                <span>Rule-based Fallbacks</span>
              </div>
              <div className="enhancement">
                <span className="check">✓</span>
                <span>Enhanced Risk Formula</span>
              </div>
              <div className="enhancement">
                <span className="check">✓</span>
                <span>Domain Hold-out Validation</span>
              </div>
            </div>
          </div>

          {/* Top Features */}
          <div className="info-section">
            <h4>Top 5 Important Features</h4>
            <div className="features-list">
              {[
                { name: 'value_length', importance: 0.2495 },
                { name: 'lifetime_category', importance: 0.0968 },
                { name: 'exposure_score', importance: 0.0939 },
                { name: 'value_length_bucket', importance: 0.0885 },
                { name: 'expiry_days', importance: 0.0692 }
              ].map((feat, idx) => (
                <div key={idx} className="feature-item">
                  <div className="feature-rank">#{idx + 1}</div>
                  <div className="feature-details">
                    <div className="feature-name">{feat.name}</div>
                    <div className="feature-bar-container">
                      <div 
                        className="feature-bar" 
                        style={{ width: `${feat.importance * 400}%` }}
                      />
                    </div>
                  </div>
                  <div className="feature-importance">{(feat.importance * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </div>

          {/* Risk Formula */}
          <div className="info-section">
            <h4>Risk Scoring Formula</h4>
            <div className="formula-box">
              <div className="formula-title">RiskScore =</div>
              <div className="formula-content">
                P(auth) × Severity × Exposure
              </div>
              <div className="formula-details">
                <div>• P(auth): ML-predicted probability</div>
                <div>• Severity: Security flag violations</div>
                <div>• Exposure: Domain breadth × Lifetime</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

// Main App Component (use your existing code, just add the ModelInfoPanel)
function App() {
  const [cookies, setCookies] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');
  const [viewMode, setViewMode] = useState('domain');
  const [expandedGroups, setExpandedGroups] = useState({});
  const [showModelInfo, setShowModelInfo] = useState(false); // NEW STATE

  // ... rest of your existing App code ...

  return (
    <div className="app">
      {/* Model Info Panel - ADD THIS */}
      <ModelInfoPanel 
        isVisible={showModelInfo}
        onToggle={() => setShowModelInfo(!showModelInfo)}
      />

      {/* Rest of your existing JSX */}
      <header className="header">
        {/* ... your existing header ... */}
      </header>

      <main className="main">
        {/* ... your existing content ... */}
      </main>

      <footer className="footer">
        <p>CookieGuard AI • Girls Who Code AI Challenge 2025 • Enhanced with 34-Feature ML Model</p>
      </footer>
    </div>
  );
}

export default App;
