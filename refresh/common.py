"""Shared allowlists, deterministic serialization, and value-free data handling."""
from __future__ import annotations
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
os.environ.update(COOKIEGUARD_USAGE_METRICS="0", DO_NOT_TRACK="1", ORT_DISABLE_TELEMETRY="1")
FORBIDDEN = re.compile(r"^(value|cookieValue|rawValue|authorization|password|api[_-]?key|access[_-]?token|refresh[_-]?token)$", re.I)
CREDENTIAL = re.compile(r"(ph[ctx]_[A-Za-z0-9_-]{20,}|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
ROW_FIELDS = [
    "crawl", "rank", "cmp", "declaredCategory", "declaredGroup", "name", "normalizedName",
    "domain", "path", "label", "secure", "httpOnly", "sameSite", "hostOnly", "session",
    "lifetimeSeconds", "valueLength", "valueCharacterSet", "declarationMatch", "features",
    "crawlDate", "trancoListId",
]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def load(path):
    return json.loads(Path(path).read_text())

def structural(node):
    if isinstance(node, dict):
        return all(not FORBIDDEN.fullmatch(k) and structural(v) for k, v in node.items())
    if isinstance(node, list):
        return all(structural(v) for v in node)
    if isinstance(node, str):
        return not CREDENTIAL.search(node)
    return not isinstance(node, float) or math.isfinite(node)

def write_json(path, obj):
    if not structural(obj):
        raise ValueError("structural-privacy-check-failed")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)

def rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)

def normalize_name(text):
    pieces = re.split(r"([_.-])", str(text).strip().lower())
    output = []
    for piece in pieces:
        mixed = len(piece) >= 6 and re.search("[a-z]", piece) and re.search("[0-9]", piece)
        hexy = len(piece) >= 8 and re.fullmatch("[0-9a-f]+", piece) and re.search("[a-f]", piece)
        output.append("#" if mixed or hexy else piece)
    return re.sub(r"\d+", "0", "".join(output))

def month_seed(month):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("invalid-month")
    return int(month.replace("-", ""))

def label(row):
    return int(row["label"] in (1, "tracker"))

def validate_row(row):
    if set(row) != set(ROW_FIELDS) or not structural(row):
        raise ValueError("invalid-row-schema")
    if row["label"] not in {"tracker", "not-tracker"} or row["normalizedName"] != normalize_name(row["name"]):
        raise ValueError("invalid-row-label-or-name")
    if len(row["features"]) != 38 or not all(isinstance(n, (float, int)) and math.isfinite(n) for n in row["features"]):
        raise ValueError("invalid-feature-vector")

def die():
    # Exceptions can carry input; diagnostics must be fixed strings.
    import sys
    print("Refresh stopped; a validation or privacy check failed.", file=sys.stderr)
    return 1
