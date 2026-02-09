"""
CookieGuard AI - Flask API Backend
Provides endpoints for cookie analysis
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from feature_extractor import CookieFeatureExtractor
from classifier import CookieClassifier
from risk_scorer import RiskScorer

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

def _coerce_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ('true','1','yes','y','✓','✓ yes','on'):
            return True
        if s in ('false','0','no','n','✗','✗ no','off'):
            return False
    return bool(v)

def normalize_cookie(raw: dict) -> dict:
    """Normalize cookie keys/types so scoring + UI use the same truth."""
    if raw is None:
        return {}
    c = dict(raw)
    # Key normalization (common variants)
    key_map = {
        'HttpOnly': 'httpOnly',
        'httponly': 'httpOnly',
        'http_only': 'httpOnly',
        'Secure': 'secure',
        'SameSite': 'sameSite',
        'expires': 'expirationDate',
        'expiry': 'expirationDate',
        'expiration': 'expirationDate',
        'host_only': 'hostOnly',
        'HostOnly': 'hostOnly',
    }
    for k, v in list(c.items()):
        if k in key_map and key_map[k] not in c:
            c[key_map[k]] = v

    # Coerce boolean-ish flags
    if 'httpOnly' in c:
        c['httpOnly'] = bool(_coerce_bool(c.get('httpOnly')))
    if 'secure' in c:
        c['secure'] = bool(_coerce_bool(c.get('secure')))
    if 'hostOnly' in c and c.get('hostOnly') is not None:
        c['hostOnly'] = bool(_coerce_bool(c.get('hostOnly')))

    # SameSite normalization (Chrome strings -> RFC-ish labels)
    ss = c.get('sameSite')
    if isinstance(ss, str):
        s = ss.strip().lower()
        if s in ('no_restriction', 'none'):
            c['sameSite'] = 'None'
        elif s == 'lax':
            c['sameSite'] = 'Lax'
        elif s == 'strict':
            c['sameSite'] = 'Strict'

    return c


# Initialize components
extractor = CookieFeatureExtractor()
classifier = None
scorer = RiskScorer()

# Load model on startup
MODEL_PATH = Path(__file__).parent.parent / 'models' / 'cookie_classifier.pkl'


def load_model():
    """Load the trained model"""
    global classifier
    
    if not MODEL_PATH.exists():
        print("ERROR: Model not found. Please run 'python backend/train_model.py' first.")
        return False
    
    try:
        classifier = CookieClassifier(str(MODEL_PATH))
        print(f"✓ Model loaded from {MODEL_PATH}")
        return True
    except Exception as e:
        print(f"ERROR loading model: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': classifier is not None
    })


@app.route('/api/analyze', methods=['POST'])
def analyze_cookies():
    """
    Analyze cookies for security risks
    
    Request body:
    {
        "cookies": [
            {
                "name": "session_id",
                "domain": ".example.com",
                "path": "/",
                "secure": true,
                "httpOnly": false,
                "sameSite": "Lax",
                "expirationDate": 1748736000,
                "value": "abc123"  // optional
            },
            ...
        ]
    }
    
    Response:
    {
        "results": [
            {
                "cookie_name": "session_id",
                "ml_classification": {...},
                "risk_assessment": {...},
                "issues": [...],
                "recommendations": [...],
                "summary": "..."
            },
            ...
        ],
        "summary_stats": {
            "total_cookies": 10,
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 2,
            "info": 2
        }
    }
    """
    if classifier is None:
        return jsonify({
            'error': 'Model not loaded. Please train the model first.',
            'instructions': 'Run: python backend/train_model.py'
        }), 500
    
    try:
        data = request.get_json()
        site_host = (data.get('domain') or data.get('host') or '').strip() or None
        cookies = data.get('cookies', [])
        # Normalize + de-duplicate cookies (name, domain, path)
        normalized = [normalize_cookie(c) for c in cookies]
        seen = set()
        cookies = []
        for c in normalized:
            key = (c.get('name'), c.get('domain'), c.get('path'))
            if key in seen:
                continue
            seen.add(key)
            cookies.append(c)
        
        if not cookies:
            return jsonify({'error': 'No cookies provided'}), 400
        
        # Analyze each cookie
        results = []
        for cookie in cookies:
            # Extract features
            features = extractor.extract_features(cookie)
            
            # ML classification
            ml_type, ml_confidence, ml_probs = classifier.predict_from_dict(features)
            
            # Risk analysis
            analysis = scorer.analyze_cookie(
                cookie, ml_type, ml_confidence, ml_probs
            , site_host=site_host)
            
            results.append(analysis)
        
        # Rank by risk
        results = scorer.rank_cookies_by_risk(results)
        
        # Calculate summary stats
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }
        
        for result in results:
            severity = result['risk_assessment']['severity']
            severity_counts[severity] += 1
        
        return jsonify({
            'results': results,
            'summary_stats': {
                'total_cookies': len(cookies),
                **severity_counts
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/demo', methods=['GET'])
def get_demo_cookies():
    """
    Get demo cookie data for testing
    
    Returns example cookies with various security issues
    """
    demo_cookies = [
        {
            "name": "session_token",
            "domain": ".mybank.com",
            "path": "/",
            "secure": True,
            "httpOnly": False,  # CRITICAL ISSUE
            "sameSite": None,  # HIGH ISSUE
            "expirationDate": 1748736000,  # 30 days
            "value": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiIxMjM0NSJ9.SflKxwRJ"
        },
        {
            "name": "user_preferences",
            "domain": "mybank.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "sameSite": "Lax",
            "expirationDate": 1780272000,  # 1 year
            "value": "theme=dark;lang=en"
        },
        {
            "name": "_ga",
            "domain": ".mybank.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "sameSite": None,
            "expirationDate": 1780272000,
            "value": "GA1.2.123456789.1234567890"
        },
        {
            "name": "auth_remember",
            "domain": ".mybank.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,  # Good!
            "sameSite": "Strict",  # Good!
            "expirationDate": 1743552000,  # 14 days
            "value": "a1b2c3d4e5f6"
        },
        {
            "name": "JSESSIONID",
            "domain": "shop.example.com",
            "path": "/",
            "secure": False,  # HIGH ISSUE
            "httpOnly": True,
            "sameSite": "Lax",
            "expirationDate": None,  # Session cookie
            "value": "5F4DCC3B5AA765D61D8327DEB882CF99"
        }
    ]
    
    return jsonify({'cookies': demo_cookies})


@app.route('/api/export-report', methods=['POST'])
def export_report():
    """
    Generate downloadable security report
    
    Request body: Same as /api/analyze
    Response: Formatted text report
    """
    try:
        data = request.get_json()
        results = data.get('results', [])
        stats = data.get('summary_stats', {})
        
        # Generate text report
        report_lines = [
            "=" * 70,
            "COOKIEGUARD AI - SECURITY REPORT",
            f"Generated: {data.get('timestamp', 'N/A')}",
            "=" * 70,
            "",
            f"SUMMARY: Analyzed {stats.get('total_cookies', 0)} cookies",
            f"  Critical: {stats.get('critical', 0)}",
            f"  High:     {stats.get('high', 0)}",
            f"  Medium:   {stats.get('medium', 0)}",
            f"  Low:      {stats.get('low', 0)}",
            "",
            "=" * 70,
            "DETAILED FINDINGS",
            "=" * 70,
            ""
        ]
        
        for i, result in enumerate(results, 1):
            report_lines.append(f"{i}. {result['cookie_name']} ({result['cookie_domain']})")
            report_lines.append(f"   Type: {result['ml_classification']['type']} "
                              f"(confidence: {result['ml_classification']['confidence']:.0%})")
            report_lines.append(f"   Severity: {result['risk_assessment']['severity'].upper()}")
            report_lines.append("")
            
            for issue in result['issues']:
                report_lines.append(f"   [{issue['severity'].upper()}] {issue['title']}")
                report_lines.append(f"   {issue['description']}")
                report_lines.append("")
            
            report_lines.append("")
        
        report_lines.append("=" * 70)
        report_lines.append("This report was generated by CookieGuard AI")
        report_lines.append("An AI-powered tool for detecting cookie security risks")
        report_lines.append("=" * 70)
        
        return jsonify({
            'report': '\n'.join(report_lines)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("CookieGuard AI - Backend Server")
    print("=" * 60)
    
    # Load model
    if load_model():
        print("✓ Server ready")
        print("\nEndpoints:")
        print("  GET  /health              - Health check")
        print("  GET  /api/demo            - Get demo cookies")
        print("  POST /api/analyze         - Analyze cookies")
        print("  POST /api/export-report   - Export report")
        print("\nStarting server on http://localhost:5000")
        print("=" * 60)
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("\n⚠ Please train the model first:")
        print("  python backend/train_model.py")