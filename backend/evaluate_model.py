"""
CookieGuard AI 2.0 — Evaluation Suite
Generates rigorous metrics for the AI challenge submission:

  1. Precision / Recall / False Positive Rate (per class + auth-focused)
  2. Top-3 ranking accuracy per domain (does the model rank auth cookies highest?)
  3. Generalization on unseen websites (Leave-One-Site-Out cross-validation)
  4. Bootstrap confidence intervals for key metrics
  5. Confusion matrix + per-class breakdown

Outputs:
  - models/evaluation_report.json    (machine-readable)
  - models/evaluation_report.txt     (human-readable for submission)
  - models/confusion_matrix.csv
"""

import json
import csv
import numpy as np
import sys
from pathlib import Path
from collections import defaultdict

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score,
    precision_score, recall_score, f1_score,
    precision_recall_curve, roc_curve, auc
)

sys.path.insert(0, str(Path(__file__).parent))
from feature_extractor import CookieFeatureExtractor
from classifier import CookieClassifier
from generate_training_data import TrainingDataGenerator


LABELS = ['other', 'authentication', 'tracking', 'preference']
LABEL_MAP = {name: i for i, name in enumerate(LABELS)}


def load_or_generate_data(data_dir, n_samples=5000):
    """Generate a larger dataset for robust evaluation."""
    generator = TrainingDataGenerator()
    # Use a fixed seed for reproducibility
    import random
    random.seed(42)
    dataset = generator.generate_dataset(n_samples=n_samples)
    return dataset


def extract_features(dataset, extractor):
    """Extract features and organize by site."""
    feature_names = extractor.get_feature_names()
    X, y, site_ids, cookie_names, domains = [], [], [], [], []

    for cookie in dataset:
        features = extractor.extract_features(cookie)
        X.append([features[n] for n in feature_names])
        y.append(LABEL_MAP[cookie['label']])
        site_ids.append(cookie.get('site_id', 'unknown'))
        cookie_names.append(cookie.get('name', ''))
        domains.append(cookie.get('domain', ''))

    return (np.array(X), np.array(y), np.array(site_ids),
            np.array(cookie_names), np.array(domains), feature_names)


# ═══════════════════════════════════════════════════════════════
# METRIC 1: Precision / Recall / FPR (per class + auth-focused)
# ═══════════════════════════════════════════════════════════════

def compute_classification_metrics(y_true, y_pred, y_probs):
    """Compute per-class and auth-specific metrics."""
    results = {}

    # Per-class precision, recall, F1
    report = classification_report(y_true, y_pred, target_names=LABELS,
                                   output_dict=True, zero_division=0)
    results['per_class'] = {}
    for label in LABELS:
        results['per_class'][label] = {
            'precision': round(report[label]['precision'], 4),
            'recall': round(report[label]['recall'], 4),
            'f1': round(report[label]['f1-score'], 4),
            'support': int(report[label]['support']),
        }

    # Overall
    results['accuracy'] = round(accuracy_score(y_true, y_pred), 4)
    results['macro_precision'] = round(precision_score(y_true, y_pred, average='macro', zero_division=0), 4)
    results['macro_recall'] = round(recall_score(y_true, y_pred, average='macro', zero_division=0), 4)
    results['macro_f1'] = round(f1_score(y_true, y_pred, average='macro', zero_division=0), 4)

    # Auth-specific: binary (auth=1 vs rest)
    y_true_auth = (y_true == 1).astype(int)
    y_pred_auth = (y_pred == 1).astype(int)
    probs_auth = y_probs[:, 1]

    # False Positive Rate for auth class
    tn = np.sum((y_true_auth == 0) & (y_pred_auth == 0))
    fp = np.sum((y_true_auth == 0) & (y_pred_auth == 1))
    fn = np.sum((y_true_auth == 1) & (y_pred_auth == 0))
    tp = np.sum((y_true_auth == 1) & (y_pred_auth == 1))

    fpr_auth = fp / max(fp + tn, 1)
    results['auth_binary'] = {
        'true_positives': int(tp),
        'false_positives': int(fp),
        'true_negatives': int(tn),
        'false_negatives': int(fn),
        'precision': round(tp / max(tp + fp, 1), 4),
        'recall': round(tp / max(tp + fn, 1), 4),
        'false_positive_rate': round(fpr_auth, 4),
        'specificity': round(tn / max(tn + fp, 1), 4),
    }

    # PR-AUC and ROC-AUC for auth class
    prec_arr, rec_arr, _ = precision_recall_curve(y_true_auth, probs_auth)
    results['auth_binary']['pr_auc'] = round(auc(rec_arr, prec_arr), 4)

    fpr_arr, tpr_arr, _ = roc_curve(y_true_auth, probs_auth)
    results['auth_binary']['roc_auc'] = round(auc(fpr_arr, tpr_arr), 4)

    # Recall at FPR thresholds
    for alpha in [0.01, 0.05, 0.10]:
        valid = fpr_arr <= alpha
        recall_at_alpha = float(tpr_arr[valid].max()) if valid.any() else 0.0
        results['auth_binary'][f'recall_at_fpr_{alpha}'] = round(recall_at_alpha, 4)

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    results['confusion_matrix'] = cm.tolist()

    return results


# ═══════════════════════════════════════════════════════════════
# METRIC 2: Top-K Ranking Accuracy per Domain
# ═══════════════════════════════════════════════════════════════

def compute_ranking_accuracy(y_true, y_probs, site_ids, k_values=[1, 2, 3]):
    """
    For each site, rank cookies by P(auth) descending.
    Check if the actual auth cookies appear in the top-K positions.

    This answers: "When CookieGuard shows the riskiest cookies first,
    does it actually surface the real auth cookies at the top?"
    """
    results = {}

    # Group by site
    sites = defaultdict(list)
    for i in range(len(y_true)):
        sites[site_ids[i]].append(i)

    for k in k_values:
        hits = 0
        total_sites = 0

        per_site_detail = {}

        for site, indices in sites.items():
            indices = np.array(indices)
            site_y = y_true[indices]
            site_probs = y_probs[indices, 1]  # P(auth)

            # Skip sites with no auth cookies
            auth_indices_in_site = np.where(site_y == 1)[0]
            if len(auth_indices_in_site) == 0:
                continue

            total_sites += 1

            # Rank by P(auth) descending
            ranked = np.argsort(-site_probs)
            top_k_positions = ranked[:k]

            # Check if any true auth cookie is in top-K
            top_k_labels = site_y[top_k_positions]
            hit = int(np.any(top_k_labels == 1))
            hits += hit

            per_site_detail[site] = {
                'total_cookies': len(indices),
                'auth_cookies': int(len(auth_indices_in_site)),
                'hit': bool(hit),
                'top_k_predicted_auth_prob': [round(float(site_probs[j]), 3) for j in top_k_positions],
            }

        accuracy = hits / max(total_sites, 1)
        results[f'top_{k}'] = {
            'accuracy': round(accuracy, 4),
            'hits': hits,
            'total_sites_with_auth': total_sites,
            'per_site': per_site_detail,
        }

    return results


# ═══════════════════════════════════════════════════════════════
# METRIC 3: Generalization — Leave-One-Site-Out Cross-Validation
# ═══════════════════════════════════════════════════════════════

def compute_generalization_metrics(X, y, site_ids, feature_names):
    """
    Train on N-1 sites, test on the held-out site.
    Repeat for each site. This tests whether the model generalizes
    to completely unseen websites.
    """
    unique_sites = np.unique(site_ids)
    fold_results = []

    for held_out_site in unique_sites:
        train_mask = site_ids != held_out_site
        test_mask = site_ids == held_out_site

        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]

        if len(X_test) < 5 or len(np.unique(y_train)) < 4:
            continue

        # Train fresh model
        clf = CookieClassifier()
        clf.train(X_train, y_train, feature_names)

        preds, probs = clf.predict(X_test)

        acc = accuracy_score(y_test, preds)
        f1_macro = f1_score(y_test, preds, average='macro', zero_division=0)

        # Auth-specific
        y_test_auth = (y_test == 1).astype(int)
        pred_auth = (preds == 1).astype(int)
        tp = np.sum((y_test_auth == 1) & (pred_auth == 1))
        fp = np.sum((y_test_auth == 0) & (pred_auth == 1))
        fn = np.sum((y_test_auth == 1) & (pred_auth == 0))
        tn = np.sum((y_test_auth == 0) & (pred_auth == 0))

        auth_precision = tp / max(tp + fp, 1)
        auth_recall = tp / max(tp + fn, 1)
        auth_fpr = fp / max(fp + tn, 1)

        fold_results.append({
            'held_out_site': held_out_site,
            'test_size': int(len(X_test)),
            'accuracy': round(float(acc), 4),
            'f1_macro': round(float(f1_macro), 4),
            'auth_precision': round(float(auth_precision), 4),
            'auth_recall': round(float(auth_recall), 4),
            'auth_fpr': round(float(auth_fpr), 4),
        })

    # Aggregate
    if fold_results:
        agg = {
            'n_folds': len(fold_results),
            'mean_accuracy': round(np.mean([r['accuracy'] for r in fold_results]), 4),
            'std_accuracy': round(np.std([r['accuracy'] for r in fold_results]), 4),
            'mean_f1_macro': round(np.mean([r['f1_macro'] for r in fold_results]), 4),
            'std_f1_macro': round(np.std([r['f1_macro'] for r in fold_results]), 4),
            'mean_auth_precision': round(np.mean([r['auth_precision'] for r in fold_results]), 4),
            'mean_auth_recall': round(np.mean([r['auth_recall'] for r in fold_results]), 4),
            'mean_auth_fpr': round(np.mean([r['auth_fpr'] for r in fold_results]), 4),
            'min_accuracy': round(min(r['accuracy'] for r in fold_results), 4),
            'max_accuracy': round(max(r['accuracy'] for r in fold_results), 4),
        }
    else:
        agg = {'error': 'Not enough data for LOSO cross-validation'}

    return {'folds': fold_results, 'aggregate': agg}


# ═══════════════════════════════════════════════════════════════
# METRIC 4: Bootstrap Confidence Intervals
# ═══════════════════════════════════════════════════════════════

def bootstrap_ci(y_true, y_pred, y_probs, metric_fn, n_bootstrap=1000, ci=0.95):
    """Compute bootstrap confidence interval for a metric."""
    np.random.seed(42)
    n = len(y_true)
    scores = []

    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        try:
            score = metric_fn(y_true[idx], y_pred[idx], y_probs[idx])
            scores.append(score)
        except Exception:
            continue

    scores = np.array(scores)
    lower = np.percentile(scores, (1 - ci) / 2 * 100)
    upper = np.percentile(scores, (1 + ci) / 2 * 100)
    return round(float(np.mean(scores)), 4), round(float(lower), 4), round(float(upper), 4)


def compute_bootstrap_intervals(y_true, y_pred, y_probs, n_bootstrap=1000):
    """Bootstrap CIs for key metrics."""
    results = {}

    # Accuracy
    mean, lo, hi = bootstrap_ci(
        y_true, y_pred, y_probs,
        lambda yt, yp, _: accuracy_score(yt, yp),
        n_bootstrap=n_bootstrap
    )
    results['accuracy'] = {'mean': mean, 'ci_95_lower': lo, 'ci_95_upper': hi}

    # Macro F1
    mean, lo, hi = bootstrap_ci(
        y_true, y_pred, y_probs,
        lambda yt, yp, _: f1_score(yt, yp, average='macro', zero_division=0),
        n_bootstrap=n_bootstrap
    )
    results['macro_f1'] = {'mean': mean, 'ci_95_lower': lo, 'ci_95_upper': hi}

    # Auth recall
    mean, lo, hi = bootstrap_ci(
        y_true, y_pred, y_probs,
        lambda yt, yp, _: recall_score(yt == 1, yp == 1, zero_division=0),
        n_bootstrap=n_bootstrap
    )
    results['auth_recall'] = {'mean': mean, 'ci_95_lower': lo, 'ci_95_upper': hi}

    # Auth FPR
    def auth_fpr_fn(yt, yp, _):
        y_true_auth = (yt == 1).astype(int)
        y_pred_auth = (yp == 1).astype(int)
        fp = np.sum((y_true_auth == 0) & (y_pred_auth == 1))
        tn = np.sum((y_true_auth == 0) & (y_pred_auth == 0))
        return fp / max(fp + tn, 1)

    mean, lo, hi = bootstrap_ci(y_true, y_pred, y_probs, auth_fpr_fn, n_bootstrap=n_bootstrap)
    results['auth_fpr'] = {'mean': mean, 'ci_95_lower': lo, 'ci_95_upper': hi}

    # Auth PR-AUC
    def pr_auc_fn(yt, _, yp_probs):
        y_auth = (yt == 1).astype(int)
        p_auth = yp_probs[:, 1]
        prec, rec, _ = precision_recall_curve(y_auth, p_auth)
        return auc(rec, prec)

    mean, lo, hi = bootstrap_ci(y_true, y_pred, y_probs, pr_auc_fn, n_bootstrap=n_bootstrap)
    results['auth_pr_auc'] = {'mean': mean, 'ci_95_lower': lo, 'ci_95_upper': hi}

    return results


# ═══════════════════════════════════════════════════════════════
# REPORT GENERATION
# ═══════════════════════════════════════════════════════════════

def generate_text_report(all_metrics):
    """Generate a human-readable evaluation report."""
    lines = []
    w = lines.append

    w("=" * 72)
    w("  CookieGuard AI 2.0 — Evaluation Report")
    w("=" * 72)

    # 1. Classification metrics
    cm = all_metrics['classification']
    w("\n1. CLASSIFICATION METRICS")
    w("-" * 40)
    w(f"  Overall Accuracy:     {cm['accuracy']:.2%}")
    w(f"  Macro Precision:      {cm['macro_precision']:.2%}")
    w(f"  Macro Recall:         {cm['macro_recall']:.2%}")
    w(f"  Macro F1:             {cm['macro_f1']:.2%}")

    w("\n  Per-Class Breakdown:")
    w(f"  {'Class':<18} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    w(f"  {'-'*58}")
    for label in LABELS:
        c = cm['per_class'][label]
        w(f"  {label:<18} {c['precision']:>10.2%} {c['recall']:>10.2%} {c['f1']:>10.2%} {c['support']:>10}")

    # Auth binary
    ab = cm['auth_binary']
    w(f"\n  Auth (Binary) Metrics:")
    w(f"    Precision:            {ab['precision']:.2%}")
    w(f"    Recall (Sensitivity): {ab['recall']:.2%}")
    w(f"    Specificity:          {ab['specificity']:.2%}")
    w(f"    False Positive Rate:  {ab['false_positive_rate']:.2%}")
    w(f"    PR-AUC:               {ab['pr_auc']:.4f}")
    w(f"    ROC-AUC:              {ab['roc_auc']:.4f}")
    w(f"    Recall @ FPR≤1%:      {ab['recall_at_fpr_0.01']:.2%}")
    w(f"    Recall @ FPR≤5%:      {ab['recall_at_fpr_0.05']:.2%}")
    w(f"    Recall @ FPR≤10%:     {ab['recall_at_fpr_0.1']:.2%}")

    w(f"\n  Confusion Matrix:")
    w(f"  {'':>18} " + "  ".join(f"{l:>14}" for l in LABELS))
    for i, label in enumerate(LABELS):
        row = cm['confusion_matrix'][i]
        w(f"  {label:>18} " + "  ".join(f"{v:>14}" for v in row))

    # 2. Ranking accuracy
    rank = all_metrics['ranking']
    w("\n\n2. TOP-K RANKING ACCURACY PER DOMAIN")
    w("-" * 40)
    w("  (Does the model rank real auth cookies in the top K?)\n")
    for k_key in sorted(rank.keys()):
        r = rank[k_key]
        w(f"  {k_key.replace('_', '-').upper()}: {r['accuracy']:.2%}  "
          f"({r['hits']}/{r['total_sites_with_auth']} sites)")

    w(f"\n  Per-Site Detail (Top-3):")
    if 'top_3' in rank:
        for site, detail in rank['top_3']['per_site'].items():
            hit_mark = "✓" if detail['hit'] else "✗"
            w(f"    {hit_mark} {site}: {detail['auth_cookies']} auth cookie(s) among "
              f"{detail['total_cookies']} total — top-3 P(auth): {detail['top_k_predicted_auth_prob']}")

    # 3. Generalization
    gen = all_metrics['generalization']
    w("\n\n3. GENERALIZATION — LEAVE-ONE-SITE-OUT CROSS-VALIDATION")
    w("-" * 40)
    w("  (Train on N-1 sites, test on held-out site)\n")

    if 'aggregate' in gen and 'error' not in gen['aggregate']:
        agg = gen['aggregate']
        w(f"  Folds:                {agg['n_folds']}")
        w(f"  Mean Accuracy:        {agg['mean_accuracy']:.2%} ± {agg['std_accuracy']:.2%}")
        w(f"  Mean F1 (macro):      {agg['mean_f1_macro']:.2%} ± {agg['std_f1_macro']:.2%}")
        w(f"  Mean Auth Precision:  {agg['mean_auth_precision']:.2%}")
        w(f"  Mean Auth Recall:     {agg['mean_auth_recall']:.2%}")
        w(f"  Mean Auth FPR:        {agg['mean_auth_fpr']:.2%}")
        w(f"  Accuracy Range:       [{agg['min_accuracy']:.2%}, {agg['max_accuracy']:.2%}]")

        w(f"\n  Per-Fold Detail:")
        w(f"  {'Held-Out Site':<22} {'N':>5} {'Acc':>8} {'F1':>8} {'AuthPrec':>10} {'AuthRec':>10} {'AuthFPR':>10}")
        w(f"  {'-'*73}")
        for fold in gen['folds']:
            w(f"  {fold['held_out_site']:<22} {fold['test_size']:>5} "
              f"{fold['accuracy']:>8.2%} {fold['f1_macro']:>8.2%} "
              f"{fold['auth_precision']:>10.2%} {fold['auth_recall']:>10.2%} "
              f"{fold['auth_fpr']:>10.2%}")

    # 4. Bootstrap CIs
    boot = all_metrics['bootstrap_ci']
    w("\n\n4. BOOTSTRAP CONFIDENCE INTERVALS (95%, n=1000)")
    w("-" * 40)
    for metric_name, vals in boot.items():
        w(f"  {metric_name:<20} {vals['mean']:.2%}  [{vals['ci_95_lower']:.2%}, {vals['ci_95_upper']:.2%}]")

    w("\n" + "=" * 72)
    w("  Report generated by CookieGuard AI 2.0 Evaluation Suite")
    w("=" * 72)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def run_evaluation():
    print("=" * 72)
    print("  CookieGuard AI 2.0 — Full Evaluation Suite")
    print("=" * 72)

    model_dir = Path(__file__).parent.parent / 'models'
    data_dir = Path(__file__).parent.parent / 'data'
    model_dir.mkdir(parents=True, exist_ok=True)

    # Load or generate data
    print("\n[1/6] Generating evaluation dataset (5000 samples, 22 sites, 40% hard)...")
    dataset = load_or_generate_data(data_dir, n_samples=1200)
    print(f"       Generated {len(dataset)} samples across "
          f"{len(set(c.get('site_id','?') for c in dataset))} sites")

    # Extract features
    print("\n[2/6] Extracting features...")
    extractor = CookieFeatureExtractor()
    X, y, site_ids, cookie_names, domains, feature_names = extract_features(dataset, extractor)
    print(f"       Feature matrix: {X.shape}")

    # Train on holdout split (same as train_model.py)
    print("\n[3/6] Training model with site-based holdout...")
    unique_sites = np.unique(site_ids)
    np.random.seed(42)
    holdout_sites = np.random.choice(unique_sites, size=min(5, len(unique_sites)), replace=False)
    val_mask = np.isin(site_ids, holdout_sites)
    train_mask = ~val_mask

    X_train, X_val = X[train_mask], X[val_mask]
    y_train, y_val = y[train_mask], y[val_mask]
    site_val = site_ids[val_mask]

    classifier = CookieClassifier()
    classifier.train(X_train, y_train, feature_names, X_val, y_val)
    preds_val, probs_val = classifier.predict(X_val)
    print(f"       Train: {len(X_train)}, Val: {len(X_val)} "
          f"(held-out sites: {list(holdout_sites)})")

    # Metric 1: Classification metrics
    print("\n[4/6] Computing classification metrics...")
    classification_metrics = compute_classification_metrics(y_val, preds_val, probs_val)
    print(f"       Accuracy: {classification_metrics['accuracy']:.2%}")
    print(f"       Auth FPR: {classification_metrics['auth_binary']['false_positive_rate']:.2%}")
    print(f"       Auth PR-AUC: {classification_metrics['auth_binary']['pr_auc']:.4f}")

    # Metric 2: Ranking accuracy
    print("\n[5/6] Computing top-K ranking accuracy per domain...")
    ranking_metrics = compute_ranking_accuracy(y_val, probs_val, site_val, k_values=[1, 2, 3])
    for k in [1, 2, 3]:
        r = ranking_metrics[f'top_{k}']
        print(f"       Top-{k}: {r['accuracy']:.2%} ({r['hits']}/{r['total_sites_with_auth']} sites)")

    # Metric 3: Generalization (LOSO)
    print("\n[6/6] Running Leave-One-Site-Out cross-validation...")
    gen_metrics = compute_generalization_metrics(X, y, site_ids, feature_names)
    if 'aggregate' in gen_metrics and 'error' not in gen_metrics['aggregate']:
        agg = gen_metrics['aggregate']
        print(f"       {agg['n_folds']} folds")
        print(f"       Mean Accuracy: {agg['mean_accuracy']:.2%} ± {agg['std_accuracy']:.2%}")
        print(f"       Mean Auth FPR: {agg['mean_auth_fpr']:.2%}")
        print(f"       Accuracy Range: [{agg['min_accuracy']:.2%}, {agg['max_accuracy']:.2%}]")

    # Bootstrap CIs
    print("\n       Computing bootstrap confidence intervals...")
    bootstrap_metrics = compute_bootstrap_intervals(y_val, preds_val, probs_val, n_bootstrap=1000)

    # Assemble full report
    all_metrics = {
        'classification': classification_metrics,
        'ranking': ranking_metrics,
        'generalization': gen_metrics,
        'bootstrap_ci': bootstrap_metrics,
        'metadata': {
            'dataset_size': len(dataset),
            'train_size': int(len(X_train)),
            'val_size': int(len(X_val)),
            'n_features': int(X.shape[1]),
            'n_sites': int(len(unique_sites)),
            'holdout_sites': list(holdout_sites),
        }
    }

    # Save JSON report
    json_path = model_dir / 'evaluation_report.json'
    with open(json_path, 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)
    print(f"\n✓ JSON report: {json_path}")

    # Save text report
    text_report = generate_text_report(all_metrics)
    txt_path = model_dir / 'evaluation_report.txt'
    with open(txt_path, 'w') as f:
        f.write(text_report)
    print(f"✓ Text report: {txt_path}")

    # Save confusion matrix CSV
    cm = classification_metrics['confusion_matrix']
    cm_path = model_dir / 'confusion_matrix.csv'
    with open(cm_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['predicted →'] + LABELS)
        for i, label in enumerate(LABELS):
            writer.writerow([label] + cm[i])
    print(f"✓ Confusion matrix: {cm_path}")

    # Print the text report
    print("\n")
    print(text_report)

    return all_metrics


if __name__ == "__main__":
    run_evaluation()
