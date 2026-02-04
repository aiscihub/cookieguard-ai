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

export default ModelInfoPanel;
