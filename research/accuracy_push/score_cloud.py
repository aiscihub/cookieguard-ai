#!/usr/bin/env python3
import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, precision_score, recall_score

HERE = Path(__file__).resolve().parent
CLOUD = HERE / "cloud"
key = json.loads((CLOUD / "sample_key.json").read_text())["items"]
metadata = json.loads((CLOUD / "run_metadata.json").read_text())
ids = list(key)
truth = np.asarray([key[item]["truth"] for item in ids], dtype=bool)


def read_reply(batch, run):
    path = CLOUD / "replies" / f"batch-{batch}-run-{run}.txt"
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


cloud = {run: {} for run in range(1, 4)}
valid_predictions = {run: 0 for run in range(1, 4)}
for batch in range(1, 7):
    public = json.loads((CLOUD / "sample_public.json").read_text())[(batch - 1) * 50:batch * 50]
    batch_ids = [item["id"] for item in public]
    for run in range(1, 4):
        reply = read_reply(batch, run)
        for item in batch_ids:
            value = reply.get(item)
            cloud[run][item] = value if isinstance(value, bool) else None
            valid_predictions[run] += isinstance(value, bool)


def prediction_array(mapping):
    return np.asarray([mapping.get(item) if isinstance(mapping.get(item), bool) else not key[item]["truth"] for item in ids], dtype=bool)


def metric(guess, probability=None):
    value = {"balancedAccuracy": float(balanced_accuracy_score(truth, guess)),
        "precision": float(precision_score(truth, guess, zero_division=0)), "recall": float(recall_score(truth, guess, zero_division=0)),
        "f1": float(f1_score(truth, guess, zero_division=0))}
    value["prAuc"] = float(average_precision_score(truth, probability)) if probability is not None else None
    return value


methods = {}
for run in range(1, 4): methods[f"cloudRun{run}"] = {"guess": prediction_array(cloud[run]), "probability": None}
for name in ["main", "m1", "shipped", "rules"]:
    guesses = np.asarray([key[item]["local"][name] for item in ids], dtype=bool)
    probability_name = f"{name}Probability"
    probabilities = np.asarray([key[item]["local"].get(probability_name, float(key[item]["local"][name])) for item in ids])
    methods[name] = {"guess": guesses, "probability": probabilities if name != "rules" else None}

majority = {}
for item in ids:
    values = [cloud[run][item] for run in range(1, 4) if isinstance(cloud[run][item], bool)]
    majority[item] = sum(values) >= 2 if len(values) >= 2 else None
methods["cloudMajority"] = {"guess": prediction_array(majority), "probability": None}

points = {name: metric(value["guess"], value["probability"]) for name, value in methods.items()}
rng = np.random.default_rng(2026111012)
samples = {name: [] for name in methods}
for _ in range(1000):
    indices = rng.integers(0, len(ids), len(ids))
    for name, value in methods.items():
        samples[name].append(balanced_accuracy_score(truth[indices], value["guess"][indices]))
for name in methods: points[name]["balancedAccuracyCi95"] = [float(x) for x in np.percentile(samples[name], [2.5, 97.5])]

pairwise = {}
for left, right in [(1, 2), (1, 3), (2, 3)]:
    agree = valid = 0
    for item in ids:
        a, b = cloud[left][item], cloud[right][item]
        if isinstance(a, bool) and isinstance(b, bool): valid += 1; agree += a == b
    pairwise[f"run{left}-run{right}"] = {"agreementOverAll300": agree / 300, "agreementAmongValid": agree / valid if valid else None,
        "agree": agree, "bothValid": valid}
complete = [item for item in ids if all(isinstance(cloud[run][item], bool) for run in range(1, 4))]
unanimous = sum(len({cloud[run][item] for run in range(1, 4)}) == 1 for item in complete)
if complete:
    p_yes = sum(cloud[run][item] for item in complete for run in range(1, 4)) / (3 * len(complete)); p_no = 1 - p_yes
    p_bar = np.mean([((sum(cloud[run][item] for run in range(1, 4))) ** 2 + (3 - sum(cloud[run][item] for run in range(1, 4))) ** 2 - 3) / 6 for item in complete])
    fleiss = float((p_bar - (p_yes ** 2 + p_no ** 2)) / (1 - (p_yes ** 2 + p_no ** 2)))
else: fleiss = None
majority_valid = sum(isinstance(majority[item], bool) for item in ids)
majority_diff = sum(isinstance(majority[item], bool) and majority[item] != key[item]["local"]["main"] for item in ids)
elapsed = [run["elapsedSeconds"] for run in metadata["runs"]]
local_timing = json.loads((HERE.parent / "llm_baseline/local_timing.json").read_text())
result = {"schemaVersion": 1, "model": metadata["model"], "reasoningEffort": metadata["reasoningEffort"],
    "sampleNames": 300, "replyFiles": 18, "validReplyFiles": sum(run["replyValid"] for run in metadata["runs"]),
    "validPredictionsByRun": {f"run{run}": valid_predictions[run] for run in range(1, 4)}, "methods": points,
    "agreement": {"completeCaseNames": len(complete), "unanimousOverAll300": unanimous / 300, "unanimousAmongComplete": unanimous / len(complete) if complete else None,
        "pairwise": pairwise, "fleissKappaCompleteCases": fleiss, "majorityValidNames": majority_valid,
        "majorityDiffersFromMain": majority_diff},
    "timing": {"cloudMeanSecondsPerPrompt": float(np.mean(elapsed)), "cloudMeanSecondsPerCookie": float(np.mean(elapsed) / 50),
        "cloudMinSecondsPerCookie": min(elapsed) / 50, "cloudMaxSecondsPerCookie": max(elapsed) / 50,
        "localWarmMillisecondsPerCookie": local_timing["summaries"]["model"]["warm_batch"]["mean_ms"] / 11,
        "localColdMillisecondsPerCookie": local_timing["summaries"]["model"]["cold_process"]["mean_ms"] / 11},
    "invalidPolicy": "Each missing or non-Boolean prediction is counted wrong; reply bytes were not repaired."}
(CLOUD / "cloud_results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
