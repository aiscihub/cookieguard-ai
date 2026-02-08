# 🍪 CookieGuard Testing Suite - Quick Start

Complete testing tools for validating the CookieGuard extension's export and login detection features.

## 📦 What's Included

1. **cookie-tester.html** - Interactive web-based testing dashboard
2. **backend_tester.py** - Python script for automated backend testing
3. **TESTING_GUIDE.md** - Comprehensive testing documentation
4. **Sample Data Files:**
   - `sample-before-login.json` - Before login snapshot (5 cookies)
   - `sample-after-login.json` - After login snapshot (8 cookies)
   - `sample-insecure.json` - Insecure cookies (6 cookies with issues)
   - `sample-secure.json` - Well-secured cookies (5 properly secured)

## 🚀 Quick Start

### Option 1: Web-Based Testing (Recommended)

1. **Open the tester:**
   ```bash
   # Just open cookie-tester.html in your browser
   open cookie-tester.html  # Mac
   xdg-open cookie-tester.html  # Linux
   # Or double-click the file
   ```

2. **Test export feature:**
   - Go to "Export Testing" tab
   - Upload any exported cookie JSON file
   - Review validation results

3. **Test login detection:**
   - Go to "Login Model Testing" tab
   - Upload `sample-before-login.json` and `sample-after-login.json`
   - Click "Analyze Login Changes"
   - Review detected patterns

### Option 2: Python Backend Testing

1. **Run automated tests:**
   ```bash
   # Make sure Flask backend is running first!
   python3 backend_tester.py
   ```

2. **Expected output:**
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

## 📋 Testing Checklist

### Export Feature Testing
- [ ] Upload `sample-secure.json` → Should show 0 critical issues
- [ ] Upload `sample-insecure.json` → Should show 2+ critical issues
- [ ] Export real cookies from extension → Should validate format
- [ ] Check cookie type detection (auth, tracking, functional)
- [ ] Verify security flag analysis (Secure, HttpOnly, SameSite)

### Login Model Testing
- [ ] Upload before/after samples → Should detect 4 added cookies
- [ ] Should identify login event with high confidence
- [ ] Should show removed CSRF token
- [ ] Generate new test pair → Should work automatically
- [ ] Test with real login flow → Should match expectations

### Backend Integration Testing
- [ ] Test /health endpoint → Should return healthy status
- [ ] Test /api/demo → Should return demo cookies
- [ ] Test /api/analyze → Should analyze cookies correctly
- [ ] Test /api/analyze-login → Should detect login events
- [ ] Test with insecure cookies → Should flag critical issues

## 🎯 Expected Test Results

### Testing Insecure Cookies
**File:** `sample-insecure.json`
```
Expected Issues:
✗ 2 CRITICAL: Auth cookies without HttpOnly/Secure
✗ 2 HIGH: Missing SameSite protection
✗ 2 MEDIUM: Broad scope, long-lived sessions
```

### Testing Login Detection
**Files:** `sample-before-login.json` + `sample-after-login.json`
```
Expected Changes:
✓ 4 cookies added (session_id, auth_token, user_id, remember_me)
✓ 1 cookie removed (csrf_temp)
✓ Login detected: HIGH confidence
```

### Testing Backend API
```
All endpoints should respond within 2 seconds:
✓ /health → 200 OK
✓ /api/demo → 200 OK, 8 demo cookies
✓ /api/analyze → 200 OK, analysis results
✓ /api/analyze-login → 200 OK, login detected
```

## 🔧 Troubleshooting

### "Backend connection failed"
- Start Flask server: `python app.py`
- Verify port 5000 is free
- Check firewall settings

### "Invalid JSON format"
- Ensure file is proper JSON
- Check for required fields
- Use sample files as reference

### "No login detected"
- Verify actual cookie differences exist
- Check timestamps (after > before)
- Review detection patterns

## 📚 Full Documentation

See `TESTING_GUIDE.md` for:
- Detailed testing procedures
- Advanced testing scenarios
- Troubleshooting guide
- Understanding results
- Performance testing

## 🎨 Testing Workflow

```
1. Development
   ↓
2. Export Test → cookie-tester.html
   ↓
3. Login Test → cookie-tester.html
   ↓
4. Backend Test → backend_tester.py
   ↓
5. Integration Test → Real extension + Backend
   ↓
6. User Testing → Real websites
   ↓
7. Ready for Submission! 🎉
```

## ⚡ Pro Tips

1. **Use generated test data** first before testing with real cookies
2. **Test backend separately** before testing full integration
3. **Keep browser console open** (F12) to see any errors
4. **Test on multiple websites** to ensure robustness
5. **Verify expected vs actual results** match consistently

## 🎓 Next Steps

Once all tests pass:
1. ✅ Test with real Chrome extension
2. ✅ Test on 5+ different websites
3. ✅ Verify UI displays results correctly
4. ✅ Test error handling with edge cases
5. ✅ Performance test with 100+ cookies
6. ✅ Security audit of findings
7. ✅ User acceptance testing
8. ✅ Final polish and submission prep

---

**Happy Testing! 🚀**

For questions or issues, review the TESTING_GUIDE.md or check your implementation.
