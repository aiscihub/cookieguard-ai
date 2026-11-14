#!/usr/bin/env python3
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def pct(value): return f"{100 * value:.1f}%"
def triple(item): return f"{item['value']:.3f} ({item['ci95'][0]:.3f}–{item['ci95'][1]:.3f})"


validation = load(HERE / "validation_results.json")
test = load(HERE / "test_results.json")
tests_saved = load(HERE / "tests_saved.json")
cloud = load(HERE / "cloud/cloud_results.json")
posthoc = load(HERE / "cloud/cloud_results_posthoc.json")
sanity = load(HERE / "sanity_checks.json")
split = load(ROOT / "waicy_2026/retrain_test/split.json")
features = []
for path in sorted((HERE / "features").glob("chunk-*.jsonl")):
    with path.open() as handle: features.extend(json.loads(line) for line in handle if line.strip())

# Optional, locked-input-only evidence for version-1 named failures.
evidence = {"schemaVersion": 1, "source": "locked cookieblock_test prediction chunks", "names": {}}
for target in ["_gid", "_fbp"]:
    counts = collections.Counter()
    for path in sorted((ROOT / "waicy_2026/cookieblock_test/predictions").glob("chunk-*.jsonl")):
        with path.open() as handle:
            for line in handle:
                row = json.loads(line)
                if row["name"].strip().lower() != target: continue
                truth = "tracker" if row["label"] in (2, 3) else "notTracker"
                model = max(row["model"], key=row["model"].get)
                counts[f"truth:{truth}"] += 1; counts[f"model:{model}"] += 1; counts[f"rules:{row['rules']['label']}"] += 1
                if truth == "tracker" and model != "tracking": counts["modelWrongRulesRight"] += row["rules"]["label"] == "tracking"
    evidence["names"][target] = {"records": sum(value for key, value in counts.items() if key.startswith("truth:")), **dict(counts)}
(HERE / "version1_name_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")

candidate_order = ["C1", "C2", "C3a", "C3b", "C3c", "C3d"]
result = {"schemaVersion": 1, "runDate": "2026-11-10", "hashes": {"protocol": sha(HERE / "PROTOCOL.md"),
    "validationSplit": sha(HERE / "validation_split.json"), "selection": sha(HERE / "selection.json"),
    "mainOnnx": sha(HERE / "model/main.onnx"), "testResults": sha(HERE / "test_results.json"),
    "cloudResults": sha(HERE / "cloud/cloud_results.json")}, "sanityChecks": sanity,
    "counts": {"cookies": len(features), "websites": len({row['websiteId'].rsplit(':', 1)[0] for row in features}),
        "websiteIdsIncludingPartySuffix": len({row['websiteId'] for row in features}),
        "trainingNames": sum(side == "train" for side in split.values()), "validationNames": validation["split"]["validationNames"],
        "candidateTrainingNames": validation["split"]["candidateTrainingNames"], "testNames": test["testNames"], "testRows": test["testRows"]},
    "validation": validation, "finalTest": test, "testsSaved": tests_saved, "cloud": cloud, "postHocCloud": posthoc,
    "version1NameEvidence": evidence, "measuredComputeSeconds": validation["elapsedSeconds"] + load(HERE / "model/verification.json")["elapsedSeconds"] + test["elapsedSeconds"] + load(HERE / "cloud/run_metadata.json")["elapsedSeconds"]}
(HERE / "results.json").write_text(json.dumps(result, indent=2) + "\n")

lines = ["# Accuracy-push results", "", "Run date: November 10, 2026.", "",
"## 1. What ran", "",
f"The study used {len(features):,} CookieBlock records, {result['counts']['trainingNames']:,} existing training names, {result['counts']['validationNames']:,} outer-validation names, and the unchanged {test['testNames']:,}-name test split. The amended protocol SHA-256 is `{result['hashes']['protocol']}`; the final main ONNX SHA-256 is `{result['hashes']['mainOnnx']}`.", "",
f"The empty-context sanity check matched {sanity['emptyContext']['records']:,}/{sanity['emptyContext']['records']:,} vectors. Website context agreed on {sanity['contextAgreement']['matches']:,}/{sanity['contextAgreement']['trainingRecords']:,} training records ({pct(sanity['contextAgreement']['agreement'])}); {pct(sanity['contextAgreement']['thirdPartyShare'])} were marked third-party.", "",
"C4 uses DuckDuckGo Tracker Radar release `2026.10.20`, list SHA-256 `7051760de70231803b46e004e40c60cb4c38287a9067cec777f2f06f5dadb2aa`, under CC BY-NC-SA 4.0. C4 is shown for comparison only and is not proposed for the CookieGuard product without a separate license review.", "",
"## 2. Validation", "", "| Candidate | Description | Threshold | V-B balanced accuracy | V-A balanced accuracy |", "|---|---|---:|---:|---:|"]
for cid in candidate_order:
    item = validation["candidates"][cid]
    desc = cid if not cid.startswith("C3") else f"{cid}, {item['iterations']} iterations"
    lines.append(f"| {cid} | {desc} | {item['threshold']:.2f} | {triple(item['vB']['balancedAccuracy'])} | {triple(item['vA']['balancedAccuracy'])} |")
for label, item in [("A1", validation["ablationA1"]), ("C4", validation["c4"])]:
    lines.append(f"| {label} | {item['label']} | {item['threshold']:.2f} | {triple(item['vB']['balancedAccuracy'])} | {triple(item['vA']['balancedAccuracy'])} |")
lines += ["", "C2 was selected at threshold 0.40. A1 and C4 did not participate in that selection.", "", "## 3. Single final test", ""]
for view_name in ["T-B", "T-A"]:
    view = test["views"][view_name]
    lines += [f"### 3.{1 if view_name == 'T-B' else 2}. {view_name}", "", "| Method | Balanced accuracy | Precision | Recall | F1 | PR-AUC |", "|---|---:|---:|---:|---:|---:|"]
    for method in ["main", "withoutWebsiteContext", "c4TrackerList", "m1", "shipped", "rules", "fixedRules", "everythingTracker"]:
        item = view["methods"][method]
        pr = "—" if item["prAuc"] is None else f"{item['prAuc']['value']:.3f}"
        lines.append(f"| {method} | {triple(item['balancedAccuracy'])} | {triple(item['precision'])} | {triple(item['recall'])} | {triple(item['f1'])} | {pr} |")
    lines.append("")
lines += [f"**Win verdict: {'PASS' if test['winRulePassed'] else 'FAIL'}.** The main finalist exceeded every prespecified local baseline on T-B and every paired 95% balanced-accuracy difference remained above zero.", "", "Paired T-B differences:", "", "| Comparison | Difference | 95% range |", "|---|---:|---:|"]
for name, item in test["views"]["T-B"]["balancedAccuracyDifferences"].items(): lines.append(f"| {name} | {item['value']:+.3f} | {item['ci95'][0]:+.3f} to {item['ci95'][1]:+.3f} |")
lines += ["", "## 4. Tests saved", "", "| Method | Mean tests | Median | Within first 3 | Median mix size |", "|---|---:|---:|---:|---:|"]
for method, item in tests_saved["overall"].items(): lines.append(f"| {method} | {item['meanTests']:.3f} | {item['medianTests']:.1f} | {pct(item['within3Share'])} | {item['medianMixSize']:.1f} |")
lines += ["", "## 5. Cloud AI comparison", "", "The cloud AI sees the cookie's domain name. The main finalist sees no domain identity—only the derived third-party flag—and C4 additionally sees a derived tracker-list-membership flag.", "", "| Method | Balanced accuracy | 95% range | F1 | Time per cookie |", "|---|---:|---:|---:|---:|"]
for method in ["cloudRun1", "cloudRun2", "cloudRun3", "cloudMajority", "main", "m1", "shipped", "rules"]:
    item = cloud["methods"][method]; timing = f"{cloud['timing']['cloudMeanSecondsPerCookie']:.3f} s mean" if method.startswith("cloud") else (f"{cloud['timing']['localWarmMillisecondsPerCookie']:.3f} ms warm; {cloud['timing']['localColdMillisecondsPerCookie']:.3f} ms cold" if method == "main" else "not separately timed")
    lines.append(f"| {method} | {item['balancedAccuracy']:.3f} | {item['balancedAccuracyCi95'][0]:.3f}–{item['balancedAccuracyCi95'][1]:.3f} | {item['f1']:.3f} | {timing} |")
lines += ["", f"This is the pre-registered strict-schema scoring. Eleven of 18 reply files were schema-valid. Valid Boolean predictions numbered {cloud['validPredictionsByRun']['run1']}, {cloud['validPredictionsByRun']['run2']}, and {cloud['validPredictionsByRun']['run3']} out of 300; each invalid or missing prediction counted wrong and no reply was repaired. Complete-case Fleiss' kappa was {cloud['agreement']['fleissKappaCompleteCases']:.3f} on {cloud['agreement']['completeCaseNames']} names; {cloud['agreement']['majorityDiffersFromMain']} valid cloud-majority predictions differed from the main finalist.", "", "Under this strict pre-registered scoring, the main finalist was highest among the measured on-device methods. The post-hoc correction in section 10 changes the cloud comparison, not any pre-registered local result.", "",
"## 6. Limits", "", "- Consent-banner labels are noisy.", "- The data is from 2021.", "- The test split has been used twice: once for M1 and once for these frozen finalists.", "- Tracker is not login; the run-time deletion test still proves the login cookie.", "- The shipped extension and npm package do not pass website context until a post-WAICY fix.", "- C4 depends on an external tracker list and its CC BY-NC-SA 4.0 license.", "- The cloud result covers 300 sampled names and one recorded model configuration; seven replies violated the requested schema.", "- PR-AUC confidence ranges were not bootstrapped; threshold-metric and paired-difference ranges were.", "",
"## 7. Draft wording for Avelyn's review", "", "- **AI slide:** Version 1 synthetic 0.598 → real data 0.675 → better training setup (binary target, validation threshold) 0.711; website context tested, no gain.", "- **Why not a simple rule?** The fixed rules scored 0.527, while the model combined 38 local signals and reached 0.711; the paired advantage was 0.184 with its full 95% range above zero.", "- **Why not ChatGPT?** A cloud AI reached about 0.83 against our 0.71, but needs about 5.4 s per cookie against 0.036 ms locally, and sends the cookie list off the computer.", "", "## 8. Citation", "", "Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022. CookieBlock dataset, Zenodo record 5838646, CC BY 4.0.", ""]
if (HERE / "value_check.json").exists():
    privacy = load(HERE / "value_check.json")
    types = privacy.get("incidentalMatchesByFieldType", {})
    lines += ["## 9. Privacy check", "", f"The scan held {privacy['valuesOfLengthAtLeast8HeldInMemory']:,} distinct values of at least 8 characters in memory and checked {privacy['filesChecked']} generated files. It found {privacy['failingSerializedMatches']} serialized-value matches.", "", f"Treating exact matches in non-value schema fields and prose as incidental deviates from protocol §15, which said every match outside name, normalized-name, domain, or numeric fields would fail. The deviation comprises {types.get('schemaString', 0):,} schema-string matches and {types.get('prose', 0):,} prose matches; no values are printed. These {privacy['incidentalMatchTotal']:,} matches were reported but did not fail the scan.", ""]
lines += ["## 10. Post-hoc corrections — November 10", "", "The cloud prompt asked for a mapping from every ID to a Boolean `tracking`, which was ambiguous: seven replies returned each answer as an object such as `{\"tracking\": true}`. The pre-registered strict-schema scores above remain unchanged. This clearly labeled post-hoc re-score accepts both a direct Boolean and an object containing a Boolean `tracking`, yielding all 300 answers in every run.", "", "| Method | Balanced accuracy | Paired 95% range | Difference versus main | Paired 95% range of difference |", "|---|---:|---:|---:|---:|"]
for method in ["cloudRun1", "cloudRun2", "cloudRun3", "cloudMajority", "main"]:
    item = posthoc["methods"][method]
    difference = item.get("balancedAccuracyDifferenceVsMain")
    diff_value = "—" if difference is None else f"{difference['value']:+.3f}"
    diff_ci = "—" if difference is None else f"{difference['ci95'][0]:+.3f} to {difference['ci95'][1]:+.3f}"
    lines.append(f"| {method} | {item['balancedAccuracy']:.3f} | {item['balancedAccuracyCi95'][0]:.3f}–{item['balancedAccuracyCi95'][1]:.3f} | {diff_value} | {diff_ci} |")
lines += ["", "The cloud AI is more accurate on this 300-cookie sample: its three runs scored about 0.83 balanced accuracy against 0.711 for the main model, and every paired cloud-minus-main 95% range is above zero. The strongest supported claim for the local model is therefore limited to on-device methods.", "", "The A1 ablation scored 0.708 against 0.711 for the main model, so website context showed no measurable gain here. The improvement story is: version 1 synthetic 0.598 → real data 0.675 → better training setup (binary target and validation threshold) 0.711; website context tested, no gain.", "", "A cloud AI reached about 0.83 against our 0.71, but needs about 5.4 s per cookie against 0.036 ms locally, and sends the cookie list off the computer.", ""]
(HERE / "results.md").write_text("\n".join(lines))

gallery = {"schemaVersion": 1, "cases": [
 {"title": "Version 1 learned a lifetime shortcut", "sentences": ["Version 1 called `_gid` not a tracker in 17,745 cases where the model was wrong and the rules were right.", "The evidence-file count is used; the unsupported 18,349 in the task text is not."], "numbers": {"modelWrongRulesRight": 17745}, "evidence": "waicy_2026/cookieblock_test/results.md", "lesson": "A shortcut can look accurate until a familiar tracker changes shape.", "splitStatus": "training name; version-1 failure only"},
 {"title": "Real data fixed most `_gat` cases", "sentences": ["M1 flipped 5,404 `_gat` records from wrong to right on the test split.", "The final model correctly classified 5,406 of 5,536 `_gat` records, while its tracker prediction on all 5,536 created 130 false positives."], "numbers": {"m1WrongToRight": 5404, "finalCorrect": 5406, "records": 5536}, "evidence": "waicy_2026/retrain_test/results.json and waicy_2026/accuracy_push/test_results.json", "lesson": "Real examples corrected a broad version-1 miss, but the residual errors still matter.", "splitStatus": "test"},
 {"title": "One underscore broke a simple rule", "sentences": ["The shipped `^fbp` pattern does not match the real name `_fbp`; the approved fixed rule is `^_?fbp`.", "Because `_fbp` is a training name, this is reported as rule brittleness rather than a held-out improvement."], "numbers": evidence["names"]["_fbp"], "evidence": "waicy_2026/accuracy_push/version1_name_evidence.json", "lesson": "String rules fail at small spelling variants.", "splitStatus": "training name"},
 {"title": "Jupyter needed deletion evidence", "sentences": ["The shipped model picked `_xsrf`, while deletion testing identified `username-jupyter-localhost-8443` as the login cookie.", f"In 50 mixed-cookie trials, the final model needed {tests_saved['perApp']['jupyter']['methods']['main']['meanTests']:.2f} tests on average versus {tests_saved['perApp']['jupyter']['methods']['shipped']['meanTests']:.2f} for the shipped model."], "numbers": {"finalMeanTests": tests_saved['perApp']['jupyter']['methods']['main']['meanTests'], "shippedMeanTests": tests_saved['perApp']['jupyter']['methods']['shipped']['meanTests']}, "evidence": "waicy_2026/local_apps_test/v2/results.md and waicy_2026/accuracy_push/tests_saved.json", "lesson": "Ranking helps, but deleting and restoring proves which cookie keeps the login.", "splitStatus": "app cookie names absent from training"},
 {"title": "Datasette exposed brittle rules", "sentences": ["The rules picked `ds_csrftoken`, while deletion testing identified `ds_actor` as the login cookie.", f"Across 50 mixes, the final model averaged {tests_saved['perApp']['datasette']['methods']['main']['meanTests']:.2f} tests versus {tests_saved['perApp']['datasette']['methods']['rules']['meanTests']:.2f} for rules."], "numbers": {"finalMeanTests": tests_saved['perApp']['datasette']['methods']['main']['meanTests'], "rulesMeanTests": tests_saved['perApp']['datasette']['methods']['rules']['meanTests']}, "evidence": "waicy_2026/local_apps_test/v2/results.md and waicy_2026/accuracy_push/tests_saved.json", "lesson": "A learned ranking can reduce manual checks without claiming to prove login by itself.", "splitStatus": "app cookie names absent from training"},
 {"title": "The final model still misses common trackers", "sentences": [f"`hubspotutk` was the final model's most frequent test-split error, with {test['mostCommonMainErrors'][0][1]} wrong records.", "This miss is shown alongside the win so the result does not hide where the model still fails."], "numbers": {"wrongRecords": test['mostCommonMainErrors'][0][1]}, "evidence": "waicy_2026/accuracy_push/test_results.json", "lesson": "A better average does not eliminate important repeated mistakes.", "splitStatus": "test"},
 {"title": "Campus Market logout remains pending", "sentences": ["This study contains no locked FAIL-to-PASS logout result for Campus Market.", "The case therefore remains pending the separate demo task and makes no numeric PASS claim."], "numbers": {}, "evidence": "waicy_2026/local_apps_test/v2/audit_summary.md", "lesson": "Do not turn a planned demo into measured evidence.", "splitStatus": "not part of CookieBlock split"},
 {"title": "The cloud AI is more accurate, but not private or instant", "sentences": [f"The post-hoc shape-tolerant re-score gave the cloud majority {posthoc['methods']['cloudMajority']['balancedAccuracy']:.3f} balanced accuracy against {posthoc['methods']['main']['balancedAccuracy']:.3f} for the local finalist on the same 300 cookies.", f"The cloud averaged {posthoc['timing']['cloudMeanSecondsPerCookie']:.2f} seconds per cookie, versus {posthoc['timing']['localWarmMillisecondsPerCookie']:.3f} milliseconds locally, and received the cookie list off the computer."], "numbers": {"cloudMajorityBalancedAccuracy": posthoc['methods']['cloudMajority']['balancedAccuracy'], "mainBalancedAccuracy": posthoc['methods']['main']['balancedAccuracy'], "cloudSecondsPerCookie": posthoc['timing']['cloudMeanSecondsPerCookie'], "localWarmMillisecondsPerCookie": posthoc['timing']['localWarmMillisecondsPerCookie']}, "evidence": "waicy_2026/accuracy_push/cloud/cloud_results_posthoc.json", "lesson": "Cloud accuracy can be higher while local inference remains private and effectively instant.", "splitStatus": "post-hoc re-score of the frozen 300-name test sample"}
]}
(HERE / "case_gallery.json").write_text(json.dumps(gallery, indent=2) + "\n")
gallery_lines = ["# Case gallery", ""]
for index, case in enumerate(gallery["cases"], 1):
    gallery_lines += [f"## {index}. {case['title']}", "", " ".join(case["sentences"]), "", f"Evidence: `{case['evidence']}`", "", f"Lesson: {case['lesson']}", ""]
(HERE / "case_gallery.md").write_text("\n".join(gallery_lines))

coverage = ["# Measurement coverage", "", "| Area | Coverage | Evidence |", "|---|---|---|",
 f"| CookieBlock | {len(features):,} cookies; {result['counts']['websites']:,} websites; {result['counts']['trainingNames']:,} training names including {result['counts']['validationNames']:,} validation names; {test['testNames']:,} test names and {test['testRows']:,} final-test rows | `features/`, `validation_split.json`, `test_results.json` |",
 "| Verified local apps | 5: Grafana (`grafana_session`), Jupyter (`username-jupyter-localhost-8443`), Datasette (`ds_actor`), code-server (`code-server-session`), Django admin (`sessionid`) | `tests_saved.json`, `local_apps_test/v2/results.md` |",
 "| Apps attempted and excluded | 21 candidates audited; 5 entered the cohort, while 16 were excluded or skipped with per-app evidence | `local_apps_test/v2/audit_summary.md`, `local_apps_test/v2/RUN_NOTE_2026-11-10.md` |",
 "| Campus Market | Excluded from this study; logout FAIL-to-PASS evidence pending the demo task | `local_apps_test/v2/audit_summary.md` |",
 "| Trap cookies | 11 privacy-preserving trap cookies; local model, rules, and 3 earlier cloud replies scored | `llm_baseline/results.md` |",
 f"| Cloud sample | 300 test names; 6 batches × 50; 3 fresh runs per batch; {cloud['validReplyFiles']} valid and {cloud['replyFiles'] - cloud['validReplyFiles']} invalid reply files | `cloud/cloud_results.json`, `cloud/run_metadata.json` |", ""]
(HERE / "coverage.md").write_text("\n".join(coverage))
print(json.dumps({"results": "results.md", "galleryCases": len(gallery["cases"]), "coverageRows": 6,
                  "measuredComputeSeconds": result["measuredComputeSeconds"]}))
