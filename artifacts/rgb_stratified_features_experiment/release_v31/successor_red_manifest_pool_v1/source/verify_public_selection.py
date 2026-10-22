"""Verify an explicit V31 publication allowlist without mutating Git or files.

Adapted from artifacts/rgb_dilated_mask_experiment/release_v30/verify_selection.py.
Offline mode reads the named manifest and its selected members only. --staged
additionally inspects the real Git index; source tests mock every Git command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath

HERE = Path(__file__).resolve().parents[3]
SELECTION = HERE / "artifacts/rgb_stratified_features_experiment/PUBLISH_SELECTION_V31.json"
MAX_BYTES = 100 * 1024 * 1024
FORBIDDEN = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif", ".smd",
             ".avif", ".heic", ".ico", ".svg", ".exr", ".tga", ".pgm", ".ppm", ".pbm", ".pnm",
             ".exe", ".com", ".o", ".obj", ".dll", ".pyd", ".so", ".dylib", ".lib", ".a", ".bin",
             ".pdb", ".pyc", ".zip", ".7z", ".tar"}


def fail(message: str) -> None:
    raise SystemExit(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("duplicate JSON key: " + key)
        result[key] = value
    return result


def contained(path: Path, label: str) -> Path:
    path = Path(path)
    if any(part.is_symlink() for part in (path, *path.parents)):
        fail(f"{label} symlink refused")
    resolved = path.resolve()
    if not resolved.is_relative_to(HERE):
        fail(f"{label} escapes repository")
    return resolved


def member_path(rel):
    if (not isinstance(rel, str) or not rel or "\\" in rel or ":" in rel
            or any(ord(c) < 32 or ord(c) == 127 for c in rel)
            or PurePosixPath(rel).is_absolute() or PureWindowsPath(rel).drive
            or any(part in {"", ".", ".."} for part in rel.split("/"))
            or any(part.endswith((" ", ".")) for part in rel.split("/"))
            or PurePosixPath(rel).as_posix() != rel):
        fail(f"invalid path {rel!r}")
    return contained(HERE / rel, "selected path")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--selection", type=Path, default=SELECTION)
    args = parser.parse_args()
    selection_path = contained(args.selection, "selection")
    if not selection_path.is_file() or selection_path.suffix.lower() != ".json":
        fail("missing contained V31 JSON selection")
    if selection_path.stat().st_size >= MAX_BYTES:
        fail("selection exceeds GitHub limit")
    inventory = selection_path.relative_to(HERE).as_posix()
    inventory_data = selection_path.read_bytes()
    selection = json.loads(inventory_data.decode("utf-8-sig"), object_pairs_hook=unique_object,
                           parse_constant=lambda token: fail("nonfinite JSON token: " + token))
    if not isinstance(selection, dict):
        fail("selection object required")
    rows = selection.get("files")
    if (not isinstance(rows, list) or type(selection.get("file_count")) is not int
            or selection["file_count"] != len(rows) or not all(isinstance(row, dict) for row in rows)):
        fail("selection file count mismatch")
    if not all(isinstance(row.get("path"), str) for row in rows):
        fail("invalid path in selection")
    if len({row.get("path") for row in rows}) != len(rows):
        fail("duplicate selected path")
    total = 0
    selected = set()
    object_format = None
    if args.staged:
        object_format = subprocess.run(["git", "rev-parse", "--show-object-format"], cwd=HERE,
                                      check=True, capture_output=True, text=True).stdout.strip()
        if object_format not in {"sha1", "sha256"}:
            fail("unsupported Git object format")
    blob_ids = {}
    for row in rows:
        rel = row.get("path")
        path = member_path(rel)
        if any(suffix.lower() in FORBIDDEN for suffix in path.suffixes):
            fail(f"forbidden selected suffix {rel}")
        if type(row.get("bytes")) is not int or not 0 <= row["bytes"] < MAX_BYTES:
            fail(f"selected file exceeds GitHub limit or has invalid byte count {rel}")
        if not isinstance(row.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", row["sha256"]):
            fail(f"invalid selected SHA256 {rel}")
        if not path.is_file():
            fail(f"missing selected file {rel}")
        if path.stat().st_size >= MAX_BYTES:
            fail(f"selected file exceeds GitHub limit {rel}")
        data = path.read_bytes()
        if len(data) >= MAX_BYTES:
            fail(f"selected file exceeds GitHub limit {rel}")
        if len(data) != row.get("bytes") or hashlib.sha256(data).hexdigest() != row.get("sha256"):
            fail(f"selected bytes changed {rel}")
        total += len(data)
        selected.add(rel)
        if args.staged:
            blob_ids[rel] = hashlib.new(object_format, b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if type(selection.get("selected_bytes")) is not int or total != selection["selected_bytes"]:
        fail("selected byte total mismatch")
    if args.staged:
        result = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], cwd=HERE,
                                check=True, capture_output=True)
        staged = {line.decode("utf-8") for line in result.stdout.split(b"\0") if line}
        expected = selected | {inventory}
        # Previously published files are already in HEAD and therefore do
        # not appear in `git diff --cached`; every newly selected path must be
        # staged, while no unrelated changed path may be staged.
        head = subprocess.run(["git", "ls-tree", "-r", "--name-only", "-z", "HEAD"], cwd=HERE,
                              check=True, capture_output=True)
        head_paths = {line.decode("utf-8") for line in head.stdout.split(b"\0") if line}
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
            rel = raw_path.decode("utf-8")
            if rel in index_entries:
                fail("duplicate index entry")
            index_entries[rel] = (mode, oid)
        indexed_paths = set(index_entries)
        if not expected <= indexed_paths:
            fail(f"selected path is absent from the index: {sorted(expected-indexed_paths)[:5]}")
        if selection_path.read_bytes() != inventory_data:
            fail("selection changed during verification")
        blob_ids[inventory] = hashlib.new(object_format, b"blob " + str(len(inventory_data)).encode()
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
