#!/usr/bin/env python3
import concurrent.futures
import datetime as dt
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLOUD = HERE / "cloud"
REPLIES = CLOUD / "replies"
REPLIES.mkdir(exist_ok=True)
CODEX = Path("/Users/zhenli/.vscode/extensions/openai.chatgpt-26.51021.22027-darwin-arm64/bin/macos-aarch64/codex")


def sha_bytes(value): return hashlib.sha256(value).hexdigest()


def one(batch, run):
    prompt = (CLOUD / "prompts" / f"batch-{batch}.txt").read_bytes()
    work = Path(tempfile.mkdtemp(prefix=f"accuracy-cloud-b{batch}-r{run}-", dir="/private/tmp"))
    reply_temp = Path(str(work) + ".reply.txt")
    command = [str(CODEX), "--no-daemon", "-a", "never", "exec", "--ignore-user-config", "--ephemeral",
        "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never", "--json", "-m", "gpt-6-astra",
        "-c", 'model_reasoning_effort="max"', "-c", "project_doc_max_bytes=0", "-c", 'web_search="disabled"',
        "--enable", "skip_host_skill_discovery", "--disable", "apps", "--disable", "plugins", "--disable", "hooks",
        "--disable", "memories", "--disable", "multi_agent", "--disable", "shell_tool", "--disable", "unified_exec",
        "--disable", "browser_use", "--disable", "browser_use_external", "--disable", "computer_use",
        "--disable", "image_generation", "--disable", "shell_snapshot", "--disable", "view_image", "--disable", "sleep_tool",
        "-C", str(work), "-o", str(reply_temp), "-"]
    started = dt.datetime.now(dt.timezone.utc); before = time.perf_counter()
    completed = subprocess.run(command, input=prompt, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elapsed = time.perf_counter() - before; ended = dt.datetime.now(dt.timezone.utc)
    reply = reply_temp.read_bytes() if reply_temp.exists() else b""
    destination = REPLIES / f"batch-{batch}-run-{run}.txt"
    destination.write_bytes(reply)
    events = []
    for line in completed.stdout.decode("utf8", "replace").splitlines():
        try: events.append(json.loads(line))
        except json.JSONDecodeError: pass
    expected = {f"C{index:03d}" for index in range(1, 301)}
    public = json.loads((CLOUD / "sample_public.json").read_text())[(batch - 1) * 50:batch * 50]
    ids = {item["id"] for item in public}
    valid = False
    try:
        parsed = json.loads(reply)
        valid = isinstance(parsed, dict) and set(parsed) == ids and all(isinstance(value, bool) for value in parsed.values())
    except Exception: pass
    return {"batch": batch, "run": run, "exitCode": completed.returncode, "startedAtUtc": started.isoformat(),
        "completedAtUtc": ended.isoformat(), "elapsedSeconds": elapsed, "cwd": str(work), "cwdEmptyAtStart": True,
        "promptSha256": sha_bytes(prompt), "replySha256": sha_bytes(reply), "replyBytes": len(reply), "replyValid": valid,
        "stderr": completed.stderr.decode("utf8", "replace")[-4000:], "eventTypes": sorted({event.get("type") for event in events if event.get("type")}),
        "usage": [event.get("usage") for event in events if event.get("usage")], "command": command}


if any(REPLIES.glob("*.txt")):
    raise SystemExit("reply files already exist; refusing to overwrite")
started = time.perf_counter()
jobs = [(batch, run) for batch in range(1, 7) for run in range(1, 4)]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    runs = list(executor.map(lambda pair: one(*pair), jobs))
metadata = {"schemaVersion": 1, "experimentDateLocal": "2026-11-10", "timezone": "America/Los_Angeles",
    "interface": "Codex CLI fresh ephemeral sessions", "codexCliVersion": "0.164.0-alpha.11.1", "model": "gpt-6-astra",
    "reasoningEffort": "max", "batches": 6, "runsPerBatch": 3, "isolatedSessions": 18,
    "method": {"emptyWorkingDirectoryPerSession": True, "identicalPromptBytesWithinBatch": True,
        "projectInstructionsToolsMemoryWebAppsPluginsShellBrowserDisabled": True, "repliesSavedBeforeScoring": True},
    "runs": sorted(runs, key=lambda item: (item["batch"], item["run"])), "elapsedSeconds": time.perf_counter() - started}
(CLOUD / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps({"runs": len(runs), "valid": sum(run["replyValid"] for run in runs), "elapsedSeconds": metadata["elapsedSeconds"]}))
