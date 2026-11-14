"""Run canaries without storing child output, credentials, or browser traces."""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from common import ROOT, load, sha, write_json

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, default=ROOT / "refresh/.work/run")
    a = p.parse_args()
    run = a.run.resolve()
    candidate = run / "candidate"
    # Children get no API credentials, even if the developer's shell has them.
    allowed = ["PATH", "HOME", "TMPDIR", "SYSTEMROOT", "WINDIR", "PLAYWRIGHT_BROWSERS_PATH"]
    env = {k: os.environ[k] for k in allowed if k in os.environ}
    env.update(COOKIEGUARD_USAGE_METRICS="0", DO_NOT_TRACK="1", ORT_DISABLE_TELEMETRY="1",
               ANONYMIZED_TELEMETRY="false", BROWSER_USE_CLOUD_SYNC="false", BROWSER_USE_DISABLE_EXTENSIONS="1",
               COOKIEGUARD_REFRESH_MODEL=str(candidate),
               COOKIEGUARD_REFRESH_PRELOAD=(ROOT / "refresh/preload_candidate.mjs").as_uri(),
               npm_config_script_shell=str(ROOT / "refresh/test-shell.sh"))
    test_count = None
    try:
        check = subprocess.run(["npm", "test"], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, timeout=600)
        npm_ok = check.returncode == 0
        counts = re.findall(r'^(?:#|ℹ) tests (\d+)$', check.stdout.decode(errors="replace"), re.M)
        test_count = int(counts[-1]) if counts else None
    except (OSError, subprocess.TimeoutExpired):
        npm_ok = False
    env.pop("npm_config_script_shell", None)
    env.pop("COOKIEGUARD_REFRESH_PRELOAD", None)
    env.pop("COOKIEGUARD_REFRESH_MODEL", None)
    result_path = run / "browser-canary.json"
    result_path.unlink(missing_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="canary-runtime-", dir=ROOT / "refresh/.work") as private_work:
            check = subprocess.run([sys.executable, str(ROOT / "refresh/browser_canary.py"), "--candidate", str(candidate),
                                    "--work", private_work, "--out", str(result_path)],
                                   cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        browser = load(result_path) if result_path.exists() else {"passed": False, "status": "missing-receipt"}
        browser["passed"] = check.returncode == 0 and browser["passed"]
    except (OSError, subprocess.TimeoutExpired):
        browser = {"passed": False, "status": "browser-canary-timeout"}
    result = {"npmTestPassed": npm_ok, "npmTestCount": test_count, "npmCandidatePreload": True, "browserUse": browser,
              "runnerSha256": sha(ROOT / "refresh/canaries.py"),
              "passed": npm_ok and browser["passed"], "modelSha256": sha(candidate / "model.onnx"),
              "childOutputStored": False}
    write_json(run / "canaries.json", result)
    print(json.dumps({"stage": "canaries", "npmTestPassed": npm_ok, "browserUsePassed": browser["passed"]}))

if __name__ == "__main__": main()
