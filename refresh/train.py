"""Fit fixed C2 settings using historical months only. No monthly test-driven selection."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import numpy as np
import onnxruntime as ort
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from common import ROOT, die, label, load, month_seed, normalize_name, rows, sha, write_json
from lookup import build_lookup

def training_files(month, pool, release_root):
    files = [pool, ROOT / "data/cookies-2026.jsonl"]
    for path in sorted(release_root.glob("????-??/cookies.jsonl")):
        if path.parent.name < month:
            manifest = load(path.parent / "manifest.json")
            if manifest.get("dryRun") or not manifest.get("privacyPassed"):
                continue
            files.append(path)
    return files

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--month", required=True)
    p.add_argument("--pool", type=Path, default=ROOT / "refresh/.work/inputs/training-pool-2021.jsonl.gz")
    p.add_argument("--run", type=Path, default=ROOT / "refresh/.work/run")
    p.add_argument("--releases", type=Path, default=ROOT / "data/releases")
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    a.pool, a.run, a.releases = a.pool.resolve(), a.run.resolve(), a.releases.resolve()
    if a.out:
        a.out = a.out.resolve()
    seed = month_seed(a.month)
    out = a.out or a.run / "candidate"
    if out.exists():
        raise ValueError("candidate-already-exists")
    if not (a.run / "baseline.json").exists():
        raise ValueError("baseline-must-be-evaluated-first")
    source = load(ROOT / "refresh/training-source.json")
    if sha(a.pool) != source["sha256"]:
        raise ValueError("training-asset-digest")
    files = training_files(a.month, a.pool, a.releases)
    records = [row for path in files for row in rows(path)]
    x = np.asarray([r["features"] for r in records], dtype=np.float32)
    y = np.asarray([label(r) for r in records], dtype=np.int64)
    groups = np.asarray([normalize_name(r["name"]) for r in records])
    if not np.isfinite(x).all() or x.shape[1] != 38:
        raise ValueError("invalid-training-features")
    fit, validation = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed).split(x, y, groups))
    if set(groups[fit]) & set(groups[validation]) or len(np.unique(y[fit])) != 2 or len(np.unique(y[validation])) != 2:
        raise ValueError("invalid-group-split")
    settings = dict(n_estimators=150, max_depth=12, min_samples_split=5, min_samples_leaf=2,
                    class_weight="balanced", random_state=42, n_jobs=2)
    selection = RandomForestClassifier(**settings).fit(x[fit], y[fit])
    probabilities = selection.predict_proba(x[validation])[:, 1]
    # Fixed threshold grid; optimize balanced accuracy. Ties: closest to .5, then lower.
    scores = []
    for t in np.linspace(.05, .95, 91):
        pred = probabilities >= t
        ba = ((pred[y[validation] == 1]).mean() + (~pred[y[validation] == 0]).mean()) / 2
        scores.append((float(ba), -abs(float(t) - .5), -float(t)))
    threshold = -max(scores)[2]
    model = RandomForestClassifier(**settings).fit(x, y)
    out.mkdir(parents=True)
    exported = convert_sklearn(model, initial_types=[("features", FloatTensorType([None, 38]))],
                               options={id(model): {"zipmap": False}}, target_opset=17)
    (out / "model.onnx").write_bytes(exported.SerializeToString())
    session_options = ort.SessionOptions()
    session_options.log_severity_level = 4
    session_options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(out / "model.onnx"), sess_options=session_options, providers=["CPUExecutionProvider"])
    chosen = np.random.default_rng(42).choice(len(x), 1000, replace=False)
    predicted = np.asarray(session.run(None, {"features": x[chosen]})[1])
    difference = float(np.max(np.abs(predicted - model.predict_proba(x[chosen]))))
    parity = {"rows": 1000, "seed": 42, "maxAbsoluteDifference": difference, "tolerance": 1e-5, "passed": difference <= 1e-5}
    write_json(out / "parity.json", parity)
    write_json(out / "lookup.json", build_lookup(records, ROOT / "refresh/reference/ocd.csv"))
    write_json(out / "membership.json", sorted(set(groups)))
    names = load(ROOT / "refresh/reference/feature_names.json")["featureNames"]
    meta = {
        "schemaVersion": 1, "month": a.month, "algorithm": "binary RandomForest C2 with N1 lookup",
        "settings": settings, "classes": [0, 1], "featureNames": names, "threshold": threshold,
        "trainingRows": len(records), "trainingNames": len(set(groups)),
        "validation": {"seed": seed, "group": "normalizedName", "fraction": .2,
                       "fitRows": len(fit), "validationRows": len(validation), "balancedAccuracy": max(scores)[0],
                       "thresholdGrid": {"start": .05, "end": .95, "step": .01},
                       "refit": "all historical rows after selecting threshold; current month never included"},
        "inputs": [{"file": ("training-pool-2021.jsonl.gz" if path == a.pool else str(path.relative_to(ROOT))),
                    "sha256": sha(path)} for path in files],
        "baselineSha256": sha(a.run / "baseline.json"), "currentMonthExcluded": True,
        "onnxSha256": sha(out / "model.onnx"), "lookupSha256": sha(out / "lookup.json"),
        "membershipSha256": sha(out / "membership.json"), "parity": parity,
        "versions": {n: importlib.metadata.version(n) for n in ["numpy", "scikit-learn", "onnx", "onnxruntime", "skl2onnx"]},
    }
    write_json(out / "meta.json", meta)
    print(json.dumps({"stage": "train", "rows": len(records), "threshold": threshold, "parityPassed": parity["passed"]}))

if __name__ == "__main__":
    try: main()
    except Exception: sys.exit(die())
