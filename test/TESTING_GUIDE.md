# CookieGuard Testing Guide

## Overview
This testing suite provides comprehensive tools to test both the export functionality and login model detection of the CookieGuard Chrome extension.

## Files Included

1. **cookie-tester.html** - Interactive web-based testing tool
2. **backend_tester.py** - Python script for backend API testing
3. **test-cookies-*.json** - Sample cookie export files (generated)

## Quick Start

### 1. Testing Cookie Export Feature

#### Using the Web Tool:
1. Open `cookie-tester.html` in your browser
2. Go to the "Export Testing" tab
3. Use the extension to export cookies from any website
4. Upload the exported JSON file to see:
   - Format validation
   - Cookie statistics
   - Security analysis
   - Type breakdown

#### What to Check:
- ✓ JSON format is valid
- ✓ All required fields present (exported_at, domain, total_cookies, cookies)
- ✓ Cookie objects have proper structure (name, value, domain, secure, httpOnly, sameSite, etc.)
- ✓ Cookie types are detected (authentication, tracking, functional)

### 2. Testing Login Model

#### Using the Web Tool:
1. Open `cookie-tester.html`
2. Go to "Login Model Testing" tab
3. Method A - Use Real Data:
   - Export cookies BEFORE logging in
   - Log into a website
   - Export cookies AFTER logging in
   - Upload both files and click "Analyze Login Changes"

4. Method B - Use Generated Test Data:
   - Go to "Generate Test Data" tab
   - Click "Generate Login Pair"
   - Two files will download automatically
   - Upload both to "Login Model Testing" tab

#### What the Analysis Shows:
- **Added Cookies**: New cookies created during login (session, auth tokens)
- **Removed Cookies**: Cookies deleted (CSRF tokens, temp cookies)
- **Modified Cookies**: Cookies with changed values
- **Pattern Detection**: 
  - Login detected if auth/session cookies added
  - Logout detected if auth cookies removed
  - Session refresh if cookies modified

#### Expected Login Patterns:
✓ Session cookies added (session_id, auth_token, user_id)
✓ CSRF/temp cookies removed
✓ Existing cookies may be modified
✓ Net increase in total cookies

#### Expected Logout Patterns:
✓ Session/auth cookies removed
✓ Tracking cookies usually remain
✓ Net decrease in total cookies

### 3. Testing Backend API

#### Using Python Script:
```bash
# Make sure Flask backend is running first!
python3 backend_tester.py --url http://localhost:5000

# Or test specific endpoint:
python3 backend_tester.py --url http://localhost:5000 --test health
python3 backend_tester.py --url http://localhost:5000 --test analyze
python3 backend_tester.py --url http://localhost:5000 --test login
```

#### Using Web Tool:
1. Open `cookie-tester.html`
2. Go to "Backend Testing" tab
3. Ensure backend URL is correct (default: http://localhost:5000)
4. Click test buttons to verify each endpoint:
   - **Test /health**: Check if backend is running and model loaded
   - **Test /api/demo**: Get demo cookies
   - **Test /api/analyze**: Analyze test cookies
   - **Test /api/analyze-login**: Test login detection

#### What Each Endpoint Should Return:

**/health**
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

**/api/demo**
```json
{
  "cookies": [...],  // Array of demo cookies
  "total": 8
}
```

**/api/analyze**
```json
{
  "results": [...],  // Analysis for each cookie
  "summary_stats": {
    "total": 10,
    "critical": 2,
    "high": 3,
    "medium": 4,
    "low": 1
  }
}
```

**/api/analyze-login**
```json
{
  "login_detected": true,
  "confidence": 0.95,
  "changes": {
    "added": [...],
    "removed": [...],
    "modified": [...]
  },
  "patterns": [...]
}
```

## Test Scenarios to Try

### Export Testing Scenarios:

1. **Normal Website**
   - Visit amazon.com, google.com, or any major site
   - Export cookies
   - Verify 10-30 cookies captured
   - Check mix of cookie types

2. **Banking/Secure Site**
   - Export from bank.com or similar
   - Verify high security flags
   - Should have auth cookies with HttpOnly + Secure

3. **Tracking-Heavy Site**
   - Visit news sites with ads
   - Should see many tracking cookies
   - Low security flags expected

### Login Testing Scenarios:

1. **Standard Login Flow**
   - Export before login
   - Login to Gmail/Twitter/any site
   - Export after login
   - Should detect session cookies added

2. **Logout Flow**
   - Export while logged in
   - Logout
   - Export after logout
   - Should detect auth cookies removed

3. **Session Refresh**
   - Export cookies
   - Wait 5 minutes without navigating
   - Export again
   - Should detect cookie value modifications

### Backend Testing Scenarios:

1. **Insecure Auth Cookie**
   - Send cookie with httpOnly=false, secure=false
   - Should return severity="critical"

2. **Secure Cookie**
   - Send cookie with all security flags
   - Should return severity="low"

3. **Bulk Analysis**
   - Send 50+ cookies
   - Verify all get analyzed
   - Check performance (should complete in <5 seconds)

## Troubleshooting

### Export Not Working
- Check browser console for errors
- Verify extension has cookie permissions
- Try exporting from chrome://extensions (should fail gracefully)
- Test on regular HTTP/HTTPS sites

### Login Detection Issues
- Ensure files are from same domain
- Check timestamps (after should be > before)
- Verify JSON format is correct
- Look for actual cookie differences (use diff tool)

### Backend Connection Failed
- Verify Flask server is running: `python app.py`
- Check port 5000 is not blocked
- Try curl: `curl http://localhost:5000/health`
- Check CORS settings if using different origin

### Model Not Loading
- Verify model file exists: `model.pkl` or `cookie_classifier.pkl`
- Check Python dependencies installed
- Look at Flask console for errors
- Try rebuilding model

## Understanding the Results

### Risk Severity Levels

**CRITICAL** (Red)
- Auth cookie without HttpOnly flag
- XSS vulnerability present
- Immediate security risk

**HIGH** (Orange)
- Auth cookie without Secure flag
- Missing SameSite protection
- CSRF vulnerability

**MEDIUM** (Yellow)
- Long-lived session cookies
- Broad domain scope
- Moderate risk

**LOW** (Green)
- Properly secured cookies
- Minimal risk factors
- Best practices followed

### Login Detection Confidence

**High Confidence (>0.8)**
- Multiple session cookies added
- Clear authentication patterns
- Definite login event

**Medium Confidence (0.5-0.8)**
- Some session cookies added
- Ambiguous patterns
- Possible login event

**Low Confidence (<0.5)**
- Few changes detected
- No clear patterns
- Unlikely login event

## Sample Data Files

Generate test data using the "Generate Test Data" tab:

1. **Mixed Scenario**: Realistic blend of cookie types
2. **Insecure Scenario**: Auth cookies without security flags
3. **Tracking Scenario**: Heavy tracking cookies
4. **Secure Scenario**: Well-secured auth cookies

Each generated file can be:
- Downloaded as JSON
- Uploaded to Export Testing
- Sent to Backend for analysis
- Used for integration testing

## Advanced Testing

### Testing with Real Chrome Extension:

1. Install extension in Chrome
2. Navigate to test website
3. Click "Scan Cookies" - verify analysis works
4. Click "Export" - download JSON
5. Upload to cookie-tester.html - verify format
6. Click "Login Scan":
   - Step 1: Capture before login
   - Step 2: Perform login manually
   - Step 3: Analyze after login
7. Verify results match expectations

### Performance Testing:

```bash
# Test with increasing cookie counts
for n in 10 50 100 200; do
  # Generate $n cookies
  # Send to backend
  # Measure response time
  # Verify accuracy maintained
done
```

### Integration Testing:

1. Extension → Backend → Extension flow
2. Verify data format consistency
3. Test error handling at each step
4. Validate security warnings display correctly

## Expected Test Results

### All Tests Passing:
```
[PASS] Health Check
[PASS] Demo Endpoint
[PASS] Basic Analysis
[PASS] Auth Cookie Analysis
[PASS] Login Detection
[PASS] Logout Detection
[PASS] Bulk Analysis
[PASS] Error Handling

Results: 8/8 tests passed
🎉 All tests passed!
```

### Common Issues:
- Backend not running → 0/8 tests pass
- Model not loaded → 1/8 tests pass (only health fails)
- Wrong endpoint URLs → Specific tests fail

## Next Steps

After confirming all tests pass:

1. ✅ Export feature works correctly
2. ✅ Login model detects changes accurately
3. ✅ Backend integration functional
4. ✅ Security analysis provides value

Then proceed to:
- User acceptance testing
- Security audit
- Performance optimization
- Documentation updates
- Submission preparation

## Support

If tests fail unexpectedly:
1. Check browser console (F12)
2. Check Flask server logs
3. Verify file formats match specification
4. Review test expectations vs. actual behavior
5. Generate diagnostic report using test tools

---

**Good luck with testing! 🍪🔒**
