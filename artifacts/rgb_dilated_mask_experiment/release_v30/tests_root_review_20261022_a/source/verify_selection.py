"""Verify the V30 publication allowlist without mutating Git or files."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[3]
SELECTION = HERE / "artifacts/rgb_dilated_mask_experiment/PUBLISH_SELECTION_V30.json"
INVENTORY = "artifacts/rgb_dilated_mask_experiment/PUBLISH_SELECTION_V30.json"
FORBIDDEN = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif", ".smd",
             ".exe", ".o", ".obj", ".dll", ".pdb", ".pyc", ".zip", ".7z", ".tar"}


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    if not SELECTION.is_file():
        fail("missing V30 selection")
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    rows = selection.get("files")
    if not isinstance(rows, list) or selection.get("file_count") != len(rows):
        fail("selection file count mismatch")
    if len({row.get("path") for row in rows}) != len(rows):
        fail("duplicate selected path")
    total = 0
    selected = set()
    object_format = subprocess.run(["git", "rev-parse", "--show-object-format"], cwd=HERE,
                                   check=True, capture_output=True, text=True).stdout.strip()
    if object_format not in {"sha1", "sha256"}:
        fail("unsupported Git object format")
    blob_ids = {}
    for row in rows:
        rel = row.get("path")
        if (not isinstance(rel, str) or "\\" in rel or Path(rel).is_absolute()
                or ".." in Path(rel).parts):
            fail(f"invalid path {rel!r}")
        path = HERE / rel
        if not path.resolve().is_relative_to(HERE) or path.is_symlink():
            fail(f"selected path escapes repository {rel}")
        if not path.is_file():
            fail(f"missing selected file {rel}")
        if path.suffix.lower() in FORBIDDEN:
            fail(f"forbidden selected suffix {rel}")
        data = path.read_bytes()
        if len(data) >= 100 * 1024 * 1024:
            fail(f"selected file exceeds GitHub limit {rel}")
        if len(data) != row.get("bytes") or hashlib.sha256(data).hexdigest() != row.get("sha256"):
            fail(f"selected bytes changed {rel}")
        total += len(data)
        selected.add(rel)
        blob_ids[rel] = hashlib.new(object_format, b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if total != selection.get("selected_bytes"):
        fail("selected byte total mismatch")
    if args.staged:
        result = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], cwd=HERE,
                                check=True, capture_output=True)
        staged = {line.decode("utf-8") for line in result.stdout.split(b"\0") if line}
        expected = selected | {INVENTORY}
        # Previously published V29 files are already in HEAD and therefore do
        # not appear in `git diff --cached`; every newly selected path must be
        # staged, while no unrelated changed path may be staged.
        head = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=HERE,
                              check=True, capture_output=True, text=True)
        head_paths = {line for line in head.stdout.splitlines() if line}
        required_changed = expected - head_paths
        if not required_changed <= staged or not staged <= expected:
            fail(f"staged path set mismatch: extra={sorted(staged-expected)[:5]} missing={sorted(required_changed-staged)[:5]}")
        indexed = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=HERE,
                                 check=True, capture_output=True)
        index_entries = {}
        for entry in indexed.stdout.split(b"\0"):
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            if stage != "0":
                fail("unmerged index entry")
            index_entries[raw_path.decode("utf-8")] = (mode, oid)
        indexed_paths = set(index_entries)
        if not expected <= indexed_paths:
            fail(f"selected path is absent from the index: {sorted(expected-indexed_paths)[:5]}")
        inventory_data = SELECTION.read_bytes()
        blob_ids[INVENTORY] = hashlib.new(object_format, b"blob " + str(len(inventory_data)).encode()
                                        + b"\0" + inventory_data).hexdigest()
        for rel, expected_oid in blob_ids.items():
            mode, actual_oid = index_entries[rel]
            if mode not in {"100644", "100755"} or actual_oid != expected_oid:
                fail(f"index bytes differ from selection {rel}")
        result = subprocess.run(["git", "diff", "--cached", "--check"], cwd=HERE, check=False)
        if result.returncode:
            fail("cached whitespace check failed")
    print(json.dumps({"passed": True, "staged": args.staged, "file_count": len(rows), "selected_bytes": total}))


if __name__ == "__main__":
    main()
