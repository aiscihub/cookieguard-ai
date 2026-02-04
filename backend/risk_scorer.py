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
                              'description':'Cookie accessible via JavaScript - vulnerable to XSS attacks',
                              'impact':'Account takeover via session hijacking'})
                risk_score += 40
                recommendations.append('Set HttpOnly flag')
            
            if not cookie.get('secure',False):
                issues.append({'severity':self.HIGH, 'title':'Missing Secure Flag',
                              'description':'Cookie sent over HTTP - vulnerable to network interception',
                              'impact':'Session token exposure on unsecured connections'})
                risk_score += 25
                recommendations.append('Set Secure flag')
            
            samesite = (cookie.get('sameSite','') or '').lower()
            if not samesite or samesite=='none':
                issues.append({'severity':self.HIGH, 'title':'Missing SameSite Protection',
                              'description':'Cookie sent with cross-site requests - vulnerable to CSRF',
                              'impact':'Unauthorized actions via cross-site request forgery'})
                risk_score += 20
                recommendations.append('Set SameSite=Lax or Strict')
            elif samesite=='lax':
                issues.append({'severity':self.MEDIUM, 'title':'SameSite=Lax (Could be Stricter)',
                              'description':'Some cross-site requests allowed',
                              'impact':'Limited CSRF risk'})
                risk_score += 5
            
            # Exposure multiplier (NEW!)
            domain = cookie.get('domain','')
            expiry = cookie.get('expirationDate')
            
            # Domain breadth factor
            breadth_factor = 1.5 if domain.startswith('.') else 1.0
            
            # Lifetime factor
            if expiry:
                dt = datetime.fromtimestamp(expiry) if isinstance(expiry,(int,float)) else datetime.fromisoformat(str(expiry))
                days = (dt - datetime.now()).days
                if days > 30:
                    issues.append({'severity':self.MEDIUM, 'title':'Long-Lived Session Cookie',
                                  'description':f'Cookie expires in {days} days',
                                  'impact':'Extended exposure window'})
                    risk_score += 10
                lifetime_factor = 1.0 + min(days/365.0, 1.0)
            else:
                lifetime_factor = 1.0
            
            # Apply exposure multiplier
            exposure = breadth_factor * lifetime_factor
            risk_score = int(risk_score * exposure)
            
            if domain.startswith('.'):
                issues.append({'severity':self.MEDIUM, 'title':'Broad Domain Scope',
                              'description':f'Cookie accessible to all subdomains of {domain[1:]}',
                              'impact':'Subdomain-based cookie theft'})
                recommendations.append('Limit scope to specific subdomain')
        
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
