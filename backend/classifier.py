"""
CookieGuard AI 2.0 - Multi-Model Classifier with Benchmarking
Trains and evaluates: RandomForest, LogisticRegression, HistGradientBoosting
Selects best model by Recall@FPR constraint + PR-AUC, saves model card.
"""

import pickle
import json
import numpy as np
from typing import Dict, Tuple, Optional, List
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    classification_report, accuracy_score, precision_recall_curve,
    auc, roc_curve, f1_score
)


class CookieClassifier:
    """Multi-model cookie classifier with calibration and rule fallbacks."""

    LABELS = {0: 'other', 1: 'authentication', 2: 'tracking', 3: 'preference'}
    LABEL_MAP = {'other': 0, 'authentication': 1, 'tracking': 2, 'preference': 3}

    def __init__(self, model_path=None):
        self.model = None
        self.model_name = None
        self.scaler = None
        self.feature_names = None
        self.feature_importance = {}
        self.calibrators = {}
        self.lr_coefficients = None  # For LR explainability
        if model_path:
            self.load_model(model_path)

    # ─────────────────────────────────────────────────────────────
    # Multi-model benchmarking
    # ─────────────────────────────────────────────────────────────

    def benchmark_models(self, X_train, y_train, X_val, y_val, feature_names, alpha=0.10):
        """
        Train and evaluate multiple models. Select best by auth recall @ FPR ≤ alpha.
        
        Returns:
            List of dicts with model name, metrics, and trained model objects.
        """
        self.feature_names = feature_names
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        candidates = {
            'RandomForest': RandomForestClassifier(
                n_estimators=150, max_depth=12, min_samples_split=5,
                min_samples_leaf=2, class_weight='balanced', random_state=42, n_jobs=-1
            ),
            'LogisticRegression': LogisticRegression(
                C=1.0, max_iter=1000, class_weight='balanced',
                solver='lbfgs', random_state=42
            ),
            'HistGradientBoosting': HistGradientBoostingClassifier(
                max_iter=200, max_depth=8, learning_rate=0.1,
                min_samples_leaf=5, random_state=42
            ),
        }

        results = []

        for name, clf in candidates.items():
            print(f"\n  Training {name}...")
            clf.fit(X_train_scaled, y_train)

            # Get probabilities
            probs_val = clf.predict_proba(X_val_scaled)
            preds_val = clf.predict(X_val_scaled)

            # Overall accuracy and F1
            acc = accuracy_score(y_val, preds_val)
            f1_macro = f1_score(y_val, preds_val, average='macro', zero_division=0)

            # Auth-specific: binary (auth=1 vs rest)
            y_val_auth = (y_val == 1).astype(int)
            probs_auth = probs_val[:, 1] if probs_val.shape[1] > 1 else probs_val[:, 0]

            # PR-AUC for auth class
            precision_arr, recall_arr, _ = precision_recall_curve(y_val_auth, probs_auth)
            pr_auc = auc(recall_arr, precision_arr)

            # Recall @ FPR ≤ alpha
            fpr, tpr, thresholds = roc_curve(y_val_auth, probs_auth)
            valid = fpr <= alpha
            recall_at_alpha = tpr[valid].max() if valid.any() else 0.0

            # Feature importance
            if hasattr(clf, 'feature_importances_'):
                importance = dict(zip(feature_names, clf.feature_importances_))
            elif hasattr(clf, 'coef_'):
                # For LR: use mean absolute coefficient across classes
                mean_abs = np.abs(clf.coef_).mean(axis=0)
                importance = dict(zip(feature_names, mean_abs / mean_abs.sum()))
            else:
                importance = {}

            results.append({
                'name': name,
                'model': clf,
                'accuracy': acc,
                'f1_macro': f1_macro,
                'pr_auc_auth': pr_auc,
                'recall_at_alpha': recall_at_alpha,
                'alpha': alpha,
                'feature_importance': importance,
                'probs_val': probs_val,
            })

            print(f"    Accuracy: {acc:.2%} | F1(macro): {f1_macro:.3f} | "
                  f"PR-AUC(auth): {pr_auc:.3f} | Recall@FPR≤{alpha}: {recall_at_alpha:.3f}")

        # Sort by: recall_at_alpha (primary), then pr_auc_auth (secondary)
        results.sort(key=lambda r: (r['recall_at_alpha'], r['pr_auc_auth']), reverse=True)
        return results

    def select_and_calibrate(self, best_result, X_val, y_val):
        """Adopt the best model and calibrate its probabilities."""
        self.model = best_result['model']
        self.model_name = best_result['name']
        self.feature_importance = best_result['feature_importance']

        # Store LR coefficients for explainability
        if hasattr(self.model, 'coef_'):
            self.lr_coefficients = {
                'coef': self.model.coef_.tolist(),
                'intercept': self.model.intercept_.tolist(),
                'classes': self.model.classes_.tolist(),
                'feature_names': self.feature_names
            }

        # Calibrate
        X_val_scaled = self.scaler.transform(X_val)
        probs_val = self.model.predict_proba(X_val_scaled)

        self.calibrators = {}
        for i in range(probs_val.shape[1]):
            cal = IsotonicRegression(out_of_bounds='clip')
            cal.fit(probs_val[:, i], y_val == i)
            self.calibrators[i] = cal

        print(f"\n  ✓ Selected model: {self.model_name}")
        print(f"  ✓ Calibration complete ({len(self.calibrators)} classes)")

    # ─────────────────────────────────────────────────────────────
    # Legacy single-model train (backward compatible)
    # ─────────────────────────────────────────────────────────────

    def train(self, X, y, feature_names, X_val=None, y_val=None):
        self.feature_names = feature_names
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=5,
            min_samples_leaf=2, class_weight='balanced', random_state=42
        )
        self.model.fit(X_scaled, y)
        self.model_name = 'RandomForest'
        self.feature_importance = dict(zip(feature_names, self.model.feature_importances_))

        if X_val is not None and y_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            probs_val = self.model.predict_proba(X_val_scaled)
            self.calibrators = {}
            for i in range(4):
                cal = IsotonicRegression(out_of_bounds='clip')
                cal.fit(probs_val[:, i], y_val == i)
                self.calibrators[i] = cal

    # ─────────────────────────────────────────────────────────────
    # Prediction
    # ─────────────────────────────────────────────────────────────

    def predict(self, features, use_calibration=True):
        if self.model is None:
            raise ValueError("Model not trained or loaded")
        if len(features.shape) == 1:
            features = features.reshape(1, -1)

        X_scaled = self.scaler.transform(features)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        if use_calibration and self.calibrators:
            cal_probs = np.zeros_like(probabilities)
            for i, cal in self.calibrators.items():
                cal_probs[:, i] = cal.predict(probabilities[:, i])
            row_sums = cal_probs.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1  # prevent div by zero
            cal_probs = cal_probs / row_sums
            probabilities = cal_probs
            predictions = np.argmax(probabilities, axis=1)

        if len(predictions) == 1:
            return predictions[0], probabilities[0]
        return predictions, probabilities

    def predict_from_dict(self, feature_dict, cookie=None):
        if cookie:
            rule = self._apply_rules(cookie)
            if rule:
                return rule

        vec = np.array([feature_dict[n] for n in self.feature_names])
        pred, probs = self.predict(vec)
        label = self.LABELS[pred]
        return label, float(probs[pred]), {self.LABELS[i]: float(p) for i, p in enumerate(probs)}

    def _apply_rules(self, cookie):
        name = cookie.get('name', '').lower()
        if name.startswith('__host-') and any(k in name for k in ['session', 'auth', 'token']):
            return ('authentication', 1.0, {'authentication': 1.0, 'tracking': 0.0, 'preference': 0.0, 'other': 0.0})
        if name in ['jsessionid', 'phpsessid', 'asp.net_sessionid']:
            return ('authentication', 0.95, {'authentication': 0.95, 'tracking': 0.0, 'preference': 0.0, 'other': 0.05})
        if name in ['_ga', '_gid', '_gat', '__utma']:
            return ('tracking', 1.0, {'authentication': 0.0, 'tracking': 1.0, 'preference': 0.0, 'other': 0.0})
        return None

    # ─────────────────────────────────────────────────────────────
    # Explainability
    # ─────────────────────────────────────────────────────────────

    def get_feature_contributions(self, feature_dict):
        """
        Get per-feature contributions to the prediction.
        Uses LR coefficients if available, otherwise feature importance * value.
        
        Returns:
            Dict with 'auth_drivers' and 'risk_drivers' lists of (feature, contribution, explanation).
        """
        if self.lr_coefficients:
            return self._lr_contributions(feature_dict)
        else:
            return self._importance_contributions(feature_dict)

    def _lr_contributions(self, feature_dict):
        """Use LR coefficients for precise per-feature contribution."""
        coef = np.array(self.lr_coefficients['coef'])
        feature_names = self.lr_coefficients['feature_names']

        # Auth class index
        auth_idx = 1
        auth_coef = coef[auth_idx]

        contributions = []
        for i, fname in enumerate(feature_names):
            val = feature_dict.get(fname, 0)
            # Scale the value the same way the model would
            if self.scaler and hasattr(self.scaler, 'mean_'):
                scaled_val = (val - self.scaler.mean_[i]) / max(self.scaler.scale_[i], 1e-10)
            else:
                scaled_val = val
            contrib = auth_coef[i] * scaled_val
            contributions.append((fname, float(contrib), float(val)))

        # Sort by absolute contribution
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)

        auth_drivers = [(n, c, v) for n, c, v in contributions if c > 0][:5]
        risk_reducers = [(n, c, v) for n, c, v in contributions if c < 0][:3]

        return {'auth_drivers': auth_drivers, 'risk_reducers': risk_reducers}

    def _importance_contributions(self, feature_dict):
        """Fallback: use feature importance * feature value as proxy."""
        contributions = []
        for fname, imp in self.feature_importance.items():
            val = feature_dict.get(fname, 0)
            contrib = imp * val
            contributions.append((fname, float(contrib), float(val)))

        contributions.sort(key=lambda x: abs(x[1]), reverse=True)

        auth_drivers = [(n, c, v) for n, c, v in contributions if c > 0][:5]
        return {'auth_drivers': auth_drivers, 'risk_reducers': []}

    # ─────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────

    def save_model(self, path):
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'model_name': self.model_name,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'feature_importance': self.feature_importance,
                'calibrators': self.calibrators,
                'lr_coefficients': self.lr_coefficients,
            }, f)

    def load_model(self, path):
        with open(path, 'rb') as f:
            d = pickle.load(f)
        self.model = d['model']
        self.model_name = d.get('model_name', 'Unknown')
        self.scaler = d['scaler']
        self.feature_names = d['feature_names']
        self.feature_importance = d.get('feature_importance', {})
        self.calibrators = d.get('calibrators', {})
        self.lr_coefficients = d.get('lr_coefficients')

    def get_top_features(self, n=5):
        if not self.feature_importance:
            return []
        return sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:n]

    def generate_model_card(self, metrics: dict = None):
        """Generate model card metadata."""
        return {
            'model_name': self.model_name,
            'version': '2.0',
            'train_date': datetime.now().isoformat(),
            'feature_count': len(self.feature_names) if self.feature_names else 0,
            'feature_groups': ['attributes', 'scope', 'lexical', 'behavior'],
            'calibrated': bool(self.calibrators),
            'has_lr_explainability': self.lr_coefficients is not None,
            'metrics': metrics or {},
        }
