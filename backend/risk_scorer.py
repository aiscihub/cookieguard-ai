"""
Enhanced Risk Scorer with Improved Formula
RiskScore = P(auth) × Severity(flags) × Exposure(scope)
"""

from typing import Dict, List
from datetime import datetime

class RiskScorer:
    CRITICAL, HIGH, MEDIUM, LOW, INFO = "critical", "high", "medium", "low", "info"

    def analyze_cookie(self, cookie, ml_type, ml_confidence, ml_probabilities):
        issues, recommendations, risk_score = [], [], 0
        is_auth = ml_type=='authentication' or ml_probabilities.get('authentication',0)>0.3

        # Severity analysis
        if is_auth:
            if not cookie.get('httpOnly',False):
                issues.append({'severity':self.CRITICAL, 'title':'Missing HttpOnly Flag',
                               'description':'Cookie accessible via JavaScript - vulnerable to XSS attacks that can steal session tokens',
                               'impact':'Account takeover via cross-site scripting (XSS)'})
                risk_score += 40
                recommendations.append('Set HttpOnly flag to prevent JavaScript access')

            if not cookie.get('secure',False):
                issues.append({'severity':self.HIGH, 'title':'Missing Secure Flag',
                               'description':'Cookie sent over HTTP - vulnerable to network interception',
                               'impact':'Session token exposure on unsecured connections'})
                risk_score += 25
                recommendations.append('Set Secure flag to require HTTPS')

            samesite = (cookie.get('sameSite','') or '').lower()
            if not samesite or samesite=='none':
                issues.append({'severity':self.HIGH, 'title':'Missing SameSite Protection',
                               'description':'Cookie sent with cross-site requests - vulnerable to CSRF attacks',
                               'impact':'Unauthorized actions via cross-site request forgery'})
                risk_score += 20
                recommendations.append('Set SameSite=Lax or Strict to prevent CSRF')
            elif samesite=='lax':
                # Only flag if other issues present
                pass

            # Exposure multiplier and domain/path analysis
            domain = cookie.get('domain','')
            path = cookie.get('path', '/')
            expiry = cookie.get('expirationDate')
            name = cookie.get('name', '')

            # Subdomain/scope risk detection
            has_scope_issue = False

            # Check for wildcard domain
            if domain and domain.startswith('.'):
                issues.append({'severity':self.MEDIUM, 'title':'Wildcard Domain - Subdomain Takeover Risk',
                               'description':f'Cookie accessible to all subdomains of {domain[1:]}. If attacker controls ANY subdomain, they can steal this session cookie.',
                               'impact':'Session hijacking via compromised subdomain'})
                risk_score += 15
                recommendations.append('Limit domain scope to specific host (remove wildcard)')
                has_scope_issue = True
                breadth_factor = 1.5
            # Check for explicit domain (suggests multi-subdomain setup)
            elif domain and domain != 'localhost' and domain != '127.0.0.1':
                issues.append({'severity':self.MEDIUM, 'title':'Explicit Domain Scope',
                               'description':f'Cookie domain set to "{domain}". In production with subdomains, this creates exposure risk.',
                               'impact':'Potential subdomain cookie access'})
                risk_score += 10
                recommendations.append('Use host-only cookies (no explicit domain) when possible')
                has_scope_issue = True
                breadth_factor = 1.3
            # Check for cookies with names suggesting sharing
            elif 'shared' in name.lower() or 'global' in name.lower():
                issues.append({'severity':self.MEDIUM, 'title':'Shared Cookie Naming',
                               'description':'Cookie name suggests it may be shared across subdomains',
                               'impact':'Increased attack surface'})
                risk_score += 8
                has_scope_issue = True
                breadth_factor = 1.2
            else:
                breadth_factor = 1.0

            # Broad path scope
            if path == '/' and has_scope_issue:
                issues.append({'severity':self.LOW, 'title':'Broad Path Scope',
                               'description':'Cookie accessible to all paths on domain. Consider limiting to specific paths like /api or /app.',
                               'impact':'Increased exposure surface'})
                risk_score += 5
                recommendations.append('Limit path scope if possible (e.g., /api instead of /)')

            # Lifetime factor
            if expiry:
                dt = datetime.fromtimestamp(expiry) if isinstance(expiry,(int,float)) else datetime.fromisoformat(str(expiry))
                days = max((dt - datetime.now()).days, 0)
                if days > 30:
                    issues.append({'severity':self.MEDIUM, 'title':'Long-Lived Session Cookie',
                                   'description':f'Cookie expires in {days} days. Extended lifetime increases window for session replay attacks.',
                                   'impact':'Extended exposure window for stolen tokens'})
                    risk_score += 10
                    recommendations.append('Use shorter expiration time for session cookies')
                elif days > 7:
                    issues.append({'severity':self.LOW, 'title':'Moderate Session Lifetime',
                                   'description':f'Cookie expires in {days} days. Consider shorter lifetime for sensitive sessions.',
                                   'impact':'Moderate exposure window'})
                    risk_score += 5
                    recommendations.append('Consider shorter session lifetime')
                elif days >= 3:
                    issues.append({'severity':self.LOW, 'title':'Multi-Day Session',
                                   'description':f'Cookie expires in {days} days',
                                   'impact':'Extended session window'})
                    risk_score += 3
                lifetime_factor = 1.0 + min(days/365.0, 1.0)
            else:
                lifetime_factor = 1.0

            # Apply exposure multiplier
            exposure = breadth_factor * lifetime_factor
            risk_score = int(risk_score * exposure)

        # Overall severity
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
        name = cookie.get('name','Unknown')
        type_desc = {'authentication':'keeps you logged in', 'tracking':'tracks activity',
                     'preference':'stores preferences', 'other':'serves functional purpose'}[ml_type]

        risk_map = {
            self.CRITICAL: 'CRITICAL - account takeover possible',
            self.HIGH: 'HIGH RISK - significant exposure',
            self.MEDIUM: 'MEDIUM RISK - some concerns',
            self.LOW: 'LOW RISK - minor improvements possible',
            self.INFO: 'No significant concerns'
        }

        summary = f"Cookie '{name}' likely {type_desc} (AI: {ml_confidence:.0%}). {risk_map[overall_severity]}. Found {len(issues)} issue(s)." if issues else f"Cookie '{name}' {type_desc}. {risk_map[overall_severity]}."

        return {
            'cookie_name': name,
            'cookie_domain': cookie.get('domain'),
            'ml_classification': {'type':ml_type, 'confidence':ml_confidence, 'probabilities':ml_probabilities},
            'risk_assessment': {'severity':overall_severity, 'score':risk_score, 'max_score':100},
            'issues': issues,
            'recommendations': recommendations,
            'summary': summary
        }

    def rank_cookies_by_risk(self, analyses):
        return sorted(analyses, key=lambda x: (x['risk_assessment']['score'],
                                               x['ml_classification']['probabilities'].get('authentication',0)), reverse=True)