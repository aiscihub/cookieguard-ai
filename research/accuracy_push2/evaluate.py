#!/usr/bin/env python3
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, precision_score, recall_score

import train_models as tm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FRESH = HERE / "fresh_test"
MODEL = HERE / "model"
METHODS = ["Base", "A", "B", "A+B", "shipped", "M1", "C2", "rules", "fixedRules", "everythingTracker"]


def atomic_json(path, value):
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def load_rows():
    output = []
    for path in sorted(FRESH.glob("rows-*.jsonl")):
        with path.open() as handle:
            output.extend(json.loads(line) for line in handle if line.strip())
    return output


def fresh_matrix(rows, variant, exact, wildcards, embeddings):
    output = []
    for row in rows:
        values = list(row["features"])
        if variant in {"A", "A+B"}:
            values.extend(tm.dictionary_vector(row["name"], exact, wildcards))
        if variant in {"B", "A+B"}:
            values.extend(embeddings[row["normalizedName"]])
        output.append(values)
    return np.asarray(output, dtype=np.float32)


def runtime(path):
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def probabilities(session, values, column):
    outputs = dict(zip([item.name for item in session.get_outputs()], session.run(None, {"features": values})))
    return np.asarray(outputs["probabilities"])[:, column]


def rule(values, fixed_name=None):
    names = json.loads((ROOT / "waicy_2026/accuracy_push/features/feature_names.json").read_text())["featureNames"]
    f = dict(zip(names, values))
    if fixed_name is not None:
        f["name_matches_tracking"] = float(any(__import__("re").search(pattern, fixed_name, __import__("re").I) for pattern in
            (r"^_ga", r"^_gid", r"analytics", r"tracking", r"^_*utm", r"^_?fbp", r"amplitude", r"mixpanel", r"^_cl")))
    authentication = f["name_matches_auth"] * .35 + (.25 if f["f_login_behavior_score"] > 0 else 0) + f["has_httponly"] * .10 + (.15 if f["value_entropy_bucket"] >= 2 else 0) + f["value_looks_like_jwt"] * .10 + f["has_secure"] * .05
    tracking = f["name_matches_tracking"] * .50 + f["f_third_party_context"] * .25 + (.15 if not f["has_httponly"] and f["f_persistent_days_bucket"] >= 2 else 0) + f["value_is_numeric"] * .10
    preference = f["name_matches_preference"] * .60 + (.20 if f["value_length_bucket"] == 0 else 0) + f["value_is_numeric"] * .10 + (.10 if not f["has_httponly"] and not f["has_secure"] else 0)
    scores = {"authentication": authentication, "tracking": tracking, "preference": preference, "other": .25}
    total = sum(scores.values())
    return tracking / total if total else .25, max(scores, key=scores.get) == "tracking"


def point(y, probability, prediction):
    return {"balancedAccuracy": float(balanced_accuracy_score(y, prediction)),
            "precision": float(precision_score(y, prediction, zero_division=0)),
            "recall": float(recall_score(y, prediction, zero_division=0)),
            "f1": float(f1_score(y, prediction, zero_division=0)),
            "prAuc": float(average_precision_score(y, probability))}


def bootstrap(rows, predictions, cluster_key, seed, selected):
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[cluster_key(row)].append(index)
    clusters = [np.asarray(indices) for indices in groups.values()]
    y = np.asarray([row["label"] for row in rows], dtype=np.int64)
    samples = {method: defaultdict(list) for method in METHODS}
    differences = []
    rng = np.random.default_rng(seed)
    for _ in range(1000):
        chosen = np.concatenate([clusters[index] for index in rng.integers(0, len(clusters), len(clusters))])
        values = {}
        for method in METHODS:
            values[method] = point(y[chosen], predictions[method]["probability"][chosen], predictions[method]["prediction"][chosen])
            for key, value in values[method].items():
                samples[method][key].append(value)
        differences.append(values[selected]["balancedAccuracy"] - values["C2"]["balancedAccuracy"])
    output = {"records": len(rows), "clusters": len(clusters), "methods": {}}
    for method in METHODS:
        output["methods"][method] = {}
        current = point(y, predictions[method]["probability"], predictions[method]["prediction"])
        for key, value in current.items():
            bounds = np.nanpercentile(samples[method][key], [2.5, 97.5])
            output["methods"][method][key] = {"value": value, "ci95": [float(bounds[0]), float(bounds[1])]}
    bounds = np.nanpercentile(differences, [2.5, 97.5])
    output["selectedMinusC2BalancedAccuracy"] = {
        "value": output["methods"][selected]["balancedAccuracy"]["value"] - output["methods"]["C2"]["balancedAccuracy"]["value"],
        "ci95": [float(bounds[0]), float(bounds[1])], "bootstrapSeed": seed,
    }
    return output


def main():
    rows = load_rows()
    manifest = json.loads((FRESH / "manifest.json").read_text())
    if len(rows) != manifest["records"]:
        raise RuntimeError("fresh row count differs from frozen manifest")
    exact, wildcards = tm.load_dictionary()
    embeddings = tm.load_embeddings()
    metadata = json.loads((MODEL / "metadata.json").read_text())
    selection = json.loads((HERE / "selection.json").read_text())
    selected = selection["variant"]
    x_base = fresh_matrix(rows, "Base", exact, wildcards, embeddings)
    predictions = {}
    for variant in ["Base", "A", "B", "A+B"]:
        values = fresh_matrix(rows, variant, exact, wildcards, embeddings)
        p = probabilities(runtime(MODEL / f"{variant.lower().replace('+', '-plus-')}.onnx"), values, 1)
        threshold = metadata["models"][variant]["threshold"]
        predictions[variant] = {"probability": p, "prediction": p >= threshold}
    shipped_runtime = runtime(ROOT / "extension-standalone/model/cookieguard_model.onnx")
    shipped_all = np.asarray(dict(zip([item.name for item in shipped_runtime.get_outputs()],
                                      shipped_runtime.run(None, {"features": x_base})))["probabilities"])
    shipped = shipped_all[:, 3]
    predictions["shipped"] = {"probability": shipped, "prediction": np.argmax(shipped_all, axis=1) == 3}
    m1_runtime = runtime(ROOT / "waicy_2026/retrain_test/model/m1.onnx")
    m1_all = dict(zip([item.name for item in m1_runtime.get_outputs()],
                      m1_runtime.run(None, {"features": x_base})))["probabilities"]
    m1_p = np.asarray(m1_all)[:, 2] + np.asarray(m1_all)[:, 3]
    predictions["M1"] = {"probability": m1_p, "prediction": m1_p >= .5}
    c2_p = probabilities(runtime(ROOT / "waicy_2026/accuracy_push/model/main.onnx"), x_base, 1)
    predictions["C2"] = {"probability": c2_p, "prediction": c2_p >= .4}
    for method, fixed in [("rules", False), ("fixedRules", True)]:
        values = [rule(row["features"], row["name"] if fixed else None) for row in rows]
        predictions[method] = {"probability": np.asarray([item[0] for item in values]),
                               "prediction": np.asarray([item[1] for item in values])}
    predictions["everythingTracker"] = {"probability": np.ones(len(rows)), "prediction": np.ones(len(rows), dtype=bool)}

    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row["normalizedName"]].append(index)
    chooser = random.Random(2026111403)
    indices = [chooser.choice(grouped[name]) for name in sorted(grouped)]
    f_b_rows = [rows[index] for index in indices]
    f_b_predictions = {method: {key: value[indices] for key, value in content.items()} for method, content in predictions.items()}
    views = {
        "F-B": bootstrap(f_b_rows, f_b_predictions, lambda row: row["normalizedName"], 2026111404, selected),
        "F-A": bootstrap(rows, predictions, lambda row: row["siteId"], 2026111405, selected),
    }
    diff = views["F-B"]["selectedMinusC2BalancedAccuracy"]
    swap = diff["value"] > 0 and diff["ci95"][0] > 0
    truth = np.asarray([row["label"] for row in rows], dtype=bool)
    fixed = Counter()
    missed = Counter()
    for index, row in enumerate(rows):
        base_ok = predictions["Base"]["prediction"][index] == truth[index]
        if not base_ok and (predictions["A"]["prediction"][index] == truth[index] or predictions["B"]["prediction"][index] == truth[index]):
            fixed[row["normalizedName"]] += 1
        if predictions[selected]["prediction"][index] != truth[index]:
            missed[row["normalizedName"]] += 1
    order = lambda counter: sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:10]
    fresh_names = sorted(grouped)
    exact_names = {row["normalizedName"] for row in rows if row["name"] in exact}
    wildcard_names = {row["normalizedName"] for row in rows if any(row["name"].startswith(prefix) for prefix in wildcards)}
    coverage = {"names": len(fresh_names), "exact": len(exact_names), "wildcard": len(wildcard_names)}
    result = {"schemaVersion": 1, "freshManifestSha256": tm.sha(FRESH / "manifest.json"), "selectedVariant": selected,
              "views": views, "swap": {"passed": swap, "verdict": "replace C2" if swap else "keep C2", "rule": "selected F-B BA > C2 and paired 95% lower bound > 0"},
              "coverage": coverage, "fixedNames": order(fixed), "stillMissedNames": order(missed)}
    atomic_json(HERE / "fresh_results.json", result)
    print(json.dumps({"selected": selected, "swap": result["swap"], "F-B": {method: views["F-B"]["methods"][method]["balancedAccuracy"]["value"] for method in METHODS}}, indent=2))


if __name__ == "__main__":
    main()
