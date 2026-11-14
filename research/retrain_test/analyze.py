#!/usr/bin/env python3
import collections
import datetime as dt
import hashlib
import json
import math
import random
import re
import statistics
import time
from pathlib import Path

import joblib
import numpy as np
import onnx
import onnxruntime as ort
from sklearn.feature_extraction.text import HashingVectorizer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FEATURE_DIR = HERE / "features"
MODEL_DIR = HERE / "model"
COOKIEBLOCK = ROOT / "waicy_2026/cookieblock_test"
APP_DIR = ROOT / "waicy_2026/local_apps_test/v2/data"
SPLIT = json.load(open(HERE / "split.json"))
FEATURE_NAMES = json.load(open(FEATURE_DIR / "feature_names.json"))["featureNames"]
FI = {name: index for index, name in enumerate(FEATURE_NAMES)}
METHODS = ["m1", "m2", "shipped", "rules", "fixedRules"]
APPS = ["grafana", "jupyter", "datasette", "code-server", "django-admin"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs():
    locks = [json.loads(line) for line in open(COOKIEBLOCK / "locks.txt") if line.strip()]
    chunk_locks = {row["chunk"]: row["sha256"] for row in locks if row.get("event") == "chunk_complete"}
    for index in range(31):
        path = COOKIEBLOCK / "predictions" / f"chunk-{index:03d}.jsonl"
        if chunk_locks.get(index) != sha(path):
            raise RuntimeError(f"CookieBlock prediction chunk {index} hash mismatch")
    if sha(APP_DIR / "app_features.json") != "edd56682f1a1b90df163b287b24e91c18ab5a43cc5127111dca6e62761de774b":
        raise RuntimeError("app_features.json hash mismatch")


def vectorizer():
    return HashingVectorizer(analyzer="char_wb", ngram_range=(2, 4), n_features=256, alternate_sign=False)


def normalize_name(value):
    pieces = re.split(r"([_.-])", str(value).strip().lower())
    output = []
    for piece in pieces:
        if piece in {"_", ".", "-"}:
            output.append(piece)
            continue
        mixed = len(piece) >= 6 and re.search("[a-z]", piece) and re.search("[0-9]", piece)
        hex_letters = len(piece) >= 8 and re.fullmatch("[0-9a-f]+", piece) and re.search("[a-f]", piece)
        output.append("#" if mixed or hex_letters else piece)
    return re.sub(r"\d+", "0", "".join(output))


def load_features():
    rows = []
    for path in sorted(FEATURE_DIR.glob("chunk-*.jsonl")):
        with path.open() as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def load_shipped(indices):
    wanted = set(indices)
    output = {}
    for path in sorted((COOKIEBLOCK / "predictions").glob("chunk-*.jsonl")):
        with path.open() as handle:
            for line in handle:
                row = json.loads(line)
                if row["recordIndex"] in wanted:
                    output[row["recordIndex"]] = row
    if len(output) != len(wanted):
        raise RuntimeError("missing shipped predictions")
    return output


def corrected_tracking_name(name):
    return any(re.search(pattern, name, re.I) for pattern in
               (r"^_ga", r"^_gid", r"analytics", r"tracking", r"^_*utm", r"^_?fbp", r"amplitude", r"mixpanel", r"^_cl"))


def rule_from_features(values, fixed_name=None):
    f = {name: values[index] for index, name in enumerate(FEATURE_NAMES)}
    if fixed_name is not None:
        f["name_matches_tracking"] = 1 if corrected_tracking_name(fixed_name) else 0
    auth = f["name_matches_auth"] * .35 + (.25 if f["f_login_behavior_score"] > 0 else 0) + f["has_httponly"] * .10 + (.15 if f["value_entropy_bucket"] >= 2 else 0) + f["value_looks_like_jwt"] * .10 + f["has_secure"] * .05
    tracking = f["name_matches_tracking"] * .50 + f["f_third_party_context"] * .25 + (.15 if not f["has_httponly"] and f["f_persistent_days_bucket"] >= 2 else 0) + f["value_is_numeric"] * .10
    preference = f["name_matches_preference"] * .60 + (.20 if f["value_length_bucket"] == 0 else 0) + f["value_is_numeric"] * .10 + (.10 if not f["has_httponly"] and not f["has_secure"] else 0)
    scores = [("authentication", auth), ("tracking", tracking), ("preference", preference), ("other", .25)]
    total = sum(score for _, score in scores)
    probabilities = {name: score / total if total else .25 for name, score in scores}
    label = max(scores, key=lambda pair: probabilities[pair[0]])[0]
    return label, probabilities[label]


def metric(counts):
    tp, fp, fn, tn = map(float, counts)
    precision = tp / (tp + fp) if tp + fp else math.nan
    recall = tp / (tp + fn) if tp + fn else math.nan
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    return {"precision": precision, "recall": recall, "f1": f1, "balancedAccuracy": (recall + specificity) / 2}


def counts(rows, method):
    result = [0, 0, 0, 0]
    for row in rows:
        truth = row["label"] in (2, 3)
        guess = row["predictions"][method]
        result[(0 if truth and guess else 1 if not truth and guess else 2 if truth else 3)] += 1
    return result


def bootstrap(rows, cluster_key, seed):
    groups = collections.defaultdict(lambda: np.zeros(len(METHODS) * 4, dtype=np.int64))
    for row in rows:
        for method_index, method in enumerate(METHODS):
            groups[cluster_key(row)][method_index * 4:(method_index + 1) * 4] += counts([row], method)
    arrays = np.stack(list(groups.values()))
    point = {method: metric(counts(rows, method)) for method in METHODS}
    samples = {method: collections.defaultdict(list) for method in METHODS}
    differences = collections.defaultdict(list)
    rng = np.random.default_rng(seed)
    comparisons = [("m1", "rules"), ("m1", "fixedRules"), ("m1", "shipped")] + [("m2", other) for other in METHODS if other != "m2"]
    for _ in range(1000):
        selected = arrays[rng.integers(0, len(arrays), size=len(arrays))].sum(axis=0)
        values = {}
        for index, method_name in enumerate(METHODS):
            values[method_name] = metric(selected[index * 4:(index + 1) * 4])
            for metric_name, value in values[method_name].items():
                samples[method_name][metric_name].append(value)
        for left, right in comparisons:
            differences[f"{left}-{right}"].append(values[left]["f1"] - values[right]["f1"])
    output = {"records": len(rows), "clusters": len(arrays), "methods": {}, "f1Differences": {}}
    for method_name in METHODS:
        output["methods"][method_name] = {}
        for metric_name, value in point[method_name].items():
            ci = np.nanpercentile(samples[method_name][metric_name], [2.5, 97.5])
            output["methods"][method_name][metric_name] = {"value": value, "ci95": [float(ci[0]), float(ci[1])]}
    for key, values in differences.items():
        left, right = key.split("-", 1)
        ci = np.nanpercentile(values, [2.5, 97.5])
        output["f1Differences"][key] = {"value": point[left]["f1"] - point[right]["f1"], "ci95": [float(ci[0]), float(ci[1])]}
    return output


def stable(namespace):
    return int(hashlib.sha256(namespace.encode()).hexdigest(), 16)


def app_cookies(models, shipped_runtime):
    source = json.load(open(APP_DIR / "app_features.json"))["apps"]
    result = {}
    for app, cookies in source.items():
        labels = json.load(open(APP_DIR / f"{app}.labels.json"))["cookies"]
        feature_rows = [[cookie["features"].get(name, 0) for name in FEATURE_NAMES] for cookie in cookies]
        x1 = np.asarray(feature_rows, dtype=np.float32)
        names = [cookie["name"].strip().lower() for cookie in cookies]
        x2 = np.concatenate([x1, vectorizer().transform(names).toarray().astype(np.float32)], axis=1)
        m1p = models["m1"].predict_proba(x1)
        m2p = models["m2"].predict_proba(x2)
        shipped_outputs = dict(zip([item.name for item in shipped_runtime.get_outputs()], shipped_runtime.run(None, {"features": x1})))
        shipped_p = np.asarray(shipped_outputs["probabilities"])
        rows = []
        for index, cookie in enumerate(cookies):
            normalized = normalize_name(cookie["name"])
            split_side = SPLIT.get(normalized, "absent")
            rule_label, rule_score = rule_from_features(feature_rows[index])
            rows.append({"name": cookie["name"], "key": cookie["key"], "normalizedName": normalized,
                         "m1TrainingName": split_side == "train", "splitSide": split_side,
                         "login": bool(labels.get(cookie["key"], {}).get("loginCookie")),
                         "m1Necessary": float(m1p[index, 0]), "m2Necessary": float(m2p[index, 0]),
                         "shippedAuthentication": float(shipped_p[index, 0]),
                         "rulesLabel": rule_label, "rulesScore": rule_score, "source": "app"})
        result[app] = rows
    return result


def ordering(cookies, method, app, site):
    if method in ("m1", "m2"):
        field = f"{method}Necessary"
        ordered = sorted(cookies, key=lambda row: (-row[field], stable(f"2026111320|{method}|{app}|{site}|{row['source']}|{row['name']}")))
    elif method == "shipped":
        ordered = sorted(cookies, key=lambda row: (-row["shippedAuthentication"], stable(f"2026111320|shipped|{app}|{site}|{row['source']}|{row['name']}")))
    else:
        ordered = sorted(cookies, key=lambda row: (0 if row["rulesLabel"] == "authentication" else 1,
                                                    -row["rulesScore"] if row["rulesLabel"] == "authentication" else 0,
                                                    stable(f"2026111320|rules|{app}|{site}|{row['source']}|{row['name']}")))
    return next(index for index, row in enumerate(ordered, 1) if row["login"])


def summarize(rows):
    return {"mixes": len(rows), "meanTests": statistics.fmean(row["tests"] for row in rows),
            "medianTests": statistics.median(row["tests"] for row in rows),
            "within3Share": statistics.fmean(row["within3"] for row in rows),
            "medianMixSize": statistics.median(row["mixSize"] for row in rows)}


def measurement_two(test_rows, app_rows):
    websites = collections.defaultdict(list)
    for row in test_rows:
        site, suffix = row["websiteId"].rsplit(":", 1)
        if suffix == "1": websites[site].append(row)
    eligible = {site: rows for site, rows in websites.items() if 10 <= len(rows) <= 60}
    methods = ["m1", "m2", "shipped", "rules", "random"]
    per_app, overall = {}, {method: [] for method in methods}
    for app_index, app in enumerate(APPS):
        selected = random.Random(2026111310 + app_index).sample(sorted(eligible), min(50, len(eligible)))
        app_names = {row["name"].lower() for row in app_rows[app]}
        k = sum(row["login"] for row in app_rows[app])
        observations = {method: [] for method in methods}
        for site in selected:
            web = [{"name": row["lowercaseName"], "m1Necessary": row["m1Probabilities"][0],
                    "m2Necessary": row["m2Probabilities"][0], "shippedAuthentication": row["shippedProbabilities"]["authentication"],
                    "rulesLabel": row["shippedRulesLabel"], "rulesScore": row["shippedRulesScore"],
                    "login": False, "source": "website"}
                   for row in eligible[site] if row["lowercaseName"] not in app_names]
            mixed = web + app_rows[app]
            n = len(mixed)
            for method in methods[:-1]:
                tests = ordering(mixed, method, app, site)
                observations[method].append({"tests": tests, "within3": tests <= 3, "mixSize": n})
            expected = (n + 1) / (k + 1)
            within = 1.0 if n <= 3 or n - k < 3 else 1 - math.comb(n - k, 3) / math.comb(n, 3)
            observations["random"].append({"tests": expected, "within3": within, "mixSize": n})
        per_app[app] = {"appCookies": app_rows[app], "methods": {method: summarize(rows) for method, rows in observations.items()}}
        for method in methods: overall[method].extend(observations[method])
    return {"eligibleWebsites": len(eligible), "perApp": per_app, "overall": {method: summarize(rows) for method, rows in overall.items()}}


def shipped_split_frequency():
    graph = onnx.load(ROOT / "extension-standalone/model/cookieguard_model.onnx")
    counts = collections.Counter()
    for node in graph.graph.node:
        if node.op_type != "TreeEnsembleClassifier": continue
        attrs = {attribute.name: attribute for attribute in node.attribute}
        modes = [item.decode() for item in attrs["nodes_modes"].strings]
        for mode, feature in zip(modes, attrs["nodes_featureids"].ints):
            if mode != "LEAF": counts[FEATURE_NAMES[feature]] += 1
    total = sum(counts.values())
    return [{"feature": name, "splitFrequency": count / total, "splits": count} for name, count in counts.most_common(10)]


def fmt_metric(item):
    return f"{item['value']:.3f} ({item['ci95'][0]:.3f}–{item['ci95'][1]:.3f})"


def write_markdown(result):
    lines = ["# Real-cookie retraining results", "", f"Run date: {result['runDate']}.", "",
             f"Environment: Python {result['versions']['python']}; NumPy {result['versions']['numpy']}; scikit-learn {result['versions']['scikitLearn']}; skl2onnx {result['versions']['skl2onnx']}; ONNX Runtime {result['versions']['onnxruntime']}; ONNX {result['versions']['onnx']}.", "",
             f"Dataset MD5: `9aece7e28a54a7cfc2250f5c2861ca20`. Split SHA-256: `{result['hashes']['split']}`. M1 ONNX: `{result['hashes']['m1']}`. M2 ONNX: `{result['hashes']['m2']}`. Shipped model: `6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2`.", "",
             f"Training: {result['counts']['trainNames']:,} names and {result['counts']['trainCookies']:,} cookies. Test: {result['counts']['testNames']:,} names and {result['counts']['testCookies']:,} cookies. Total elapsed time through analysis: {result['runtimeSeconds']:.1f} seconds.", "",
             f"Training class counts (necessary, functional, analytics, advertising): {result['counts']['trainClassCounts']['0']:,}, {result['counts']['trainClassCounts']['1']:,}, {result['counts']['trainClassCounts']['2']:,}, {result['counts']['trainClassCounts']['3']:,}. Test class counts: {result['counts']['testClassCounts']['0']:,}, {result['counts']['testClassCounts']['1']:,}, {result['counts']['testClassCounts']['2']:,}, {result['counts']['testClassCounts']['3']:,}.", "",
             "## 1. Tracker detection on test names", "", "Each cell is estimate (paired bootstrap 95% range).", "",
             "| View | Method | Precision | Recall | F1 | Balanced accuracy |", "|---|---|---:|---:|---:|---:|"]
    labels = {"m1": "M1", "m2": "M2", "shipped": "Shipped model", "rules": "Rules", "fixedRules": "Fixed rules"}
    for view in ("T-B", "T-A"):
        for method in METHODS:
            row = result["trackerDetection"]["views"][view]["methods"][method]
            lines.append(f"| {view} | {labels[method]} | {fmt_metric(row['precision'])} | {fmt_metric(row['recall'])} | {fmt_metric(row['f1'])} | {fmt_metric(row['balancedAccuracy'])} |")
    main = result["trackerDetection"]["views"]["T-B"]["f1Differences"]["m1-rules"]
    lines += ["", f"**Main verdict: {result['trackerDetection']['verdict'].upper()}.** T-B M1-minus-rules F1 = {main['value']:.3f} (95% range {main['ci95'][0]:.3f}–{main['ci95'][1]:.3f}).", "",
              "Prespecified paired F1 differences (left minus right):", "", "| View | Comparison | Difference | 95% range |", "|---|---|---:|---:|"]
    comparisons = [("m1-rules", "M1 − rules"), ("m1-fixedRules", "M1 − fixed rules"), ("m1-shipped", "M1 − shipped"),
                   ("m2-m1", "M2 − M1"), ("m2-shipped", "M2 − shipped"), ("m2-rules", "M2 − rules"), ("m2-fixedRules", "M2 − fixed rules")]
    for view in ("T-B", "T-A"):
        for key, label in comparisons:
            item = result["trackerDetection"]["views"][view]["f1Differences"][key]
            lines.append(f"| {view} | {label} | {item['value']:.3f} | {item['ci95'][0]:.3f}–{item['ci95'][1]:.3f} |")
    lines += ["",
              "## 2. Semi-synthetic tests saved", "", "The app-cookie split column reports whether each normalized app-cookie name was in M1 training (`train`), held out (`test`), or absent from CookieBlock (`absent`).", "",
              "| App | App cookie normalized-name split | Method | Mean tests | Median tests | Within first 3 | Median mix size |", "|---|---|---|---:|---:|---:|---:|"]
    for app in APPS + ["overall"]:
        if app == "overall":
            split_text, methods = "—", result["testsSaved"]["overall"]
        else:
            split_text = "; ".join(f"{row['name']}: {row['splitSide']}" for row in result["testsSaved"]["perApp"][app]["appCookies"])
            methods = result["testsSaved"]["perApp"][app]["methods"]
        for method in ("m1", "m2", "shipped", "rules", "random"):
            row = methods[method]
            lines.append(f"| {app} | {split_text} | {method.upper() if method in ('m1','m2') else method.title()} | {row['meanTests']:.2f} | {row['medianTests']:.2f} | {row['within3Share']:.1%} | {row['medianMixSize']:.1f} |")
    lines += ["", "## 3. What changed from the shipped model", "", "Most common test names that flipped from wrong to right:", ""]
    lines.extend(f"- `{name}`: {count:,}" for name, count in result["changes"]["wrongToRight"])
    lines += ["", "Most common test names that flipped from right to wrong:", ""]
    lines.extend(f"- `{name}`: {count:,}" for name, count in result["changes"]["rightToWrong"])
    lines += ["", "Prespecified names:", ""]
    lines.extend(f"- `{name}`: normalized `{item['normalizedName']}`, split `{item['splitSide']}`." for name, item in result["specialNames"].items())
    lines += ["", "## 4. Feature importance", "", "M1 impurity importance (descriptive, not causal):", "", "| Rank | Feature | Importance |", "|---:|---|---:|"]
    for index, row in enumerate(result["featureImportance"]["m1"], 1): lines.append(f"| {index} | `{row['feature']}` | {row['importance']:.4f} |")
    lines += ["", "The shipped artifact contains no training impurity statistics, so exact shipped impurity importance cannot be recovered. Its ONNX split-frequency proxy is shown separately:", "", "| Rank | Feature | Split share |", "|---:|---|---:|"]
    for index, row in enumerate(result["featureImportance"]["shippedSplitFrequencyProxy"], 1): lines.append(f"| {index} | `{row['feature']}` | {row['splitFrequency']:.4f} |")
    lines += ["", "## 5. Limits", "", "- Consent-banner labels are noisy.", "- The data is from 2021.", "- Necessary is not login; the run-time deletion test remains necessary.", "- M1 has no authentication class and cannot replace the shipped model inside `createOnnxClassifier`.", "- M2 requires an engine change.", "- Normalized-name grouping cannot remove every semantic similarity.", "- Impurity importance and ONNX split frequency are descriptive and are not directly equivalent.", "",
              "## 6. Draft wording for review", "", "If M1 wins:", "", "- Slide: Training on real cookies made the same Random Forest beat the simple rules on cookie names it never saw.", "- Answer: The rules match known strings, while the real-data model combines 38 independent signals and generalized better to held-out normalized names under a test fixed before training.", "", "If M1 does not win:", "", "- Slide: Even after retraining on real cookies, the model did not beat the simple rules on unseen names, so CookieGuard keeps AI as a reviewable suggestion rather than a claim of superiority.", "- Answer: For this year, the evidence says the simple rules are the stronger general baseline. The model can still help rank uncertain cases, but the deletion test and user confirmation are what make the workflow trustworthy.", "",
              "## 7. Citation", "", "Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022. CookieBlock dataset, Zenodo record 5838646, CC BY 4.0.", ""]
    if result.get("valueCheck"):
        check = result["valueCheck"]
        lines += ["## 8. Privacy check", "", f"Serialized cookie values were found in {check['filesContainingSerializedValue']} output files. The raw scan also measured long incidental string overlaps in {check['filesWithLongIncidentalOverlap']} files and short incidental overlaps in {check['filesWithShortIncidentalOverlap']} files; these are retained in `value_check.json` with their classification reason.", ""]
    (HERE / "results.md").write_text("\n".join(lines))


def main():
    started = time.time()
    verify_inputs()
    all_rows = load_features()
    test_rows = [row for row in all_rows if SPLIT[row["normalizedName"]] == "test"]
    shipped = load_shipped(row["recordIndex"] for row in test_rows)
    m1, m2 = joblib.load(MODEL_DIR / "m1.joblib"), joblib.load(MODEL_DIR / "m2.joblib")
    x1 = np.asarray([row["features"] for row in test_rows], dtype=np.float32)
    x2 = np.concatenate([x1, vectorizer().transform([row["lowercaseName"] for row in test_rows]).toarray().astype(np.float32)], axis=1)
    m1p, m2p = m1.predict_proba(x1), m2.predict_proba(x2)
    for index, row in enumerate(test_rows):
        saved = shipped[row["recordIndex"]]
        row["m1Probabilities"] = [float(value) for value in m1p[index]]
        row["m2Probabilities"] = [float(value) for value in m2p[index]]
        row["shippedProbabilities"] = saved["model"]
        row["shippedRulesLabel"] = saved["rules"]["label"]
        row["shippedRulesScore"] = saved["rules"]["score"]
        fixed_label, _ = rule_from_features(row["features"], row["lowercaseName"])
        shipped_label = max(("authentication", "other", "preference", "tracking"), key=lambda name: saved["model"][name])
        row["predictions"] = {"m1": m1p[index, 2] + m1p[index, 3] >= .5,
                              "m2": m2p[index, 2] + m2p[index, 3] >= .5,
                              "shipped": shipped_label == "tracking",
                              "rules": saved["rules"]["label"] == "tracking",
                              "fixedRules": fixed_label == "tracking"}
    groups = collections.defaultdict(list)
    for row in test_rows: groups[row["normalizedName"]].append(row)
    chooser = random.Random(2026111303)
    t_b = [chooser.choice(groups[name]) for name in sorted(groups)]
    views = {"T-B": bootstrap(t_b, lambda row: row["normalizedName"], 2026111304),
             "T-A": bootstrap(test_rows, lambda row: row["websiteId"].rsplit(":", 1)[0], 2026111305)}
    main_diff = views["T-B"]["f1Differences"]["m1-rules"]
    verdict = "win" if main_diff["value"] >= .05 and main_diff["ci95"][0] > 0 else "loss" if main_diff["value"] < 0 else "tie/no win"
    wrong_to_right, right_to_wrong = collections.Counter(), collections.Counter()
    for row in test_rows:
        truth = row["label"] in (2, 3)
        m1_ok, shipped_ok = row["predictions"]["m1"] == truth, row["predictions"]["shipped"] == truth
        if m1_ok and not shipped_ok: wrong_to_right[row["lowercaseName"]] += 1
        if shipped_ok and not m1_ok: right_to_wrong[row["lowercaseName"]] += 1
    shipped_runtime = ort.InferenceSession(str(ROOT / "extension-standalone/model/cookieguard_model.onnx"), providers=["CPUExecutionProvider"])
    apps = app_cookies({"m1": m1, "m2": m2}, shipped_runtime)
    tests = measurement_two(test_rows, apps)
    lock_rows = [json.loads(line) for line in open(HERE / "locks.txt") if line.strip()]
    split_lock = next(row for row in lock_rows if row["event"] == "split_frozen")
    model_lock = next(row for row in lock_rows if row["event"] == "models_frozen")
    protocol_time = dt.datetime.fromisoformat(lock_rows[0]["at"].replace("Z", "+00:00"))
    result = {"schemaVersion": 1, "runDate": dt.datetime.now(dt.timezone.utc).isoformat(),
              "versions": json.load(open(MODEL_DIR / "m1_meta.json"))["versions"],
              "hashes": {"split": split_lock["sha256"], "m1": model_lock["m1OnnxSha256"], "m2": model_lock["m2OnnxSha256"],
                         "shipped": "6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2"},
              "counts": {"trainNames": split_lock["trainNames"], "testNames": split_lock["testNames"],
                         "trainCookies": split_lock["trainCookies"], "testCookies": split_lock["testCookies"],
                         "trainClassCounts": split_lock["trainClassCounts"], "testClassCounts": split_lock["testClassCounts"]},
              "runtimeSeconds": (dt.datetime.now(dt.timezone.utc) - protocol_time).total_seconds(),
              "analysisSeconds": time.time() - started,
              "trackerDetection": {"views": views, "verdict": verdict, "excludedLabels": 0},
              "testsSaved": tests,
              "changes": {"wrongToRight": wrong_to_right.most_common(15), "rightToWrong": right_to_wrong.most_common(15)},
              "specialNames": {name: {"normalizedName": normalize_name(name), "splitSide": SPLIT.get(normalize_name(name), "absent")} for name in ("_gid", "_gat", "optanonalertboxclosed")},
              "featureImportance": {"m1": [{"feature": FEATURE_NAMES[index], "importance": float(m1.feature_importances_[index])} for index in np.argsort(m1.feature_importances_)[::-1][:10]],
                                    "shippedSplitFrequencyProxy": shipped_split_frequency()},
              "onnxVerification": next(row for row in lock_rows if row["event"] == "onnx_verified")}
    if (HERE / "value_check.json").exists(): result["valueCheck"] = json.load(open(HERE / "value_check.json"))
    (HERE / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    write_markdown(result)
    print(json.dumps({"verdict": verdict, "testCookies": len(test_rows), "eligibleMixWebsites": tests["eligibleWebsites"], "analysisSeconds": round(time.time() - started, 2)}))


if __name__ == "__main__":
    main()
