"""
Cookie Classifier - ML Model for Cookie Type Prediction
Predicts: authentication, tracking, preference, or other
"""

import pickle
import numpy as np
from typing import Dict, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class CookieClassifier:
    """ML-powered cookie classification system"""
    
    def __init__(self, model_path: str = None):
        """
        Initialize classifier
        
        Args:
            model_path: Path to pre-trained model file (pickle)
        """
        self.model = None
        self.scaler = None
        self.feature_names = None
        
        if model_path:
            self.load_model(model_path)
    
    def train(self, X: np.ndarray, y: np.ndarray, feature_names: list):
        """
        Train the classifier
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (0=other, 1=authentication, 2=tracking, 3=preference)
            feature_names: List of feature names
        """
        self.feature_names = feature_names
        
        # Normalize features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Random Forest classifier
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',  # Handle class imbalance
            random_state=42
        )
        
        self.model.fit(X_scaled, y)
        
        # Calculate feature importance
        self.feature_importance = dict(zip(
            feature_names,
            self.model.feature_importances_
        ))
    
    def predict(self, features: np.ndarray) -> Tuple[int, np.ndarray]:
        """
        Predict cookie type
        
        Args:
            features: Feature vector (n_features,) or matrix (n_samples, n_features)
        
        Returns:
            (predicted_class, probability_distribution)
        """
        if self.model is None:
            raise ValueError("Model not trained or loaded")
        
        # Handle single sample
        if len(features.shape) == 1:
            features = features.reshape(1, -1)
        
        # Scale and predict
        X_scaled = self.scaler.transform(features)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        if len(predictions) == 1:
            return predictions[0], probabilities[0]
        return predictions, probabilities
    
    def predict_from_dict(self, feature_dict: Dict) -> Tuple[str, float, Dict]:
        """
        Predict from feature dictionary
        
        Args:
            feature_dict: Dictionary of features from FeatureExtractor
        
        Returns:
            (cookie_type, confidence, all_probabilities)
        """
        # Extract features in correct order
        feature_vector = np.array([
            feature_dict[name] for name in self.feature_names
        ])
        
        # Predict
        pred_class, probs = self.predict(feature_vector)
        
        # Map class to label
        class_labels = {
            0: 'other',
            1: 'authentication',
            2: 'tracking',
            3: 'preference'
        }
        
        cookie_type = class_labels[pred_class]
        confidence = float(probs[pred_class])
        
        all_probs = {
            class_labels[i]: float(prob)
            for i, prob in enumerate(probs)
        }
        
        return cookie_type, confidence, all_probs
    
    def save_model(self, path: str):
        """Save trained model to file"""
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'feature_importance': self.feature_importance
        }
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
    
    def load_model(self, path: str):
        """Load pre-trained model from file"""
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.feature_importance = model_data.get('feature_importance', {})
    
    def get_top_features(self, n: int = 5) -> list:
        """Get top N most important features"""
        if not hasattr(self, 'feature_importance'):
            return []
        
        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_features[:n]


if __name__ == "__main__":
    # Test classifier with dummy data
    from sklearn.datasets import make_classification
    
    print("Cookie Classifier Test\n" + "="*50)
    
    # Generate synthetic data
    X, y = make_classification(
        n_samples=200,
        n_features=18,
        n_informative=12,
        n_redundant=3,
        n_classes=4,
        random_state=42
    )
    
    # Feature names
    feature_names = [
        'has_secure', 'has_httponly', 'has_samesite', 'samesite_level',
        'is_session_cookie', 'expiry_days', 'domain_is_wildcard',
        'domain_depth', 'path_is_root', 'name_matches_auth',
        'name_matches_tracking', 'name_matches_preference',
        'name_entropy', 'name_length', 'value_length', 'value_entropy',
        'value_looks_like_jwt', 'value_looks_like_hex'
    ]
    
    # Train
    classifier = CookieClassifier()
    classifier.train(X[:150], y[:150], feature_names)
    
    # Test
    test_features = X[150]
    pred_class, probs = classifier.predict(test_features)
    
    print(f"\nPredicted class: {pred_class}")
    print(f"Probabilities: {probs}")
    print(f"\nTop 5 important features:")
    for feature, importance in classifier.get_top_features(5):
        print(f"  {feature}: {importance:.4f}")
