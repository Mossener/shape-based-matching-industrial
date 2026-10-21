#!/usr/bin/env python3
"""Read-only actual-85 development provenance audit; no image decoding or matching.

Only selected development RGB and the selected object's training RGB/mask bytes
are opened. Heldout RGB paths in the index/manifest are never opened. Current
attempt/manifest hashes absent from the original runner are reported as current
semantic cross-checks, not invented historical attestations.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys
import zlib


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CORE = "b25df46f6ddf9c24fb43f5836f1414dc38c8caed"
ALLOWED = [1, 2, 5, 8, 12, 17]
PINS = {
    "line2Dup.cpp": "85b5eb328a3b5cae3e161561e261833873d25a9f57c7457c4410dd21e52083ab",
    "line2Dup.h": "c3a8f742fc897bdcfa83a82a9a025e6b304f410bc081c321695f5e6f7f461fc0",
    "line2Dup_local.hpp": "1b29137fa481b7c1b5f9c210a2d948aef21fc24219ad43fb59e5df91bbe96001",
    "line2Dup_matches.hpp": "80c8d1ee482307a0472a46d7a1e4da868154f2f893fcdc32d53b9be8f35c0344",
    "line2Dup_response.hpp": "33075cfd694488c1b1cb46f8bb821131ed64202f50b5557e4468eea8c0e871a9",
    "line2Dup_search.hpp": "5a92c1c55bb9a2529307c825859136244e2e8ee40b5bde3ca029248d28b8220a",
    "line2Dup_spread.hpp": "fe821b7c9eca784817fac78334020ed34630cc2426254cde9df830db9c524c5e",
    "mipp.h": "7a8c742a19a0797b3340f27e92e6d402669aa7bbc2075d2715d99ebc62202d42",
    "tless_eval.cpp": "c9e4016d1cd7ad6ce37d49bc04f49f1f3d496573a0047a9d1b8da951eb7204ef",
    "eval_metrics.hpp": "1339092b5fbf2f5283dced01fc0b74eea467074223943d8248b89b6e48249de3",
    "build.ps1": "724160300b935fc633cf708acde8904399fd7ea4a932b3ee5c0d6d2005fd3fa4",
}
EXE_PIN = "e9df27dbb815d281c3027018093307fece61b9acececbc75293bfa4f7b01efa6"
HEADER = ["scene", "image", "variant", "class_id", "rank", "score", "template_id",
          "training_image", "angle", "scale", "match_x", "match_y", "bbox_x", "bbox_y", "bbox_w", "bbox_h"]


class AuditError(ValueError):
    pass


def require(value, message):
    if not value:
        raise AuditError(message)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def absolute(root, value):
    path = Path(str(value).replace("\\", "/"))
    return (path if path.is_absolute() else root / path).resolve()


def within(root, relative):
    text = str(relative).replace("\\", "/")
    require(text and not Path(text).is_absolute() and ".." not in Path(text).parts, "Unsafe dataset relative path")
    path = (root / text).resolve()
    require(path.is_relative_to(root), "Dataset path escapes root")
    return path


def load_bytes(data):
    return json.loads(data.decode("utf-8-sig"))


def float32(value):
    value = float(value)
    require(math.isfinite(value), "Nonfinite raw float")
    try:
        bits = struct.pack("<f", value)
    except OverflowError as exc:
        raise AuditError("Raw float32 overflow") from exc
    require(struct.unpack("<f", bits)[0] == value, "Raw decimal is not exact float32")
    return value, bits.hex()


def canonical(row):
    return (-row[0], row[1], row[2], row[4], row[3], row[5][1], row[5][0], row[5][2], row[5][3])


class Verifier:
    def __init__(self, root=ROOT, pins=None, exe_pin=EXE_PIN):
        self.root = root.resolve()
        self.pins = PINS if pins is None else pins
        self.exe_pin = exe_pin
        self.records = {}
        self.dataset_reads = set()
        self.allowed_dataset_reads = set()

    def read(self, path, expected=None, role="metadata", dataset=False):
        path = path.resolve()
        if dataset:
            require(path in self.allowed_dataset_reads, "Attempted read outside selected train/development allowlist")
            self.dataset_reads.add(path)
        data = path.read_bytes()
        digest = sha_bytes(data)
        if expected is not None:
            require(digest == expected.lower(), f"SHA mismatch: {path}")
        old = self.records.get(path)
        require(old is None or old["sha256"] == digest, f"Input changed during audit: {path}")
        roles = set(old["roles"] if old else [])
        roles.add(role)
        self.records[path] = {"path": path.as_posix(), "sha256": digest, "bytes": len(data), "roles": sorted(roles)}
        return data

    def json(self, path, expected=None, role="metadata"):
        return load_bytes(self.read(path, expected, role))

    def current_build(self, build_file, protocol):
        build = self.json(build_file, role="current_public_build")
        require(build["core_git_revision"] == CORE, "Public build is not pinned V11")
        by_name = {}
        for value, expected in build["source_sha256"].items():
            path = absolute(self.root, value)
            name = path.name
            require(name in self.pins and name not in by_name, "Unexpected/duplicate public source pin")
            require(expected.lower() == self.pins[name], f"Wrong frozen source pin: {name}")
            self.read(path, expected, "frozen_public_source")
            by_name[name] = expected.lower()
        require(set(by_name) == set(self.pins), "Incomplete pinned public source list")
        require(protocol["adapter_sha256"] == by_name["tless_eval.cpp"] and
                protocol["metrics_sha256"] == by_name["eval_metrics.hpp"], "Coverage/shared adapter recipe pin differs")
        require(build["executable_sha256"].lower() == self.exe_pin, "Public executable does not match frozen build")
        self.read(build_file.with_name("tless_eval.exe"), self.exe_pin, "public_executable")
        return build

    @staticmethod
    def recipe(config, actual=False):
        shape = {"features": 32, "angle_step": 30, "scales": [.75, 1., 1.5, 2.],
                 "pyramid_T": [4, 8], "weak_threshold": 20, "strong_threshold": 40,
                 "training_border": 16, "input_padding": 64, "nms_iou": .3,
                 "match_iou": .5, "eligible_visibility": .5}
        for name, value in shape.items():
            require(config.get(name) == value, f"Changed frozen recipe: {name}")
        if actual:
            require(config.get("coarse_threshold") == config.get("selected_post_threshold") == 85 and
                    config.get("post_threshold_grid") == [85], "Raw run must use actual85/post85, not coarse50 cache")

    def verify(self, dataset, training, raw, protocol_file, manifest_file=None, build_file=None):
        dataset, training, raw = [absolute(self.root, value) for value in (dataset, training, raw)]
        protocol_file = absolute(self.root, protocol_file)
        protocol = self.json(protocol_file, role="coverage_protocol")
        require(protocol.get("core_revision") == CORE and protocol.get("allowed_split") == "development" and
                protocol.get("allowed_objects") == ALLOWED and protocol.get("forbidden_objects") == [25, 29], "Changed coverage scope")
        require(protocol.get("actual_matcher_threshold") == protocol.get("post_score_threshold") == 85 and
                protocol.get("coverage_policies") == [.5, .65, .8] and protocol.get("radius_l0_pixels") == 2 and
                protocol.get("nms_iou") == .3 and protocol.get("match_iou") == .5, "Changed frozen coverage policy")
        index_file = dataset / "index.json"
        index = self.json(index_file, role="dataset_index")
        tiny = index.get("schema_version", 1) < 2
        require(index.get("schema_version", 1) in (1, 2), "Unsupported dataset schema")
        train_file = training / "training_config.json"
        train = self.json(train_file, role="training_config")
        self.recipe(train)
        objects = train.get("target_objects", [1] if tiny else [])
        require(len(objects) == 1 and objects[0] in ALLOWED and (not tiny or objects == [1]), "Only one allowed development object is supported")
        obj = objects[0]
        class_id = f"tless_object_{obj}"
        if tiny:
            require(index.get("target_object_id") == 1, "Unexpected tiny target")
        else:
            require(index.get("development_objects") == ALLOWED and index.get("strict_object_generalization") == [25, 29], "Changed expanded partition")
        require(absolute(self.root, train["dataset_root"]) == dataset and absolute(self.root, train["training_directory"]) == training, "Training roots differ")
        provenance_file = raw / "execution_provenance.json"
        provenance = self.json(provenance_file, role="raw_execution_provenance")
        require(provenance.get("mode") in ("pilot", "develop") and provenance.get("exit_code") == 0, "Only completed development raw runs are allowed")
        pilot = provenance["mode"] == "pilot"
        require(not (tiny and pilot), "Tiny protocol supports full development only")
        require(provenance.get("opencv_threads") == 1 and provenance.get("openmp_threads") == 4, "Changed baseline thread configuration")
        config_file = raw / ("pilot_config.json" if pilot else "frozen_config.json")
        config = self.json(config_file, role="actual_run_config")
        self.recipe(config, actual=True)
        require(config.get("target_objects") == objects and config.get("evaluation_stage") == ("pilot" if pilot else "development_full") and
                config.get("candidate_equivalence_pass") == 1, "Wrong target/stage or failed raw equality")
        require(absolute(self.root, config["dataset_root"]) == dataset and absolute(self.root, config["training_directory"]) == training, "Raw config roots differ")
        argv = provenance["argv"]
        require(len(argv) % 2 == 0 and len(set(argv[::2])) == len(argv[::2]), "Invalid recorded argv")
        args = dict(zip(argv[::2], argv[1::2]))
        require(args.get("--mode") == provenance["mode"] and absolute(self.root, args.get("--dataset", "")) == dataset and
                absolute(self.root, args.get("--output", "")) == raw and absolute(self.root, args.get("--trained", "")) == training, "Raw argv/config paths differ")
        if "--objects" in args:
            require(args["--objects"] == str(obj), "Raw argv target mismatch")
        require(set(args) <= {"--mode", "--dataset", "--output", "--trained", "--objects"}, "Unexpected raw argv policy override")
        build_file = absolute(self.root, build_file or "artifacts/public_evaluation/build/build_manifest.json")
        build = self.current_build(build_file, protocol)
        require(provenance["build_manifest"] == build, "Raw execution did not use the pinned current public build")
        manifest_file = absolute(self.root, manifest_file or f"artifacts/public_datasets/tless_{'tiny' if tiny else 'expanded'}_manifest.json")
        metadata_file = training / "template_metadata.json"
        bank_file = training / f"templates_{class_id}.yml.gz"
        required_pins = {index_file, manifest_file, build_file, train_file, metadata_file, bank_file}
        historical = {}
        for name, digest in provenance["input_sha256"].items():
            path = absolute(self.root, name)
            require(path not in historical, "Duplicate normalized provenance input path")
            historical[path] = digest
        require(set(historical) == required_pins, "Raw provenance input list differs from approved metadata/bank inputs")
        for path, expected in historical.items():
            self.read(path, expected, "historically_pinned_raw_input")
        manifest = self.json(manifest_file, role="dataset_member_manifest")
        if not tiny:
            require(index.get("plan_sha256") == manifest.get("plan_sha256"), "Expanded index/manifest plan differs")
        training_provenance = self.json(training / "execution_provenance.json", role="training_execution_provenance")
        training_core = training_provenance.get("build_manifest", {}).get("core_git_revision")
        require(training_provenance.get("mode") == "train" and training_provenance.get("exit_code") == 0 and
                training_core in (CORE, "c41f04762fb62ca5598f60e5d66ea9cfa2fbc2a0"), "Unsupported/failed training origin")
        require(tiny or training_core == CORE, "Expanded training must use frozen V11")
        training_pins = {absolute(self.root, name): digest.lower() for name, digest in training_provenance["input_sha256"].items()}
        for path in (index_file, manifest_file):
            require(training_pins.get(path) == self.records[path]["sha256"], "Training/raw dataset identity differs")
        members = {}
        for item in manifest["files"]:
            name = str(item["local_path"]).replace("\\", "/")
            require(name not in members, "Duplicate dataset member manifest path")
            members[name] = item

        # Select before opening any member bytes. Index-only heldout metadata is
        # available for exclusion, but none of those RGB/mask paths is read.
        training_rows = []
        for row in index["training"]:
            targets = [g for g in row["instances"] if g["obj_id"] == obj]
            target = row.get("target_obj_id", row["instances"][0]["obj_id"] if row["instances"] else 0)
            if target != obj:
                continue
            require(len(targets) == 1 and (tiny or row.get("split") == "development"), "Invalid training target/split")
            mask = targets[0].get("mask") or row.get("mask")
            require(isinstance(mask, str) and mask, "No official selected training mask")
            training_rows.append((row, mask))
        require(len(training_rows) == 72 and len({r["image_id"] for r, _ in training_rows}) == 72, "Frozen training view count changed")
        development = [row for row in index["test"] if row["split"] == "development"]
        require(len(development) == (16 if tiny else 400), "Frozen development size changed")
        require(len({(r["scene_id"], r["image_id"]) for r in development}) == len(development), "Duplicate development frame")
        if pilot:
            selected, seen = [], set()
            for row in development:
                if row["scene_id"] not in seen:
                    selected.append(row)
                    seen.add(row["scene_id"])
            require(len(selected) == 8, "Expanded pilot requires first frame of 8 scenes")
        else:
            selected = development
        expected_rgb = {str(r["rgb"]).replace("\\", "/") for r in selected}
        expected_train = {str(value).replace("\\", "/") for row, mask in training_rows for value in (row["rgb"], mask)}
        allowlist = expected_rgb | expected_train
        self.allowed_dataset_reads = {within(dataset, name) for name in allowlist}
        for name in sorted(allowlist):
            require(name in members, f"Selected input absent from member manifest: {name}")
            item = members[name]
            data = self.read(within(dataset, name), item["sha256"], "development_rgb" if name in expected_rgb else "selected_training_rgb_or_mask", dataset=True)
            require(len(data) == item["bytes"], "Selected member byte length mismatch")
            if "archive_crc32" in item:
                require(f"{zlib.crc32(data) & 0xffffffff:08x}" == item["archive_crc32"].lower(), "Selected member CRC mismatch")

        metadata = self.json(metadata_file, role="template_metadata")["templates"]
        require(len(metadata) == train["template_count"] == config["template_count"], "Bank metadata count mismatch")
        meta = {}
        for tid, item in enumerate(metadata):
            cls = item.get("class_id", class_id if tiny else "")
            require(cls == class_id and item["template_id"] == tid, "Metadata class/contiguous ID mismatch")
            require(all(math.isfinite(float(v)) for v in item["warped_mask_bbox"]) and len(item["warped_mask_bbox"]) == 4 and
                    item["warped_mask_bbox"][2] > 0 and item["warped_mask_bbox"][3] > 0, "Invalid metadata bbox")
            meta[(cls, tid)] = item
        attempts_file = training / "template_attempts.csv"
        attempts = list(csv.DictReader(io.StringIO(self.read(attempts_file, role="current_training_attempts_semantic_check").decode("utf-8-sig"))))
        expected_attempts = [(r["image_id"], angle, scale) for r, _ in training_rows for scale in [.75, 1., 1.5, 2.] for angle in range(0, 360, 30)]
        require(len(attempts) == len(expected_attempts) == 3456, "Training attempt count changed")
        successful = 0
        for row, expected in zip(attempts, expected_attempts):
            require(row.get("class_id", class_id if tiny else "") == class_id and
                    (int(row["training_image"]), float(row["angle"]), float(row["scale"])) == expected, "Training attempt recipe/order mismatch")
            require(row["success"] in ("0", "1"), "Invalid attempt status")
            if row["success"] == "1":
                require(int(row["template_id"]) == successful, "Attempt successful IDs shifted")
                item = meta[(class_id, successful)]
                require((item["training_image_id"], item["angle"], item["scale"], item["tl_x"], item["tl_y"]) ==
                        (expected[0], expected[1], expected[2], int(row["templ_tl_x"]), int(row["templ_tl_y"])), "Successful attempt/metadata mismatch")
                require(item["warped_mask_bbox"] == [int(row[k]) for k in ("mask_x", "mask_y", "mask_w", "mask_h")], "Attempt mask box differs")
                require(5 <= int(row["features_l0"]) < 8192 and 5 <= int(row["features_l1"]) < 8192, "Invalid successful feature count")
                successful += 1
            else:
                require(int(row["template_id"]) == -1, "Failed attempt consumed template ID")
        require(successful == len(metadata), "Successful attempt count differs")

        metrics_file = raw / "metrics.json"
        metrics = self.json(metrics_file, role="raw_frame_count_crosscheck")
        self.recipe(metrics, actual=True)
        require(metrics.get("all_frames_exact_candidate_equality") == 1, "Run aggregate equality crosscheck failed")
        metric_frames = metrics["frames"]
        expected_keys = [(r["scene_id"], r["image_id"]) for r in selected]
        require([(r["scene_id"], r["image_id"]) for r in metric_frames] == expected_keys, "Run metric frame set/order differs from frozen selection")
        equality_file = raw / "candidate_equality.csv"
        equality = list(csv.DictReader(io.StringIO(self.read(equality_file, role="raw_equality_crosscheck").decode("utf-8-sig"))))
        require([(int(r["scene"]), int(r["image"])) for r in equality] == expected_keys and
                all(r["exact_multiset_equal"] == "1" for r in equality), "Recorded candidate equality/frame set failed")
        archive_pins = {}
        for archive in provenance["raw_archives"]:
            path = absolute(self.root, archive["path"])
            require(path.parent == raw and path.name not in archive_pins, "Unexpected/duplicate raw archive path")
            archive_pins[path.name] = archive
        expected_names = {f"s{r['scene_id']}_i{r['image_id']}_{v}_raw.csv.gz" for r in selected for v in ("fallback", "fused")}
        require(set(archive_pins) == expected_names, "Incomplete/extra raw archive manifest list")
        frames, total = [], 0
        for source, metric, eq in zip(selected, metric_frames, equality):
            require(metric["split"] == "development" and metric["rgb"] == source["rgb"], "Run frame source differs")
            require(metric.get("fused_raw_count") == metric["raw_count"], "Metric variant counts differ")
            variants, archive_results = {}, {}
            for variant in ("fallback", "fused"):
                name = f"s{source['scene_id']}_i{source['image_id']}_{variant}_raw.csv.gz"
                path = raw / name
                pin = archive_pins[name]
                compressed = self.read(path, pin["sha256"], "historically_pinned_raw_archive")
                require(len(compressed) == pin["bytes"], "Raw compressed byte count differs from provenance")
                try:
                    data = gzip.decompress(compressed)
                except (OSError, EOFError, zlib.error) as exc:
                    raise AuditError("Invalid gzip/CRC") from exc
                manifest_path = raw / name.replace(".csv.gz", "_manifest.json")
                archive_manifest = self.json(manifest_path, role="current_raw_manifest_crosscheck")
                require((archive_manifest["scene_id"], archive_manifest["image_id"], archive_manifest["rgb"], archive_manifest["variant"]) ==
                        (source["scene_id"], source["image_id"], source["rgb"], variant), "Raw per-frame manifest identity differs")
                require(absolute(self.root, archive_manifest["path"]) == path and archive_manifest.get("class_ids") == [class_id] and
                        archive_manifest.get("class_id") == class_id, "Raw manifest class/path mismatch")
                require(len(compressed) == archive_manifest["compressed_bytes"] and len(data) == archive_manifest["uncompressed_bytes"], "Raw manifest byte counts differ")
                reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
                require(reader.fieldnames == HEADER, "Raw gzip CSV schema differs")
                rows, keys = [], set()
                for rank, row in enumerate(reader):
                    require(None not in row and all(value is not None for value in row.values()), "Raw CSV width differs")
                    require((int(row["scene"]), int(row["image"]), row["variant"], int(row["rank"])) ==
                            (source["scene_id"], source["image_id"], variant, rank), "Raw frame/variant/rank differs")
                    score, bits = float32(row["score"])
                    require(85 <= score <= 100 and row["class_id"] == class_id, "Raw class/actual threshold differs")
                    tid, x, y = [int(row[k]) for k in ("template_id", "match_x", "match_y")]
                    require(-(2**31) <= x < 2**31 and -(2**31) <= y < 2**31, "Raw coordinate not C++ int32")
                    require((class_id, tid) in meta, "Unknown raw template identity")
                    item = meta[(class_id, tid)]
                    angle, _ = float32(row["angle"])
                    scale, _ = float32(row["scale"])
                    require((int(row["training_image"]), angle, scale) == (item["training_image_id"], item["angle"], item["scale"]), "Raw training metadata differs")
                    box = tuple(float(row["bbox_" + k]) for k in ("x", "y", "w", "h"))
                    s = item["warped_mask_bbox"]
                    require(all(math.isfinite(v) for v in box) and box == (x - 64 + s[0] - item["tl_x"], y - 64 + s[1] - item["tl_y"], s[2], s[3]), "Raw predicted box differs from frozen transform")
                    converted = (score, class_id, tid, x, y, box, bits)
                    require(not rows or canonical(rows[-1]) <= canonical(converted), "Raw rows are not canonical ordered")
                    key = (class_id, x, y, bits)
                    require(key not in keys, "V11 canonical raw contains duplicate semantic key")
                    keys.add(key)
                    rows.append(converted)
                require(len(rows) == archive_manifest["raw_candidate_count"] == metric["raw_count"] == int(eq[variant + "_count"]), "Raw row/rank/count recovery incomplete")
                variants[variant] = rows
                archive_results[variant] = {"path": path.as_posix(), "manifest": manifest_path.as_posix(), "sha256": sha_bytes(compressed), "rows": len(rows)}
            require(variants["fallback"] == variants["fused"], "Fallback/fused exact float32/class/identity/coordinate/box mismatch")
            require(metric.get("exact_candidate_equality") == 1, "Metric equality crosscheck failed")
            total += len(variants["fallback"])
            width, height = source["width"], source["height"]
            frames.append({"scene_id": source["scene_id"], "image_id": source["image_id"], "rgb": source["rgb"],
                           "width": width, "height": height, "fallback_raw": archive_results["fallback"]["path"],
                           "fused_raw": archive_results["fused"]["path"], "raw_count": len(variants["fallback"]),
                           "padding": [64, 64, 64 + (16 - (width + 128) % 16) % 16, 64 + (16 - (height + 128) % 16) % 16],
                           "archives": archive_results})
        # All recorded inputs, including selected image bytes, must remain stable.
        for path, record in list(self.records.items()):
            require(sha_bytes(path.read_bytes()) == record["sha256"], f"Input changed after read: {path}")
        require(self.dataset_reads == self.allowed_dataset_reads, "Selected member coverage incomplete")
        return {"schema_version": 1, "verified": 1, "split": "development", "dataset_root": dataset.as_posix(),
                "training_directory": training.as_posix(), "raw_directory": raw.as_posix(), "config_file": config_file.as_posix(),
                "target_objects": objects, "dataset_schema": 1 if tiny else 2, "evaluation_stage": config["evaluation_stage"],
                "core_revision": CORE, "protocol_file": protocol_file.as_posix(), "protocol_sha256": sha_bytes(protocol_file.read_bytes()),
                "verifier_sha256": sha_bytes(Path(__file__).read_bytes()), "frames": frames,
                "input_sha256": sorted(self.records.values(), key=lambda r: r["path"]),
                "training": {"views": len(training_rows), "attempts": len(attempts), "successful_templates": len(metadata),
                             "original_core_revision": training_core,
                             "attempts_historical_sha_pinned": 0, "attempts_current_sha_and_success_metadata_crosscheck": 1},
                "raw_rows_per_variant": total, "exact_equality_frames": len(frames),
                "selected_dataset_member_reads": len(self.dataset_reads), "dataset_rgb_decoded": 0,
                "heldout_member_reads": 0, "heldout_matching": 0, "matcher_calls": 0,
                "scope": "Integrity and complete actual85 development candidate recovery only; no coverage score, accuracy result, threshold choice or speed claim",
                "limitations": ["Original raw wrapper pinned config/metadata/bank/archive SHA, not training attempts or per-frame raw manifest SHA; the latter receive current SHA and semantic checks here.",
                                "No image decoding or re-extraction; selected raw member bytes checked against pinned dataset manifest SHA/CRC only.",
                                "Training recipe may carry legacy coarse50 settings; only its shape recipe is reused. Actual matched run is strictly coarse85/post85.",
                                "Tiny bank was originally extracted with V10; raw run pins its exact bytes and V11 actual85 matching. Later reconstruction must compare serialized features, not assume retraining identity.",
                                "Current public build manifest pins mipp.h but not all transitive MIPP headers; audit reports the original recorded source scope."]}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fixture(root, tiny=False, pilot=True, obj=1):
    """Synthetic raw bytes are deliberately not PNGs; no decoder is permitted."""
    root.mkdir(parents=True, exist_ok=False)
    dataset, training, raw = [root / name for name in ("dataset", "training", "raw")]
    for path in (dataset, training, raw):
        path.mkdir()
    source = root / "sources"
    source.mkdir()
    pins, sources = {}, {}
    for name in PINS:
        path = source / name
        path.write_bytes(("synthetic source " + name).encode())
        pins[name] = sha_bytes(path.read_bytes())
        sources[path.as_posix()] = pins[name]
    build_file = root / "build" / "build_manifest.json"
    build_file.parent.mkdir()
    executable = build_file.with_name("tless_eval.exe")
    executable.write_bytes(b"not an executable; fixture never executes it")
    exe_pin = sha_bytes(executable.read_bytes())
    build = {"core_git_revision": CORE, "executable_sha256": exe_pin, "source_sha256": sources}
    write_json(build_file, build)
    protocol = {"core_revision": CORE, "adapter_sha256": pins["tless_eval.cpp"], "metrics_sha256": pins["eval_metrics.hpp"],
                "allowed_split": "development", "allowed_objects": ALLOWED, "forbidden_objects": [25, 29], "actual_matcher_threshold": 85,
                "post_score_threshold": 85, "coverage_policies": [.5, .65, .8], "radius_l0_pixels": 2, "nms_iou": .3, "match_iou": .5}
    protocol_file = root / "protocol.json"
    write_json(protocol_file, protocol)
    class_id = f"tless_object_{obj}"
    member_files = []

    def member(name):
        path = within(dataset, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = ("synthetic member; not a decoded image: " + name).encode()
        path.write_bytes(data)
        member_files.append({"local_path": name, "bytes": len(data), "sha256": sha_bytes(data), "archive_crc32": f"{zlib.crc32(data)&0xffffffff:08x}"})

    train_rows = []
    for image in range(72):
        rgb, mask = f"train/{obj}/rgb/{image}.png", f"train/{obj}/mask/{image}.png"
        member(rgb)
        member(mask)
        train_rows.append({"split": "template" if tiny else "development", "scene_id": obj, "image_id": image,
                           "target_obj_id": obj, "rgb": rgb, "width": 400, "height": 400,
                           "instances": [{"obj_id": obj, "gt_id": 0, "mask": mask}]})
    dev_rows = []
    size = 16 if tiny else 400
    for i in range(size):
        scene, image = (i // 2 + 1, i % 2) if tiny else (i // 50 + 1, i % 50)
        name = f"dev/{scene}/rgb/{image}.png"
        dev_rows.append({"split": "development", "scene_id": scene, "image_id": image, "rgb": name, "width": 19, "height": 17, "instances": []})
    selected = dev_rows if not pilot else [dev_rows[i * 50] for i in range(8)]
    for row in selected:
        member(row["rgb"])
    # The heldout path intentionally does not exist, so any member read fails.
    index = {"schema_version": 1 if tiny else 2, "target_object_id": 1, "development_objects": ALLOWED,
             "strict_object_generalization": [25, 29], "plan_sha256": "fixture-plan", "training": train_rows,
             "test": dev_rows + [{"split": "heldout" if tiny else "heldout_scene", "scene_id": 99, "image_id": 99,
                                  "rgb": "HELDOUT_MUST_NEVER_BE_OPENED.png", "instances": []}]}
    write_json(dataset / "index.json", index)
    manifest_file = root / "dataset_manifest.json"
    write_json(manifest_file, {"plan_sha256": "fixture-plan", "files": member_files})
    shape = {"features": 32, "angle_step": 30, "scales": [.75, 1., 1.5, 2.], "pyramid_T": [4, 8],
             "weak_threshold": 20, "strong_threshold": 40, "training_border": 16, "input_padding": 64,
             "nms_iou": .3, "match_iou": .5, "eligible_visibility": .5,
             "target_objects": [obj], "dataset_root": dataset.as_posix(), "training_directory": training.as_posix(), "template_count": 1}
    train_config = dict(shape, coarse_threshold=50, selected_post_threshold=0, post_threshold_grid=[50, 85])
    if tiny:
        train_config.pop("target_objects")
    write_json(training / "training_config.json", train_config)
    write_json(training / "execution_provenance.json", {"mode": "train", "exit_code": 0, "build_manifest": build,
               "input_sha256": {path.as_posix(): sha_bytes(path.read_bytes()) for path in (dataset / "index.json", manifest_file, build_file)}})
    metadata = {"template_id": 0, "training_image_id": 0, "angle": 0., "scale": .75, "tl_x": 7, "tl_y": 9,
                "warped_mask_bbox": [2., 3., 11., 13.]}
    if not tiny:
        metadata["class_id"] = class_id
    write_json(training / "template_metadata.json", {"templates": [metadata]})
    attempt_header = ["class_id", "training_image", "angle", "scale", "success", "template_id", "templ_tl_x", "templ_tl_y", "mask_x", "mask_y", "mask_w", "mask_h", "features_l0", "features_l1"]
    with (training / "template_attempts.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(attempt_header)
        for image in range(72):
            for scale in [.75, 1., 1.5, 2.]:
                for angle in range(0, 360, 30):
                    success = image == 0 and scale == .75 and angle == 0
                    writer.writerow([class_id, image, angle, scale, int(success), 0 if success else -1, 7, 9, 2, 3, 11, 13, 5, 5])
    bank = training / f"templates_{class_id}.yml.gz"
    bank.write_bytes(gzip.compress(b"fixture bank; hash only", mtime=0))
    config_file = raw / ("pilot_config.json" if pilot else "frozen_config.json")
    write_json(config_file, dict(shape, coarse_threshold=85, selected_post_threshold=85, post_threshold_grid=[85],
                                 evaluation_stage="pilot" if pilot else "development_full", candidate_equivalence_pass=1))
    provenance = {"mode": "pilot" if pilot else "develop", "exit_code": 0, "opencv_threads": 1, "openmp_threads": 4,
                  "argv": ["--mode", "pilot" if pilot else "develop", "--dataset", dataset.as_posix(), "--output", raw.as_posix(), "--trained", training.as_posix()],
                  "build_manifest": build, "input_sha256": {}, "raw_archives": []}
    for path in [dataset / "index.json", manifest_file, build_file, training / "training_config.json", training / "template_metadata.json", bank]:
        provenance["input_sha256"][path.as_posix()] = sha_bytes(path.read_bytes())
    metrics, equality = [], []
    for frame in selected:
        scene, image = frame["scene_id"], frame["image_id"]
        for variant in ("fallback", "fused"):
            stream = io.StringIO()
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(HEADER)
            # Include an empty archive and a noninteger exactly-float32 score.
            count = 0 if scene == 1 and image == 0 else 1
            if count:
                writer.writerow([scene, image, variant, class_id, 0, 85.125, 0, 0, 0, .75, 70, 80, 1, 10, 11, 13])
            data = stream.getvalue().encode()
            path = raw / f"s{scene}_i{image}_{variant}_raw.csv.gz"
            path.write_bytes(gzip.compress(data, mtime=0))
            provenance["raw_archives"].append({"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha_bytes(path.read_bytes())})
            write_json(raw / path.name.replace(".csv.gz", "_manifest.json"), {"scene_id": scene, "image_id": image, "rgb": frame["rgb"], "variant": variant,
                       "class_id": class_id, "class_ids": [class_id], "raw_candidate_count": count, "path": path.as_posix(), "compressed_bytes": path.stat().st_size, "uncompressed_bytes": len(data)})
        metrics.append({"scene_id": scene, "image_id": image, "split": "development", "rgb": frame["rgb"], "raw_count": count, "fused_raw_count": count, "exact_candidate_equality": 1})
        equality.append([scene, image, count, count, 1])
    write_json(raw / "execution_provenance.json", provenance)
    write_json(raw / "metrics.json", dict(shape, coarse_threshold=85, selected_post_threshold=85, post_threshold_grid=[85], frames=metrics, all_frames_exact_candidate_equality=1))
    with (raw / "candidate_equality.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scene", "image", "fallback_count", "fused_count", "exact_multiset_equal"])
        writer.writerows(equality)
    return {"root": root, "pins": pins, "exe_pin": exe_pin,
            "arguments": [dataset, training, raw, protocol_file, manifest_file, build_file]}


def self_test(output):
    root = output.parent / "build" / (output.stem + "_fixtures")
    require(not root.exists(), "Synthetic fixture directory must be fresh")
    root.mkdir(parents=True)
    outcomes = []
    fixtures = []
    for name, tiny, pilot, obj in [("tiny_actual85", True, False, 1), ("expanded_obj1_pilot", False, True, 1),
                                  ("expanded_obj1_full", False, False, 1), ("expanded_obj2_pilot", False, True, 2)]:
        f = fixture(root / name, tiny, pilot, obj)
        fixtures.append(f)
        result = Verifier(f["root"], f["pins"], f["exe_pin"]).verify(*f["arguments"])
        require(result["verified"] == 1 and result["heldout_member_reads"] == 0, "Fixture green failed")
        outcomes.append({"name": name, "expected": "PASS", "actual": "PASS", "frames": len(result["frames"])})
    f = fixtures[1]
    dataset, training, raw, protocol, _, _ = f["arguments"]

    def reject(name, changes):
        saved = {path: path.read_bytes() for path in changes}
        try:
            for path, data in changes.items():
                path.write_bytes(data)
            try:
                Verifier(f["root"], f["pins"], f["exe_pin"]).verify(*f["arguments"])
            except (AuditError, KeyError, ValueError, OSError) as error:
                outcomes.append({"name": name, "expected": "REJECT", "actual": "REJECT", "reason": str(error)})
            else:
                raise AuditError("Mutation unexpectedly accepted: " + name)
        finally:
            for path, data in saved.items():
                path.write_bytes(data)

    def changed_json(path, edit):
        value = load_bytes(path.read_bytes())
        edit(value)
        return json.dumps(value).encode()

    config = raw / "pilot_config.json"
    reject("coarse50_cache", {config: changed_json(config, lambda d: d.update(coarse_threshold=50))})
    reject("post_threshold_changed", {config: changed_json(config, lambda d: d.update(selected_post_threshold=90))})
    reject("coverage_radius_changed", {protocol: changed_json(protocol, lambda d: d.update(radius_l0_pixels=3))})
    reject("reserved_target", {training / "training_config.json": changed_json(training / "training_config.json", lambda d: d.update(target_objects=[25]))})
    reject("heldout_stage", {raw / "execution_provenance.json": changed_json(raw / "execution_provenance.json", lambda d: d.update(mode="final"))})
    reject("failed_equivalence", {config: changed_json(config, lambda d: d.update(candidate_equivalence_pass=0))})
    reject("core_source_changed", {f["root"] / "sources" / "line2Dup.cpp": b"tampered"})
    reject("bank_sha_changed", {training / "templates_tless_object_1.yml.gz": b"tampered"})
    reject("metadata_sha_changed", {training / "template_metadata.json": b"{}"})
    reject("attempt_success_id_changed", {training / "template_attempts.csv": (training / "template_attempts.csv").read_bytes().replace(b"tless_object_1,0,0,0.75,1,0", b"tless_object_1,0,0,0.75,1,1", 1)})
    member = dataset / "dev/1/rgb/0.png"
    reject("selected_member_sha_changed", {member: b"tampered selected development bytes"})
    raw_file = raw / "s2_i0_fallback_raw.csv.gz"
    reject("raw_archive_sha_changed", {raw_file: raw_file.read_bytes() + b"tampered"})
    manifest = raw / "s2_i0_fallback_raw_manifest.json"
    reject("raw_manifest_count_changed", {manifest: changed_json(manifest, lambda d: d.update(raw_candidate_count=2))})
    prov_file = raw / "execution_provenance.json"
    reject("incomplete_raw_archive_list", {prov_file: changed_json(prov_file, lambda d: d["raw_archives"].pop())})
    reject("foreign_rgb_provenance_path", {prov_file: changed_json(prov_file, lambda d: d["input_sha256"].update({str(dataset / "HELDOUT_MUST_NEVER_BE_OPENED.png"): "0" * 64}))})

    def raw_change(name, transform):
        text = gzip.decompress(raw_file.read_bytes()).decode()
        new = gzip.compress(transform(text).encode(), mtime=0)
        prov = raw / "execution_provenance.json"
        def update(d):
            for row in d["raw_archives"]:
                if row["path"] == raw_file.as_posix():
                    row.update(sha256=sha_bytes(new), bytes=len(new))
        reject(name, {raw_file: new, prov: changed_json(prov, update), manifest: changed_json(manifest, lambda d: d.update(compressed_bytes=len(new), uncompressed_bytes=len(transform(text).encode())))})

    raw_change("raw_rank_changed", lambda s: s.replace("fallback,tless_object_1,0,", "fallback,tless_object_1,1,"))
    raw_change("non_float32_decimal", lambda s: s.replace("85.125", "85.123456789"))
    raw_change("fallback_fused_float_bits_changed", lambda s: s.replace("85.125", "85.25"))
    raw_change("raw_box_changed", lambda s: s.replace(",1,10,11,13\n", ",2,10,11,13\n"))
    require(all(item["expected"] == item["actual"] for item in outcomes), "Fixture suite mismatch")
    result = {"schema_version": 1, "passed": 1, "verifier_sha256": sha_bytes(Path(__file__).read_bytes()),
              "green_cases": 4, "rejected_mutations": len(outcomes) - 4, "cases": outcomes,
              "scope": "Synthetic byte files only; no PNG decoding, matcher/coverage calls or real dataset member reads; nonexistent heldout fixture paths prove exclusion"}
    write_json(output, result)
    print(f"PASS synthetic provenance fixtures: 4 valid runs, {len(outcomes)-4} rejected mutations; no dataset images decoded")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--training", type=Path)
    parser.add_argument("--raw-run", type=Path)
    parser.add_argument("--protocol", type=Path, default=HERE / "COVERAGE_PROTOCOL.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    require(not args.output.exists(), "Output must be a fresh JSON file")
    if args.self_test:
        self_test(args.output.resolve())
    else:
        require(args.dataset and args.training and args.raw_run, "Need --dataset, --training and --raw-run")
        result = Verifier().verify(args.dataset, args.training, args.raw_run, args.protocol)
        write_json(args.output, result)
        print(json.dumps({"verified": result["verified"], "target_objects": result["target_objects"], "frames": len(result["frames"]),
                          "raw_rows_per_variant": result["raw_rows_per_variant"], "selected_dataset_member_reads": result["selected_dataset_member_reads"],
                          "dataset_rgb_decoded": 0, "heldout_member_reads": 0, "matcher_calls": 0}))


if __name__ == "__main__":
    try:
        main()
    except (AuditError, KeyError, ValueError, OSError, json.JSONDecodeError) as error:
        print("AUDIT FAILED: " + str(error), file=sys.stderr)
        sys.exit(1)
