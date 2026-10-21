"""Freeze or verify exact Git blobs for the committed V10 matcher and MIPP."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).resolve().parent / "baseline"
COMMIT = "c41f04762fb62ca5598f60e5d66ea9cfa2fbc2a0"
PRODUCTION = ("line2Dup.cpp", "line2Dup.h", "line2Dup_local.hpp", "line2Dup_search.hpp",
              "line2Dup_response.hpp", "line2Dup_spread.hpp")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    commit = git("rev-parse", COMMIT).decode().strip()
    paths = list(PRODUCTION) + git("ls-tree", "-r", "--name-only", commit, "--", "MIPP").decode().splitlines()
    entries = {}
    for relative in sorted(paths):
        original = git("show", f"{commit}:{relative}")
        entries[relative] = dict(sha256=hashlib.sha256(original).hexdigest().upper(), bytes=len(original),
                                 git_blob=git("rev-parse", f"{commit}:{relative}").decode().strip())
        target = BASELINE / relative
        if target.exists():
            if target.read_bytes() != original:
                raise ValueError(f"Frozen bytes differ from {commit}: {relative}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)
    manifest = BASELINE / "manifest.json"
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        if saved["commit"] != commit or saved["files"] != entries:
            raise ValueError("Existing frozen manifest differs")
    else:
        manifest.write_text(json.dumps(dict(commit=commit, created_at=datetime.now(timezone.utc).isoformat(),
            method="git show exact stdout bytes; no newline or encoding conversion", files=entries), indent=2) + "\n")
    print(f"PASS exact V10 snapshot: {commit}, {len(entries)} matcher/MIPP files")


if __name__ == "__main__":
    main()
