#!/usr/bin/env python3
import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FRESH = HERE / "fresh_test"
OUT = HERE / "prepared"
SOURCE_FEATURES = ROOT / "waicy_2026/accuracy_push/features"
RAW = ROOT / "waicy_2026/cookieblock_test/raw/06_Training_Data/tranco_05May_20210510_201615.json"
ASSIGNMENTS = json.loads((ROOT / "waicy_2026/accuracy_push/validation_split.json").read_text())["assignments"]
CATEGORIES = ["Functional", "Marketing", "Analytics", "Security", "Necessary", "Personalization"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def load_jsonl(folder, pattern):
    for path in sorted(folder.glob(pattern)):
        with path.open() as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def verify_fresh():
    manifest = json.loads((FRESH / "manifest.json").read_text())
    for item in manifest["rowFiles"]:
        if sha(FRESH / item["file"]) != item["sha256"]:
            raise RuntimeError(f"fresh row hash mismatch: {item['file']}")
    if manifest["normalizedNames"] < 1:
        raise RuntimeError("fresh test is empty")
    return manifest


def dictionary():
    exact = defaultdict(set)
    wildcard = set()
    rows = 0
    with (HERE / "inputs/open-cookie-database.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            name = row["Cookie / Data Key name"].strip()
            category = row["Category"].strip()
            if name and category in CATEGORIES:
                exact[name].add(category)
            if name and row["Wildcard match"].strip().lower() in {"1", "true", "yes"}:
                wildcard.add(name)
    resolved = {name: next(iter(values)) for name, values in exact.items() if len(values) == 1}
    conflicts = {name: sorted(values) for name, values in exact.items() if len(values) > 1}
    return resolved, sorted(wildcard), {
        "sourceSha256": sha(HERE / "inputs/open-cookie-database.csv"), "rows": rows,
        "exactUniqueNames": len(exact), "resolvedExactNames": len(resolved),
        "conflictingExactNames": len(conflicts), "wildcardPrefixes": len(wildcard),
        "categoryCounts": dict(Counter(resolved.values())), "conflicts": conflicts,
    }


def dictionary_vector(name, exact, wildcards):
    values = [0.0] * 7
    category = exact.get(name)
    if category in CATEGORIES:
        values[CATEGORIES.index(category)] = 1.0
    values[6] = float(any(name.startswith(prefix) for prefix in wildcards))
    return values


def embedding_text(name):
    text = re.sub(r"[_.-]+", " ", str(name))
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return re.sub(r"\s+", " ", text).strip()


def make_embeddings(names):
    tokenizer = Tokenizer.from_file(str(HERE / "inputs/minilm/tokenizer.json"))
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding()
    runtime = ort.InferenceSession(str(HERE / "inputs/minilm/model.onnx"), providers=["CPUExecutionProvider"])
    inputs = {item.name for item in runtime.get_inputs()}
    output = {}
    ordered = sorted(names)
    for start in range(0, len(ordered), 128):
        batch_names = ordered[start:start + 128]
        encodings = tokenizer.encode_batch([embedding_text(name) for name in batch_names])
        ids = np.asarray([item.ids for item in encodings], dtype=np.int64)
        masks = np.asarray([item.attention_mask for item in encodings], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": masks}
        if "token_type_ids" in inputs:
            feed["token_type_ids"] = np.asarray([item.type_ids for item in encodings], dtype=np.int64)
        hidden = runtime.run(["last_hidden_state"], feed)[0]
        pooled = (hidden * masks[:, :, None]).sum(axis=1) / masks.sum(axis=1, keepdims=True)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise RuntimeError("zero embedding norm")
        pooled = (pooled / norms).astype(np.float32)
        for name, vector in zip(batch_names, pooled):
            output[name] = vector
    return output


def atomic_npz(path, names, vectors):
    temporary = Path(str(path) + ".tmp.npz")
    np.savez(temporary, names=np.asarray(names), embeddings=np.stack([vectors[name] for name in names]))
    temporary.replace(path)


def main():
    manifest = verify_fresh()
    OUT.mkdir(parents=True, exist_ok=True)
    training_rows = list(load_jsonl(SOURCE_FEATURES, "chunk-*.jsonl"))
    training_rows = [row for row in training_rows if row["normalizedName"] in ASSIGNMENTS]
    fresh_rows = list(load_jsonl(FRESH, "rows-*.jsonl"))
    raw_names = [row["name"] for row in json.loads(RAW.read_text()).values()]
    exact, wildcards, dictionary_manifest = dictionary()

    sides = {"candidate-training": set(), "validation": set(), "fresh": set()}
    for row in training_rows:
        sides[ASSIGNMENTS[row["normalizedName"]]].add(raw_names[row["recordIndex"]])
    sides["fresh"] = {row["name"] for row in fresh_rows}
    dictionary_manifest["coverage"] = {}
    for side, names in sides.items():
        dictionary_manifest["coverage"][side] = {
            "names": len(names), "exact": sum(name in exact for name in names),
            "wildcard": sum(any(name.startswith(prefix) for prefix in wildcards) for name in names),
        }
    atomic_json(OUT / "dictionary_manifest.json", dictionary_manifest)

    embedding_names = set(ASSIGNMENTS) | {row["normalizedName"] for row in fresh_rows}
    vectors = make_embeddings(embedding_names)
    chunk_files = []
    ordered = sorted(vectors)
    for index, start in enumerate(range(0, len(ordered), 2000), 1):
        names = ordered[start:start + 2000]
        path = OUT / f"embeddings-{index}.npz"
        atomic_npz(path, names, vectors)
        chunk_files.append({"file": path.name, "names": len(names), "sha256": sha(path)})

    check_names = random.Random(2026111401).sample(ordered, min(100, len(ordered)))
    repeated = make_embeddings(check_names)
    maximum = max(float(np.max(np.abs(vectors[name] - repeated[name]))) for name in check_names)
    if maximum > 1e-6:
        raise RuntimeError(f"embedding recovery check failed: {maximum}")
    atomic_json(OUT / "embedding_manifest.json", {
        "schemaVersion": 1, "modelSha256": sha(HERE / "inputs/minilm/model.onnx"),
        "tokenizerSha256": sha(HERE / "inputs/minilm/tokenizer.json"), "dimensions": 384,
        "normalizedNames": len(ordered), "chunks": chunk_files,
        "recomputeSeed": 2026111401, "recomputedNames": len(check_names), "maximumAbsoluteDifference": maximum,
        "freshManifestSha256": sha(FRESH / "manifest.json"),
    })
    atomic_json(OUT / "feature_manifest.json", {
        "schemaVersion": 1, "baseWidth": 38, "dictionaryWidth": 7, "embeddingWidth": 384,
        "variantWidths": {"Base": 38, "A": 45, "B": 422, "A+B": 429},
        "trainingRows": len(training_rows), "freshRows": len(fresh_rows),
        "candidateTrainingNames": sum(value == "candidate-training" for value in ASSIGNMENTS.values()),
        "validationNames": sum(value == "validation" for value in ASSIGNMENTS.values()),
        "freshNormalizedNames": manifest["normalizedNames"],
    })
    print(json.dumps({"dictionary": dictionary_manifest["coverage"], "embeddingNames": len(ordered), "recomputeMaximum": maximum}, indent=2))


if __name__ == "__main__":
    main()
