#!/usr/bin/env python3
"""Fetch a small, fixed real-image T-LESS slice from official BOP archives.

Only the Python standard library is needed. HTTP Range is mandatory: the large
archives are never downloaded in full. External images stay under datasets/.
This program prepares data and verifies provenance; it does not run a matcher.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import urllib.parse
import urllib.request
import zipfile
import zlib


REVISION = "5fd309a04476a842d93abfb584fba9ee7caecdf1"
HF_BASE = f"https://huggingface.co/datasets/bop-benchmark/tless/resolve/{REVISION}/"
ARCHIVES = {
    "train": {
        "name": "tless_train_primesense.zip",
        "bytes": 2486152818,
        "sha256": "7262fdf0e9de09cf5d051ca108d860c7c5fd563ee58496751e970458c6897ba1",
    },
    "test": {
        "name": "tless_test_primesense_bop19.zip",
        "bytes": 825276992,
        "sha256": "1a18f6bbfb5ac4ced8529f7a35225adfed88c0f62ef38067933e2b541ef1d00b",
    },
}
SOURCES = {
    "dataset_home": "https://cmp.felk.cvut.cz/t-less/",
    "dataset_downloads": "https://cmp.felk.cvut.cz/t-less/download.html",
    "official_bop_listing": "https://bop.felk.cvut.cz/datasets/#T-LESS",
    "bop_format": "https://github.com/thodan/bop_toolkit/blob/master/docs/bop_datasets_format.md",
    "hf_metadata": "https://huggingface.co/api/datasets/bop-benchmark/tless",
    "hf_file_sizes": "https://huggingface.co/api/datasets/bop-benchmark/tless/tree/main?recursive=false",
}
LICENSE = {
    "identifier": "CC-BY-4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "official_statement": "This work is licensed under Creative Commons Attribution 4.0 International.",
    "statement_source": SOURCES["dataset_home"],
    "attribution": (
        "T. Hodan, P. Haluza, S. Obdrzalek, J. Matas, M. Lourakis, X. Zabulis. "
        "T-LESS: An RGB-D Dataset for 6D Pose Estimation of Texture-less Objects. "
        "IEEE WACV, 2017."
    ),
    "notice": "Credit the authors and dataset, link the license, and indicate changes. See the license for complete terms.",
}
# Fixed before running any matcher. The two positive scenes have different
# physical arrangements; scene 9 also contains multiple object-1 instances.
SCENES = {
    5: {"split": "development", "role": "positive"},
    2: {"split": "development", "role": "negative"},
    9: {"split": "heldout", "role": "positive"},
    3: {"split": "heldout", "role": "negative"},
}
FRAME_RANKS = [0, 7, 14, 21, 28, 35, 42, 49]
TRAIN_FRAMES = list(range(0, 1296, 18))
TARGET_ID = 1


def dump_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class RangeClient:
    def __init__(self, limit: int):
        self.limit = limit
        self.transferred = 0
        self.requests: list[dict] = []
        self.resolved: dict[str, str] = {}

    def get(self, archive: str, start: int, length: int) -> bytes:
        spec = ARCHIVES[archive]
        if length <= 0:
            return b""
        if start < 0 or start + length > spec["bytes"]:
            raise ValueError("Requested range is outside the pinned archive")
        if self.transferred + length > self.limit:
            raise RuntimeError(f"Download budget would exceed {self.limit} bytes; stopping before request")
        canonical = HF_BASE + spec["name"]
        url = self.resolved.get(archive, canonical)
        request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{start + length - 1}"})
        with urllib.request.urlopen(request, timeout=90) as response:
            expected_range = f"bytes {start}-{start + length - 1}/{spec['bytes']}"
            if response.status != 206 or response.headers.get("Content-Range") != expected_range:
                raise RuntimeError("Server did not honor the exact HTTP Range; refusing a full archive download")
            data = response.read(length + 1)
            self.transferred += len(data)
            self.requests.append({
                "archive": spec["name"], "start": start, "end_inclusive": start + length - 1,
                "body_bytes": len(data), "status": response.status,
                "resolved_host": urllib.parse.urlsplit(response.url).hostname,
            })
            self.resolved[archive] = response.url
        if len(data) != length:
            raise RuntimeError(f"Truncated HTTP Range: expected {length}, received {len(data)}")
        return data


class RangeFile(io.RawIOBase):
    def __init__(self, client: RangeClient, archive: str):
        self.client, self.archive, self.pos = client, archive, 0
        self.size = ARCHIVES[archive]["bytes"]

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def read(self, size: int = -1) -> bytes:
        size = self.size - self.pos if size < 0 else min(size, self.size - self.pos)
        if size <= 0:
            return b""
        data = self.client.get(self.archive, self.pos, size)
        self.pos += size
        return data


def read_index(client: RangeClient, archive: str) -> dict[str, dict]:
    print(f"Reading {archive} ZIP directory using HTTP Range", flush=True)
    with zipfile.ZipFile(RangeFile(client, archive)) as remote:
        entries = {}
        for item in remote.infolist():
            entries[item.filename] = {
                "path": item.filename, "crc32": item.CRC, "size": item.file_size,
                "compressed_size": item.compress_size, "compression": item.compress_type,
                "header_offset": item.header_offset,
            }
        return entries


def member_from_block(entry: dict, block: bytes, block_offset: int) -> bytes:
    p = entry["header_offset"] - block_offset
    header = block[p:p + 30]
    if len(header) != 30:
        raise RuntimeError("Missing ZIP local header")
    fields = struct.unpack("<4s5H3I2H", header)
    if fields[0] != b"PK\x03\x04" or fields[2] & 1:
        raise RuntimeError("Unsupported ZIP local header")
    filename_length, extra_length = fields[-2:]
    local_name = block[p + 30:p + 30 + filename_length].decode("utf-8")
    if local_name != entry["path"]:
        raise RuntimeError("ZIP local and central filenames differ")
    data_start = p + 30 + filename_length + extra_length
    payload = block[data_start:data_start + entry["compressed_size"]]
    if len(payload) != entry["compressed_size"]:
        raise RuntimeError("ZIP member extends beyond requested range")
    if entry["compression"] == zipfile.ZIP_DEFLATED:
        data = zlib.decompress(payload, -15)
    elif entry["compression"] == zipfile.ZIP_STORED:
        data = payload
    else:
        raise RuntimeError("Unsupported ZIP compression")
    if len(data) != entry["size"] or zlib.crc32(data) & 0xFFFFFFFF != entry["crc32"]:
        raise RuntimeError(f"ZIP size/CRC failure for {entry['path']}")
    return data


def safe_local(root: Path, member: str) -> Path:
    name = PurePosixPath(member)
    if name.is_absolute() or ".." in name.parts or "\\" in member:
        raise ValueError("Unsafe ZIP member path")
    target = root.joinpath(*name.parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("ZIP member escaped the dataset directory")
    return target


def fetch_member(client: RangeClient, archive: str, entry: dict) -> bytes:
    # Read local header first, so there is no assumption about local ZIP extras.
    head = client.get(archive, entry["header_offset"], 30)
    fields = struct.unpack("<4s5H3I2H", head)
    length = 30 + fields[-2] + fields[-1] + entry["compressed_size"]
    block = head + client.get(archive, entry["header_offset"] + 30, length - 30)
    return member_from_block(entry, block, entry["header_offset"])


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Invalid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def annotations(root: Path, prefix: str, image_id: int, gt: dict, gt_info: dict) -> list[dict]:
    rows = []
    poses, info = gt[str(image_id)], gt_info[str(image_id)]
    if len(poses) != len(info):
        raise ValueError("GT pose/info instance counts differ")
    for gt_id, (pose, item) in enumerate(zip(poses, info)):
        mask = f"{prefix}/mask/{image_id:06d}_{gt_id:06d}.png"
        visible = f"{prefix}/mask_visib/{image_id:06d}_{gt_id:06d}.png"
        rows.append({
            "gt_id": gt_id, "obj_id": pose["obj_id"],
            "bbox_obj": item["bbox_obj"], "bbox_visib": item["bbox_visib"],
            "visib_fract": item["visib_fract"],
            "mask": mask if (root / mask).is_file() else None,
            "mask_visib": visible if (root / visible).is_file() else None,
            "eligible_at_visib_0_5": pose["obj_id"] == TARGET_ID and item["visib_fract"] >= 0.5,
        })
    return rows


def build_index(root: Path, scene_frames: dict[int, list[int]]) -> dict:
    result = {
        "schema_version": 1,
        "name": "tless_tiny_object_1_real_exploratory",
        "root": ".", "target_object_id": TARGET_ID,
        "warning": "Tiny exploratory slice; not a full T-LESS benchmark or an estimate of industrial deployment accuracy.",
        "bbox_format": "[x, y, width, height], original RGB pixel coordinates, top-left origin; no image resize",
        "bbox_obj_semantics": "Bounding rectangle of the full projected object silhouette, possibly partly outside the image",
        "bbox_visib_semantics": "Bounding rectangle of the visible part of the projected object silhouette",
        "mask_semantics": "Official BOP object silhouette mask; mask_visib marks the visible part; nonzero means foreground",
        "pose_warning": "The official cam_R_m2c and cam_t_m2c are 3D poses, not 2D angle/scale ground truth; they are deliberately absent here.",
        "training": [], "test": [],
    }
    selections = [("train_primesense", 1, TRAIN_FRAMES, "template", "positive")]
    selections += [("test_primesense", s, scene_frames[s], SCENES[s]["split"], SCENES[s]["role"]) for s in SCENES]
    for partition, scene, frame_ids, split, role in selections:
        prefix = f"{partition}/{scene:06d}"
        gt = json.loads((root / prefix / "scene_gt.json").read_text(encoding="utf-8"))
        info = json.loads((root / prefix / "scene_gt_info.json").read_text(encoding="utf-8"))
        for frame in frame_ids:
            rgb = f"{prefix}/rgb/{frame:06d}.png"
            width, height = png_dimensions(root / rgb)
            instances = annotations(root, prefix, frame, gt, info)
            present = any(a["obj_id"] == TARGET_ID for a in instances)
            if present != (role == "positive"):
                raise ValueError(f"Unexpected target presence in scene {scene}, frame {frame}")
            for item in instances:
                if item["mask"] is not None and png_dimensions(root / item["mask"]) != (width, height):
                    raise ValueError("Mask and RGB dimensions differ")
            row = {
                "split": split, "role": role, "scene_id": scene, "image_id": frame,
                "rgb": rgb, "width": width, "height": height,
                "target_present": present, "instances": instances,
            }
            result["training" if partition == "train_primesense" else "test"].append(row)
    return result


def verify(root: Path, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = safe_local(root, item["local_path"])
        data = path.read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"SHA/size mismatch: {path}")
        if f"{zlib.crc32(data) & 0xFFFFFFFF:08x}" != item["archive_crc32"]:
            raise ValueError(f"CRC mismatch: {path}")
    index = build_index(root, {int(k): v for k, v in manifest["selection"]["test_frame_ids"].items()})
    disk_index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    if index != disk_index:
        raise ValueError("Simplified index differs from the original annotations")
    print(f"Verified {len(manifest['files'])} original archive members, {len(index['training'])} training images, {len(index['test'])} test images", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("datasets/tless_tiny"))
    parser.add_argument("--manifest", type=Path, default=Path("artifacts/public_datasets/tless_tiny_manifest.json"))
    parser.add_argument("--max-download-bytes", type=int, default=190000000)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = args.output.resolve()
    if args.verify_only:
        verify(root, args.manifest)
        return
    if args.manifest.exists() and (root / "index.json").exists():
        print("Existing cache found; verifying offline. Use a separate output and manifest to fetch another copy.", flush=True)
        verify(root, args.manifest)
        return
    root.mkdir(parents=True, exist_ok=True)
    # A local exclusion in the data directory prevents accidental image commits
    # even when the repository's top-level ignore rules do not mention datasets.
    (root / ".gitignore").write_text("*\n", encoding="utf-8")
    client = RangeClient(args.max_download_bytes)
    manifest = {
        "schema_version": 1, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dataset": "T-LESS", "slice": "tiny exploratory object-1 real RGB slice",
        "sources": SOURCES, "license": LICENSE, "huggingface_revision": REVISION,
        "archives": {name: {**spec, "url": HF_BASE + spec["name"], "whole_archive_sha256_verified": False} for name, spec in ARCHIVES.items()},
        "selection": {
            "target_object_id": TARGET_ID, "training_scene_id": 1,
            "training_image_ids": TRAIN_FRAMES,
            "training_rule": "72 evenly spaced training IDs: range(0, 1296, 18)",
            "test_scene_roles": {str(s): v for s, v in SCENES.items()},
            "test_frame_ranks": FRAME_RANKS, "test_frame_ids": {},
            "split_policy": "Different physical scenes for development versus heldout; frames spread over the 50 official BOP19 target frames in each scene. Selection fixed before matcher results.",
        },
        "files": [],
    }

    def save(archive: str, entry: dict, data: bytes) -> None:
        target = safe_local(root, entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest["files"].append({
            "archive": ARCHIVES[archive]["name"], "archive_member": entry["path"],
            "local_path": entry["path"], "archive_crc32": f"{entry['crc32']:08x}",
            "archive_compressed_bytes": entry["compressed_size"],
            "archive_header_offset": entry["header_offset"],
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        })

    train = read_index(client, "train")
    prefix = "train_primesense/000001/"
    scene_start = train[prefix + "scene_camera.json"]["header_offset"]
    scene_end = train["train_primesense/000002/scene_camera.json"]["header_offset"]
    print(f"Fetching object-1 training block: {scene_end - scene_start:,} bytes", flush=True)
    block = client.get("train", scene_start, scene_end - scene_start)
    train_members = [prefix + file for file in ("scene_camera.json", "scene_gt.json", "scene_gt_info.json")]
    for frame in TRAIN_FRAMES:
        train_members += [prefix + f"rgb/{frame:06d}.png", prefix + f"mask/{frame:06d}_000000.png", prefix + f"mask_visib/{frame:06d}_000000.png"]
    for member in train_members:
        save("train", train[member], member_from_block(train[member], block, scene_start))
    del block, train
    print(f"Saved 72 training views; transferred {client.transferred:,} bytes so far", flush=True)

    test = read_index(client, "test")
    scene_frames = {}
    for scene, role in SCENES.items():
        prefix = f"test_primesense/{scene:06d}/"
        for filename in ("scene_camera.json", "scene_gt.json", "scene_gt_info.json"):
            entry = test[prefix + filename]
            save("test", entry, fetch_member(client, "test", entry))
        gt = json.loads((root / prefix / "scene_gt.json").read_text(encoding="utf-8"))
        frames = sorted(map(int, gt))
        if len(frames) != 50:
            raise ValueError("Pinned BOP19 scene no longer has the expected 50 annotated frames")
        selected = [frames[rank] for rank in FRAME_RANKS]
        scene_frames[scene] = selected
        manifest["selection"]["test_frame_ids"][str(scene)] = selected
        rgb_entries = sorted((e for name, e in test.items() if name.startswith(prefix + "rgb/")), key=lambda e: e["header_offset"])
        rgb_offsets = {e["path"]: i for i, e in enumerate(rgb_entries)}
        for frame in selected:
            rgb_entry = test[prefix + f"rgb/{frame:06d}.png"]
            ordinal = rgb_offsets[rgb_entry["path"]]
            start = rgb_entry["header_offset"]
            # Each archive frame block contains RGB, depth and its masks. Fetch
            # it once but retain only RGB and the official instance masks.
            if ordinal + 1 < len(rgb_entries):
                end = rgb_entries[ordinal + 1]["header_offset"]
            else:
                later = [e["header_offset"] for name, e in test.items() if e["header_offset"] > start and not name.startswith(prefix)]
                end = min(later) if later else max(e["header_offset"] + e["compressed_size"] + len(e["path"].encode()) + 30 for e in test.values() if e["path"].startswith(prefix))
            block = client.get("test", start, end - start)
            members = [rgb_entry]
            for gt_id in range(len(gt[str(frame)])):
                members += [test[prefix + f"mask/{frame:06d}_{gt_id:06d}.png"], test[prefix + f"mask_visib/{frame:06d}_{gt_id:06d}.png"]]
            for entry in members:
                save("test", entry, member_from_block(entry, block, start))
        print(f"Saved scene {scene} ({role['split']}, {role['role']}), frames {selected}; total {client.transferred:,} bytes", flush=True)

    index = build_index(root, scene_frames)
    dump_json(root / "index.json", index)
    manifest["files"].sort(key=lambda item: item["local_path"])
    manifest["download"] = {
        "http_range_body_bytes": client.transferred, "request_count": len(client.requests),
        "budget_bytes": client.limit, "requests": client.requests,
        "whole_archives_downloaded": False,
        "accounting": "Exact response body bytes for the successful data HTTP Range requests in this fetch; excludes HTTP/TLS headers and earlier research probes.",
    }
    manifest["summary"] = {
        "training_images": len(index["training"]), "test_images": len(index["test"]),
        "development_images": sum(r["split"] == "development" for r in index["test"]),
        "heldout_images": sum(r["split"] == "heldout" for r in index["test"]),
        "positive_images": sum(r["target_present"] for r in index["test"]),
        "negative_images": sum(not r["target_present"] for r in index["test"]),
        "target_instances": sum(a["obj_id"] == TARGET_ID for r in index["test"] for a in r["instances"]),
        "eligible_target_instances_visib_ge_0_5": sum(a["eligible_at_visib_0_5"] for r in index["test"] for a in r["instances"]),
        "original_archive_members_saved": len(manifest["files"]),
        "original_member_bytes_saved": sum(f["bytes"] for f in manifest["files"]),
    }
    dump_json(args.manifest, manifest)
    (root / "LICENSE-SOURCE.txt").write_text(
        LICENSE["attribution"] + "\n\n" + LICENSE["official_statement"] + "\n" +
        LICENSE["url"] + "\nSource: " + LICENSE["statement_source"] + "\n\n" +
        "Images and original annotations are unchanged archive members. This is a selected subset; index.json is a derived convenience index.\n" +
        "The selection and its SHA/CRC manifest are recorded separately.\n", encoding="utf-8")
    verify(root, args.manifest)
    print(json.dumps({"output": str(root), "manifest": str(args.manifest.resolve()), "download_bytes": client.transferred, **manifest["summary"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
