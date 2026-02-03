# CookieGuard AI - Setup & Testing Guide

## Quick Start (5 minutes)

### Prerequisites
- Python 3.8 or higher
- Node.js 16 or higher
- pip and npm

### Automated Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd cookieguard-ai

# Run setup script (installs dependencies & trains model)
chmod +x setup.sh
./setup.sh
```

### Manual Setup

#### Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Train the ML model (required for first run)
python backend/train_model.py

# This will:
# - Generate 800 synthetic training examples
# - Train a Random Forest classifier
# - Save the model to models/cookie_classifier.pkl
# - Display training accuracy and feature importance
```

#### Frontend Setup

```bash
# Install Node dependencies
cd frontend
npm install
```

---

## Running the Application

### Option 1: Full Web Application

**Terminal 1 - Backend Server:**
```bash
cd cookieguard-ai
python backend/app.py

# Server will start on http://localhost:5000
# Endpoints:
#   GET  /health              - Health check
#   GET  /api/demo            - Get demo cookies
#   POST /api/analyze         - Analyze cookies
#   POST /api/export-report   - Export security report
```

**Terminal 2 - Frontend:**
```bash
cd cookieguard-ai/frontend
npm start

# React app will open at http://localhost:3000
```

**Usage:**
1. Click "Load Demo" to see example cookies with security issues
2. Or upload your own cookie export (JSON format)
3. Click "Analyze Cookies" to run AI detection
4. View detailed security report with risk rankings
5. Export report as text file

### Option 2: Command-Line Demo

```bash
cd cookieguard-ai
python backend/demo.py

# Runs a complete demonstration showing:
# - AI classification of 4 example cookies
# - Risk scoring and severity assessment
# - Detailed security issue explanations
# - Summary statistics
```

---

## Testing the System

### Test 1: Model Training

```bash
python backend/train_model.py
```

**Expected Output:**
- Generates 800 training samples (200 per class)
- Feature matrix shape: (800, 18)
- Training accuracy: ~95-100%
- Top features: value_length, value_entropy, expiry_days
- Successfully saves model to `models/cookie_classifier.pkl`

**What This Tests:**
- Feature extraction pipeline
- ML model training
- Synthetic data generation
- Model serialization

---

### Test 2: Feature Extraction

```bash
python backend/feature_extractor.py
```

**Expected Output:**
- Extracts features from 2 test cookies
- Shows 18 features per cookie:
  - Security flags (secure, httpOnly, sameSite)
  - Expiry characteristics
  - Domain/path scope
  - Name pattern matching
  - Entropy calculations

**What This Tests:**
- Cookie attribute parsing
- Pattern matching (auth/tracking/preference)
- Entropy calculations
- Feature engineering

---

### Test 3: ML Classification

```bash
python backend/classifier.py
```

**Expected Output:**
- Generates synthetic training data
- Trains Random Forest on 150 samples
- Tests on 50 samples
- Shows prediction probabilities
- Lists top 5 important features

**What This Tests:**
- ML model functionality
- Probability outputs
- Feature importance ranking

---

### Test 4: Risk Scoring

```bash
python backend/risk_scorer.py
```

**Expected Output:**
- Analyzes a vulnerable authentication cookie
- Identifies 2-3 critical/high severity issues:
  - Missing HttpOnly flag (CRITICAL)
  - Missing SameSite protection (HIGH)
  - Broad domain scope (MEDIUM)
- Provides plain-language explanations
- Suggests security recommendations

**What This Tests:**
- Security rule evaluation
- Risk severity calculation
- Plain-language explanation generation
- Recommendation engine

---

### Test 5: Full Demo Workflow

```bash
python backend/demo.py
```

**Expected Output:**
```
================================================================================
COOKIEGUARD AI - LIVE DEMONSTRATION
================================================================================

[1/4] Loading AI Model...
✓ Model loaded successfully

[2/4] Loading Example Cookies...
✓ Loaded 4 example cookies

[3/4] Running AI Analysis...
Analyzing Cookie 1/4: session_token
  AI Classification: authentication (100% confidence)
  Risk Level: CRITICAL
  Issues Found: 3
...

SUMMARY STATISTICS
Total Cookies Analyzed: 4
Critical Risk: 1
High Risk: 1
...

KEY INSIGHTS
✓ AI detected 2 authentication cookie(s)
✓ Found 1 CRITICAL security issue(s)
✓ 5 total security issues identified
```

**What This Tests:**
- End-to-end pipeline
- AI classification accuracy
- Risk prioritization
- Multiple cookie analysis
- Report generation

---

### Test 6: API Endpoints

**Start the backend server:**
```bash
python backend/app.py
```

**Test health check:**
```bash
curl http://localhost:5000/health
```
Expected: `{"status":"healthy","model_loaded":true}`

**Test demo cookies endpoint:**
```bash
curl http://localhost:5000/api/demo
```
Expected: JSON with 5 example cookies

**Test analysis endpoint:**
```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "cookies": [{
      "name": "test_session",
      "domain": "example.com",
      "path": "/",
      "secure": false,
      "httpOnly": false,
      "sameSite": null
    }]
  }'
```
Expected: JSON with analysis results including ML classification and risk assessment

---

## Validation Checklist

Use this checklist to verify the system is working correctly:

### Backend
- [ ] `requirements.txt` dependencies install without errors
- [ ] Model training completes with >90% accuracy
- [ ] Model file saved to `models/cookie_classifier.pkl`
- [ ] Demo script runs and identifies critical issues
- [ ] Flask API starts on port 5000
- [ ] `/health` endpoint returns healthy status
- [ ] `/api/demo` returns example cookies
- [ ] `/api/analyze` correctly classifies cookies

### Frontend
- [ ] `npm install` completes successfully
- [ ] App starts on http://localhost:3000
- [ ] "Load Demo" button loads example cookies
- [ ] "Analyze Cookies" button triggers analysis
- [ ] Results display with severity badges
- [ ] Critical issues show in red
- [ ] Export report generates downloadable file

### AI Functionality
- [ ] Authentication cookies classified correctly (>80% confidence)
- [ ] Tracking cookies classified correctly (>80% confidence)
- [ ] Preference cookies classified correctly (>60% confidence)
- [ ] Missing HttpOnly on auth cookies = CRITICAL
- [ ] Missing Secure on auth cookies = HIGH
- [ ] Missing SameSite on auth cookies = HIGH
- [ ] Cookies ranked by risk score (highest first)

---

## Common Issues & Solutions

### "Model not found" error
**Solution:** Run `python backend/train_model.py` first

### Port 5000 already in use
**Solution:** Either kill the existing process or change the port in `backend/app.py`

### CORS errors in frontend
**Solution:** Ensure backend is running and `flask-cors` is installed

### npm start fails
**Solution:** 
- Delete `node_modules` and `package-lock.json`
- Run `npm install` again
- Ensure Node.js version is 16+

### Feature extraction errors
**Solution:** Check that cookies have all required fields (name, domain, path)

---

## Performance Benchmarks

On typical hardware:
- **Model Training:** 2-5 seconds (800 samples)
- **Single Cookie Analysis:** <10ms
- **Batch Analysis (50 cookies):** <500ms
- **Frontend Load Time:** <2 seconds

---

## Next Steps After Testing

1. **Customize Training Data:** Add real-world cookie examples to improve accuracy
2. **Tune Model:** Adjust Random Forest parameters for your use case
3. **Add Cookie Sources:** Support browser exports (Chrome, Firefox, Edge)
4. **Deploy:** Use Gunicorn for backend, build frontend for production

---

## Support

If you encounter issues:
1. Check this testing guide
2. Run each test individually to isolate the problem
3. Check console output for error messages
4. Verify all dependencies are installed correctly
