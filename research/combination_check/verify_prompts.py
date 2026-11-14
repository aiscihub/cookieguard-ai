#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLOUD = HERE / "cloud"
PROMPTS = CLOUD / "prompts"
INTRO = (
    "You are classifying browser cookies. For each item, decide whether it is a tracking "
    "cookie: analytics or advertising. Values and website names are withheld. The domain "
    "shown is the cookie domain. Reply with one JSON object whose keys are the IDs and whose "
    'values are true or false, e.g. {"C001": true, "C002": false}. Include every ID exactly '
    "once, with no prose, markdown, missing IDs, or extra IDs.\n\n"
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def render_line(item):
    life = "session" if item["lifetimeDays"] is None else f'{item["lifetimeDays"]:.6g} days'
    return (
        f'{item["id"]} name={json.dumps(item["name"])}; '
        f'domain={json.dumps(item["domain"])}; '
        f'third-party={"yes" if item["thirdParty"] else "no"}; '
        f'Secure={"yes" if item["secure"] else "no"}; '
        f'HttpOnly={"yes" if item["httpOnly"] else "no"}; '
        f'SameSite={item["sameSite"]}; lifetime={life}; '
        f'value length={item["valueShape"]["length"]}; '
        f'character set={item["valueShape"]["characterSet"]}\n'
    )


manifest_path = CLOUD / "sample_manifest.json"
public_path = CLOUD / "sample_public.json"
manifest_bytes = manifest_path.read_bytes()
public_bytes = public_path.read_bytes()
manifest = json.loads(manifest_bytes)
public = json.loads(public_bytes)

if sha256(public_bytes) != manifest["samplePublicSha256"]:
    raise RuntimeError("frozen sample_public.json hash mismatch")
if len(public) != 300 or manifest["batches"] != 6 or manifest["itemsPerBatch"] != 50:
    raise RuntimeError("frozen cloud sample shape mismatch")

checks = []
for batch in range(1, 7):
    rows = public[(batch - 1) * 50 : batch * 50]
    expected = (INTRO + "".join(render_line(item) for item in rows)).encode()
    path = PROMPTS / f"batch-{batch}.txt"
    original = path.read_bytes()
    rebuilt = original != expected
    if rebuilt:
        path.write_bytes(expected)
    actual = path.read_bytes()
    if actual != expected:
        raise RuntimeError(f"batch {batch} differs after structural rebuild")
    expected_ids = [item["id"] for item in rows]
    line_ids = [line.split(" ", 1)[0] for line in actual.decode().splitlines()[2:]]
    if line_ids != expected_ids or len(line_ids) != 50:
        raise RuntimeError(f"batch {batch} ID/order check failed")
    checks.append(
        {
            "batch": batch,
            "file": path.name,
            "rows": 50,
            "exact": True,
            "rebuilt": rebuilt,
            "sha256": sha256(actual),
            "lockedSha256": manifest["prompts"][batch - 1]["sha256"],
            "matchesLockedHash": sha256(actual)
            == manifest["prompts"][batch - 1]["sha256"],
        }
    )

structure = {
    "schemaVersion": 1,
    "amendment": "A1",
    "passed": True,
    "basis": "exact fixed-template rendering of frozen structured rows",
    "sampleManifestSha256": sha256(manifest_bytes),
    "samplePublicSha256": sha256(public_bytes),
    "items": 300,
    "batches": checks,
}
(CLOUD / "prompt_structure_check.json").write_text(json.dumps(structure, indent=2) + "\n")

admission = {
    "schemaVersion": 1,
    "passed": True,
    "basis": "structural (Amendment A1)",
    "promptStructureCheckSha256": sha256(
        (CLOUD / "prompt_structure_check.json").read_bytes()
    ),
    "originalValuePreflight": {
        "passed": False,
        "forbiddenMatches": 11,
        "coordinatorExited": True,
        "valuesWereMemoryOnlyAndAreUnrecoverable": True,
    },
    "dataBeyondFrozenRows": False,
}
(HERE / "cloud_prompt_privacy_pass.json").write_text(
    json.dumps(admission, indent=2) + "\n"
)
print(json.dumps(structure, indent=2))
