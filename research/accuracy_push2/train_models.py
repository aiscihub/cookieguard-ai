#!/usr/bin/env python3
import csv
import hashlib
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import onnxruntime as ort
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, precision_score, recall_score
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FEATURES = ROOT / "waicy_2026/accuracy_push/features"
RAW = ROOT / "waicy_2026/cookieblock_test/raw/06_Training_Data/tranco_05May_20210510_201615.json"
PREPARED = HERE / "prepared"
OUT = HERE / "model"
ASSIGNMENTS = json.loads((ROOT / "waicy_2026/accuracy_push/validation_split.json").read_text())["assignments"]
CATEGORIES = ["Functional", "Marketing", "Analytics", "Security", "Necessary", "Personalization"]
WIDTHS = {"Base": 38, "A": 45, "B": 422, "A+B": 429}
RF = dict(n_estimators=150, max_depth=12, min_samples_split=5, min_samples_leaf=2,
          class_weight="balanced", random_state=42, n_jobs=-1)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def rows():
    for path in sorted(FEATURES.glob("chunk-*.jsonl")):
        with path.open() as handle:
            for line in handle:
                row = json.loads(line)
                if row["normalizedName"] in ASSIGNMENTS:
                    yield row


def load_dictionary():
    exact = defaultdict(set)
    wildcard = set()
    with (HERE / "inputs/open-cookie-database.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = row["Cookie / Data Key name"].strip()
            category = row["Category"].strip()
            if name and category in CATEGORIES:
                exact[name].add(category)
            if name and row["Wildcard match"].strip().lower() in {"1", "true", "yes"}:
                wildcard.add(name)
    return {name: next(iter(values)) for name, values in exact.items() if len(values) == 1}, tuple(sorted(wildcard))


def dictionary_vector(name, exact, wildcards):
    values = [0.0] * 7
    category = exact.get(name)
    if category in CATEGORIES:
        values[CATEGORIES.index(category)] = 1.0
    values[6] = float(any(name.startswith(prefix) for prefix in wildcards))
    return values


def load_embeddings():
    output = {}
    manifest = json.loads((PREPARED / "embedding_manifest.json").read_text())
    for item in manifest["chunks"]:
        path = PREPARED / item["file"]
        if sha(path) != item["sha256"]:
            raise RuntimeError(f"embedding hash mismatch: {path.name}")
        data = np.load(path)
        for name, vector in zip(data["names"].tolist(), data["embeddings"]):
            output[name] = vector.astype(np.float32)
    return output


def matrix(data, variant, raw_names, exact, wildcards, embeddings):
    result = []
    for row in data:
        values = list(row["features"])
        if variant in {"A", "A+B"}:
            values.extend(dictionary_vector(raw_names[row["recordIndex"]], exact, wildcards))
        if variant in {"B", "A+B"}:
            values.extend(embeddings[row["normalizedName"]])
        result.append(values)
    return np.asarray(result, dtype=np.float32)


def choose_threshold(y, probability):
    candidates = [(balanced_accuracy_score(y, probability >= value), -abs(value - .5), value)
                  for value in np.linspace(0, 1, 101)]
    return float(max(candidates)[2])


def metrics(y, probability, threshold):
    prediction = probability >= threshold
    return {"balancedAccuracy": float(balanced_accuracy_score(y, prediction)),
            "precision": float(precision_score(y, prediction, zero_division=0)),
            "recall": float(recall_score(y, prediction, zero_division=0)),
            "f1": float(f1_score(y, prediction, zero_division=0)),
            "prAuc": float(average_precision_score(y, probability))}


def main():
    if not (HERE / "fresh_test/manifest.json").exists():
        raise RuntimeError("fresh test is not frozen")
    if not (PREPARED / "feature_manifest.json").exists():
        raise RuntimeError("prepared features are not frozen")
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = list(rows())
    raw_names = [row["name"] for row in json.loads(RAW.read_text()).values()]
    exact, wildcards = load_dictionary()
    embeddings = load_embeddings()
    candidate = [row for row in all_rows if ASSIGNMENTS[row["normalizedName"]] == "candidate-training"]
    validation = [row for row in all_rows if ASSIGNMENTS[row["normalizedName"]] == "validation"]
    groups = defaultdict(list)
    for row in validation:
        groups[row["normalizedName"]].append(row)
    chooser = random.Random(2026111004)
    validation_b = [chooser.choice(groups[name]) for name in sorted(groups)]
    y_candidate = np.isin([row["label"] for row in candidate], [2, 3]).astype(np.int64)
    y_validation = np.isin([row["label"] for row in validation_b], [2, 3]).astype(np.int64)

    results = {"schemaVersion": 1, "candidateTrainingRows": len(candidate),
               "candidateTrainingNames": len({row['normalizedName'] for row in candidate}),
               "validationRows": len(validation_b), "variants": {}}
    for variant in WIDTHS:
        x_train = matrix(candidate, variant, raw_names, exact, wildcards, embeddings)
        x_validation = matrix(validation_b, variant, raw_names, exact, wildcards, embeddings)
        started = time.perf_counter()
        model = RandomForestClassifier(**RF).fit(x_train, y_candidate)
        fit_seconds = time.perf_counter() - started
        started = time.perf_counter()
        probability = model.predict_proba(x_validation)[:, list(model.classes_).index(1)]
        inference_seconds = time.perf_counter() - started
        threshold = choose_threshold(y_validation, probability)
        result = {"width": WIDTHS[variant], "threshold": threshold,
                  "fitSeconds": fit_seconds, "inferenceSeconds": inference_seconds,
                  "metrics": metrics(y_validation, probability, threshold)}
        results["variants"][variant] = result
        joblib.dump(model, OUT / f"validation-{variant.lower().replace('+', '-plus-')}.joblib")

    best = max(item["metrics"]["balancedAccuracy"] for item in results["variants"].values())
    tie_set = [name for name in WIDTHS if best - results["variants"][name]["metrics"]["balancedAccuracy"] <= .005]
    selected = tie_set[0]
    results["selection"] = {"variant": selected, "bestBalancedAccuracy": best, "simplicityTieSet": tie_set,
                            "rule": "maximum V-B balanced accuracy; within 0.005 prefer Base, A, B, A+B"}
    atomic_json(HERE / "validation_results.json", results)
    atomic_json(HERE / "selection.json", results["selection"])

    y_all = np.isin([row["label"] for row in all_rows], [2, 3]).astype(np.int64)
    verification_rows = random.Random(2026111402).sample(validation, min(1000, len(validation)))
    metadata = {"schemaVersion": 1, "featureOrder": {"base": json.loads((FEATURES / "feature_names.json").read_text())["featureNames"],
                "dictionary": CATEGORIES + ["wildcard-prefix"], "embeddingDimensions": 384}, "models": {}}
    for variant in WIDTHS:
        x_all = matrix(all_rows, variant, raw_names, exact, wildcards, embeddings)
        started = time.perf_counter()
        model = RandomForestClassifier(**RF).fit(x_all, y_all)
        fit_seconds = time.perf_counter() - started
        stem = variant.lower().replace('+', '-plus-')
        joblib_path = OUT / f"{stem}.joblib"
        onnx_path = OUT / f"{stem}.onnx"
        joblib.dump(model, joblib_path)
        graph = convert_sklearn(model, initial_types=[("features", FloatTensorType([None, WIDTHS[variant]]))],
                                options={id(model): {"zipmap": False}}, target_opset=15)
        temporary = Path(str(onnx_path) + ".tmp")
        temporary.write_bytes(graph.SerializeToString())
        temporary.replace(onnx_path)
        x_verify = matrix(verification_rows, variant, raw_names, exact, wildcards, embeddings)
        expected = model.predict_proba(x_verify)[:, list(model.classes_).index(1)]
        runtime = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        outputs = dict(zip([item.name for item in runtime.get_outputs()], runtime.run(None, {"features": x_verify})))
        actual = np.asarray(outputs["probabilities"])[:, 1]
        maximum = float(np.max(np.abs(expected - actual)))
        if maximum > 1e-5:
            raise RuntimeError(f"ONNX verification failed for {variant}: {maximum}")
        metadata["models"][variant] = {"width": WIDTHS[variant], "threshold": results["variants"][variant]["threshold"],
            "trainingRows": len(all_rows), "trainingNames": len(ASSIGNMENTS), "fitSeconds": fit_seconds,
            "joblibSha256": sha(joblib_path), "onnxSha256": sha(onnx_path), "onnxMaximumAbsoluteDifference": maximum,
            "verificationRows": len(verification_rows), "requiresEmbeddingRuntime": variant in {"B", "A+B"}}
    atomic_json(OUT / "metadata.json", metadata)
    print(json.dumps({"selection": results["selection"], "validation": {name: row["metrics"] for name, row in results["variants"].items()},
                      "onnxMaximums": {name: row["onnxMaximumAbsoluteDifference"] for name, row in metadata["models"].items()}}, indent=2))


if __name__ == "__main__":
    main()
