#!/usr/bin/env python3
import ast
import collections
import datetime as dt
import glob
import hashlib
import json
import math
import random
import statistics
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PRED = HERE / "predictions"
APP_DATA = ROOT / "waicy_2026/local_apps_test/v2/data"
CLASSES = ["authentication", "other", "preference", "tracking"]
APP_ORDER = ["grafana", "jupyter", "datasette", "code-server", "django-admin"]


def load_rows():
    rows = []
    for path in sorted(PRED.glob("chunk-*.jsonl")):
        with path.open() as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def predicted(probabilities):
    return max(CLASSES, key=lambda name: (probabilities[name], -CLASSES.index(name)))


def truth_tracking(label):
    return label in (2, 3)


def confusion(rows):
    result = {"model": [0, 0, 0, 0], "rules": [0, 0, 0, 0]}
    for row in rows:
        truth = truth_tracking(row["label"])
        for method, guess in (("model", predicted(row["model"]) == "tracking"), ("rules", row["rules"]["label"] == "tracking")):
            if truth and guess:
                result[method][0] += 1
            elif not truth and guess:
                result[method][1] += 1
            elif truth and not guess:
                result[method][2] += 1
            else:
                result[method][3] += 1
    return result


def metric_values(counts):
    tp, fp, fn, tn = map(float, counts)
    precision = tp / (tp + fp) if tp + fp else math.nan
    recall = tp / (tp + fn) if tp + fn else math.nan
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    balanced = (recall + specificity) / 2 if not (math.isnan(recall) or math.isnan(specificity)) else math.nan
    return {"precision": precision, "recall": recall, "f1": f1, "balancedAccuracy": balanced}


def aggregate_by(rows, key):
    groups = collections.defaultdict(lambda: np.zeros(8, dtype=np.int64))
    for row in rows:
        c = confusion([row])
        groups[key(row)][:4] += c["model"]
        groups[key(row)][4:] += c["rules"]
    return np.stack(list(groups.values()))


def bootstrap(rows, key, seed):
    point_counts = confusion(rows)
    point = {method: metric_values(counts) for method, counts in point_counts.items()}
    clusters = aggregate_by(rows, key)
    rng = np.random.default_rng(seed)
    samples = {method: collections.defaultdict(list) for method in ("model", "rules")}
    differences = []
    for _ in range(1000):
        indices = rng.integers(0, len(clusters), size=len(clusters))
        totals = clusters[indices].sum(axis=0)
        values = {"model": metric_values(totals[:4]), "rules": metric_values(totals[4:])}
        for method in values:
            for metric, value in values[method].items():
                samples[method][metric].append(value)
        differences.append(values["model"]["f1"] - values["rules"]["f1"])
    output = {}
    for method in ("model", "rules"):
        output[method] = {}
        for metric, value in point[method].items():
            low, high = np.nanpercentile(samples[method][metric], [2.5, 97.5])
            output[method][metric] = {"value": value, "ci95": [float(low), float(high)]}
    diff_low, diff_high = np.nanpercentile(differences, [2.5, 97.5])
    output["f1Difference"] = {
        "value": point["model"]["f1"] - point["rules"]["f1"],
        "ci95": [float(diff_low), float(diff_high)],
    }
    output["records"] = len(rows)
    output["clusters"] = len(clusters)
    return output


def training_names():
    names = {str(row["name"]).lower() for row in json.load(open(ROOT / "data/training_cookies.json"))}
    tree = ast.parse((ROOT / "backend/generate_training_data.py").read_text())
    names.update(node.value.lower() for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str))
    return names


def tracker_measurement(rows):
    eligible = [row for row in rows if row["label"] in (0, 1, 2, 3)]
    excluded = len(rows) - len(eligible)
    by_name = collections.defaultdict(list)
    for row in eligible:
        by_name[row["name"].lower()].append(row)
    rng = random.Random(2026111402)
    view_b = [rng.choice(by_name[name]) for name in sorted(by_name)]
    known = training_names()
    view_c = [row for row in view_b if row["name"].lower() not in known]
    views = {
        "A": bootstrap(eligible, lambda row: row["websiteId"].rsplit(":", 1)[0], 2026111401),
        "B": bootstrap(view_b, lambda row: row["name"].lower(), 2026111403),
        "C": bootstrap(view_c, lambda row: row["name"].lower(), 2026111404),
    }
    diff = views["C"]["f1Difference"]
    if diff["value"] >= 0.05 and diff["ci95"][0] > 0:
        verdict = "win"
    elif diff["value"] < 0:
        verdict = "loss"
    else:
        verdict = "tie/no win"
    model_wrong_rules_right = collections.Counter()
    rules_wrong_model_right = collections.Counter()
    for row in eligible:
        truth = truth_tracking(row["label"])
        model_ok = (predicted(row["model"]) == "tracking") == truth
        rules_ok = (row["rules"]["label"] == "tracking") == truth
        if not model_ok and rules_ok:
            model_wrong_rules_right[row["name"].lower()] += 1
        if not rules_ok and model_ok:
            rules_wrong_model_right[row["name"].lower()] += 1
    return {
        "eligible": len(eligible),
        "excludedOtherLabels": excluded,
        "views": views,
        "mainVerdict": verdict,
        "modelWrongRulesRight": model_wrong_rules_right.most_common(20),
        "rulesWrongModelRight": rules_wrong_model_right.most_common(20),
    }


def stable_number(namespace):
    return int(hashlib.sha256(namespace.encode()).hexdigest(), 16)


def app_inputs(app):
    prediction = json.load(open(APP_DATA / f"{app}.predictions.json"))
    labels = json.load(open(APP_DATA / f"{app}.labels.json"))["cookies"]
    cookies = []
    for cookie in prediction["cookies"]:
        cookies.append({
            "name": cookie["name"],
            "modelAuth": cookie["model"]["probabilities"]["authentication"],
            "rulesLabel": cookie["rules"]["label"],
            "rulesScore": cookie["rules"]["score"],
            "login": bool(labels.get(cookie["key"], {}).get("loginCookie")),
            "source": "app",
        })
    return cookies


def position(cookies, method, app, website):
    if method == "model":
        ordered = sorted(cookies, key=lambda c: (-c["modelAuth"], stable_number(f"2026111410|model|{app}|{website}|{c['source']}|{c['name']}")))
    else:
        ordered = sorted(cookies, key=lambda c: (
            0 if c["rulesLabel"] == "authentication" else 1,
            -c["rulesScore"] if c["rulesLabel"] == "authentication" else 0,
            stable_number(f"2026111410|rules|{app}|{website}|{c['source']}|{c['name']}"),
        ))
    return next(index for index, cookie in enumerate(ordered, 1) if cookie["login"])


def summarize_mix(rows):
    return {
        "mixes": len(rows),
        "meanTests": statistics.fmean(row["tests"] for row in rows),
        "medianTests": statistics.median(row["tests"] for row in rows),
        "within3Share": statistics.fmean(row["within3"] for row in rows),
        "medianMixSize": statistics.median(row["mixSize"] for row in rows),
    }


def tests_saved(rows):
    websites = collections.defaultdict(list)
    for row in rows:
        site, first_party = row["websiteId"].rsplit(":", 1)
        if first_party == "1":
            websites[site].append(row)
    eligible = {site: cookies for site, cookies in websites.items() if 10 <= len(cookies) <= 60}
    per_app = {}
    overall = {method: [] for method in ("model", "rules", "random")}
    for app_index, app in enumerate(APP_ORDER):
        app_cookies = app_inputs(app)
        login_count = sum(cookie["login"] for cookie in app_cookies)
        if not login_count:
            raise RuntimeError(f"{app} has no login cookie")
        selected = random.Random(2026111405 + app_index).sample(sorted(eligible), min(50, len(eligible)))
        method_rows = {method: [] for method in ("model", "rules", "random")}
        app_names = {cookie["name"].lower() for cookie in app_cookies}
        for site in selected:
            web = [{
                "name": row["name"], "modelAuth": row["model"]["authentication"],
                "rulesLabel": row["rules"]["label"], "rulesScore": row["rules"]["score"],
                "login": False, "source": "website",
            } for row in eligible[site] if row["name"].lower() not in app_names]
            mixed = web + app_cookies
            n, k = len(mixed), login_count
            for method in ("model", "rules"):
                tests = position(mixed, method, app, site)
                method_rows[method].append({"tests": tests, "within3": tests <= 3, "mixSize": n})
            expected = (n + 1) / (k + 1)
            if n <= 3:
                within = 1.0
            elif n - k < 3:
                within = 1.0
            else:
                within = 1 - math.comb(n - k, 3) / math.comb(n, 3)
            method_rows["random"].append({"tests": expected, "within3": within, "mixSize": n})
        per_app[app] = {method: summarize_mix(values) for method, values in method_rows.items()}
        for method in overall:
            overall[method].extend(method_rows[method])
    return {
        "eligibleWebsites": len(eligible),
        "perApp": per_app,
        "overall": {method: summarize_mix(values) for method, values in overall.items()},
    }


def fmt(value):
    return f"{value:.3f}"


def metric_cell(item):
    return f"{fmt(item['value'])} ({fmt(item['ci95'][0])}–{fmt(item['ci95'][1])})"


def elapsed_from_locks():
    events = [json.loads(line) for line in (HERE / "locks.txt").read_text().splitlines() if line.strip()]
    chunks = [event for event in events if event.get("event") == "chunk_complete"]
    completed = [event for event in events if event.get("event") == "scoring_complete"]
    if not chunks or not completed:
        return None
    parse = lambda value: dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parse(completed[-1]["at"]) - parse(chunks[0]["at"])).total_seconds()


def write_markdown(result):
    tracker = result["trackerDetection"]
    mixes = result["testsSaved"]
    lines = [
        "# CookieBlock comparison results", "",
        f"Run date: {result['runDate']}. Dataset MD5: `9aece7e28a54a7cfc2250f5c2861ca20`. Model SHA-256: `6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2`.", "",
        f"Scored {result['cookieCount']:,} cookies from {result['websiteCount']:,} website IDs. Excluded {tracker['excludedOtherLabels']:,} cookies for unsupported labels. Scoring phase elapsed time: {result['scoringElapsedSeconds']:.1f} seconds; analysis elapsed time: {result['analysisElapsedSeconds']:.1f} seconds.", "",
        "## 1. Tracker detection", "",
        "Each cell is point estimate (website/name bootstrap 95% range).", "",
        "| View | Method | Precision | Recall | F1 | Balanced accuracy |", "|---|---|---:|---:|---:|---:|",
    ]
    for view in ("A", "B", "C"):
        for method in ("model", "rules"):
            row = tracker["views"][view][method]
            lines.append(f"| {view} | {method.title()} | {metric_cell(row['precision'])} | {metric_cell(row['recall'])} | {metric_cell(row['f1'])} | {metric_cell(row['balancedAccuracy'])} |")
    diff = tracker["views"]["C"]["f1Difference"]
    lines += ["", f"View sizes: A = {tracker['views']['A']['records']:,} cookies in {tracker['views']['A']['clusters']:,} website clusters; B = {tracker['views']['B']['records']:,} names; C = {tracker['views']['C']['records']:,} unseen names.", "", f"**Main result: {tracker['mainVerdict'].upper()}.** View C model-minus-rules F1 = {fmt(diff['value'])} (95% range {fmt(diff['ci95'][0])}–{fmt(diff['ci95'][1])}). The predeclared win rule requires a difference of at least 0.05 and an interval entirely above zero.", "",
              "## 2. Semi-synthetic tests saved", "", f"Eligible CookieBlock websites: {mixes['eligibleWebsites']:,}. Each app uses 50 fixed-seed mixes.", "",
              "| App | Method | Mean tests | Median tests | Within first 3 | Median mix size |", "|---|---|---:|---:|---:|---:|"]
    for app in APP_ORDER + ["overall"]:
        source = mixes["overall"] if app == "overall" else mixes["perApp"][app]
        for method in ("model", "rules", "random"):
            row = source[method]
            lines.append(f"| {app} | {method.title()} | {row['meanTests']:.2f} | {row['medianTests']:.2f} | {row['within3Share']:.1%} | {row['medianMixSize']:.1f} |")
    lines += ["", "App cookie names and deletion-tested login cookies:", ""]
    for app in APP_ORDER:
        cookies = app_inputs(app)
        lines.append(f"- {app}: {', '.join(c['name'] for c in cookies)}; login cookie(s): {', '.join(c['name'] for c in cookies if c['login'])}.")
    lines += ["", "## 3. Where each method fails", "", "Model wrong and rules right:", ""]
    lines.extend(f"- `{name}`: {count:,}" for name, count in tracker["modelWrongRulesRight"])
    lines += ["", "Rules wrong and model right:", ""]
    lines.extend(f"- `{name}`: {count:,}" for name, count in tracker["rulesWrongModelRight"])
    lines += ["", "## 4. Limits", "", "- Consent-banner labels can be wrong.", "- The dataset is from 2021.", "- Necessary cookies combine login and other essential cookies, so tracker detection does not directly measure login-cookie detection.", "- The tests-saved measurement is semi-synthetic.", "- The app study contains only five apps, including one single-cookie app.", "",
              "## 5. Draft wording for Avelyn's review", "", "If the model wins:", "", "- Slide line: On unseen real cookie names, CookieGuard beat the simple rules on tracking F1 and also reduced the tests needed to find app login cookies.", "- Answer: The rules recognize patterns we already know. The model also combines security settings, lifetime, domain, name, and value-shape signals, and on this held-out test it performed better by the rule we fixed before running it.", "", "If the model does not win:", "", "- Slide line: On this held-out real-cookie test, the model did not beat the simple rules; CookieGuard therefore keeps the AI suggestion reviewable instead of treating it as automatic truth.", "- Answer: This test did not show that the model is broadly better than simple rules. Its value is as a second, reviewable ranking signal in the login-cookie workflow, while the rules remain a strong baseline and the user confirms the choice.", "",
              "## 6. Citation", "", "Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022. CookieBlock dataset, Zenodo record 5838646, CC BY 4.0.", "",
              "## 7. Privacy check", "", f"`value_check.json` reports {result['valueCheck']['filesContainingSerializedValue']} files containing a serialized cookie value. It separately records {result['valueCheck']['filesWithIncidentalSubstringMatch']} files with harmless raw substring overlaps, such as a value matching a cookie name or numeric output fragment.", ""]
    (HERE / "results.md").write_text("\n".join(lines))


def main():
    started = time.time()
    rows = load_rows()
    tracker = tracker_measurement(rows)
    mixes = tests_saved(rows)
    analysis_elapsed = time.time() - started
    websites = {row["websiteId"].rsplit(":", 1)[0] for row in rows}
    value_check = json.load(open(HERE / "value_check.json"))
    result = {
        "schemaVersion": 1,
        "runDate": dt.datetime.now(dt.timezone.utc).isoformat(),
        "cookieCount": len(rows),
        "websiteCount": len(websites),
        "scoringElapsedSeconds": elapsed_from_locks(),
        "analysisElapsedSeconds": analysis_elapsed,
        "trackerDetection": tracker,
        "testsSaved": mixes,
        "valueCheck": value_check,
    }
    (HERE / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    write_markdown(result)
    print(json.dumps({"verdict": tracker["mainVerdict"], "cookies": len(rows), "websites": len(websites), "analysisSeconds": round(analysis_elapsed, 2)}))


if __name__ == "__main__":
    main()
