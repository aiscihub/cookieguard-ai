#!/usr/bin/env python3
"""Open the frozen test exactly once and save all local predictions."""
import hashlib
import json
import random
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
from dictionary_matcher import match

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TEST = HERE / "test"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value, indent=2) + "\n")


def load_rows():
    output = []
    for path in sorted((TEST / "batches").glob("rows-*.jsonl")):
        output.extend(json.loads(line) for line in path.read_text().splitlines() if line)
    return output


manifest = json.loads((TEST / "manifest.json").read_text())
rows = load_rows()
if len(rows) != manifest["records"] or len({row["normalizedName"] for row in rows}) != manifest["normalizedNames"]:
    raise RuntimeError("frozen manifest does not match row shards")
for item in manifest["rowFiles"]:
    path = TEST / item["file"]
    if sha(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
        raise RuntimeError(f"row shard mismatch: {path}")
for line in (HERE / "locks_pre_crawl.txt").read_text().splitlines():
    digest, name = line.split("  ", 1)
    if sha(HERE / name) != digest:
        raise RuntimeError(f"pre-crawl lock changed: {name}")
if sha(ROOT / "waicy_2026/accuracy_push/model/main.onnx") != "a4f3905c7f4ccbd061846e5e3e1c20a51a172daa37f31a8af16e7233e6be2a93":
    raise RuntimeError("v3 model changed")
if sha(ROOT / "waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/vendor/engine.cjs") != "bcc2718198f0798b77505c27efcfd0bf8a251cfd90dc31b0daf375dc9df7e4bd":
    raise RuntimeError("rules engine changed")

d1 = json.loads((HERE / "dictionary/d1_deployment.json").read_text())
d2 = json.loads((HERE / "dictionary/d2.json").read_text())
hits = [match(row["name"], row["normalizedName"], d1, d2) for row in rows]
unseen = sum(hit is None for hit in hits)
if manifest["usableSites"] < 150 or unseen < 300:
    write_new(TEST / "minimum_check.json", {"passed": False, "usableSites": manifest["usableSites"], "unseenRows": unseen})
    raise RuntimeError("minimum clean-test evidence not reached; inference and cloud are forbidden")

groups = defaultdict(list)
for index, row in enumerate(rows):
    groups[row["normalizedName"]].append(index)
rng = random.Random(2026111201)
mb = [rng.choice(groups[name]) for name in sorted(groups)]
write_new(TEST / "mb_selection.json", {"seed": 2026111201, "indices": mb, "normalizedNames": sorted(groups)})
write_new(TEST / "evaluation_opened.json", {
    "schemaVersion": 1,
    "openedAfterFreeze": True,
    "manifestSha256": sha(TEST / "manifest.json"),
    "deploymentD1Sha256": sha(HERE / "dictionary/d1_deployment.json"),
    "d2Sha256": sha(HERE / "dictionary/d2.json"),
    "usableSites": manifest["usableSites"],
    "unseenRows": unseen,
})

# The marker exists before either model or the rules engine is loaded.
subprocess.run(["node", str(HERE / "score_rules.mjs")], check=True)
rule_scores = [json.loads(line) for line in (TEST / "rule_scores.jsonl").read_text().splitlines() if line]
if len(rule_scores) != len(rows) or [item["rowIndex"] for item in rule_scores] != list(range(len(rows))):
    raise RuntimeError("rule-score alignment failed")

def session(path):
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

def probabilities(model, matrix):
    active = session(model)
    result = dict(zip([out.name for out in active.get_outputs()], active.run(None, {"features": matrix})))
    return np.asarray(result["probabilities"])

x = np.asarray([row["features"] for row in rows], dtype=np.float32)
v3 = probabilities(ROOT / "waicy_2026/accuracy_push/model/main.onnx", x)[:, 1]
v1_all = probabilities(ROOT / "extension-standalone/model/cookieguard_model.onnx", x)
v1 = v1_all[:, 3]
v1_decision = np.argmax(v1_all, axis=1) == 3
selected = json.loads((HERE / "development/selection.json").read_text())["selected"]
if selected not in {"N1", "N2", "N3"}:
    raise RuntimeError("unknown selected method")

output = []
for index, (row, hit, p, v1p, v1d, rule) in enumerate(zip(rows, hits, v3, v1, v1_decision, rule_scores)):
    k0 = bool(p >= 0.40)
    if hit is None:
        selected_decision = k0
    elif selected == "N1":
        selected_decision = bool(hit["label"])
    elif selected == "N2":
        reject = (hit["label"] == 1 and p < 0.10) or (hit["label"] == 0 and p > 0.70)
        selected_decision = k0 if reject else bool(hit["label"])
    else:
        selected_decision = bool(hit["label"]) if 0.25 <= p <= 0.55 else k0
    evidence = None if hit is None else {
        "source": hit["source"], "matchType": hit["matchType"], "entry": hit["entry"], "label": hit["label"],
        "trackerVotes": hit.get("trackerVotes"), "notTrackerVotes": hit.get("notTrackerVotes"),
        "recordIds": [item.get("id") for item in hit.get("records", [])],
    }
    output.append({
        "rowIndex": index, "label": row["label"], "normalizedName": row["normalizedName"], "name": row["name"],
        "siteId": row["siteId"], "dictionary": evidence,
        "scores": {"selectedN": float(p), "K0": float(p), "K1": float(rule["normalizedTracking"]), "v1": float(v1p), "everythingTracker": 1.0},
        "decisions": {"selectedN": bool(selected_decision), "K0": k0, "K1": bool(rule["tracker"]), "v1": bool(v1d), "everythingTracker": True},
    })

path = TEST / "predictions.jsonl"
if path.exists():
    raise RuntimeError("predictions already exist")
path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in output))
write_new(TEST / "evaluation_completed.json", {
    "schemaVersion": 1, "selected": selected, "rows": len(rows), "unseenRows": unseen,
    "predictionsSha256": sha(path), "ruleScoresSha256": sha(TEST / "rule_scores.jsonl"),
})
print(json.dumps({"rows": len(rows), "names": len(groups), "unseenRows": unseen, "selected": selected, "M-B": len(mb)}, indent=2))
