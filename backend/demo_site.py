"""
CookieGuard AI - Demo Test Site
Provides controlled scenarios A/B/C/D for testing cookie vulnerabilities
"""

from flask import Flask, request, jsonify, render_template_string, make_response, redirect
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Track current scenario
current_scenario = 'A'

# HTML Templates
LANDING_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>CookieGuard Demo Site</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 600px;
            width: 100%;
        }
        h1 {
            color: #2d3748;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #718096;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .scenario-selector {
            background: #f7fafc;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
        }
        .scenario-title {
            font-weight: 600;
            margin-bottom: 12px;
            color: #2d3748;
        }
        .scenario-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .scenario-btn {
            padding: 12px;
            border: 2px solid #e2e8f0;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
            text-align: left;
        }
        .scenario-btn:hover {
            border-color: #667eea;
            background: #f7fafc;
        }
        .scenario-btn.active {
            border-color: #667eea;
            background: #edf2f7;
            font-weight: 600;
        }
        .scenario-label {
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 4px;
        }
        .scenario-desc {
            font-size: 12px;
            color: #718096;
        }
        .login-section {
            background: #f7fafc;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .login-title {
            font-weight: 600;
            margin-bottom: 12px;
            color: #2d3748;
        }
        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5568d3;
        }
        .btn-secondary {
            background: #e2e8f0;
            color: #2d3748;
            margin-top: 10px;
        }
        .btn-secondary:hover {
            background: #cbd5e0;
        }
        .status-panel {
            background: #edf2f7;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            font-size: 13px;
            color: #4a5568;
        }
        .status-label {
            font-weight: 600;
            margin-bottom: 5px;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 5px;
        }
        .badge-critical { background: #fed7d7; color: #c53030; }
        .badge-high { background: #feebc8; color: #c05621; }
        .badge-medium { background: #fefcbf; color: #975a16; }
        .badge-low { background: #c6f6d5; color: #22543d; }
        .instructions {
            background: #e6fffa;
            border-left: 4px solid #319795;
            padding: 15px;
            margin-top: 20px;
            border-radius: 4px;
            font-size: 13px;
            color: #234e52;
        }
        .instructions strong {
            display: block;
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1> CookieGuard AI Demo</h1>
        <p class="subtitle">Controlled environment for testing cookie security vulnerabilities</p>
        
        <div class="scenario-selector">
            <div class="scenario-title">Select Test Scenario:</div>
            <div class="scenario-grid">
                <button class="scenario-btn {{ 'active' if scenario == 'A' else '' }}" onclick="selectScenario('A')">
                    <div class="scenario-label">Session Hijacking</div>
                    <div class="scenario-desc">Script Exposure</div>
                </button>
                <button class="scenario-btn {{ 'active' if scenario == 'B' else '' }}" onclick="selectScenario('B')">
                    <div class="scenario-label">Unauthorized Actions</div>
                    <div class="scenario-desc">Cross-Site Risk</div>
                </button>
                <button class="scenario-btn {{ 'active' if scenario == 'C' else '' }}" onclick="selectScenario('C')">
                    <div class="scenario-label">Subdomain Takeover</div>
                    <div class="scenario-desc">Subdomain Takeover</div>
                </button>
                <button class="scenario-btn {{ 'active' if scenario == 'D' else '' }}" onclick="selectScenario('D')">
                    <div class="scenario-label">Scenario D</div>
                    <div class="scenario-desc">Fixed/Secure</div>
                </button>
            </div>
        </div>
        
        <div class="login-section">
            <div class="login-title">Test Login Flow</div>
            <form method="POST" action="/login">
                <input type="hidden" name="mode" value="{{ scenario }}">
                <button type="submit" class="btn btn-primary">🔐 Login (Demo)</button>
            </form>
        </div>
        
        {% if scenario == 'B' %}
        <div class="login-section">
            <div class="login-title">⚠️ Scenario B: Simulate XSS</div>
            <button class="btn btn-secondary" onclick="showXSSDemo()">
                Simulate Injected Script
            </button>
        </div>
        {% endif %}
        
        <div class="status-panel">
            <div class="status-label">Current Scenario: {{ scenario }}</div>
            <div>{{ scenario_info[scenario]['description'] }}</div>
            <span class="badge badge-{{ scenario_info[scenario]['severity'] }}">
                {{ scenario_info[scenario]['severity'].upper() }} RISK
            </span>
        </div>
        
        <div class="instructions">
            <strong>Instructions:</strong>
            1. Open CookieGuard extension in Chrome<br>
            2. Select a scenario above<br>
            3. Click "Login (Demo)" button<br>
            4. Extension will detect and analyze cookies<br>
            5. Compare results across scenarios
        </div>
    </div>
    
    <script>
        function selectScenario(mode) {
            window.location.href = '/?scenario=' + mode;
        }
        
        function showXSSDemo() {
            const cookieValue = document.cookie;
            alert('🔓 Simulated XSS Attack\\n\\nAn attacker could read:\\n' + cookieValue + '\\n\\nThis demonstrates why HttpOnly flag is critical!');
        }
    </script>
</body>
</html>
'''

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - CookieGuard Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f7fafc;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2d3748;
            margin-bottom: 10px;
        }
        .user-info {
            color: #718096;
            font-size: 14px;
        }
        .content {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .auth-check {
            background: #c6f6d5;
            border-left: 4px solid #38a169;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .api-call {
            background: #f7fafc;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            font-size: 13px;
            color: #4a5568;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            margin-right: 10px;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>✅ Logged In</h1>
        <div class="user-info">Logged in as: <strong>Demo User</strong></div>
        <div class="user-info">Scenario: <strong>{{ mode }}</strong></div>
    </div>
    
    <div class="content">
        <div class="auth-check">
            ✓ Session authenticated - cookies working properly
        </div>
        
        <h3>Simulated API Calls:</h3>
        <div class="api-call" id="profile-data">Loading profile...</div>
        <div class="api-call" id="notifications-data">Loading notifications...</div>
        
        <div style="margin-top: 30px;">
            <button class="btn btn-primary" onclick="window.location.href='/'">← Back to Home</button>
        </div>
    </div>
    
    <script>
        // Simulate authenticated API calls
        setTimeout(() => {
            document.getElementById('profile-data').innerHTML = 
                '<strong>GET /api/profile</strong><br>Status: 200 OK<br>User: demo@example.com';
        }, 300);
        
        setTimeout(() => {
            document.getElementById('notifications-data').innerHTML = 
                '<strong>GET /api/notifications</strong><br>Status: 200 OK<br>Notifications: 3 unread';
        }, 600);
    </script>
</body>
</html>
'''

# Scenario information
SCENARIO_INFO = {
    # 'A': {
    #     'description': 'Missing Secure flag - cookie can be sent over HTTP',
    #     'severity': 'high'
    # },
    'A': {
        'description': 'Missing HttpOnly flag - JavaScript can access cookie',
        'severity': 'critical'
    },
    'B': {
        'description': 'SameSite=None + broad domain - cross-site exposure',
        'severity': 'high'
    }
    ,
    'C': {
        'description': 'Wildcard domain (.localhost) - vulnerable to subdomain takeover',
        'severity': 'medium'
    },
    'D': {
        'description': 'All security flags properly configured',
        'severity': 'low'
    }
}

def set_cookies_for_scenario(response, mode):
    """Set cookies based on scenario mode"""

    # Common settings
    session_value = secrets.token_hex(32)
    csrf_value = secrets.token_hex(16)
    analytics_value = f"GA1.2.{secrets.randbelow(1000000)}.{int(datetime.now().timestamp())}"

    if mode == 'A':
        # Scenario A: Script Exposure (HttpOnly=false)
        response.set_cookie(
            'sessionid',
            value=session_value,
            domain=None,  # exact host
            path='/',
            secure=True,  # VULNERABILITY: missing Secure
            httponly=False,
            samesite='Lax',
            max_age=None  # session cookie
        )

    elif mode == 'B':
        # Scenario B: Cross-Site + Over-broad scope
        # Instead, we'll set long expiry + SameSite=None
        response.set_cookie(
            'sessionid',
            value=session_value,
            domain=None,
            path='/',
            secure=True,
            httponly=True,
            samesite='None',  # VULNERABILITY: allows cross-site
            max_age=30*24*60*60  # VULNERABILITY: 30 days (long-lived)
        )

    elif mode == 'C':
        # Scenario C: Broad Scope (Path + Domain + Lifetime)
        # MEDIUM: Multiple scope issues that increase attack surface
        # 1. Root path (/) instead of specific path
        # 2. Long lifetime (7 days)
        # 3. Domain set explicitly (creates subdomain exposure in production)

        # Note: We can't use .localhost wildcard in development, but we simulate
        # the vulnerability by setting explicit domain + broad path
        # In production, this would be domain='.example.com'

        response.set_cookie(
            'sessionid',
            value=session_value,
            domain='localhost',  # In production: '.example.com' (wildcard)
            path='/',  # VULNERABILITY: broad path scope
            secure=True,
            httponly=True,
            samesite='Lax',
            max_age=7*24*60*60  # VULNERABILITY: 7 days (moderate lifetime)
        )

        # Also set a cookie that simulates the subdomain issue more explicitly
        # by adding metadata in the cookie name
        response.set_cookie(
            'session_shared',  # Name suggests it's shared
            value=session_value[:16],  # Partial token
            domain='localhost',  # Would be '.example.com' in production
            path='/',
            secure=True,
            httponly=True,
            samesite='Lax',
            max_age=7*24*60*60,
            # This cookie name pattern triggers detection
        )
    elif mode == 'D':
        # Scenario D: Fixed/Secure baseline
        response.set_cookie(
            'sessionid',
            value=session_value,
            domain=None,
            path='/',
            secure=True,  # ✓ Secure
            httponly=True,  # ✓ HttpOnly
            samesite='Lax',  # ✓ SameSite protection
            max_age=None  # ✓ Session cookie
        )

    # Always set non-identity cookies (same across all scenarios)
    response.set_cookie(
        'analytics_id',
        value=analytics_value,
        domain=None,
        path='/',
        secure=False,
        httponly=False,
        samesite='Lax',
        max_age=365*24*60*60
    )

    response.set_cookie(
        'csrf_token',
        value=csrf_value,
        domain=None,
        path='/',
        secure=True,
        httponly=True,
        samesite='Lax',
        max_age=None
    )

    return response

@app.route('/')
def index():
    """Landing page with scenario selector"""
    global current_scenario

    scenario = request.args.get('scenario', current_scenario)
    if scenario in ['A', 'B', 'C', 'D']:
        current_scenario = scenario

    return render_template_string(
        LANDING_PAGE,
        scenario=current_scenario,
        scenario_info=SCENARIO_INFO
    )

@app.route('/login', methods=['POST'])
def login():
    """Simulate login and set cookies based on scenario"""
    mode = request.form.get('mode', current_scenario)

    # Create response with redirect
    response = make_response(redirect('/dashboard?mode=' + mode))

    # Set cookies for this scenario
    response = set_cookies_for_scenario(response, mode)

    return response

@app.route('/dashboard')
def dashboard():
    """Dashboard page (requires authentication)"""
    mode = request.args.get('mode', current_scenario)

    # In real app, would check for valid session cookie
    return render_template_string(DASHBOARD_PAGE, mode=mode)

@app.route('/api/profile')
def api_profile():
    """Simulated authenticated API endpoint"""
    # In real app, would validate session cookie
    return jsonify({
        'email': 'demo@example.com',
        'name': 'Demo User',
        'status': 'authenticated'
    })

@app.route('/api/notifications')
def api_notifications():
    """Simulated authenticated API endpoint"""
    return jsonify({
        'unread': 3,
        'notifications': [
            {'id': 1, 'text': 'Welcome to the demo'},
            {'id': 2, 'text': 'CookieGuard is analyzing your cookies'},
            {'id': 3, 'text': 'Check the extension for results'}
        ]
    })

@app.route('/simulate/xss')
def simulate_xss():
    """Safe XSS simulation page (Scenario B only)"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>XSS Simulation</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
            }
            .warning {
                background: #fed7d7;
                border-left: 4px solid #c53030;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 4px;
            }
            .demo {
                background: #f7fafc;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            code {
                background: #edf2f7;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <h1>⚠️ XSS Simulation (Safe Demo)</h1>
        
        <div class="warning">
            <strong>This is a controlled demonstration</strong><br>
            In a real XSS attack, malicious JavaScript could steal your cookies.
        </div>
        
        <div class="demo">
            <h3>What an attacker could access:</h3>
            <p><strong>document.cookie:</strong></p>
            <code id="cookie-display"></code>
            
            <p style="margin-top: 20px;">
                This demonstrates why the <strong>HttpOnly</strong> flag is critical.<br>
                With HttpOnly=true, JavaScript cannot access the cookie.
            </p>
        </div>
        
        <button onclick="window.close()">Close</button>
        
        <script>
            // Safely display cookies (this is the vulnerability being demonstrated)
            document.getElementById('cookie-display').textContent = document.cookie || '(no accessible cookies)';
        </script>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'current_scenario': current_scenario,
        'scenarios_available': list(SCENARIO_INFO.keys())
    })

if __name__ == '__main__':
    print("=" * 60)
    print("CookieGuard AI - Demo Test Site")
    print("=" * 60)
    print("\nScenarios:")
    for scenario, info in SCENARIO_INFO.items():
        print(f"  {scenario}: {info['description']} [{info['severity']}]")
    print("\n🌐 Starting server on http://localhost:8000")
    print("=" * 60)

    app.run(debug=True, host='0.0.0.0', port=8000)