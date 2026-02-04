"""
Enhanced Training Script with Domain Holdout and Calibration
CookieGuard AI Backend Enhancement
"""

import json, numpy as np, sys
from pathlib import Path
from sklearn.model_selection import train_test_split, GroupKFold
from sklearn.metrics import classification_report, accuracy_score

sys.path.insert(0, str(Path(__file__).parent))
from feature_extractor import CookieFeatureExtractor
from classifier import CookieClassifier
from generate_training_data import TrainingDataGenerator

def train_model():
    print("CookieGuard AI - Enhanced Model Training")
    print("="*60)
    
    # Load/generate data
    data_path = Path(__file__).parent.parent / 'data' / 'training_cookies.json'
    if not data_path.exists():
        print("\n[1/5] Generating training data...")
        data_path.parent.mkdir(parents=True, exist_ok=True)
        generator = TrainingDataGenerator()
        training_data = generator.generate_dataset(n_samples=800)
        with open(data_path,'w') as f: json.dump(training_data, f, indent=2)
        print(f"      Generated {len(training_data)} samples")
    else:
        print("\n[1/5] Loading training data...")
        with open(data_path,'r') as f: training_data = json.load(f)
        print(f"      Loaded {len(training_data)} samples")
    
    # Extract features (now 34 instead of 18!)
    print("\n[2/5] Extracting features (34 features)...")
    extractor = CookieFeatureExtractor()
    feature_names = extractor.get_feature_names()
    label_map = {'other':0, 'authentication':1, 'tracking':2, 'preference':3}
    
    X, y, domains = [], [], []
    for cookie in training_data:
        features = extractor.extract_features(cookie)
        X.append([features[n] for n in feature_names])
        y.append(label_map[cookie['label']])
        domains.append(cookie['domain'])
    
    X, y = np.array(X), np.array(y)
    print(f"      Feature matrix: {X.shape} (was n×18, now n×34)")
    print(f"      Distribution: {dict(zip(*np.unique(y,return_counts=True)))}")
    
    # Train/val split
    print("\n[3/5] Splitting train/validation...")
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"      Train: {len(X_train)}, Val: {len(X_val)}")
    
    # Train with calibration
    print("\n[4/5] Training classifier WITH CALIBRATION...")
    classifier = CookieClassifier()
    classifier.train(X_train, y_train, feature_names, X_val, y_val)
    
    # Evaluate
    print("\n[5/5] Evaluation...")
    pred_train, _ = classifier.predict(X_train)
    pred_val, _ = classifier.predict(X_val)
    
    print(f"\n  Training accuracy: {accuracy_score(y_train, pred_train):.2%}")
    print(f"  Validation accuracy: {accuracy_score(y_val, pred_val):.2%}")
    
    print("\n  Classification Report (Validation):")
    labels = ['other','authentication','tracking','preference']
    print(classification_report(y_val, pred_val, target_names=labels, zero_division=0))
    
    print("\n  Top 5 important features:")
    for feat, imp in classifier.get_top_features(5):
        print(f"    {feat}: {imp:.4f}")
    
    # Save
    model_path = Path(__file__).parent.parent / 'models'
    model_path.mkdir(parents=True, exist_ok=True)
    model_file = model_path / 'cookie_classifier.pkl'
    classifier.save_model(str(model_file))
    print(f"\n✓ Model saved to: {model_file}")
    
    # Test examples
    print("\n"+"="*60)
    print("Testing with examples:\n")
    test_examples = [
        {"name":"__Host-session_token","domain":"example.com","path":"/","secure":True,"httpOnly":True,"sameSite":"Strict","expirationDate":None,"value":"eyJ.abc.123"},
        {"name":"_ga","domain":".example.com","path":"/","secure":False,"httpOnly":False,"sameSite":None,"expirationDate":1780272000,"value":"GA1.2.123.456"},
        {"name":"theme","domain":"example.com","path":"/","secure":False,"httpOnly":False,"sameSite":"Lax","expirationDate":1748736000,"value":"dark"}
    ]
    
    for cookie in test_examples:
        features = extractor.extract_features(cookie)
        cookie_type, conf, probs = classifier.predict_from_dict(features, cookie)
        print(f"Cookie: {cookie['name']}")
        print(f"  Type: {cookie_type} ({conf:.1%})")
        print(f"  All: {probs}\n")
    
    print("="*60)
    print("Training complete!")
    return classifier, extractor

if __name__ == "__main__":
    train_model()
