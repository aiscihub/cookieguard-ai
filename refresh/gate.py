"""Fixed acceptance gates. Never publishes or changes package defaults."""
import argparse
import json
from pathlib import Path
from common import ROOT, load, sha, structural, write_json
from health import assess_health, health_report

def assess(manifest, evaluation, parity, canaries):
    gates = {}
    for name, subset in [("No regression", "natural"), ("Unseen names", "unseenNames")]:
        details = {}
        for baseline in ["production-rules", "production-v1"]:
            interval = evaluation["candidateMinus"][baseline][subset]["metrics"]["balancedAccuracy"]
            details[baseline] = interval["lower"]
        gates[name] = {"passed": all(v is not None and v >= -.01 for v in details.values()),
                       "rule": "paired balanced-accuracy lower 95% bound >= -0.01 against both production baselines",
                       "lowerBounds": details}
    gates["Canaries"] = {"passed": canaries["passed"], "rule": "npm test with candidate preload; real Browser Use candidate bridge: FAIL CG001 / PASS"}
    gates["Parity"] = {"passed": parity["passed"] and parity["rows"] >= 1000 and parity["maxAbsoluteDifference"] <= 1e-5,
                       "rule": "ONNX versus scikit-learn <= 1e-5 on 1000 rows", "maxAbsoluteDifference": parity["maxAbsoluteDifference"]}
    gates["Privacy"] = {"passed": manifest["privacyPassed"] and manifest["structuralPassed"] and manifest["complete"],
                        "rule": "all shard receipts passed; complete frame; structural check passed"}
    gates["Health"] = assess_health(manifest)
    return gates

def score_text(metric):
    if metric["estimate"] is None:
        return "N/A"
    point = "%.2f%%" % (100 * metric["estimate"])
    if metric["lower"] is None:
        return point + " (CI unavailable)"
    return point + " [%.2f, %.2f]" % (100 * metric["lower"], 100 * metric["upper"])

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, default=ROOT / "refresh/.work/run")
    p.add_argument("--release", type=Path, required=True)
    a = p.parse_args()
    run, release = a.run.resolve(), a.release.resolve()
    manifest, evaluation = load(release / "manifest.json"), load(run / "evaluation.json")
    parity, canaries = load(run / "candidate/parity.json"), load(run / "canaries.json")
    meta = load(run / "candidate/meta.json")
    if sha(release / "cookies.jsonl") != evaluation["rowsSha256"] or sha(run / "candidate/model.onnx") != canaries["modelSha256"]:
        raise ValueError("gate-provenance")
    gates = assess(manifest, evaluation, parity, canaries)
    passed = all(g["passed"] for g in gates.values())
    result = {"schemaVersion": 1, "month": manifest["month"], "dryRun": manifest["dryRun"],
              "allGatesPassed": passed, "eligibleForModelPR": passed and not manifest["dryRun"],
              "humanModelApprovalRequired": True, "gates": gates,
              "modelSha256": meta["onnxSha256"], "evaluationSha256": sha(run / "evaluation.json")}
    write_json(run / "gate.json", result)
    lines = [
        "# Monthly refresh report: " + manifest["month"], "",
        "**LOCAL DRY RUN — no publication or promotion.**" if manifest["dryRun"] else "**Candidate artifacts only. Every model release requires human approval.**", "",
        "Tranco list: " + manifest["trancoListId"] + ". Attempted sites: " + str(manifest["attempted"]) +
        "; visited sites: " + str(manifest.get("visitedSites", "unavailable")) + "; usable sites: " + str(manifest["usableSites"]) + "; labeled cookies: " + str(manifest["rows"]) + ".", "",
        "## 1. Gates", "", "| Gate | Result | Evidence |", "|---|---|---|",
    ]
    for name, gate in gates.items():
        details = {k: v for k, v in gate.items() if k not in {"passed", "rule"}}
        lines.append("| " + name + " | " + ("PASS" if gate["passed"] else "FAIL") + " | " + gate["rule"] +
                     ("; " + json.dumps(details, sort_keys=True) if details else "") + " |")
    lines += ["", "## 2. Evaluation", "",
              "Tracker is the positive class. Intervals are 95% site-cluster bootstrap intervals from 1,000 seeded draws. "
              "Paired differences use the same sampled sites. Unseen comparisons use rows unseen to both methods. "
              "An interval is unavailable if fewer than 950 draws define the metric or fewer than two sites are available.", "",
              "| Method | Subset | Rows | Sites | Balanced accuracy | Precision | Recall |", "|---|---|---:|---:|---|---|---|"]
    for name, model in evaluation["models"].items():
        for subset in ["natural", "unseenNames"]:
            result_row = model[subset]
            lines.append("| " + " | ".join([name, subset, str(result_row["rows"]), str(result_row["sites"])] +
                                          [score_text(result_row["metrics"][m]) for m in ["balancedAccuracy", "precision", "recall"]]) + " |")
    lines += ["", "### Paired candidate differences", "",
              "| Baseline | Subset | Rows | Balanced accuracy difference |", "|---|---|---:|---|"]
    for name, comparison in evaluation["candidateMinus"].items():
        for subset in ["natural", "unseenNames"]:
            item = comparison[subset]
            lines.append("| " + name + " | " + subset + " | " + str(item["rows"]) + " | " + score_text(item["metrics"]["balancedAccuracy"]) + " |")
    lines += ["", "### Lookup and declaration disagreement", "",
              "| Method | Lookup hits | Hit rate | Hit accuracy | Disagreements |", "|---|---:|---|---|---:|"]
    for name, model in evaluation["models"].items():
        lookup = model["lookup"]
        fmt = lambda n: "N/A" if n is None else "%.2f%%" % (n * 100)
        lines.append("| " + " | ".join([name, str(lookup["hits"]), fmt(lookup["hitRate"]), fmt(lookup["hitAccuracy"]), str(lookup["labelDisagreements"])]) + " |")
    lines += ["", "Normalized names with conflicting site labels: " + str(evaluation["disagreementNames"]) + ".", "",
              "## 3. Crawl and privacy", "", "| Status | Sites |", "|---|---:|"]
    for status, count in manifest["statusCounts"].items():
        lines.append("| " + status + " | " + str(count) + " |")
    lines += health_report(manifest)
    lines += ["", "No site is revisited. A site with an unverifiable robots policy is skipped conservatively. "
              "All shards run at concurrency 4 with a 30-second site cap. Cookies remain in memory; no browser traces, "
              "screenshots, storage-state files, page text, or raw exceptions are exported.", "",
              "Privacy receipts record the frozen crawler's incremental cross-scan: strings of at least 8 characters, "
              "with independently observed cookie names, domains, and numeric coincidences accounted for. Short strings "
              "are protected by fixed schemas and exclusion of contents fields. Grep is an additional check, not proof "
              "that arbitrary unknown secrets are impossible.", "",
              "## 4. Training and provenance", "",
              "Training rows: " + str(meta["trainingRows"]) + "; normalized names: " + str(meta["trainingNames"]) +
              "; threshold: " + format(meta["threshold"], ".2f") + ". No current-month refresh rows enter training or lookup construction.", "",
              "C2: 150 trees, depth 12, minimum split 5, minimum leaf 2, balanced weights, random state 42. "
              "Threshold selection holds out normalized names using the month seed, then refits on historical rows only.", "",
              "The v1 unseen-name membership conservatively includes all names in the supplied production training source "
              "(including validation); its exact historical fit membership was not recorded. Website declarations are "
              "proxy labels, and Cookiebot/OneTrust coverage is not representative of all websites.", "",
              "Model SHA-256: " + meta["onnxSha256"], "",
              "Lookup SHA-256: " + meta["lookupSha256"], "",
              "Dataset SHA-256: " + evaluation["rowsSha256"], "",
              "## 5. Validation evidence", "",
              "npm test: " + str(canaries.get("npmTestCount", "unknown")) + " tests; passed=" + str(canaries["npmTestPassed"]) + ". "
              "Both real Browser Use scenarios invoke the candidate model. The test adapter is isolated from the shipped bridge.", "",
              "The public crawl used " + str(len(manifest["shardReceipts"])) + " shards. A separate browser fixture exercises "
              "a usable Cookiebot declaration, consent, reload, 38-feature extraction, and content exclusion without any public requests. "
              "Fixture results are not added to the dataset or its yield.", "",
              "See privacy-audit.json for the SHA-256 output inventory and grep-proof.txt for actual zero-match checks. "
              "The privacy audit is run after this report is written.", "",
              "## 6. Decision", "",
              "No model PR is eligible." if not result["eligibleForModelPR"] else "All gates pass; a model PR may be opened for human review.",
              "Package defaults are unchanged. No package publication is performed.", "",
    ]
    report = "\n".join(lines)
    (run / "REPORT.md").write_text(report)
    (release / "REPORT.md").write_text(report)
    (run / "candidate/MODEL_CARD.md").write_text(
        "# CookieGuard monthly candidate: " + manifest["month"] + "\n\n"
        "Status: " + ("gate-passing candidate awaiting human review" if result["eligibleForModelPR"] else "not eligible for release") + ".\n\n"
        "Use: optional cookie tracking classification research artifact. Authentication policy gates remain rule-driven. "
        "Binary labels represent site declarations; output scores are uncalibrated. No package default is changed.\n\n"
        + report
    )
    print(json.dumps({"stage": "gate", "allGatesPassed": passed, "eligibleForModelPR": result["eligibleForModelPR"]}))

if __name__ == "__main__": main()
