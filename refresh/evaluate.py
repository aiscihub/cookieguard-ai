"""Paired site-cluster evaluation. This module never changes a model or threshold."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import onnxruntime as ort
from common import ROOT, die, label, load, month_seed, rows, sha, write_json
from lookup import Lookup

METRICS = ("balancedAccuracy", "precision", "recall")

def metrics(counts):
    tn, fp, fn, tp = map(float, counts)
    recall = tp / (tp + fn) if tp + fn else None
    specificity = tn / (tn + fp) if tn + fp else None
    return {
        "balancedAccuracy": (recall + specificity) / 2 if recall is not None and specificity is not None else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": recall,
    }

def cluster_counts(y, prediction, clusters):
    result = np.zeros((len(set(clusters)), 4), dtype=np.int64)
    indices = {site: i for i, site in enumerate(sorted(set(clusters)))}
    for truth, pred, site in zip(y, prediction, clusters):
        result[indices[site], int(truth) * 2 + int(pred)] += 1
    return result

def interval(values, draws):
    finite = [v for v in values if v is not None and np.isfinite(v)]
    # Do not manufacture a confidence interval from a mostly degenerate bootstrap.
    return {
        "lower": float(np.quantile(finite, .025)) if len(finite) >= .95 * draws else None,
        "upper": float(np.quantile(finite, .975)) if len(finite) >= .95 * draws else None,
        "validDraws": len(finite), "requestedDraws": draws,
    }

def summary(y, pred, clusters, seed, draws=1000):
    table = cluster_counts(y, pred, clusters)
    point = metrics(table.sum(axis=0))
    rng = np.random.default_rng(seed)
    samples = {name: [] for name in METRICS}
    for _ in range(draws):
        score = metrics(table[rng.integers(0, len(table), len(table))].sum(axis=0)) if len(table) >= 2 else dict.fromkeys(METRICS)
        for name in METRICS:
            samples[name].append(score[name])
    return {
        "rows": len(y), "sites": len(table), "trackerRows": int(sum(y)),
        "confusion": dict(zip(["tn", "fp", "fn", "tp"], map(int, table.sum(axis=0)))),
        "metrics": {name: {"estimate": point[name], **interval(samples[name], draws)} for name in METRICS},
    }

def paired(y, candidate, baseline, clusters, seed, draws=1000):
    left, right = cluster_counts(y, candidate, clusters), cluster_counts(y, baseline, clusters)
    rng = np.random.default_rng(seed)
    samples = {name: [] for name in METRICS}
    for _ in range(draws):
        if len(left) < 2:
            a = b = dict.fromkeys(METRICS)
        else:
            selection = rng.integers(0, len(left), len(left))
            a, b = metrics(left[selection].sum(axis=0)), metrics(right[selection].sum(axis=0))
        for name in METRICS:
            samples[name].append(None if a[name] is None or b[name] is None else a[name] - b[name])
    a, b = metrics(left.sum(axis=0)), metrics(right.sum(axis=0))
    return {
        "rows": len(y), "sites": len(left),
        "metrics": {name: {"estimate": None if a[name] is None or b[name] is None else a[name] - b[name],
                           **interval(samples[name], draws)} for name in METRICS},
    }

def infer(path, x):
    if not len(x):
        return [], np.zeros((0, 2))
    options = ort.SessionOptions()
    options.log_severity_level = 4
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
    result = dict(zip([o.name for o in session.get_outputs()], session.run(None, {"features": x})))
    probabilities = result["probabilities"]
    if isinstance(probabilities, list) and probabilities and isinstance(probabilities[0], dict):
        probabilities = [[p[k] for k in sorted(p)] for p in probabilities]
    return list(result["label"]), np.asarray(probabilities)

def load_candidate(directory, records, x):
    meta = load(directory / "meta.json")
    if (sha(directory / "model.onnx") != meta["onnxSha256"] or
        sha(directory / "lookup.json") != meta["lookupSha256"] or
        sha(directory / "membership.json") != meta["membershipSha256"]):
        raise ValueError("candidate-digest-mismatch")
    _, probabilities = infer(directory / "model.onnx", x)
    lookup = Lookup(load(directory / "lookup.json"))
    membership = set(load(directory / "membership.json"))
    hits = [lookup.match(r["name"]) for r in records]
    pred = [hit[1]["label"] if hit else int(p[1] >= meta["threshold"]) for hit, p in zip(hits, probabilities)]
    unseen = [r["normalizedName"] not in membership and hit is None for r, hit in zip(records, hits)]
    return pred, unseen, hits, meta

def describe(y, prediction, unseen, hits, clusters, seed):
    prediction, unseen = np.asarray(prediction, dtype=int), np.asarray(unseen, dtype=bool)
    matched = [(i, h) for i, h in enumerate(hits) if h]
    return {
        "natural": summary(y, prediction, clusters, seed),
        "unseenNames": summary(y[unseen], prediction[unseen], clusters[unseen], seed),
        "lookup": {"hits": len(matched), "hitRate": len(matched) / len(y) if len(y) else None,
                   "hitAccuracy": sum(h[1]["label"] == y[i] for i, h in matched) / len(matched) if matched else None,
                   "labelDisagreements": sum(h[1]["label"] != y[i] for i, h in matched)},
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--month", required=True)
    p.add_argument("--run", type=Path, default=ROOT / "refresh/.work/run")
    p.add_argument("--release", type=Path)
    p.add_argument("--candidate", type=Path)
    p.add_argument("--phase", choices=["baseline", "candidate"], required=True)
    a = p.parse_args()
    a.run = a.run.resolve()
    if a.release:
        a.release = a.release.resolve()
    if a.candidate:
        a.candidate = a.candidate.resolve()
    seed = month_seed(a.month)
    release = a.release or ROOT / "data/releases" / a.month
    records = list(rows(release / "cookies.jsonl"))
    x = np.asarray([r["features"] for r in records], dtype=np.float32).reshape((-1, 38))
    y = np.asarray([label(r) for r in records], dtype=int)
    clusters = np.asarray([str(r["rank"]) for r in records])
    predictions, unseen, hit_map, sources = {}, {}, {}, {}
    a.run.mkdir(parents=True, exist_ok=True)
    if a.phase == "baseline":
        if (a.run / "baseline.json").exists():
            raise ValueError("baseline-already-opened")
        subprocess.run(["node", str(ROOT / "refresh/score_rules.mjs"), "--rows", str(release / "cookies.jsonl"),
                        "--out", str(a.run / "rules.json")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        predictions["production-rules"] = load(a.run / "rules.json")
        unseen["production-rules"] = [True] * len(y)
        hit_map["production-rules"] = [None] * len(y)
        v1 = ROOT / "extension-standalone/model/cookieguard_model.onnx"
        provenance = load(ROOT / "refresh/reference/provenance.json")
        if sha(v1) != provenance["productionOnnxSha256"]:
            raise ValueError("production-model-changed")
        labels, _ = infer(v1, x)
        predictions["production-v1"] = [int(str(v) == "tracking") for v in labels]
        v1_names = set(load(ROOT / "refresh/reference/v1-membership.json"))
        unseen["production-v1"] = [r["normalizedName"] not in v1_names for r in records]
        hit_map["production-v1"] = [None] * len(y)
        sources["production-v1"] = {"onnxSha256": sha(v1), "membershipBasis": provenance["productionMembershipBasis"]}
        sources["production-rules"] = {"engineSha256": sha(ROOT / "packages/core/vendor/engine.cjs")}
        previous = sorted(path for path in (ROOT / "models/releases").glob("????-??") if path.name < a.month and (path / "meta.json").exists())
        if previous:
            pred, mask, hits, meta = load_candidate(previous[-1], records, x)
            predictions["previous-candidate"], unseen["previous-candidate"], hit_map["previous-candidate"] = pred, mask, hits
            sources["previous-candidate"] = {"month": previous[-1].name, "onnxSha256": meta["onnxSha256"]}
        else:
            study_path = ROOT / "refresh/reference/study-c2.onnx"
            if sha(study_path) != provenance["studyOnnxSha256"]:
                raise ValueError("study-model-changed")
            _, prob = infer(study_path, x)
            lookup = Lookup(load(ROOT / "refresh/reference/study-lookup.json"))
            hits = [lookup.match(r["name"]) for r in records]
            membership = set(load(ROOT / "refresh/reference/study-membership.json"))
            predictions["study-N1-C2"] = [h[1]["label"] if h else int(p[1] >= .4) for h, p in zip(hits, prob)]
            unseen["study-N1-C2"] = [r["normalizedName"] not in membership and h is None for r, h in zip(records, hits)]
            hit_map["study-N1-C2"] = hits
            sources["study-N1-C2"] = {"onnxSha256": sha(study_path), "threshold": .4}
        metrics_result = {name: describe(y, pred, unseen[name], hit_map[name], clusters, seed) for name, pred in predictions.items()}
        labels_by_name = defaultdict(set)
        for row in records:
            labels_by_name[row["normalizedName"]].add(label(row))
        baseline = {
            "schemaVersion": 1, "month": a.month, "rowsSha256": sha(release / "cookies.jsonl"),
            "seed": seed, "bootstrapDraws": 1000, "resamplingUnit": "site; paired draws shared across methods",
            "sources": sources, "models": metrics_result,
            "disagreementNames": sum(len(labels) > 1 for labels in labels_by_name.values()),
            "predictionLabels": predictions, "unseenMasks": unseen,
        }
        write_json(a.run / "baseline.json", baseline)
        print(json.dumps({"stage": "baseline", "rows": len(records), "models": list(predictions)}))
        return
    baseline = load(a.run / "baseline.json")
    if baseline["rowsSha256"] != sha(release / "cookies.jsonl") or baseline["month"] != a.month:
        raise ValueError("test-data-changed-after-opening")
    candidate = a.candidate or a.run / "candidate"
    pred, mask, hits, meta = load_candidate(candidate, records, x)
    if meta["month"] != a.month or meta["baselineSha256"] != sha(a.run / "baseline.json") or not meta["currentMonthExcluded"]:
        raise ValueError("candidate-provenance")
    current, mask = np.asarray(pred), np.asarray(mask, dtype=bool)
    comparisons = {}
    for name, values in baseline["predictionLabels"].items():
        reference = np.asarray(values)
        # Compare the same rows, unseen to BOTH models; never subtract metrics on different subsets.
        both = mask & np.asarray(baseline["unseenMasks"][name], dtype=bool)
        comparisons[name] = {
            "natural": paired(y, current, reference, clusters, seed),
            "unseenNames": paired(y[both], current[both], reference[both], clusters[both], seed),
        }
    output = {k: v for k, v in baseline.items() if k not in {"predictionLabels", "unseenMasks"}}
    output["models"]["candidate"] = describe(y, pred, mask, hits, clusters, seed)
    output["sources"]["candidate"] = {"onnxSha256": meta["onnxSha256"], "lookupSha256": meta["lookupSha256"],
                                      "threshold": meta["threshold"], "metaSha256": sha(candidate / "meta.json")}
    output["candidateMinus"] = comparisons
    output["unseenComparisonDefinition"] = "intersection: absent from both models' training-name memberships and every applicable lookup match"
    write_json(a.run / "evaluation.json", output)
    print(json.dumps({"stage": "candidate-evaluation", "rows": len(records), "models": list(output["models"])}))

if __name__ == "__main__":
    try: main()
    except Exception: sys.exit(die())
