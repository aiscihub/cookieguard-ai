#!/usr/bin/env python3
"""
CookieGuard Backend Testing Suite
Tests all Flask API endpoints with various scenarios
"""

import requests
import json
from typing import Dict, List, Any
from datetime import datetime
import sys

class BackendTester:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.results = []
        
    def log(self, message: str, status: str = "INFO"):
        """Log test results"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "PASS": "\033[92m",  # Green
            "FAIL": "\033[91m",  # Red
            "INFO": "\033[94m",  # Blue
            "WARN": "\033[93m",  # Yellow
            "RESET": "\033[0m"
        }
        color = colors.get(status, colors["INFO"])
        print(f"[{timestamp}] {color}{status:5}{colors['RESET']} | {message}")
        
    def test_health(self) -> bool:
        """Test /health endpoint"""
        self.log("Testing /health endpoint...", "INFO")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "healthy":
                self.log(f"✓ Health check passed - Model loaded: {data.get('model_loaded')}", "PASS")
                return True
            else:
                self.log(f"✗ Health check failed - Status: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"✗ Health check failed - {str(e)}", "FAIL")
            return False
    
    def test_demo(self) -> bool:
        """Test /api/demo endpoint"""
        self.log("Testing /api/demo endpoint...", "INFO")
        try:
            response = requests.get(f"{self.base_url}/api/demo", timeout=5)
            data = response.json()
            
            if response.status_code == 200 and "cookies" in data:
                cookie_count = len(data["cookies"])
                self.log(f"✓ Demo endpoint working - {cookie_count} cookies returned", "PASS")
                return True
            else:
                self.log(f"✗ Demo endpoint failed - Status: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"✗ Demo endpoint failed - {str(e)}", "FAIL")
            return False
    
    def test_analyze_basic(self) -> bool:
        """Test /api/analyze with basic cookies"""
        self.log("Testing /api/analyze with basic cookies...", "INFO")
        
        test_cookies = [
            {
                "name": "session_id",
                "value": "abc123xyz",
                "domain": "example.com",
                "path": "/",
                "secure": False,
                "httpOnly": False,
                "sameSite": "none"
            }
        ]
        
        try:
            response = requests.post(
                f"{self.base_url}/api/analyze",
                json={"cookies": test_cookies},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            data = response.json()
            
            if response.status_code == 200 and "results" in data:
                result_count = len(data["results"])
                summary = data.get("summary_stats", {})
                self.log(f"✓ Analysis passed - {result_count} results, {summary.get('critical', 0)} critical issues", "PASS")
                return True
            else:
                self.log(f"✗ Analysis failed - Status: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"✗ Analysis failed - {str(e)}", "FAIL")
            return False
    
    def test_analyze_auth_cookies(self) -> bool:
        """Test /api/analyze with authentication cookies"""
        self.log("Testing /api/analyze with insecure auth cookies...", "INFO")
        
        test_cookies = [
            {
                "name": "auth_token",
                "value": "secret_token_12345",
                "domain": "example.com",
                "path": "/",
                "secure": False,  # Insecure!
                "httpOnly": False,  # Insecure!
                "sameSite": "none"  # Insecure!
            },
            {
                "name": "session_key",
                "value": "sess_xyz789",
                "domain": "example.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "strict"
            }
        ]
        
        try:
            response = requests.post(
                f"{self.base_url}/api/analyze",
                json={"cookies": test_cookies},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            data = response.json()
            
            if response.status_code == 200:
                summary = data.get("summary_stats", {})
                critical = summary.get("critical", 0)
                
                if critical > 0:
                    self.log(f"✓ Correctly detected {critical} critical issues in insecure auth cookie", "PASS")
                    return True
                else:
                    self.log("✗ Failed to detect critical issues in insecure auth cookie", "FAIL")
                    return False
            else:
                self.log(f"✗ Analysis failed - Status: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"✗ Analysis failed - {str(e)}", "FAIL")
            return False
    
    def test_analyze_login_basic(self) -> bool:
        """Test /api/analyze-login with basic scenario"""
        self.log("Testing /api/analyze-login with login scenario...", "INFO")
        
        before_cookies = [
            {
                "name": "_ga",
                "value": "GA1.2.123456",
                "domain": "example.com",
                "type": "tracking"
            }
        ]
        
        after_cookies = [
            {
                "name": "_ga",
                "value": "GA1.2.123456",
                "domain": "example.com",
                "type": "tracking"
            },
            {
                "name": "session_id",
                "value": "new_session_xyz",
                "domain": "example.com",
                "type": "authentication",
                "secure": True,
                "httpOnly": True
            },
            {
                "name": "user_id",
                "value": "12345",
                "domain": "example.com",
                "type": "authentication"
            }
        ]
        
        try:
            response = requests.post(
                f"{self.base_url}/api/analyze-login",
                json={"before": before_cookies, "after": after_cookies},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            data = response.json()
            
            if response.status_code == 200:
                login_detected = data.get("login_detected", False)
                added = len(data.get("changes", {}).get("added", []))
                
                if login_detected and added > 0:
                    self.log(f"✓ Correctly detected login - {added} new cookies", "PASS")
                    return True
                else:
                    self.log(f"✗ Failed to detect login event", "FAIL")
                    return False
            else:
                self.log(f"✗ Login analysis failed - Status: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"✗ Login analysis failed - {str(e)}", "FAIL")
            return False
    
    def test_analyze_logout(self) -> bool:
        """Test /api/analyze-login with logout scenario"""
        self.log("Testing /api/analyze-login with logout scenario...", "INFO")
        
        before_cookies = [
            {
                "name": "session_id",
                "value": "active_session",
                "domain": "example.com",
                "type": "authentication"
            },
            {
                "name": "user_id",
                "value": "12345",
                "domain": "example.com",
                "type": "authentication"
            }
        ]
        
        after_cookies = [
            # Session cookies removed after logout
        ]
        
        try:
            response = requests.post(
                f"{self.base_url}/api/analyze-login",
                json={"before": before_cookies, "after": after_cookies},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            data = response.json()
            
            if response.status_code == 200:
                removed = len(data.get("changes", {}).get("removed", []))
                
                if removed > 0:
                    self.log(f"✓ Correctly detected logout - {removed} cookies removed", "PASS")
                    return True
                else:
                    self.log("✗ Failed to detect logout event", "FAIL")
                    return False
            else:
                self.log(f"✗ Logout analysis failed - Status: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"✗ Logout analysis failed - {str(e)}", "FAIL")
            return False
    
    def test_analyze_bulk(self) -> bool:
        """Test /api/analyze with many cookies"""
        self.log("Testing /api/analyze with bulk cookies...", "INFO")
        
        # Generate 50 test cookies
        test_cookies = []
        cookie_types = ["tracking", "functional", "authentication"]
        cookie_names = {
            "tracking": ["_ga", "_gid", "__utma", "__utmz", "analytics_id"],
            "functional": ["preferences", "language", "theme", "currency"],
            "authentication": ["session", "token", "auth", "user_id", "csrf"]
        }
        
        for i in range(50):
            cookie_type = cookie_types[i % 3]
            name_list = cookie_names[cookie_type]
            
            test_cookies.append({
                "name": f"{name_list[i % len(name_list)]}_{i}",
                "value": f"value_{i}",
                "domain": "example.com",
                "path": "/",
                "secure": i % 2 == 0,
                "httpOnly": cookie_type == "authentication" and i % 2 == 0,
                "sameSite": "lax" if i % 3 == 0 else "none"
            })
        
        try:
            response = requests.post(
                f"{self.base_url}/api/analyze",
                json={"cookies": test_cookies},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            data = response.json()
            
            if response.status_code == 200 and len(data.get("results", [])) == 50:
                self.log(f"✓ Bulk analysis passed - {len(data['results'])} cookies analyzed", "PASS")
                return True
            else:
                self.log(f"✗ Bulk analysis failed - Expected 50 results, got {len(data.get('results', []))}", "FAIL")
                return False
        except Exception as e:
            self.log(f"✗ Bulk analysis failed - {str(e)}", "FAIL")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling with invalid input"""
        self.log("Testing error handling...", "INFO")
        
        tests = [
            ("Empty cookie list", {"cookies": []}),
            ("Missing cookies key", {}),
            ("Invalid cookie format", {"cookies": [{"invalid": "data"}]}),
        ]
        
        passed = 0
        for test_name, payload in tests:
            try:
                response = requests.post(
                    f"{self.base_url}/api/analyze",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                
                # Should either succeed with empty results or return proper error
                if response.status_code in [200, 400]:
                    passed += 1
                    self.log(f"  ✓ {test_name}: Handled correctly", "PASS")
                else:
                    self.log(f"  ✗ {test_name}: Unexpected status {response.status_code}", "FAIL")
            except Exception as e:
                self.log(f"  ✗ {test_name}: {str(e)}", "FAIL")
        
        if passed == len(tests):
            self.log(f"✓ Error handling passed - {passed}/{len(tests)} tests", "PASS")
            return True
        else:
            self.log(f"✗ Error handling failed - {passed}/{len(tests)} tests passed", "FAIL")
            return False
    
    def run_all_tests(self):
        """Run all tests and generate report"""
        self.log("=" * 60, "INFO")
        self.log("CookieGuard Backend Test Suite", "INFO")
        self.log(f"Testing: {self.base_url}", "INFO")
        self.log("=" * 60, "INFO")
        
        tests = [
            ("Health Check", self.test_health),
            ("Demo Endpoint", self.test_demo),
            ("Basic Analysis", self.test_analyze_basic),
            ("Auth Cookie Analysis", self.test_analyze_auth_cookies),
            ("Login Detection", self.test_analyze_login_basic),
            ("Logout Detection", self.test_analyze_logout),
            ("Bulk Analysis", self.test_analyze_bulk),
            ("Error Handling", self.test_error_handling),
        ]
        
        results = []
        for test_name, test_func in tests:
            self.log("", "INFO")
            self.log(f"Running: {test_name}", "INFO")
            self.log("-" * 60, "INFO")
            try:
                passed = test_func()
                results.append((test_name, passed))
            except Exception as e:
                self.log(f"Test crashed: {str(e)}", "FAIL")
                results.append((test_name, False))
        
        # Summary
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        self.log("Test Summary", "INFO")
        self.log("=" * 60, "INFO")
        
        passed_count = sum(1 for _, passed in results if passed)
        total_count = len(results)
        
        for test_name, passed in results:
            status = "PASS" if passed else "FAIL"
            self.log(f"{test_name:30} : {'✓' if passed else '✗'}", status)
        
        self.log("", "INFO")
        self.log(f"Results: {passed_count}/{total_count} tests passed", 
                "PASS" if passed_count == total_count else "WARN")
        
        if passed_count == total_count:
            self.log("🎉 All tests passed!", "PASS")
            return 0
        else:
            self.log(f"⚠️  {total_count - passed_count} test(s) failed", "WARN")
            return 1

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="CookieGuard Backend Testing Suite")
    parser.add_argument(
        "--url",
        default="http://localhost:5000",
        help="Backend URL (default: http://localhost:5000)"
    )
    parser.add_argument(
        "--test",
        choices=["health", "demo", "analyze", "login", "all"],
        default="all",
        help="Specific test to run (default: all)"
    )
    
    args = parser.parse_args()
    
    tester = BackendTester(args.url)
    
    if args.test == "all":
        return tester.run_all_tests()
    elif args.test == "health":
        return 0 if tester.test_health() else 1
    elif args.test == "demo":
        return 0 if tester.test_demo() else 1
    elif args.test == "analyze":
        return 0 if tester.test_analyze_basic() else 1
    elif args.test == "login":
        return 0 if tester.test_analyze_login_basic() else 1

if __name__ == "__main__":
    sys.exit(main())
