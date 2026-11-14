"""Fetch only the approved, hash-pinned public training asset."""
import argparse
from pathlib import Path
import urllib.request
import shutil
from common import ROOT, load, sha

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "refresh/.work/inputs")
    a = parser.parse_args()
    config = load(ROOT / "refresh/training-source.json")
    if not config["uploadApproved"]:
        raise SystemExit("Training asset upload awaits owner approval; no download attempted.")
    a.out.mkdir(parents=True, exist_ok=True)
    dest = a.out / config["assetName"]
    urllib.request.urlretrieve(config["url"], dest)
    if sha(dest) != config["sha256"]:
        dest.unlink()
        raise SystemExit("Training asset digest mismatch.")
    sidecar = ROOT / "refresh/reference/training-pool-2021.attribution.json"
    if load(sidecar)["sha256"] != config["sha256"]:
        raise SystemExit("Training attribution digest mismatch.")
    shutil.copyfile(sidecar, a.out / sidecar.name)

if __name__ == "__main__": main()
