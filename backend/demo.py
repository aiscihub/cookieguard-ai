"""
CookieGuard AI - Demo Script
Demonstrates the full analysis workflow
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from feature_extractor import CookieFeatureExtractor
from classifier import CookieClassifier
from risk_scorer import RiskScorer


def run_demo():
    """Run a complete demonstration of CookieGuard AI"""
    
    print("=" * 80)
    print("COOKIEGUARD AI - LIVE DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Initialize components
    print("[1/4] Loading AI Model...")
    model_path = Path(__file__).parent.parent / 'models' / 'cookie_classifier.pkl'
    
    if not model_path.exists():
        print("ERROR: Model not found. Please run: python backend/train_model.py")
        return
    
    extractor = CookieFeatureExtractor()
    classifier = CookieClassifier(str(model_path))
    scorer = RiskScorer()
    print("✓ Model loaded successfully\n")
    
    # Demo cookies representing real-world scenarios
    print("[2/4] Loading Example Cookies...")
    demo_cookies = [
        {
            "name": "session_token",
            "domain": ".mybank.com",
            "path": "/",
            "secure": True,
            "httpOnly": False,  # CRITICAL VULNERABILITY
            "sameSite": None,  # HIGH VULNERABILITY
            "expirationDate": 1748736000,  # 30 days
            "value": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiIxMjM0NSJ9.SflKxw"
        },
        {
            "name": "PHPSESSID",
            "domain": "shop.example.com",
            "path": "/",
            "secure": False,  # HIGH VULNERABILITY
            "httpOnly": True,
            "sameSite": "Lax",
            "expirationDate": None,  # Session cookie
            "value": "5F4DCC3B5AA765D61D8327DEB882CF99"
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
            "name": "theme_preference",
            "domain": "mybank.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "sameSite": "Lax",
            "expirationDate": 1780272000,
            "value": "dark"
        }
    ]
    
    print(f"✓ Loaded {len(demo_cookies)} example cookies\n")
    
    # Analyze each cookie
    print("[3/4] Running AI Analysis...")
    print("-" * 80)
    
    results = []
    for i, cookie in enumerate(demo_cookies, 1):
        print(f"\nAnalyzing Cookie {i}/{len(demo_cookies)}: {cookie['name']}")
        
        # Extract features
        features = extractor.extract_features(cookie)
        
        # ML classification
        ml_type, ml_confidence, ml_probs = classifier.predict_from_dict(features)
        
        # Risk analysis
        analysis = scorer.analyze_cookie(cookie, ml_type, ml_confidence, ml_probs)
        results.append(analysis)
        
        # Display results
        print(f"  AI Classification: {ml_type} ({ml_confidence:.0%} confidence)")
        print(f"  Risk Level: {analysis['risk_assessment']['severity'].upper()}")
        print(f"  Issues Found: {len(analysis['issues'])}")
    
    print("\n" + "-" * 80)
    
    # Display detailed results
    print("\n[4/4] Detailed Security Report")
    print("=" * 80)
    
    # Rank by risk
    results = scorer.rank_cookies_by_risk(results)
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['cookie_name']} ({result['cookie_domain']})")
        print("-" * 80)
        
        # Classification
        ml_info = result['ml_classification']
        print(f"AI Classification: {ml_info['type'].upper()}")
        print(f"Confidence: {ml_info['confidence']:.0%}")
        
        # Risk
        risk_info = result['risk_assessment']
        severity_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢',
            'info': '🔵'
        }
        emoji = severity_emoji.get(risk_info['severity'], '⚪')
        print(f"\nRisk Level: {emoji} {risk_info['severity'].upper()} "
              f"(Score: {risk_info['score']}/{risk_info['max_score']})")
        
        # Summary
        print(f"\nSummary:")
        print(f"  {result['summary']}")
        
        # Issues
        if result['issues']:
            print(f"\nSecurity Issues ({len(result['issues'])}):")
            for issue in result['issues']:
                print(f"\n  [{issue['severity'].upper()}] {issue['title']}")
                print(f"  → {issue['description']}")
                print(f"  → Impact: {issue['impact']}")
        
        # Recommendations
        if result['recommendations']:
            print(f"\nRecommendations:")
            for rec in result['recommendations']:
                print(f"  • {rec}")
        
        print()
    
    # Summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for result in results:
        severity = result['risk_assessment']['severity']
        severity_counts[severity] += 1
    
    print(f"\nTotal Cookies Analyzed: {len(results)}")
    print(f"Critical Risk: {severity_counts['critical']}")
    print(f"High Risk: {severity_counts['high']}")
    print(f"Medium Risk: {severity_counts['medium']}")
    print(f"Low Risk: {severity_counts['low']}")
    print(f"Info Only: {severity_counts['info']}")
    
    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    
    auth_cookies = [r for r in results if r['ml_classification']['type'] == 'authentication']
    critical_issues = [r for r in results if r['risk_assessment']['severity'] == 'critical']
    
    print(f"\n✓ AI detected {len(auth_cookies)} authentication cookie(s)")
    print(f"✓ Found {len(critical_issues)} CRITICAL security issue(s)")
    print(f"✓ {sum(len(r['issues']) for r in results)} total security issues identified")
    
    print("\nWithout AI:")
    print("  • Users would need to manually inspect each cookie's technical attributes")
    print("  • No way to distinguish critical session cookies from harmless preferences")
    print("  • Risk of ignoring dangerous misconfigurations in authentication cookies")
    
    print("\nWith CookieGuard AI:")
    print("  • Automatic classification of cookie types")
    print("  • Prioritized risk assessment with plain-language explanations")
    print("  • Clear, actionable security recommendations")
    
    print("\n" + "=" * 80)
    print("Demo complete! This shows CookieGuard AI protecting digital identity.")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
