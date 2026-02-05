# ⚡ Quick Start - Backend Integration

## 🎯 Two Ways to Use CookieGuard

### **Option 1: Local Only** ✅ (Already Working!)
No changes needed - extension works as-is!

### **Option 2: With Backend** 🔌 (5-Minute Setup)

---

## 🚀 Enable Backend in 5 Minutes

### **Step 1: Edit One Line** (30 seconds)

Open `popup.js` and find line 9:

**Change from**:
```javascript
const CONFIG = {
  useBackend: false,  // ← Currently false
```

**Change to**:
```javascript
const CONFIG = {
  useBackend: true,  // ← Change to true
```

Save the file.

---

### **Step 2: Add CORS to Flask** (1 minute)

Open your `app.py` and add CORS:

**Add at the top**:
```python
from flask_cors import CORS
```

**Add after creating app**:
```python
app = Flask(__name__)
CORS(app)  # ← Add this line
```

**Install CORS** (if needed):
```bash
pip install flask-cors
```

Save the file.

---

### **Step 3: Start Flask Backend** (1 minute)

```bash
# Navigate to your backend folder
cd /path/to/your/backend

# Start Flask
python app.py

# You should see:
# ✓ Model loaded from models/cookie_classifier.pkl
# ✓ Server ready
# Starting server on http://localhost:5001
```

**Leave this terminal running!**

---

### **Step 4: Reload Extension** (30 seconds)

1. Go to `chrome://extensions/`
2. Find "CookieGuard AI"
3. Click the **refresh icon** (circular arrow)

---

### **Step 5: Test It** (2 minutes)

1. Open `github.com`
2. Click CookieGuard extension
3. Click "Scan This Site"
4. Right-click popup → Inspect → Console
5. Look for: `🌐 Using backend analysis...`

**If you see that message = Success!** ✅

---

## ✅ Quick Verification

**Backend Mode Working?**

Check these signs:
- [ ] Flask terminal shows: "POST /api/analyze" when you scan
- [ ] Extension console shows: "🌐 Using backend analysis..."
- [ ] Scan results appear normally

**If all ✅ → Backend integration successful!** 🎉

---

## 🔄 Test Fallback (Optional)

**Make sure fallback works**:

1. Scan a site (should work with backend)
2. Stop Flask (Ctrl+C in terminal)
3. Scan again
4. Should see: "⚠️ Backend not available, using local analysis"
5. Scan still works!

**This proves the extension is resilient** - judges love this! 💪

---

## 🐛 Something Not Working?

### **Console says "Backend not available"**

Check:
```bash
# Is Flask running?
ps aux | grep python

# Test Flask manually
curl http://localhost:5001/health

# Should return: {"status":"healthy","model_loaded":true}
```

**Common fixes**:
- Start Flask: `python app.py`
- Check port: Flask must be on 5001 (not 5000)
- Check CORS: Must have `CORS(app)` in app.py

---

### **CORS error in console**

```python
# Make sure app.py has both:
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # ← This line is essential!
```

Then:
```bash
pip install flask-cors
python app.py  # Restart Flask
```

---

### **Still using local analysis**

That's fine! It means:
- Backend is not reachable, OR
- You have `useBackend: false`

