#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = json.loads((HERE / "dictionary/d1_deployment.json").read_text())
all_items = dict(source["normalized"])
all_items.update(source["ties"]["normalized"])
payload = {
    "schemaVersion": 1,
    "sourceSha256": hashlib.sha256((HERE / "dictionary/d1_deployment.json").read_bytes()).hexdigest(),
    "seenInTraining": sorted(name for name, item in all_items.items() if int(item.get("eraRows", {}).get("2021", 0)) > 0),
    "seenInDevelopment": sorted(name for name, item in all_items.items() if int(item.get("eraRows", {}).get("2026", 0)) > 0),
}
target = HERE / "dictionary/source_membership.json"
if target.exists():
    raise RuntimeError(f"refusing to overwrite {target}")
target.write_text(json.dumps(payload, indent=2) + "\n")
print(json.dumps({"trainingNames": len(payload["seenInTraining"]), "developmentNames": len(payload["seenInDevelopment"])}, indent=2))
