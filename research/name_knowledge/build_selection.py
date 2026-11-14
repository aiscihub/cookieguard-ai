#!/usr/bin/env python3
import csv
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "development"
DICT = HERE / "dictionary"
TEST = HERE / "test"
OCD = HERE / "source/open-cookie-database"
FRESH = ROOT / "waicy_2026/accuracy_push2/finalization_retry/fresh_test"
RAW = ROOT / "waicy_2026/cookieblock_test/raw/06_Training_Data/tranco_05May_20210510_201615.json"
SPLIT = json.loads((ROOT / "waicy_2026/retrain_test/split.json").read_text())
VSPLIT = json.loads((ROOT / "waicy_2026/accuracy_push/validation_split.json").read_text())["assignments"]
COMBO = json.loads((ROOT / "waicy_2026/combination_check/development/splits.json").read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    if path.exists():
        if json.loads(path.read_text()) == value:
            return
        raise RuntimeError(f"refusing to overwrite non-identical {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def normalize_name(value):
    import re
    pieces = re.split(r"([_.-])", str(value).strip().lower())
    out = []
    for piece in pieces:
        if piece in "_.-" and len(piece) == 1:
            out.append(piece)
            continue
        mixed = len(piece) >= 6 and re.search("[a-z]", piece) and re.search("[0-9]", piece)
        hexy = len(piece) >= 8 and re.fullmatch("[0-9a-f]+", piece) and re.search("[a-f]", piece)
        out.append("#" if mixed or hexy else piece)
    return re.sub(r"\d+", "0", "".join(out))


def rows(folder):
    output = []
    for path in sorted(folder.glob("rows-*.jsonl")):
        output.extend(json.loads(line) for line in path.read_text().splitlines() if line)
    return output


def vote_table(items, key):
    votes = defaultdict(Counter)
    eras = defaultdict(Counter)
    for item in items:
        votes[item[key]][str(item["label"])] += 1
        eras[item[key]][item["era"]] += 1
    entries, ties = {}, {}
    for name in sorted(votes):
        no = votes[name]["0"]
        yes = votes[name]["1"]
        evidence = {"trackerVotes": yes, "notTrackerVotes": no, "eraRows": dict(sorted(eras[name].items()))}
        if yes == no:
            ties[name] = evidence
        else:
            entries[name] = {**evidence, "label": int(yes > no)}
    return entries, ties


def make_d1(items):
    raw, raw_ties = vote_table(items, "rawName")
    normalized, normalized_ties = vote_table(items, "normalizedName")
    return {"raw": raw, "normalized": normalized, "ties": {"raw": raw_ties, "normalized": normalized_ties}}


def category_label(value):
    value = str(value or "").strip().lower()
    if value in {"marketing", "analytics"}:
        return 1
    if value in {"functional", "security", "personalization"}:
        return 0
    return None


def build_d2():
    grouped = {"exact": defaultdict(list), "wildcard": defaultdict(list)}
    excluded_unknown = []
    with (OCD / "open-cookie-database.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            label = category_label(row.get("Category"))
            name = str(row.get("Cookie / Data Key name") or "")
            evidence = {"id": row.get("ID"), "platform": row.get("Platform"), "category": row.get("Category"), "name": name}
            if label is None or not name:
                excluded_unknown.append(evidence)
                continue
            kind = "wildcard" if str(row.get("Wildcard match", "")).strip() == "1" else "exact"
            grouped[kind][name].append({**evidence, "label": label})
    output, conflicts = {"exact": {}, "wildcard": {}}, {"exact": {}, "wildcard": {}}
    for kind in ["exact", "wildcard"]:
        for name in sorted(grouped[kind]):
            evidence = sorted(grouped[kind][name], key=lambda x: str(x["id"]))
            labels = {x["label"] for x in evidence}
            if len(labels) != 1:
                conflicts[kind][name] = evidence
            else:
                output[kind][name] = {"label": evidence[0]["label"], "literalPrefix": name, "records": evidence}
    return {"schemaVersion": 1, **output, "conflicts": conflicts, "excludedUnknown": excluded_unknown}


def match(name, normalized, d1, d2):
    if name in d1["raw"]:
        return {"source": "D1", "matchType": "raw", "entry": name, **d1["raw"][name]}
    if normalized in d1["normalized"]:
        return {"source": "D1", "matchType": "normalized", "entry": normalized, **d1["normalized"][normalized]}
    if name in d2["exact"]:
        return {"source": "D2", "matchType": "exact", "entry": name, **d2["exact"][name]}
    candidates = [(len(prefix), prefix, item) for prefix, item in d2["wildcard"].items() if name.startswith(prefix)]
    if not candidates:
        return None
    longest = max(x[0] for x in candidates)
    best = [x for x in candidates if x[0] == longest]
    if len({x[2]["label"] for x in best}) != 1:
        return None
    _, prefix, item = sorted(best, key=lambda x: x[1])[0]
    return {"source": "D2", "matchType": "wildcard", "entry": prefix, **item}


def ba_fraction(y, pred):
    tp = int(sum(bool(t == 1 and p) for t, p in zip(y, pred))); fn = int(sum(bool(t == 1 and not p) for t, p in zip(y, pred)))
    tn = int(sum(bool(t == 0 and not p) for t, p in zip(y, pred))); fp = int(sum(bool(t == 0 and p) for t, p in zip(y, pred)))
    return (Fraction(tp, tp + fn) + Fraction(tn, tn + fp)) / 2


def confusion(y, pred):
    return {"tn": int(sum(bool(t == 0 and not p) for t, p in zip(y, pred))), "fp": int(sum(bool(t == 0 and p) for t, p in zip(y, pred))),
            "fn": int(sum(bool(t == 1 and not p) for t, p in zip(y, pred))), "tp": int(sum(bool(t == 1 and p) for t, p in zip(y, pred)))}


OUT.mkdir(parents=True, exist_ok=True); DICT.mkdir(parents=True, exist_ok=True); TEST.mkdir(parents=True, exist_ok=True)
raw_records = list(json.loads(RAW.read_text()).values())
items21 = []
for index, record in enumerate(raw_records):
    raw_name = str(record.get("name") or "")
    normalized = normalize_name(raw_name)
    if SPLIT.get(normalized) != "train":
        continue
    if VSPLIT.get(normalized) not in {"candidate-training", "validation"}:
        raise RuntimeError(f"ambiguous 2021 assignment for {normalized}")
    items21.append({"identity": f"2021:{index}", "rawName": raw_name, "normalizedName": normalized,
                    "label": int(record["label"] in [2, 3]), "era": "2021"})

fresh = rows(FRESH)
site_side = COMBO["siteAssignments2026"]
items26 = [{"identity": f"2026:{i}", "rawName": row["name"], "normalizedName": row["normalizedName"],
            "label": int(row["label"]), "era": "2026", "siteId": row["siteId"], "rowIndex": i} for i, row in enumerate(fresh)]
selection_items = items21 + [x for x in items26 if site_side[x["siteId"]] == "fit"]
deployment_items = items21 + items26
selection_d1 = make_d1(selection_items); deployment_d1 = make_d1(deployment_items); d2 = build_d2()
write_json(DICT / "d1_selection.json", {"schemaVersion": 1, "sourceRows": len(selection_items), **selection_d1})
write_json(DICT / "d1_deployment.json", {"schemaVersion": 1, "sourceRows": len(deployment_items), **deployment_d1})
write_json(DICT / "d2.json", d2)

select_indices = COMBO["selectRows"]["2026"]
select_rows = [fresh[i] for i in select_indices]
session = ort.InferenceSession(str(ROOT / "waicy_2026/accuracy_push/model/main.onnx"), providers=["CPUExecutionProvider"])
p = np.asarray(dict(zip([o.name for o in session.get_outputs()], session.run(None, {"features": np.asarray([r["features"] for r in select_rows], np.float32)})))["probabilities"])[:, 1]
y = [int(r["label"]) for r in select_rows]
hits = [match(r["name"], r["normalizedName"], selection_d1, d2) for r in select_rows]
k0 = [x >= .4 for x in p]
n1 = [bool(h["label"]) if h else base for h, base in zip(hits, k0)]
n2 = []
for h, base, prob in zip(hits, k0, p):
    if not h or (h["label"] == 1 and prob < .1) or (h["label"] == 0 and prob > .7): n2.append(base)
    else: n2.append(bool(h["label"]))
n3 = [bool(h["label"]) if h and .25 <= prob <= .55 else base for h, prob, base in zip(hits, p, k0)]
decisions = {"N1": n1, "N2": n2, "N3": n3}
scores = {name: ba_fraction(y, pred) for name, pred in decisions.items()}
best = max(scores.values()); eligible = [name for name in ["N1", "N2", "N3"] if best - scores[name] <= Fraction(5, 1000)]
selected = eligible[0]
hit_counts = Counter("miss" if h is None else f'{h["source"]}_{h["matchType"]}' for h in hits)
selection = {"schemaVersion": 1, "selected": selected, "tieSet": eligible, "rule": "within 0.005 prefer N1, N2, N3",
             "rows": len(select_rows), "tracker": sum(y), "notTracker": len(y)-sum(y), "hitCounts": dict(sorted(hit_counts.items())),
             "methods": {name: {"balancedAccuracy": float(scores[name]), "confusion": confusion(y, pred)} for name, pred in decisions.items()},
             "K0": {"balancedAccuracy": float(ba_fraction(y, k0)), "confusion": confusion(y, k0)},
             "rowIndices": select_indices, "probabilities": [float(x) for x in p],
             "decisions": {name: [bool(x) for x in pred] for name, pred in decisions.items()}}
write_json(OUT / "selection.json", selection)

domains = [line.split(",", 1) for line in (ROOT / "waicy_2026/accuracy_push2/inputs/tranco-947N2-top20000.csv").read_text().splitlines()]
combo_manifest = json.loads((ROOT / "waicy_2026/combination_check/test/manifest.json").read_text())
if combo_manifest["lastRank"] != 12560:
    raise RuntimeError("combination crawl frontier is not 12560")
frame = []
for rank in range(12561, 20001):
    source_rank, domain = domains[rank - 1]
    if int(source_rank) != rank: raise RuntimeError("Tranco rank mismatch")
    site_id = hashlib.sha256(f"947N2:{rank}:{domain}".encode()).hexdigest()
    frame.append({"rank": rank, "siteId": site_id})
write_json(TEST / "frame.json", {"schemaVersion": 1, "listId": "947N2", "firstRank": 12561, "lastRank": 20000,
                                  "priorFrontier": 12560, "frame": frame})

source = {"schemaVersion": 1, "repository": "https://github.com/jkwakman/Open-Cookie-Database.git",
          "commit": "7786335566460016f07a50705a92fc781c976f6f", "license": "Apache-2.0",
          "licenseSha256": sha(OCD / "LICENSE"), "csvSha256": sha(OCD / "open-cookie-database.csv"),
          "jsonSha256": sha(OCD / "open-cookie-database.json"), "edpbJsonSha256": sha(OCD / "open-cookie-database-edpb.json")}
write_json(OUT / "source_manifest.json", source)
manifest = {"schemaVersion": 1, "inputs": {"head": "1f0ede14ee9d5e3c990a575f8eeae986a588d346",
            "v3Sha256": sha(ROOT / "waicy_2026/accuracy_push/model/main.onnx"),
            "v1Sha256": sha(ROOT / "extension-standalone/model/cookieguard_model.onnx"),
            "rulesSha256": sha(ROOT / "waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/vendor/engine.cjs")},
            "counts": {"d1SelectionRows": len(selection_items), "d1DeploymentRows": len(deployment_items), "rows2021": len(items21), "rows2026": len(items26)},
            "artifacts": {str(path.relative_to(HERE)): sha(path) for path in [DICT/"d1_selection.json", DICT/"d1_deployment.json", DICT/"d2.json", OUT/"selection.json", OUT/"source_manifest.json", TEST/"frame.json"]}}
write_json(OUT / "manifest.json", manifest)
print(json.dumps({"selected": selected, "scores": {k: float(v) for k, v in scores.items()}, "eligible": eligible,
                  "selectionHits": dict(hit_counts), "counts": manifest["counts"], "ocd": source}, indent=2))
