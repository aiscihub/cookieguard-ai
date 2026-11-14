#!/usr/bin/env python3
import datetime as dt
import hashlib
import json
import os
import random
from pathlib import Path

import joblib
import numpy as np
import onnx
import onnxruntime as ort
import sklearn
import skl2onnx
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import HashingVectorizer
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

HERE = Path(__file__).resolve().parent
FEATURES = HERE / "features"
MODEL = HERE / "model"
LOCKS = HERE / "locks.txt"
SPLIT_PATH = HERE / "split.json"
FEATURE_NAMES = json.load(open(FEATURES / "feature_names.json"))["featureNames"]
CLASSES = [0, 1, 2, 3]
SPLIT_SHA = hashlib.sha256(SPLIT_PATH.read_bytes()).hexdigest()

if MODEL.exists():
    raise SystemExit("model directory already exists; refusing to overwrite")
MODEL.mkdir()
split = json.load(open(SPLIT_PATH))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def append_lock(entry):
    entry = {**entry, "at": dt.datetime.now(dt.timezone.utc).isoformat()}
    with LOCKS.open("a") as handle:
        handle.write(json.dumps(entry, separators=(",", ":")) + "\n")

def vectorizer():
    return HashingVectorizer(analyzer="char_wb", ngram_range=(2, 4), n_features=256, alternate_sign=False)

train_features, train_names, train_labels = [], [], []
for path in sorted(FEATURES.glob("chunk-*.jsonl")):
    with path.open() as handle:
        for line in handle:
            row = json.loads(line)
            if split[row["normalizedName"]] != "train":
                continue
            train_features.append(row["features"])
            train_names.append(row["lowercaseName"])
            train_labels.append(row["label"])

X1 = np.asarray(train_features, dtype=np.float32)
y = np.asarray(train_labels, dtype=np.int64)
if set(np.unique(y)) != set(CLASSES):
    raise RuntimeError(f"training classes differ: {np.unique(y)}")

settings = dict(n_estimators=150, max_depth=12, min_samples_split=5, min_samples_leaf=2,
                class_weight="balanced", random_state=42, n_jobs=-1)
m1 = RandomForestClassifier(**settings)
m1.fit(X1, y)

hashed = vectorizer().transform(train_names).toarray().astype(np.float32, copy=False)
X2 = np.concatenate([X1, hashed], axis=1)
m2 = RandomForestClassifier(**settings)
m2.fit(X2, y)

if list(m1.classes_) != CLASSES or list(m2.classes_) != CLASSES:
    raise RuntimeError("model class order differs from [0,1,2,3]")

m1_joblib = MODEL / "m1.joblib"
m2_joblib = MODEL / "m2.joblib"
joblib.dump(m1, m1_joblib)
joblib.dump(m2, m2_joblib)

def export(model, width, path):
    converted = convert_sklearn(
        model,
        initial_types=[("features", FloatTensorType([None, width]))],
        options={id(model): {"zipmap": False}},
        target_opset=17,
    )
    path.write_bytes(converted.SerializeToString())
    graph = onnx.load(path)
    inputs = [value.name for value in graph.graph.input]
    outputs = [value.name for value in graph.graph.output]
    if inputs != ["features"] or "probabilities" not in outputs:
        raise RuntimeError(f"unexpected ONNX names for {path.name}: {inputs}, {outputs}")

m1_onnx = MODEL / "m1.onnx"
m2_onnx = MODEL / "m2.onnx"
export(m1, 38, m1_onnx)
export(m2, 294, m2_onnx)

versions = {
    "python": ".".join(map(str, os.sys.version_info[:3])),
    "numpy": np.__version__,
    "scikitLearn": sklearn.__version__,
    "skl2onnx": skl2onnx.__version__,
    "onnx": onnx.__version__,
    "onnxruntime": ort.__version__,
}
common = {
    "schemaVersion": 1,
    "classes": CLASSES,
    "trainingRows": len(y),
    "trainingNames": sum(side == "train" for side in split.values()),
    "splitSha256": SPLIT_SHA,
    "randomForest": settings,
    "versions": versions,
}
m1_meta = {**common, "model": "M1", "featureNames": FEATURE_NAMES,
           "joblibSha256": sha(m1_joblib), "onnxSha256": sha(m1_onnx)}
m2_meta = {**common, "model": "M2", "featureNames": FEATURE_NAMES + [f"name_hash_{i:03d}" for i in range(256)],
           "nameHashing": {"analyzer": "char_wb", "ngramRange": [2, 4], "nFeatures": 256, "alternateSign": False},
           "joblibSha256": sha(m2_joblib), "onnxSha256": sha(m2_onnx)}
(MODEL / "m1_meta.json").write_text(json.dumps(m1_meta, indent=2) + "\n")
(MODEL / "m2_meta.json").write_text(json.dumps(m2_meta, indent=2) + "\n")

# This lock is written before any test feature row is loaded below.
append_lock({
    "event": "models_frozen",
    "splitSha256": SPLIT_SHA,
    "m1JoblibSha256": sha(m1_joblib), "m1OnnxSha256": sha(m1_onnx), "m1MetaSha256": sha(MODEL / "m1_meta.json"),
    "m2JoblibSha256": sha(m2_joblib), "m2OnnxSha256": sha(m2_onnx), "m2MetaSha256": sha(MODEL / "m2_meta.json"),
})

# Test rows are opened only after the model lock above.
test_rows = []
for path in sorted(FEATURES.glob("chunk-*.jsonl")):
    with path.open() as handle:
        for line in handle:
            row = json.loads(line)
            if split[row["normalizedName"]] == "test":
                test_rows.append(row)
indices = random.Random(2026111302).sample(range(len(test_rows)), 1000)
sample = [test_rows[index] for index in indices]
V1 = np.asarray([row["features"] for row in sample], dtype=np.float32)
VH = vectorizer().transform([row["lowercaseName"] for row in sample]).toarray().astype(np.float32, copy=False)
V2 = np.concatenate([V1, VH], axis=1)

def verify(sklearn_model, onnx_path, values):
    expected = sklearn_model.predict_proba(values)
    runtime = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    outputs = dict(zip([item.name for item in runtime.get_outputs()], runtime.run(None, {"features": values})))
    actual = np.asarray(outputs["probabilities"])
    return float(np.max(np.abs(expected - actual)))

m1_difference = verify(m1, m1_onnx, V1)
m2_difference = verify(m2, m2_onnx, V2)
if m1_difference > 1e-5 or m2_difference > 1e-5:
    raise RuntimeError(f"ONNX verification failed: M1={m1_difference}, M2={m2_difference}")
append_lock({"event": "onnx_verified", "rows": 1000, "seed": 2026111302,
             "tolerance": 1e-5, "m1MaxAbsoluteDifference": m1_difference,
             "m2MaxAbsoluteDifference": m2_difference})
print(json.dumps({"trainingRows": len(y), "m1MaxDifference": m1_difference, "m2MaxDifference": m2_difference}))
