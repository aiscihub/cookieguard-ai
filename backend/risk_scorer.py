"""
Risk Scoring Engine
Combines ML classification with security rule analysis
"""

from typing import Dict, List, Tuple


class RiskScorer:
    """Score cookie security risk and generate explanations"""
    
    # Risk severity levels
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    
    def analyze_cookie(
        self,
        cookie: Dict,
        ml_type: str,
        ml_confidence: float,
        ml_probabilities: Dict
    ) -> Dict:
        """
        Complete risk analysis of a cookie
        
        Args:
            cookie: Original cookie dictionary
            ml_type: ML predicted type (authentication/tracking/preference/other)
            ml_confidence: Confidence in ML prediction
            ml_probabilities: All class probabilities
        
        Returns:
            Risk analysis with severity, score, issues, and recommendations
        """
        issues = []
        risk_score = 0
        recommendations = []
        
        # Is this an authentication cookie?
        is_auth = ml_type == 'authentication' or ml_probabilities.get('authentication', 0) > 0.3
        
        # Security flag analysis
        if is_auth:
            # CRITICAL: Authentication cookies should have HttpOnly
            if not cookie.get('httpOnly', False):
                issues.append({
                    'severity': self.CRITICAL,
                    'title': 'Missing HttpOnly Flag on Authentication Cookie',
                    'description': 'This cookie can be accessed by JavaScript, making it vulnerable to XSS attacks. An attacker could steal your session token through malicious scripts.',
                    'impact': 'Account takeover via session hijacking'
                })
                risk_score += 40
                recommendations.append('This cookie MUST have the HttpOnly flag set')
            
            # HIGH: Authentication cookies should be Secure
            if not cookie.get('secure', False):
                issues.append({
                    'severity': self.HIGH,
                    'title': 'Missing Secure Flag on Authentication Cookie',
                    'description': 'This cookie can be sent over unencrypted HTTP connections, allowing attackers on the same network to intercept it.',
                    'impact': 'Session token exposure on unsecured networks'
                })
                risk_score += 25
                recommendations.append('This cookie should only be sent over HTTPS')
            
            # MEDIUM-HIGH: SameSite protection
            samesite = cookie.get('sameSite', '') or ''
            samesite = samesite.lower() if samesite else ''
            if not samesite or samesite == 'none':
                issues.append({
                    'severity': self.HIGH,
                    'title': 'Missing SameSite Protection',
                    'description': 'This cookie will be sent with cross-site requests, making you vulnerable to CSRF attacks. Attackers could trigger actions on your behalf.',
                    'impact': 'Unauthorized actions via cross-site request forgery'
                })
                risk_score += 20
                recommendations.append('Set SameSite=Lax or SameSite=Strict')
            elif samesite == 'lax':
                # Lax is okay but not ideal
                issues.append({
                    'severity': self.MEDIUM,
                    'title': 'SameSite=Lax (Could be Stricter)',
                    'description': 'This cookie is sent with some cross-site requests. For maximum security, consider SameSite=Strict.',
                    'impact': 'Limited CSRF risk on top-level navigation'
                })
                risk_score += 5
        
        # Expiry analysis
        expiry = cookie.get('expirationDate')
        if is_auth and expiry:
            from datetime import datetime, timedelta
            if isinstance(expiry, (int, float)):
                expiry_dt = datetime.fromtimestamp(expiry)
            else:
                expiry_dt = datetime.fromisoformat(str(expiry))
            
            days_until_expiry = (expiry_dt - datetime.now()).days
            
            if days_until_expiry > 30:
                issues.append({
                    'severity': self.MEDIUM,
                    'title': 'Long-Lived Authentication Cookie',
                    'description': f'This cookie expires in {days_until_expiry} days. Long-lived session cookies increase the window of opportunity for attackers.',
                    'impact': 'Extended exposure window if cookie is stolen'
                })
                risk_score += 10
                recommendations.append('Use session cookies or shorter expiration times')
        
        # Domain scope analysis
        domain = cookie.get('domain', '')
        if is_auth and domain.startswith('.'):
            # Wildcard domain
            issues.append({
                'severity': self.MEDIUM,
                'title': 'Broad Domain Scope (Wildcard)',
                'description': f'This cookie is accessible to all subdomains of {domain[1:]}. A compromised subdomain could steal this authentication cookie.',
                'impact': 'Subdomain-based cookie theft'
            })
            risk_score += 15
            recommendations.append('Limit cookie scope to specific subdomain if possible')
        
        # ML confidence analysis
        if is_auth and ml_confidence < 0.6:
            issues.append({
                'severity': self.INFO,
                'title': 'Uncertain Cookie Classification',
                'description': f'AI classified this as authentication with only {ml_confidence:.0%} confidence. It might serve multiple purposes.',
                'impact': 'Classification uncertainty'
            })
        
        # Calculate overall severity
        if risk_score >= 50:
            overall_severity = self.CRITICAL
        elif risk_score >= 30:
            overall_severity = self.HIGH
        elif risk_score >= 15:
            overall_severity = self.MEDIUM
        elif risk_score > 0:
            overall_severity = self.LOW
        else:
            overall_severity = self.INFO
        
        # Generate summary
        summary = self._generate_summary(
            cookie, ml_type, ml_confidence, overall_severity, len(issues)
        )
        
        return {
            'cookie_name': cookie.get('name'),
            'cookie_domain': cookie.get('domain'),
            'ml_classification': {
                'type': ml_type,
                'confidence': ml_confidence,
                'probabilities': ml_probabilities
            },
            'risk_assessment': {
                'severity': overall_severity,
                'score': risk_score,
                'max_score': 100
            },
            'issues': issues,
            'recommendations': recommendations,
            'summary': summary
        }
    
    def _generate_summary(
        self,
        cookie: Dict,
        ml_type: str,
        confidence: float,
        severity: str,
        issue_count: int
    ) -> str:
        """Generate plain-language summary"""
        
        name = cookie.get('name', 'Unknown')
        
        if ml_type == 'authentication':
            type_desc = "keeps you logged in"
        elif ml_type == 'tracking':
            type_desc = "tracks your activity"
        elif ml_type == 'preference':
            type_desc = "stores your preferences"
        else:
            type_desc = "serves a functional purpose"
        
        if severity == self.CRITICAL:
            risk_desc = "This is CRITICAL - your account could be taken over"
        elif severity == self.HIGH:
            risk_desc = "This is HIGH RISK - significant security exposure"
        elif severity == self.MEDIUM:
            risk_desc = "This is MEDIUM RISK - some security concerns"
        elif severity == self.LOW:
            risk_desc = "This is LOW RISK - minor security improvements possible"
        else:
            risk_desc = "No significant security concerns detected"
        
        if issue_count == 0:
            return f"Cookie '{name}' {type_desc}. {risk_desc}."
        else:
            return f"Cookie '{name}' likely {type_desc} (AI confidence: {confidence:.0%}). {risk_desc}. Found {issue_count} security issue(s)."
    
    def rank_cookies_by_risk(self, analyses: List[Dict]) -> List[Dict]:
        """
        Sort cookie analyses by risk score (highest first)
        
        Args:
            analyses: List of analysis results from analyze_cookie()
        
        Returns:
            Sorted list (most risky first)
        """
        return sorted(
            analyses,
            key=lambda x: (
                x['risk_assessment']['score'],
                x['ml_classification'].get('probabilities', {}).get('authentication', 0)
            ),
            reverse=True
        )


if __name__ == "__main__":
    # Test risk scorer
    scorer = RiskScorer()
    
    # Test case: Vulnerable auth cookie
    test_cookie = {
        "name": "session_token",
        "domain": ".example.com",
        "path": "/",
        "secure": True,
        "httpOnly": False,  # VULNERABLE!
        "sameSite": None,  # VULNERABLE!
        "expirationDate": 1748736000,  # 30 days
        "value": "abc123"
    }
    
    ml_result = {
        'type': 'authentication',
        'confidence': 0.92,
        'probabilities': {
            'authentication': 0.92,
            'tracking': 0.03,
            'preference': 0.02,
            'other': 0.03
        }
    }
    
    analysis = scorer.analyze_cookie(
        test_cookie,
        ml_result['type'],
        ml_result['confidence'],
        ml_result['probabilities']
    )
    
    print("Risk Analysis Test")
    print("=" * 60)
    print(f"\nSummary: {analysis['summary']}")
    print(f"\nOverall Severity: {analysis['risk_assessment']['severity'].upper()}")
    print(f"Risk Score: {analysis['risk_assessment']['score']}/100")
    print(f"\nIssues Found ({len(analysis['issues'])}):")
    for issue in analysis['issues']:
        print(f"\n  [{issue['severity'].upper()}] {issue['title']}")
        print(f"  {issue['description']}")
        print(f"  Impact: {issue['impact']}")
    
    if analysis['recommendations']:
        print(f"\nRecommendations:")
        for rec in analysis['recommendations']:
            print(f"  • {rec}")
