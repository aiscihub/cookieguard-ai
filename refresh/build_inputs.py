"""Build local, inspectable assets from frozen inputs. Never uploads anything."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil
import sys
from common import CREDENTIAL, ROOT, die, load, normalize_name, rows, sha, structural, write_json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "refresh/.work/inputs")
    a = parser.parse_args()
    frozen, out = a.frozen_root.resolve(), a.out.resolve()
    if frozen == ROOT or frozen in out.parents:
        raise ValueError("outputs-must-be-in-new-worktree")
    out.mkdir(parents=True, exist_ok=True)
    reference = ROOT / "refresh/reference"
    reference.mkdir(parents=True, exist_ok=True)
    feature_dir = frozen / "waicy_2026/accuracy_push/features"
    write_json(reference / "feature_names.json", load(feature_dir / "feature_names.json"))
    # Recover exact case using recordIndex. No other raw fields leave memory.
    original_path = frozen / "waicy_2026/cookieblock_test/raw/06_Training_Data/tranco_05May_20210510_201615.json"
    originals = json.loads(original_path.read_text())
    names = [str(row.get("name") or "") for row in originals.values()]
    del originals
    target = out / "training-pool-2021.jsonl.gz"
    count, excluded = 0, 0
    feature_files = sorted(feature_dir.glob("chunk-*.jsonl"))
    with target.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as stream:
        for path in feature_files:
            for row in rows(path):
                name = names[row["recordIndex"]]
                if name.lower() != row["lowercaseName"]:
                    raise ValueError("source-name-alignment")
                if CREDENTIAL.search(name):
                    excluded += 1
                    continue
                if row["label"] not in {0, 1, 2, 3}:
                    raise ValueError("unknown-cookieblock-category")
                record = {"name": name, "normalizedName": normalize_name(name), "label": int(row["label"] in {2, 3}),
                          "features": row["features"], "siteId": row["websiteId"]}
                if record["label"] not in {0, 1} or len(record["features"]) != 38 or not structural(record):
                    raise ValueError("invalid-training-record")
                stream.write((json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n").encode())
                count += 1
    attribution = {
        "schemaVersion": 1, "asset": target.name, "sha256": sha(target), "rows": count,
        "excludedCredentialLikeNames": excluded, "license": "CC-BY-4.0",
        "attribution": "Bollinger, Kubicek, Cotrini, Basin. Automating Cookie Consent and GDPR Violation Detection. USENIX Security 2022.",
        "source": "https://zenodo.org/records/5838646",
        "originalNamesSourceSha256": sha(original_path),
        "featureFiles": [{"file": p.name, "sha256": sha(p)} for p in feature_files],
        "fields": ["name", "normalizedName", "label", "features", "siteId"],
        "transformation": "38 precomputed numeric features; binary labels; exact names joined by validated recordIndex; cookie contents omitted",
    }
    write_json(out / "training-pool-2021.attribution.json", attribution)
    # CI downloads only this public asset after the owner explicitly approves upload.
    config = {
        "schemaVersion": 1, "assetName": target.name, "sha256": sha(target),
        "url": "https://github.com/aiscihub/cookieguard-ai/releases/download/refresh-inputs-2021/" + target.name,
        "uploadApproved": False, "rows": count,
    }
    write_json(ROOT / "refresh/training-source.json", config)
    write_json(reference / "training-pool-2021.attribution.json", attribution)
    tranco = frozen / "waicy_2026/accuracy_push2/inputs/tranco-947N2-top20000.csv"
    domains = [line.split(",", 1)[1].strip().lower() for line in tranco.read_text().splitlines() if line]
    if len(set(domains)) != 20000:
        raise ValueError("initial-exclusion-count")
    state = ROOT / "refresh/state/crawled_domains.txt"
    state.parent.mkdir(parents=True, exist_ok=True)
    if not state.exists():
        state.write_text("\n".join(sorted(domains)) + "\n")
    write_json(reference / "seed.json", {"trancoListId": "947N2", "sourceSha256": sha(tranco), "domains": 20000})
    study = frozen / "waicy_2026/accuracy_push/model/main.onnx"
    shutil.copyfile(study, reference / "study-c2.onnx")
    write_json(reference / "study-c2.meta.json", load(frozen / "waicy_2026/accuracy_push/model/main_meta.json"))
    d1 = load(frozen / "waicy_2026/name_knowledge/dictionary/d1_deployment.json")
    d2 = load(frozen / "waicy_2026/name_knowledge/dictionary/d2.json")
    study_lookup = {
        "raw": [{"name": name, **entry} for name, entry in d1["raw"].items() if not CREDENTIAL.search(name)],
        "normalized": [{"name": name, **entry} for name, entry in d1["normalized"].items()],
        "ocdExact": [{"name": name, "label": entry["label"]} for name, entry in d2["exact"].items() if not CREDENTIAL.search(name)],
        "ocdPrefix": [{"name": name, "label": entry["label"]} for name, entry in d2["wildcard"].items() if not CREDENTIAL.search(name)],
    }
    write_json(reference / "study-lookup.json", study_lookup)
    membership = load(frozen / "waicy_2026/name_knowledge/dictionary/source_membership.json")
    write_json(reference / "study-membership.json", sorted(set(membership["seenInTraining"] + membership["seenInDevelopment"])))
    ocd = frozen / "waicy_2026/name_knowledge/source/open-cookie-database"
    manifest = load(frozen / "waicy_2026/name_knowledge/development/source_manifest.json")
    if sha(ocd / "open-cookie-database.csv") != manifest["csvSha256"]:
        raise ValueError("ocd-source-changed")
    shutil.copyfile(ocd / "open-cookie-database.csv", reference / "ocd.csv")
    shutil.copyfile(ocd / "LICENSE", reference / "OCD-LICENSE")
    write_json(reference / "ocd-source.json", manifest)
    # Conservative membership: includes the supplied production source's validation names.
    production = load(ROOT / "data/training_cookies.json")
    write_json(reference / "v1-membership.json", sorted({normalize_name(r["name"]) for r in production}))
    write_json(reference / "provenance.json", {
        "studyOnnxSha256": sha(reference / "study-c2.onnx"),
        "productionOnnxSha256": sha(ROOT / "extension-standalone/model/cookieguard_model.onnx"),
        "productionTrainingSourceSha256": sha(ROOT / "data/training_cookies.json"),
        "productionMembershipBasis": "conservative full supplied training-source name union, including validation; exact exported-model fit membership was not recorded",
        "rulesMembershipBasis": "handwritten classifier; no fitted training pool",
        "sourceScripts": ["waicy_2026/name_knowledge/crawl.mjs", "waicy_2026/name_knowledge/build_selection.py"],
    })
    print(json.dumps({"stage": "inputs", "rows": count, "sha256": sha(target), "uploaded": False}))

if __name__ == "__main__":
    try: main()
    except Exception: sys.exit(die())
