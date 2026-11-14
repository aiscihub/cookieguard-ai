"""Verify shard provenance and privacy receipts before exporting a monthly dataset."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from common import ROOT, ROW_FIELDS, die, load, month_seed, rows, sha, structural, validate_row, write_json
from health import attempt_metrics, COMPARABILITY_NOTICE

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, default=ROOT / "refresh/.work/run")
    p.add_argument("--releases", type=Path, default=ROOT / "data/releases")
    p.add_argument("--state", type=Path, default=ROOT / "refresh/state/crawled_domains.txt")
    a = p.parse_args()
    a.run, a.releases, a.state = a.run.resolve(), a.releases.resolve(), a.state.resolve()
    frame = load(a.run / "frame.json")
    month_seed(frame["month"])
    frame_hash = sha(a.run / "frame.json")
    feature_names = load(ROOT / "refresh/reference/feature_names.json")["featureNames"]
    engine_hash = sha(ROOT / "packages/core/vendor/engine.cjs")
    records, attempts, receipts, missing, seen = [], [], [], [], set()
    for shard in range(1, frame["shards"] + 1):
        folder = a.run / "shards" / ("shard-" + str(shard))
        if not (folder / "receipt.json").exists():
            missing.append(shard)
            continue
        receipt = load(folder / "receipt.json")
        receipts.append(receipt)
        if not structural(receipt) or receipt["frameSha256"] != frame_hash or receipt["shard"] != shard:
            raise ValueError("receipt-provenance")
        if not receipt["privacy"]["passed"]:
            continue
        if receipt["of"] != frame["shards"] or receipt["month"] != frame["month"]:
            raise ValueError("receipt-frame-mismatch")
        if receipt["engineSha256"] != engine_hash or receipt["featureNames"] != feature_names:
            raise ValueError("shard-engine-mismatch")
        if receipt["rowsSha256"] != sha(folder / "cookies.jsonl") or receipt["attemptsSha256"] != sha(folder / "attempts.json"):
            raise ValueError("shard-digest-mismatch")
        expected = {s["siteId"]: s for s in frame["frame"] if s["shard"] == shard}
        shard_attempts = load(folder / "attempts.json")
        if not structural(shard_attempts):
            raise ValueError("attempt-privacy-failure")
        coverage = attempt_metrics(shard_attempts)
        if receipt.get("visitedSites") != coverage["visitedSites"]:
            raise ValueError("visited-count-mismatch")
        if len(shard_attempts) != len(expected) or receipt["attempted"] != len(expected):
            raise ValueError("incomplete-shard")
        for attempt in shard_attempts:
            site = expected.get(attempt["siteId"])
            if not site or any(attempt[k] != site[k] for k in ["domain", "rank", "shard"]) or site["siteId"] in seen:
                raise ValueError("unexpected-or-duplicate-attempt")
            seen.add(site["siteId"])
        shard_rows = list(rows(folder / "cookies.jsonl"))
        usable_ranks = {x["rank"] for x in shard_attempts if x["status"] == "usable"}
        if len(shard_rows) != receipt["rows"]:
            raise ValueError("row-count-mismatch")
        identities = set()
        for row in shard_rows:
            validate_row(row)
            identity = (row["rank"], row["name"], row["domain"], row["path"])
            if identity in identities or row["rank"] not in usable_ranks or row["trancoListId"] != frame["trancoListId"]:
                raise ValueError("row-frame-mismatch")
            identities.add(identity)
        if len({r["rank"] for r in shard_rows}) != len(usable_ranks):
            raise ValueError("usable-count-mismatch")
        records.extend(shard_rows)
        attempts.extend(shard_attempts)
    complete = len(seen) == frame["sites"] and not missing
    private = complete and all(r["privacy"]["passed"] for r in receipts)
    records.sort(key=lambda r: (r["rank"], r["name"], r["domain"], r["path"]))
    dest = a.releases / frame["month"]
    if dest.exists():
        raise ValueError("release-already-exists")
    dest.mkdir(parents=True)
    # Do not export data from incomplete/quarantined runs.
    if not private:
        records = []
    with (dest / "cookies.jsonl").open("w") as stream:
        for row in records:
            stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
    with (dest / "cookies.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[k for k in ROW_FIELDS if k != "features"] + feature_names)
        writer.writeheader()
        for row in records:
            # Escape spreadsheet formula prefixes; JSONL retains exact metadata.
            cells = {k: ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v)
                     for k, v in row.items() if k != "features"}
            writer.writerow({**cells, **dict(zip(feature_names, row["features"]))})
    status = dict(sorted(Counter(x["status"] for x in attempts).items()))
    coverage = attempt_metrics(attempts)
    stats = {
        **coverage,
        "rows": len(records), "sites": len({r["rank"] for r in records}),
        "normalizedNames": len({r["normalizedName"] for r in records}),
        "labels": dict(Counter(r["label"] for r in records)),
        "featureNames": feature_names,
    }
    write_json(dest / "stats.json", stats)
    manifest = {
        **coverage,
        "schemaVersion": 1, "month": frame["month"], "dryRun": frame["dryRun"],
        "createdAt": datetime.now(timezone.utc).isoformat(), "frameSha256": frame_hash,
        "trancoListId": frame["trancoListId"], "trancoSha256": frame["trancoSha256"],
        "planned": frame["sites"], "attempted": len(attempts), "statusCounts": status,
        "usableSites": stats["sites"], "rows": len(records), "complete": complete,
        "privacyPassed": private, "structuralPassed": all(structural(r) for r in records),
        "missingShards": missing, "shardReceipts": receipts,
        "files": {name: sha(dest / name) for name in ["cookies.jsonl", "cookies.csv", "stats.json"]},
        "license": "CC-BY-4.0",
    }
    write_json(dest / "manifest.json", manifest)
    (dest / "README.md").write_text(
        "# CookieGuard monthly observations: " + frame["month"] + "\n\n"
        + ("LOCAL DRY RUN. Not a published dataset or approved model.\n\n" if frame["dryRun"] else "")
        + str(stats["rows"]) + " labeled cookies from " + str(stats["sites"]) + " usable sites.\n\n"
        "Labels are website declarations, not independently verified tracking behavior. Only Cookiebot "
        "and OneTrust sites with usable declarations are represented. JSONL preserves metadata; CSV "
        "prefixes spreadsheet formulas with an apostrophe. No cookie contents are exported. "
        "The 38 numeric features include measurements of contents computed in memory.\n\n"
        + COMPARABILITY_NOTICE + "\n\n"
        "License: CC BY 4.0. Attribution: Avelyn Jing, CookieGuard AI cookie database, "
        + frame["month"] + ". Ranking: Tranco " + frame["trancoListId"] + ".\n"
    )
    index_path = a.releases / "index.json"
    index = load(index_path) if index_path.exists() else {"schemaVersion": 1, "releases": []}
    entry = {"id": frame["month"], "month": frame["month"], "kind": "monthly",
             "title": "Monthly observations — " + frame["month"], "dryRun": frame["dryRun"],
             "rows": stats["rows"], "sites": stats["sites"], "createdAt": manifest["createdAt"],
             "path": "data/releases/" + frame["month"] + "/"}
    index["releases"] = [entry] + [e for e in index["releases"] if e["id"] != entry["id"]]
    write_json(index_path, index)
    # Reserve the entire frame, including failures: an attempted site is never revisited.
    excluded = set(a.state.read_text().splitlines())
    excluded.update((a.run / "exclusions.txt").read_text().splitlines())
    excluded.update(s["domain"] for s in frame["frame"])
    a.state.write_text("\n".join(sorted(excluded)) + "\n")
    write_json(a.run / "merge.json", {"release": str(dest.relative_to(ROOT)), "privacyPassed": private, "complete": complete})
    print(json.dumps({"stage": "merge", "rows": len(records), "attempted": len(attempts), "privacyPassed": private}))

if __name__ == "__main__":
    try: main()
    except Exception: sys.exit(die())
