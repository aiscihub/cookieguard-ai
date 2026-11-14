"""Audit release outputs, not source code or installed dependencies. Never print matches."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from pathlib import Path
import re
import subprocess
from common import CREDENTIAL, FORBIDDEN, ROOT, load, sha, structural, write_json

FIELDS = r'"(value|cookieValue|rawValue|authorization|password|api[_-]?key|access[_-]?token|refresh[_-]?token)"\s*:'
TOKENS = CREDENTIAL.pattern + r'|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}'

def check_file(path):
    # Every file is checked, including binary ONNX and decompressed training rows.
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        data = stream.read()
    text = data.decode("utf8", errors="replace")
    if re.search(TOKENS, text) or re.search(FIELDS, text, re.I):
        return False
    suffix = path.suffixes[-2] if path.suffix == ".gz" else path.suffix
    if suffix == ".json":
        return structural(json.loads(text))
    if suffix == ".jsonl":
        return all(structural(json.loads(line)) for line in text.splitlines() if line.strip())
    if suffix == ".csv":
        header = next(csv.reader(text.splitlines()), [])
        return not any(FORBIDDEN.fullmatch(key) for key in header)
    return True

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, default=ROOT / "refresh/.work/run")
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--pool", type=Path, default=ROOT / "refresh/.work/inputs/training-pool-2021.jsonl.gz")
    a = p.parse_args()
    run, release, pool = a.run.resolve(), a.release.resolve(), a.pool.resolve()
    ignored = {folder / name for folder in (run, release) for name in ("privacy-audit.json", "grep-proof.txt")}
    files = (set(run.rglob("*")) | set(release.rglob("*")) | set((ROOT / "refresh/reference").rglob("*")) |
             {pool, pool.with_name("training-pool-2021.attribution.json"), ROOT / "refresh/training-source.json",
              ROOT / "refresh/state/crawled_domains.txt", release.parent / "index.json", ROOT / "data/releases/index.json"})
    files = sorted(f for f in files if f.is_file() and f not in ignored)
    checks = [{"path": str(f.relative_to(ROOT)), "sha256": sha(f), "passed": check_file(f)} for f in files]
    # rg exit 1 means zero matches. Use --files-with-matches so a failure cannot print a secret.
    normal = [str(f) for f in files if f.suffix != ".gz"]
    proof, grep_results = ["Output privacy grep (actual local commands; matches are never printed)", ""], []
    for title, pattern in [("Forbidden contents/credential fields", FIELDS), ("Credential and JWT signatures", TOKENS)]:
        command = ["rg", "--text", "--ignore-case", "--files-with-matches", "--", pattern, *normal]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        matches = len(result.stdout.splitlines())
        ok = result.returncode == 1 and matches == 0
        grep_results.append({"check": title, "exitCode": result.returncode, "matchingFiles": matches, "passed": ok})
        proof += [title, "rg --text --ignore-case --files-with-matches -- " + repr(pattern) + " <inventoried output files>",
                  "exit=" + str(result.returncode) + "; matching files=" + str(matches), ""]
        with gzip.open(pool, "rb") as source:
            compressed = subprocess.run(["rg", "--text", "--ignore-case", "--files-with-matches", "--", pattern],
                                        input=source.read(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        n = len(compressed.stdout.splitlines())
        grep_results.append({"check": title + " in decompressed training asset", "exitCode": compressed.returncode,
                             "matchingFiles": n, "passed": compressed.returncode == 1 and n == 0})
        proof += ["gzip -cd training-pool-2021.jsonl.gz | rg --text --ignore-case --files-with-matches -- " + repr(pattern),
                  "exit=" + str(compressed.returncode) + "; matching streams=" + str(n), ""]
    receipts = [load(f) for f in (run / "shards").glob("shard-*/receipt.json")]
    frame = load(run / "frame.json")
    receipt_ok = len(receipts) == frame["shards"] and all(r["privacy"]["passed"] for r in receipts)
    passed = all(c["passed"] for c in checks + grep_results) and receipt_ok
    result = {"passed": passed, "scope": "all run/release deliverables, reference assets, exclusion state, release indexes, decompressed training asset and attribution",
              "files": checks, "grep": grep_results, "shardReceiptsPassed": receipt_ok,
              "limitations": "Signature grep cannot prove absence of arbitrary unknown strings. Live shard cross-scans and fixed output schemas provide the cookie-content checks."}
    write_json(run / "privacy-audit.json", result)
    write_json(release / "privacy-audit.json", result)
    proof_text = "\n".join(proof) + "Overall passed=" + str(passed) + "\n"
    (run / "grep-proof.txt").write_text(proof_text)
    (release / "grep-proof.txt").write_text(proof_text)
    print(json.dumps({"stage": "privacy-audit", "files": len(files), "passed": passed}))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
