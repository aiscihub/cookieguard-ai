# 🔌 CookieGuard AI - Backend-Integrated Version

## 🚀 Quick Start (Local Mode)

**No setup needed** - just install and use!

```
1. Load extension in Chrome (chrome://extensions/)
2. Click extension icon on any site
3. Click "Scan This Site"
4. Results in 2 seconds!
```

## 🔧 Troubleshooting

### "Export shows 0 cookies" ⚠️ MOST COMMON ISSUE
**Cause:** Missing `host_permissions` in manifest.json

**Solution:**
```json
"host_permissions": ["<all_urls>"]
```

**Steps:**
1. Update manifest.json with host_permissions
2. Go to `chrome://extensions`
3. Click reload 🔄 on CookieGuard extension
4. Grant permissions when prompted
5. Visit any website (e.g., google.com)
6. Try export again - should work!

**Verify permissions:**
- Open extension popup
- Right-click → Inspect
- Console: `chrome.cookies.getAll({}).then(c => console.log(c.length))`
- Should show > 0 cookies