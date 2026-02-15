"""
CookieGuard AI 2.0 - Training Script with Multi-Model Benchmarking
Trains RF, LR, HistGBT → selects best → calibrates → saves model + model_card.json
"""

import json
import csv
import numpy as np
import sys
from pathlib import Path

from sklearn.model_selection import train_test_split, GroupKFold
from sklearn.metrics import classification_report, accuracy_score

sys.path.insert(0, str(Path(__file__).parent))
from feature_extractor import CookieFeatureExtractor
from classifier import CookieClassifier
from generate_training_data import TrainingDataGenerator


def train_model():
    print("=" * 70)
    print("  CookieGuard AI 2.0 — Multi-Model Training Pipeline")
    print("=" * 70)

    data_dir = Path(__file__).parent.parent / 'data'
    model_dir = Path(__file__).parent.parent / 'models'
    data_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    data_path = data_dir / 'training_cookies.json'

    # ──────────────────────────────────────────────────────────
    # Step 1: Generate / Load data
    # ──────────────────────────────────────────────────────────
    if not data_path.exists():
        print("\n[1/6] Generating training data with behavior features...")
        generator = TrainingDataGenerator()
        training_data = generator.generate_dataset(n_samples=1000)
        with open(data_path, 'w') as f:
            json.dump(training_data, f, indent=2)
        print(f"      Generated {len(training_data)} samples")
    else:
        print("\n[1/6] Loading training data...")
        with open(data_path, 'r') as f:
            training_data = json.load(f)
        print(f"      Loaded {len(training_data)} samples")

    # ──────────────────────────────────────────────────────────
    # Step 2: Extract features (38 features)
    # ──────────────────────────────────────────────────────────
    print("\n[2/6] Extracting 38 features (attributes + scope + lexical + behavior)...")
    extractor = CookieFeatureExtractor()
    feature_names = extractor.get_feature_names()
    label_map = {'other': 0, 'authentication': 1, 'tracking': 2, 'preference': 3}

    X, y, site_ids = [], [], []
    for cookie in training_data:
        features = extractor.extract_features(cookie)
        X.append([features[n] for n in feature_names])
        y.append(label_map[cookie['label']])
        site_ids.append(cookie.get('site_id', 'unknown'))

    X, y = np.array(X), np.array(y)
    site_ids = np.array(site_ids)

    print(f"      Feature matrix: {X.shape}")
    print(f"      Feature groups: {list(extractor.get_feature_groups().keys())}")
    unique, counts = np.unique(y, return_counts=True)
    print(f"      Class distribution: {dict(zip([label_map_inv for label_map_inv in ['other','auth','track','pref']], counts))}")

    # ──────────────────────────────────────────────────────────
    # Step 3: Group-holdout split by site_id
    # ──────────────────────────────────────────────────────────
    print("\n[3/6] Splitting with site-based group holdout...")
    unique_sites = np.unique(site_ids)

    # Hold out 2 sites for validation
    np.random.seed(42)
    holdout_sites = np.random.choice(unique_sites, size=min(2, len(unique_sites)), replace=False)
    val_mask = np.isin(site_ids, holdout_sites)
    train_mask = ~val_mask

    # If holdout is too small, fall back to random split
    if val_mask.sum() < 50:
        print("      (Group holdout too small, falling back to random split)")
        train_mask_idx, val_mask_idx = train_test_split(
            np.arange(len(y)), test_size=0.2, random_state=42, stratify=y
        )
        train_mask = np.zeros(len(y), dtype=bool)
        val_mask = np.zeros(len(y), dtype=bool)
        train_mask[train_mask_idx] = True
        val_mask[val_mask_idx] = True

    X_train, X_val = X[train_mask], X[val_mask]
    y_train, y_val = y[train_mask], y[val_mask]

    print(f"      Train: {len(X_train)} (sites: {np.unique(site_ids[train_mask])})")
    print(f"      Val:   {len(X_val)} (sites: {np.unique(site_ids[val_mask])})")

    # ──────────────────────────────────────────────────────────
    # Step 4: Multi-model benchmarking
    # ──────────────────────────────────────────────────────────
    print("\n[4/6] Benchmarking 3 models...")
    classifier = CookieClassifier()
    results = classifier.benchmark_models(X_train, y_train, X_val, y_val, feature_names, alpha=0.10)

    # Print ranking table
    print("\n  ┌─────────────────────────┬──────────┬──────────┬───────────┬────────────────┐")
    print("  │ Model                   │ Accuracy │ F1 Macro │ PR-AUC    │ Recall@FPR≤0.1 │")
    print("  ├─────────────────────────┼──────────┼──────────┼───────────┼────────────────┤")
    for r in results:
        print(f"  │ {r['name']:<23} │ {r['accuracy']:.4f}   │ {r['f1_macro']:.4f}   │ {r['pr_auc_auth']:.4f}    │ {r['recall_at_alpha']:.4f}         │")
    print("  └─────────────────────────┴──────────┴──────────┴───────────┴────────────────┘")

    # Save metrics CSV
    metrics_path = model_dir / 'benchmark_results.csv'
    with open(metrics_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['model', 'accuracy', 'f1_macro', 'pr_auc_auth', 'recall_at_alpha'])
        writer.writeheader()
        for r in results:
            writer.writerow({
                'model': r['name'],
                'accuracy': f"{r['accuracy']:.4f}",
                'f1_macro': f"{r['f1_macro']:.4f}",
                'pr_auc_auth': f"{r['pr_auc_auth']:.4f}",
                'recall_at_alpha': f"{r['recall_at_alpha']:.4f}"
            })
    print(f"\n  ✓ Benchmark results saved to {metrics_path}")

    # ──────────────────────────────────────────────────────────
    # Step 5: Select best and calibrate
    # ──────────────────────────────────────────────────────────
    print(f"\n[5/6] Selecting best model: {results[0]['name']}")
    classifier.select_and_calibrate(results[0], X_val, y_val)

    # Evaluate selected model
    pred_train, _ = classifier.predict(X_train)
    pred_val, _ = classifier.predict(X_val)
    
    labels = ['other', 'authentication', 'tracking', 'preference']
    print(f"\n  Training accuracy:   {accuracy_score(y_train, pred_train):.2%}")
    print(f"  Validation accuracy: {accuracy_score(y_val, pred_val):.2%}")
    print(f"\n  Classification Report (Validation):")
    print(classification_report(y_val, pred_val, target_names=labels, zero_division=0))

    print("  Top 5 important features:")
    for feat, imp in classifier.get_top_features(5):
        print(f"    {feat}: {imp:.4f}")

    # ──────────────────────────────────────────────────────────
    # Step 6: Save model + model card + feature schema
    # ──────────────────────────────────────────────────────────
    print(f"\n[6/6] Saving artifacts...")

    model_file = model_dir / 'cookie_classifier.pkl'
    classifier.save_model(str(model_file))
    print(f"  ✓ Model: {model_file}")

    # Model card
    model_card = classifier.generate_model_card(metrics={
        'accuracy': float(accuracy_score(y_val, pred_val)),
        'f1_macro': float(results[0]['f1_macro']),
        'pr_auc_auth': float(results[0]['pr_auc_auth']),
        'recall_at_alpha': float(results[0]['recall_at_alpha']),
        'alpha': float(results[0]['alpha']),
        'train_size': int(len(X_train)),
        'val_size': int(len(X_val)),
    })
    card_path = model_dir / 'model_card.json'
    with open(card_path, 'w') as f:
        json.dump(model_card, f, indent=2)
    print(f"  ✓ Model card: {card_path}")

    # Feature schema
    feature_schema = {
        'version': '2.0',
        'total_features': len(feature_names),
        'feature_names': feature_names,
        'feature_groups': extractor.get_feature_groups(),
    }
    schema_path = model_dir / 'feature_schema.json'
    with open(schema_path, 'w') as f:
        json.dump(feature_schema, f, indent=2)
    print(f"  ✓ Feature schema: {schema_path}")

    # ──────────────────────────────────────────────────────────
    # Test examples
    # ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  Testing with examples:")
    print("=" * 70)

    test_examples = [
        {
            "name": "__Host-session_token", "domain": "example.com", "path": "/",
            "secure": True, "httpOnly": True, "sameSite": "Strict",
            "expirationDate": None, "value": "eyJ.abc.123",
            "changed_during_login": 1, "new_after_login": 1, "rotated_after_login": 1
        },
        {
            "name": "_ga", "domain": ".example.com", "path": "/",
            "secure": False, "httpOnly": False, "sameSite": None,
            "expirationDate": 1780272000, "value": "GA1.2.123.456",
            "changed_during_login": 0, "new_after_login": 0, "rotated_after_login": 0
        },
        {
            "name": "theme", "domain": "example.com", "path": "/",
            "secure": False, "httpOnly": False, "sameSite": "Lax",
            "expirationDate": 1748736000, "value": "dark",
            "changed_during_login": 0, "new_after_login": 0, "rotated_after_login": 0
        },
        {
            "name": "session_id", "domain": ".bank.com", "path": "/",
            "secure": False, "httpOnly": False, "sameSite": None,
            "expirationDate": None, "value": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "changed_during_login": 1, "new_after_login": 1, "rotated_after_login": 1
        },
    ]

    for cookie in test_examples:
        features = extractor.extract_features(cookie)
        cookie_type, conf, probs = classifier.predict_from_dict(features, cookie)
        contributions = classifier.get_feature_contributions(features)
        print(f"\n  Cookie: {cookie['name']}")
        print(f"    Type: {cookie_type} ({conf:.1%})")
        print(f"    Probs: {probs}")
        if contributions.get('auth_drivers'):
            print(f"    Top auth signals: {[(n, f'{c:.3f}') for n, c, v in contributions['auth_drivers'][:3]]}")

    print("\n" + "=" * 70)
    print("  Training complete!")
    print("=" * 70)
    return classifier, extractor


if __name__ == "__main__":
    train_model()
