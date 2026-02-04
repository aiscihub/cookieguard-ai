"""
Enhanced Classifier with Calibration and Rule Fallbacks
CookieGuard AI Backend Enhancement
"""

import pickle, numpy as np
from typing import Dict, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression

class CookieClassifier:
    def __init__(self, model_path=None):
        self.model, self.scaler, self.feature_names, self.calibrators = None, None, None, {}
        if model_path: self.load_model(model_path)
    
    def train(self, X, y, feature_names, X_val=None, y_val=None):
        self.feature_names = feature_names
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.model = RandomForestClassifier(n_estimators=100, max_depth=10, min_samples_split=5, 
                                           min_samples_leaf=2, class_weight='balanced', random_state=42)
        self.model.fit(X_scaled, y)
        self.feature_importance = dict(zip(feature_names, self.model.feature_importances_))
        
        if X_val is not None and y_val is not None:
            print("  Calibrating probabilities...")
            X_val_scaled = self.scaler.transform(X_val)
            probs_val = self.model.predict_proba(X_val_scaled)
            for i in range(4):
                cal = IsotonicRegression(out_of_bounds='clip')
                cal.fit(probs_val[:,i], y_val==i)
                self.calibrators[i] = cal
            print("  ✓ Calibration complete")
    
    def predict(self, features, use_calibration=True):
        if self.model is None: raise ValueError("Model not trained")
        if len(features.shape)==1: features = features.reshape(1,-1)
        
        X_scaled = self.scaler.transform(features)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        if use_calibration and self.calibrators:
            cal_probs = np.zeros_like(probabilities)
            for i, cal in self.calibrators.items():
                cal_probs[:,i] = cal.predict(probabilities[:,i])
            cal_probs = cal_probs / cal_probs.sum(axis=1, keepdims=True)
            probabilities = cal_probs
            predictions = np.argmax(probabilities, axis=1)
        
        return (predictions[0], probabilities[0]) if len(predictions)==1 else (predictions, probabilities)
    
    def predict_from_dict(self, feature_dict, cookie=None):
        if cookie:
            rule = self._apply_rules(cookie)
            if rule: return rule
        
        vec = np.array([feature_dict[n] for n in self.feature_names])
        pred, probs = self.predict(vec)
        labels = {0:'other', 1:'authentication', 2:'tracking', 3:'preference'}
        return labels[pred], float(probs[pred]), {labels[i]:float(p) for i,p in enumerate(probs)}
    
    def _apply_rules(self, cookie):
        name = cookie.get('name','').lower()
        if name.startswith('__host-') and any(k in name for k in ['session','auth','token']):
            return ('authentication', 1.0, {'authentication':1.0,'tracking':0.0,'preference':0.0,'other':0.0})
        if name in ['jsessionid','phpsessid','asp.net_sessionid']:
            return ('authentication', 0.95, {'authentication':0.95,'tracking':0.0,'preference':0.0,'other':0.05})
        if name in ['_ga','_gid','_gat','__utma']:
            return ('tracking', 1.0, {'authentication':0.0,'tracking':1.0,'preference':0.0,'other':0.0})
        return None
    
    def save_model(self, path):
        with open(path,'wb') as f:
            pickle.dump({'model':self.model,'scaler':self.scaler,'feature_names':self.feature_names,
                        'feature_importance':self.feature_importance,'calibrators':self.calibrators}, f)
    
    def load_model(self, path):
        with open(path,'rb') as f:
            d = pickle.load(f)
        self.model, self.scaler = d['model'], d['scaler']
        self.feature_names = d['feature_names']
        self.feature_importance = d.get('feature_importance',{})
        self.calibrators = d.get('calibrators',{})
    
    def get_top_features(self, n=5):
        if not hasattr(self,'feature_importance'): return []
        return sorted(self.feature_importance.items(), key=lambda x:x[1], reverse=True)[:n]
