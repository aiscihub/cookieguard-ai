"""
CookieGuard AI 2.0 - Flask Backend
Endpoints:
  GET  /health              → health check
  POST /api/analyze          → full cookie analysis with explainability + attack sim
  GET  /api/model-info       → model card + feature schema
"""

import json
import sys
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent))

from feature_extractor import CookieFeatureExtractor
from classifier import CookieClassifier
from risk_scorer import RiskScorer
from explainability import explain_prediction
from attack_simulator import simulate_attacks

app = Flask(__name__)
CORS(app)

# ── Load model ──────────────────────────────────────────────
MODEL_DIR = Path(__file__).parent.parent / 'models'
MODEL_PATH = MODEL_DIR / 'cookie_classifier.pkl'

extractor = CookieFeatureExtractor()
scorer = RiskScorer()

if MODEL_PATH.exists():
    classifier = CookieClassifier(str(MODEL_PATH))
    print(f"✓ Model loaded: {classifier.model_name} ({len(classifier.feature_names)} features)")
else:
    classifier = None
    print("⚠ No trained model found. Run train_model.py first.")


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'version': '2.0',
        'model_loaded': classifier is not None,
        'model_name': classifier.model_name if classifier else None,
        'features': len(extractor.get_feature_names()),
    })


@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    if not data or 'cookies' not in data:
        return jsonify({'error': 'Missing cookies field'}), 400

    cookies = data['cookies']
    context = data.get('context', {})
    site_domain = data.get('domain', '')

    # Build context for feature extraction
    extract_context = {
        'loginEvent': context.get('loginEvent', False),
        'changedCookies': context.get('changedCookies', []),
        'beforeCookieIndex': context.get('beforeCookieIndex', {}),
        'currentDomain': site_domain,
        'scanType': context.get('scanType', 'single'),
    }

    results = []

    for cookie in cookies:
        # 1. Extract features
        features = extractor.extract_features(cookie, extract_context)

        # 2. Classify
        if classifier:
            cookie_type, confidence, probabilities = classifier.predict_from_dict(features, cookie)
            model_contributions = classifier.get_feature_contributions(features)
        else:
            # Fallback: rule-based
            cookie_type, confidence, probabilities = _fallback_classify(cookie)
            model_contributions = None

        # 3. Risk scoring
        risk_result = scorer.analyze_cookie(
            cookie, cookie_type, confidence, probabilities, site_host=site_domain
        )

        # 4. Explainability (NEW in 2.0)
        explanations = explain_prediction(
            features=features,
            classification_type=cookie_type,
            classification_probs=probabilities,
            risk_severity=risk_result['risk_assessment']['severity'],
            risk_issues=risk_result['issues'],
            model_contributions=model_contributions,
        )

        # 5. Attack simulation (NEW in 2.0)
        attack_sim = simulate_attacks(
            cookie=cookie,
            classification_type=cookie_type,
            risk_severity=risk_result['risk_assessment']['severity'],
            risk_issues=risk_result['issues'],
            features=features,
        )

        # 6. Behavior signals summary (NEW in 2.0)
        behavior_signals = {
            'changed_during_login': bool(features.get('f_changed_during_login', 0)),
            'new_after_login': bool(features.get('f_new_after_login', 0)),
            'rotated_after_login': bool(features.get('f_rotated_after_login', 0)),
            'third_party': bool(features.get('f_third_party_context', 0)),
            'subdomain_shared': bool(features.get('f_subdomain_shared', 0)),
            'login_behavior_score': int(features.get('f_login_behavior_score', 0)),
            'security_posture_score': int(features.get('f_security_posture_score', 0)),
        }

        # Merge into result
        result = risk_result.copy()
        result['explanations'] = explanations
        result['attack_simulation'] = attack_sim
        result['behavior_signals'] = behavior_signals
        results.append(result)

    # Sort by risk score descending
    results.sort(key=lambda r: r['risk_assessment']['score'], reverse=True)

    # Summary stats
    severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for r in results:
        sev = r['risk_assessment']['severity']
        if sev in severity_counts:
            severity_counts[sev] += 1

    return jsonify({
        'results': results,
        'summary_stats': {
            'total_cookies': len(results),
            **severity_counts,
            'model_version': '2.0',
            'model_name': classifier.model_name if classifier else 'rule-based',
        },
    })


@app.route('/api/model-info', methods=['GET'])
def model_info():
    """Return model card and feature schema."""
    card_path = MODEL_DIR / 'model_card.json'
    schema_path = MODEL_DIR / 'feature_schema.json'

    card = {}
    schema = {}
    if card_path.exists():
        with open(card_path) as f:
            card = json.load(f)
    if schema_path.exists():
        with open(schema_path) as f:
            schema = json.load(f)

    return jsonify({'model_card': card, 'feature_schema': schema})


def _fallback_classify(cookie):
    """Simple rule-based classification when no model is loaded."""
    name = cookie.get('name', '').lower()
    if any(k in name for k in ['session', 'auth', 'token', 'login', 'sid']):
        return 'authentication', 0.80, {'authentication': 0.80, 'tracking': 0.05, 'preference': 0.05, 'other': 0.10}
    if any(k in name for k in ['_ga', '_gid', 'analytics', 'tracking', 'fbp']):
        return 'tracking', 0.85, {'authentication': 0.02, 'tracking': 0.85, 'preference': 0.03, 'other': 0.10}
    if any(k in name for k in ['theme', 'lang', 'pref', 'consent']):
        return 'preference', 0.70, {'authentication': 0.05, 'tracking': 0.10, 'preference': 0.70, 'other': 0.15}
    return 'other', 0.55, {'authentication': 0.10, 'tracking': 0.15, 'preference': 0.15, 'other': 0.60}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
