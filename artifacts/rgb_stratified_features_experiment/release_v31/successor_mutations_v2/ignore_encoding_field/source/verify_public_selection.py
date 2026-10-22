"""Verify V31 public evidence with a manifest-bound numeric pool exception.

Successor of release_v31/verify_selection.py; that frozen source is unchanged.
Only a root-supplied accepted_training_export pin can authorize exact identity
pools_NNNNNN.bin.gz members from the selected complete lossless export.
Offline mode reads selected files only. --staged inspects but never mutates Git.
This verifies publication bindings, not the underlying training/export audit.
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
MAX_STORED_EXPORT = 95 * 1024 * 1024
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


def relative_name(rel):
    if (not isinstance(rel, str) or not rel or "\\" in rel or ":" in rel
            or any(ord(c) < 32 or ord(c) == 127 for c in rel)
            or PurePosixPath(rel).is_absolute() or PureWindowsPath(rel).drive
            or any(part in {"", ".", ".."} for part in rel.split("/"))
            or any(part.endswith((" ", ".")) for part in rel.split("/"))
            or PurePosixPath(rel).as_posix() != rel):
        fail(f"invalid path {rel!r}")
    return rel


def member_path(rel):
    relative_name(rel)
    return contained(HERE / rel, "selected path")


def numeric_pin(value, label, full=False):
    keys = {"bytes", "sha256"} | ({"path"} if full else set())
    if (not isinstance(value, dict) or set(value) != keys
            or type(value.get("bytes")) is not int or value["bytes"] < 0
            or not isinstance(value.get("sha256"), str)
            or not re.fullmatch("[0-9a-f]{64}", value["sha256"])):
        fail(f"invalid {label} pin")
    if full:
        raw = value["path"]
        if (not isinstance(raw, str) or not Path(raw).is_absolute()
                or str(contained(Path(raw), label)) != raw):
            fail(f"noncanonical {label} pin path")
    return value


def export_pool_pins(selection, rows):
    """Validate the selected accepted export before permitting any .bin bytes."""
    if "accepted_training_export" not in selection:
        return {}
    trusted = numeric_pin(selection["accepted_training_export"],
                          "accepted training export", full=True)
    path = contained(Path(trusted["path"]), "accepted training export")
    if path.name != "EXPORT_MANIFEST.json":
        fail("accepted training export must name EXPORT_MANIFEST.json")
    rel = path.relative_to(HERE).as_posix()
    selected = {row["path"]: row for row in rows}
    manifest_row = selected.get(rel)
    if (manifest_row is None
            or {key: manifest_row.get(key) for key in ("bytes", "sha256")}
            != {key: trusted[key] for key in ("bytes", "sha256")}):
        fail("accepted export manifest must be selected with its exact trusted pin")
    if (trusted["bytes"] >= MAX_BYTES or not path.is_file()
            or path.stat().st_size >= MAX_BYTES):
        fail("accepted export manifest missing or exceeds GitHub limit")
    raw = path.read_bytes()
    if (len(raw) >= MAX_BYTES or len(raw) != trusted["bytes"]
            or hashlib.sha256(raw).hexdigest() != trusted["sha256"]):
        fail("accepted export manifest bytes changed")
    manifest = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object,
                          parse_constant=lambda token: fail("nonfinite JSON token: " + token))
    if (not isinstance(manifest, dict)
            or manifest.get("schema") != "rgb_stratified_lossless_training_export_v1"
            or manifest.get("passed") is not True):
        fail("complete accepted training export manifest required")
    members = manifest.get("files")
    if (not isinstance(members, list) or not members
            or type(manifest.get("file_count")) is not int
            or manifest["file_count"] != len(members)):
        fail("export manifest file count differs")
    for name in ("training_provenance", "training_acceptance", "source"):
        numeric_pin(manifest.get(name), "export " + name, full=True)
    originals, stored_names, allowed = set(), set(), {}
    original_bytes = stored_bytes = 0
    for member in members:
        if not isinstance(member, dict):
            fail("export member object required")
        original = relative_name(member.get("original_path"))
        stored = relative_name(member.get("stored_path"))
        if original in originals or stored in stored_names:
            fail("duplicate export original or stored path")
        originals.add(original)
        stored_names.add(stored)
        before = numeric_pin(member.get("original"), "export original")
        saved = numeric_pin(member.get("stored"), "export stored")
        if saved["bytes"] > MAX_STORED_EXPORT:
            fail("export stored member exceeds 95 MiB")
        encoding = "identity"
        if (encoding not in ("identity", "gzip")
                or Path(original).suffix not in (".json", ".jsonl", ".gz")
                or stored != (original + ".gz" if encoding == "gzip" else original)
                or (encoding == "gzip" and Path(original).suffix == ".gz")):
            fail("export member storage mapping differs")
        if encoding == "identity" and before != saved:
            fail("identity export original/stored pins differ")
        target = contained(path.parent / stored, "export member")
        target_rel = target.relative_to(HERE).as_posix()
        selected_member = selected.get(target_rel)
        if (selected_member is None
                or {key: selected_member.get(key) for key in ("bytes", "sha256")} != saved):
            fail("complete export member must be selected with its stored pin")
        suffixes = {suffix.lower() for name in (original, stored)
                    for suffix in Path(name).suffixes}
        forbidden = suffixes & FORBIDDEN
        if forbidden:
            if (forbidden != {".bin"}
                    or not re.fullmatch(r"pools_[0-9]{6}\.bin\.gz", original)
                    or stored != original or encoding != "identity" or before != saved):
                fail("forbidden export member: only exact identity numeric pools permitted")
            allowed[target_rel] = saved
        original_bytes += before["bytes"]
        stored_bytes += saved["bytes"]
    if (type(manifest.get("stored_bytes")) is not int
            or manifest["stored_bytes"] != stored_bytes or stored_bytes > 2 * 1024**3
            or type(manifest.get("original_physical_bytes")) is not int
            or manifest["original_physical_bytes"] != original_bytes):
        fail("export byte accounting differs")
    return allowed


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
    pool_pins = export_pool_pins(selection, rows)
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
        forbidden = {suffix.lower() for suffix in path.suffixes} & FORBIDDEN
        if forbidden and not (forbidden == {".bin"} and path.suffixes == [".bin", ".gz"]
                              and pool_pins.get(rel) == {key: row.get(key) for key in ("bytes", "sha256")}):
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
