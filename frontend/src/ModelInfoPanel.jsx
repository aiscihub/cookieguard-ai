import React from 'react';

// Standalone Model Info Panel Component
const ModelInfoPanel = ({ isVisible, onToggle }) => {
  return (
    <>
      {/* Floating toggle button */}
      <button 
        className={`model-info-toggle-btn ${isVisible ? 'hidden' : ''}`}
        onClick={onToggle}
        title="Show AI Model Details"
      >
        🧠
      </button>

      {/* Sliding panel */}
      <div className={`model-info-panel ${isVisible ? 'visible' : ''}`}>
        <div className="panel-header">
          <h3>Model Details</h3>
          <button className="panel-toggle" onClick={onToggle}>×</button>
        </div>

        <div className="panel-content">
          {/* Model Name */}
          <div className="info-section">
            <h4>Model Name</h4>
            <div className="model-name-display">
              <span className="model-name-text">CookieGuard Random Forest Classifier</span>
              <span className="model-version">v2.1.0</span>
            </div>
          </div>

          {/* Architecture */}
          <div className="info-section">
            <h4>Architecture</h4>
            <div className="info-grid">
              <div className="info-item">
                <span className="label">Trees</span>
                <span className="value">100</span>
              </div>
              <div className="info-item">
                <span className="label">Max Depth</span>
                <span className="value">10</span>
              </div>
              <div className="info-item">
                <span className="label">Features</span>
                <span className="value highlight">34</span>
              </div>
              <div className="info-item">
                <span className="label">Classes</span>
                <span className="value">4</span>
              </div>
            </div>
          </div>

          {/* Feature Groups */}
          <div className="info-section">
            <h4>Feature Groups</h4>
            <div className="feature-groups">
              <div className="feature-group">
                <div className="group-header">
                  <span className="group-name">Security Attributes</span>
                  <span className="group-count">7</span>
                </div>
                <div className="group-details">HttpOnly, Secure, SameSite, expiry, lifetime</div>
              </div>
              <div className="feature-group">
                <div className="group-header">
                  <span className="group-name">Scope & Exposure</span>
                  <span className="group-count">7</span>
                </div>
                <div className="group-details">Domain breadth, path scope, cross-site risk</div>
              </div>
              <div className="feature-group">
                <div className="group-header">
                  <span className="group-name">Lexical & Token</span>
                  <span className="group-count">20</span>
                </div>
                <div className="group-details">Name patterns, value structure, entropy analysis</div>
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

          {/* Risk Scoring */}
          <div className="info-section">
            <h4>Risk Scoring Formula</h4>
            <div className="formula-box">
              <div className="formula-title">Risk Score =</div>
              <div className="formula-content">
                P(auth) × Severity × Exposure
              </div>
              <div className="formula-details">
                <div>• P(auth): ML-predicted auth probability (0-1)</div>
                <div>• Severity: Security flag violations (1-5)</div>
                <div>• Exposure: Domain breadth × Cookie lifetime</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ModelInfoPanel;