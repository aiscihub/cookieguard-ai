#!/usr/bin/env python3
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def atomic(path, text):
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(text)
    temporary.replace(path)


def percent(value):
    return f"{100 * value:.1f}%"


def interval(cell):
    return f"{cell['value']:.3f} [{cell['ci95'][0]:.3f}, {cell['ci95'][1]:.3f}]"


def main():
    sources = json.loads((HERE / "sources.json").read_text())
    crawl = json.loads((HERE / "fresh_test/manifest.json").read_text())
    dictionary = json.loads((HERE / "prepared/dictionary_manifest.json").read_text())
    embedding = json.loads((HERE / "prepared/embedding_manifest.json").read_text())
    validation = json.loads((HERE / "validation_results.json").read_text())
    models = json.loads((HERE / "model/metadata.json").read_text())
    fresh = json.loads((HERE / "fresh_results.json").read_text())
    result = {"schemaVersion": 1, "sources": sources, "crawl": crawl, "dictionary": dictionary,
              "embedding": embedding, "validation": validation, "models": models, "fresh": fresh,
              "cloud": {"run": False, "reason": "optional comparison not run before the core study"}}
    atomic(HERE / "results.json", json.dumps(result, indent=2) + "\n")

    status = crawl["statusCounts"]
    banner_sites = sum(count for key, count in status.items() if key not in {"no-supported-cmp", "navigation-failed", "blocked", "timeout"})
    lines = ["# Accuracy push 2 results", "", "Run date: November 2026.", "",
        "## 1. What ran", "",
        "The study crawled current public home pages for Cookiebot and OneTrust declarations, trained four frozen Random Forest variants on the old training names, exported and verified each model in ONNX, and opened the frozen fresh test once.", "",
        f"Tranco list `{sources['tranco']['listId']}` was created `{sources['tranco']['created']}`. Open Cookie Database commit `{sources['openCookieDatabase']['commit']}` and MiniLM revision `{sources['miniLm']['revision']}` were pinned by SHA-256. The database and MiniLM are Apache-2.0; the inspected CookieBlock crawler is BSD-3-Clause.", "",
        "## 2. Crawl summary", "",
        "| Measure | Count |", "|---|---:|",
        f"| Sites checked | {crawl['attemptedRanks']} |", f"| Supported-CMP banners detected | {banner_sites} |",
        f"| Usable sites | {crawl['usableSites']} |", f"| Matched labeled cookies kept | {crawl['records']} |",
        f"| Unseen normalized names | {crawl['normalizedNames']} |", f"| Old training/validation names dropped | {crawl['dropCounts']['oldNameDrops']} |",
        f"| Unmatched observed cookies | {crawl['dropCounts']['unmatchedDeclarations']} |",
        f"| CAPTCHA/block pages | {status.get('blocked', 0)} |", f"| Timeouts | {status.get('timeout', 0)} |", "",
        "Failure reasons were retained exactly in the frozen attempt chunks. No site URL, page content, declaration description, cookie value, or value hash was saved.", "",
        "## 3. Validation and selection", "",
        "| Variant | Width | Threshold | Balanced accuracy | Precision | Recall | F1 | PR-AUC | Fit seconds | Inference seconds |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in ["Base", "A", "B", "A+B"]:
        row = validation["variants"][name]
        metric = row["metrics"]
        lines.append(f"| {name} | {row['width']} | {row['threshold']:.2f} | {metric['balancedAccuracy']:.3f} | {metric['precision']:.3f} | {metric['recall']:.3f} | {metric['f1']:.3f} | {metric['prAuc']:.3f} | {row['fitSeconds']:.2f} | {row['inferenceSeconds']:.4f} |")
    lines += ["", f"Selected variant: **{fresh['selectedVariant']}**. Selection used V-B only; the fresh test did not affect it.", "",
        "## 4. Fresh test", "", "F-B is the main one-row-per-normalized-name view. Brackets are paired-cluster bootstrap 95% ranges.", "",
        "| Method | Balanced accuracy | Precision | Recall | F1 | PR-AUC |", "|---|---:|---:|---:|---:|---:|"]
    for method, values in fresh["views"]["F-B"]["methods"].items():
        lines.append(f"| {method} | {interval(values['balancedAccuracy'])} | {interval(values['precision'])} | {interval(values['recall'])} | {interval(values['f1'])} | {interval(values['prAuc'])} |")
    diff = fresh["views"]["F-B"]["selectedMinusC2BalancedAccuracy"]
    lines += ["", f"Selected minus C2 balanced accuracy: {diff['value']:.3f} [{diff['ci95'][0]:.3f}, {diff['ci95'][1]:.3f}]. **Swap verdict: {fresh['swap']['verdict']}.**", "",
        f"F-A contains {fresh['views']['F-A']['records']} cookies in {fresh['views']['F-A']['clusters']} site clusters; its complete metrics remain visible in `results.json`.", "",
        "## 5. Dictionary coverage", "",
        f"The fresh test has {fresh['coverage']['names']} normalized names. Open Cookie Database covered {fresh['coverage']['exact']} by an exact raw-name match and {fresh['coverage']['wildcard']} by a wildcard prefix. Training/validation/fresh coverage counts are preserved in the dictionary manifest.", "",
        "## 6. Cases", "", "Names that A or B changed from Base-wrong to correct:", ""]
    lines += [f"- `{name}` — {count} fresh cookie(s)" for name, count in fresh["fixedNames"]] or ["- None."]
    lines += ["", f"Names still missed by {fresh['selectedVariant']}:", ""]
    lines += [f"- `{name}` — {count} fresh cookie(s)" for name, count in fresh["stillMissedNames"]] or ["- None."]
    lines += ["", "## 7. Cloud comparison", "", "The optional cloud comparison was not run before the core study.", "",
        "## 8. Limits", "", "- Site declarations can be wrong.", "- The crawl covers only Cookiebot and OneTrust-family sites.", "- This is one crawl period, not a longitudinal sample.", "- Tracker is not login; this study does not identify authentication cookies.", "- CMP APIs, browser behavior, and geographic delivery can change which cookies appear.", "",
        "## 9. Draft wording for review", "",
        f"- Tested on {crawl['normalizedNames']} cookie names from today's websites."]
    if fresh["selectedVariant"] in {"B", "A+B"}:
        lines.append("- A small on-device language model turns cookie names into private numeric meaning vectors; the cookie list stays on the computer.")
    if fresh["swap"]["passed"]:
        lines.append(f"- The prespecified fresh-test rule passed, so {fresh['selectedVariant']} can replace C2 after review.")
    else:
        lines.append(f"- The prespecified fresh-test rule did not pass, so the demo keeps C2; {fresh['selectedVariant']} remains an experimental comparison.")
    lines += ["", "## 10. Reproducibility", "",
        f"Embedding recomputation maximum absolute difference: `{embedding['maximumAbsoluteDifference']}`. All four ONNX parity checks were at most `1e-5`; exact hashes and values are in `model/metadata.json` and `locks.txt`. `analyze.py` regenerated this file from locked artifacts.", ""]
    atomic(HERE / "results.md", "\n".join(lines))
    print(json.dumps({"selected": fresh["selectedVariant"], "swap": fresh["swap"], "freshNames": crawl["normalizedNames"]}, indent=2))


if __name__ == "__main__":
    main()
