"""Run the real scripted Browser Use demo through an isolated candidate bridge."""
from __future__ import annotations
import argparse
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from common import ROOT, load, sha, write_json

async def run(candidate, work, output):
    # Import only after process-level opt-outs. All library logs go to the null device.
    from cookieguard import _engine
    from cookieguard.browser_use.demo.scripted import run_scenario
    original = _engine.engine_dir()
    isolated = Path(tempfile.mkdtemp(prefix="candidate-", dir=work)) / "engine"
    shutil.copytree(original, isolated)
    bridge = isolated / "bridge.mjs"
    source = bridge.read_text()
    adapter = (ROOT / "refresh/candidate.mjs").as_uri()
    injection = "import { createCandidate } from " + json.dumps(adapter) + ";\nconst refreshClassifier = await createCandidate(" + json.dumps(str(candidate)) + ");\n"
    source = injection + source
    # Every audit collector, including provisional snapshots, receives the candidate.
    source = source.replace("startCookieAudit(state.context, state.config)", "startCookieAudit(state.context, { ...state.config, classifier: refreshClassifier })")
    source = source.replace("startCookieAudit(context, { origins: state.config.origins, policy: state.config.policy, timeoutMs: 10000 })",
                            "startCookieAudit(context, { origins: state.config.origins, policy: state.config.policy, timeoutMs: 10000, classifier: refreshClassifier })")
    # Evidence sent back is already sanitized; add an invocation count as proof.
    source = source.replace("report: JSON.parse(formatJson(report)),", "report: { ...JSON.parse(formatJson(report)), refreshCandidateCalls: refreshClassifier.calls },")
    bridge.write_text(source)
    manifest = load(isolated / "manifest.json")
    manifest["bridge"]["bridge.mjs"] = sha(bridge)
    (isolated / "manifest.json").write_text(json.dumps(manifest))
    _engine._ENGINE_DIR = isolated
    _engine._verified_dirs.clear()
    # The shipped bridge disallows native addons; relax only this private test copy.
    # This is deliberately not a production package change.
    _engine.node_command = lambda node, directory, script="bridge.mjs": [node, str(directory / script)]
    outcomes = []
    for mode, expected in [("insecure", "FAIL"), ("secure", "PASS")]:
        outcome = await run_scenario(mode)
        result = outcome.result
        codes = [finding.rule_id for finding in result.confirmed_findings]
        calls = result.report.get("refreshCandidateCalls", 0)
        outcomes.append({"mode": mode, "status": result.status, "loginSucceeded": outcome.login_succeeded,
                         "candidateCalls": calls, "CG001": "CG001" in codes,
                         "passed": outcome.login_succeeded and result.status == expected and calls > 0
                                   and (mode != "insecure" or "CG001" in codes)})
    write_json(output, {"passed": all(r["passed"] for r in outcomes), "scenarios": outcomes,
                        "modelSha256": sha(candidate / "model.onnx"),
                        "adapterSha256": sha(ROOT / "refresh/candidate.mjs"),
                        "bridgeIsolation": "private test copy; production files and defaults unchanged"})

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.work, a.candidate, a.out = a.work.resolve(), a.candidate.resolve(), a.out.resolve()
    a.work.mkdir(parents=True, exist_ok=True)
    # Browser Use's local session metadata belongs in this ignored scratch directory.
    os.chdir(a.work.resolve())
    os.environ.update(ANONYMIZED_TELEMETRY="false", BROWSER_USE_CLOUD_SYNC="false",
                      BROWSER_USE_DISABLE_EXTENSIONS="1", COOKIEGUARD_USAGE_METRICS="0", DO_NOT_TRACK="1")
    # Capture nothing from the demo: page text, prompts, logs and exceptions never become artifacts.
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            asyncio.run(run(a.candidate.resolve(), a.work.resolve(), a.out.resolve()))
        except Exception:
            write_json(a.out, {"passed": False, "status": "browser-canary-failed"})
            return 1
    return 0

if __name__ == "__main__": sys.exit(main())
