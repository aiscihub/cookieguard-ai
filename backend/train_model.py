"""
Train the CookieGuard AI classifier model
"""

import json
import numpy as np
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from feature_extractor import CookieFeatureExtractor
from classifier import CookieClassifier
from generate_training_data import TrainingDataGenerator


def train_model():
    """Main training pipeline"""
    
    print("CookieGuard AI - Model Training")
    print("=" * 60)
    
    # Step 1: Generate or load training data
    data_path = Path(__file__).parent.parent / 'data' / 'training_cookies.json'
    
    if not data_path.exists():
        print("\n[1/4] Generating training data...")
        data_path.parent.mkdir(parents=True, exist_ok=True)
        generator = TrainingDataGenerator()
        training_data = generator.generate_dataset(n_samples=800)
        
        with open(data_path, 'w') as f:
            json.dump(training_data, f, indent=2)
        print(f"      Generated {len(training_data)} samples")
    else:
        print("\n[1/4] Loading existing training data...")
        with open(data_path, 'r') as f:
            training_data = json.load(f)
        print(f"      Loaded {len(training_data)} samples")
    
    # Step 2: Extract features
    print("\n[2/4] Extracting features...")
    extractor = CookieFeatureExtractor()
    feature_names = extractor.get_feature_names()
    
    X = []
    y = []
    label_map = {
        'other': 0,
        'authentication': 1,
        'tracking': 2,
        'preference': 3
    }
    
    for cookie in training_data:
        features = extractor.extract_features(cookie)
        feature_vector = [features[name] for name in feature_names]
        X.append(feature_vector)
        y.append(label_map[cookie['label']])
    
    X = np.array(X)
    y = np.array(y)
    
    print(f"      Feature matrix shape: {X.shape}")
    print(f"      Class distribution: {dict(zip(*np.unique(y, return_counts=True)))}")
    
    # Step 3: Train classifier
    print("\n[3/4] Training Random Forest classifier...")
    classifier = CookieClassifier()
    classifier.train(X, y, feature_names)
    
    # Calculate training accuracy
    predictions, _ = classifier.predict(X)
    accuracy = np.mean(predictions == y)
    print(f"      Training accuracy: {accuracy:.2%}")
    
    # Show feature importance
    print("\n      Top 5 important features:")
    for feature, importance in classifier.get_top_features(5):
        print(f"        {feature}: {importance:.4f}")
    
    # Step 4: Save model
    print("\n[4/4] Saving model...")
    model_path = Path(__file__).parent.parent / 'models'
    model_path.mkdir(parents=True, exist_ok=True)
    
    model_file = model_path / 'cookie_classifier.pkl'
    classifier.save_model(str(model_file))
    print(f"      Model saved to: {model_file}")
    
    # Test with example cookies
    print("\n" + "=" * 60)
    print("Testing with example cookies:\n")
    
    test_examples = [
        {
            "name": "session_token",
            "domain": ".example.com",
            "path": "/",
            "secure": True,
            "httpOnly": False,  # Vulnerable!
            "sameSite": "Lax",
            "expirationDate": None,
            "value": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        },
        {
            "name": "_ga",
            "domain": ".example.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "sameSite": None,
            "expirationDate": 1780272000,
            "value": "GA1.2.123456789.1234567890"
        },
        {
            "name": "theme",
            "domain": "example.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "sameSite": "Lax",
            "expirationDate": 1748736000,
            "value": "dark"
        }
    ]
    
    for cookie in test_examples:
        features = extractor.extract_features(cookie)
        cookie_type, confidence, all_probs = classifier.predict_from_dict(features)
        
        print(f"Cookie: {cookie['name']}")
        print(f"  Predicted type: {cookie_type} (confidence: {confidence:.1%})")
        print(f"  All probabilities: {all_probs}")
        print()
    
    print("=" * 60)
    print("Training complete! Model ready for use.")
    return classifier, extractor


if __name__ == "__main__":
    train_model()
