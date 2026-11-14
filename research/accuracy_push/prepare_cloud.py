#!/usr/bin/env python3
import json
import random
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CLOUD = HERE / "cloud"
CLOUD.mkdir(exist_ok=True)
(CLOUD / "prompts").mkdir(exist_ok=True)
SPLIT = json.loads((ROOT / "waicy_2026/retrain_test/split.json").read_text())


def load_rows(folder):
    rows = []
    for path in sorted(folder.glob("chunk-*.jsonl")):
        with path.open() as handle: rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


rows = load_rows(HERE / "features")
old = {row["recordIndex"]: row for row in load_rows(ROOT / "waicy_2026/retrain_test/features")}
test = [row for row in rows if SPLIT[row["normalizedName"]] == "test"]
groups = defaultdict(list)
for row in test: groups[row["normalizedName"]].append(row)
chooser = random.Random(2026111303)
tb = {name: chooser.choice(groups[name]) for name in sorted(groups)}
selected_names = random.Random(2026111010).sample(sorted(tb), 300)
selected = [tb[name] for name in selected_names]
ids = [f"C{index:03d}" for index in range(1, 301)]
random.Random(2026111011).shuffle(ids)
models = {"main": joblib.load(HERE / "model/main.joblib"), "m1": joblib.load(ROOT / "waicy_2026/retrain_test/model/m1.joblib")}
x = np.asarray([row["features"] for row in selected], np.float32)
x_old = np.asarray([old[row["recordIndex"]]["features"] for row in selected], np.float32)
main = models["main"].predict_proba(x)[:, 1]
m1p = models["m1"].predict_proba(x_old); m1 = m1p[:, 2] + m1p[:, 3]
wanted = {row["recordIndex"] for row in selected}; shipped = {}
for path in sorted((ROOT / "waicy_2026/cookieblock_test/predictions").glob("chunk-*.jsonl")):
    with path.open() as handle:
        for line in handle:
            item = json.loads(line)
            if item["recordIndex"] in wanted: shipped[item["recordIndex"]] = item
key = {"schemaVersion": 1, "sampleSeed": 2026111010, "idSeed": 2026111011, "items": {}}
public = []
for index, (opaque, row) in enumerate(zip(ids, selected)):
    saved = shipped[row["recordIndex"]]
    item = {"id": opaque, "name": row["lowercaseName"], "domain": row["domain"], "thirdParty": row["thirdParty"],
            "secure": row["secure"], "httpOnly": row["httpOnly"], "sameSite": row["sameSite"],
            "lifetimeDays": row["lifetimeDays"], "valueShape": row["valueShape"]}
    public.append(item)
    key["items"][opaque] = {"recordIndex": row["recordIndex"], "normalizedName": row["normalizedName"],
        "truth": row["label"] in (2, 3), "local": {"main": bool(main[index] >= .40), "mainProbability": float(main[index]),
        "m1": bool(m1[index] >= .5), "m1Probability": float(m1[index]),
        "shipped": max(saved["model"], key=saved["model"].get) == "tracking", "shippedProbability": saved["model"]["tracking"],
        "rules": saved["rules"]["label"] == "tracking"}}
(CLOUD / "sample_public.json").write_text(json.dumps(public, indent=2) + "\n")
(CLOUD / "sample_key.json").write_text(json.dumps(key, indent=2) + "\n")
intro = """You are classifying browser cookies. For each item, decide whether it is a tracking cookie: analytics or advertising. Values and website names are withheld. The domain shown is the cookie's domain. Reply with exactly one JSON object mapping every ID to a Boolean `tracking`, with no prose, markdown, missing IDs, or extra IDs.\n\n"""
for batch in range(6):
    items = public[batch * 50:(batch + 1) * 50]
    lines = [intro]
    for item in items:
        lifetime = "session" if item["lifetimeDays"] is None else f"{item['lifetimeDays']:.6g} days"
        lines.append(f"{item['id']} name={json.dumps(item['name'])}; domain={json.dumps(item['domain'])}; third-party={'yes' if item['thirdParty'] else 'no'}; Secure={'yes' if item['secure'] else 'no'}; HttpOnly={'yes' if item['httpOnly'] else 'no'}; SameSite={item['sameSite']}; lifetime={lifetime}; value length={item['valueShape']['length']}; character set={item['valueShape']['characterSet']}\n")
    (CLOUD / "prompts" / f"batch-{batch + 1}.txt").write_text("".join(lines))
print(json.dumps({"items": len(public), "batches": 6, "itemsPerBatch": 50}))
