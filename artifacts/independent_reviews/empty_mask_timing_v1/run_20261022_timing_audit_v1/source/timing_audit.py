"""Independent numeric audit for the V23 fixed timing stage.

This module reads only frozen JSON/CSV/CSV.gz numeric evidence.  It never
opens dataset images, starts the native evaluator, imports target evaluator
code, or uses Git.  The audit checks the native route/order contract, binds
raw/selected counts to the completed development run, recomputes native
nearest-rank quantiles and paired ratios, and emits an additional equal-frame
and equal-object summary.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


OBJECTS = (1, 2, 5, 8, 12, 17)
ARMS = ("rgb", "binary_empty_mask")
PATHS = ("fallback", "fused")
VARIANTS = tuple((arm, path) for arm in ARMS for path in PATHS)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPERIMENT = ROOT / "artifacts/silhouette_empty_mask_experiment"
EXPECTED_CALLS = 12_288
EXPECTED_OBJECT_FRAMES = 384
EXPECTED_FRAMES = 64
FORMAL_ROUNDS = tuple(range(1, 8))
TIMING_HEADER = "object_id,scene,image,round,warmup,order,arm,path,match_ms,external_call_ms,raw,selected,exact_own_reference".split(",")
BANK_HEADER = "object_id,arm,templates,metadata_load_ms,bank_load_ms".split(",")
PER_FRAME_HEADER = "object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp".split(",")
EQUALITY_HEADER = "object_id,scene,image,arm,fallback_count,fused_count,exact_order_fields_score_bits,reference_exact,fallback_match_ms,fused_match_ms,fallback_external_ms,fused_external_ms".split(",")
INPUT_VERSION = "empty_mask_quality_inputs_v1"


class AuditError(ValueError):
    """A fail-closed numeric evidence error."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(value: str) -> str:
    text = str(value).replace("\\", "/")
    path = PurePosixPath(text)
    need(text and not path.is_absolute() and ".." not in path.parts and ":" not in text and str(path) == text,
         "unsafe relative numeric path")
    return text


class Reader:
    """Hash-pinned reader that rejects image bytes and dataset traversal."""

    IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".smd"}

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.seen: dict[str, dict] = {}
        self.pin_indexes: dict[int, dict[str, dict]] = {}

    def allowed(self, path: Path) -> Path:
        resolved = path.resolve(strict=True)
        need(resolved.is_relative_to(self.root), "audit path escaped review root")
        need(resolved.suffix.lower() not in self.IMAGE_SUFFIXES, "image/private material access refused")
        need(not resolved.is_relative_to(self.root / "datasets"), "all dataset byte access refused")
        return resolved

    def read(self, path: Path) -> bytes:
        resolved = self.allowed(path)
        data = resolved.read_bytes()
        pin = {"path": str(resolved), "sha256": digest(data), "bytes": len(data)}
        need(self.seen.setdefault(str(resolved), pin) == pin, "numeric file changed during audit")
        return data

    def json(self, path: Path) -> dict:
        return json.loads(self.read(path).decode("utf-8-sig"))

    def check(self, pin: Mapping) -> bytes:
        path = Path(str(pin["path"]))
        data = self.read(path)
        need(len(data) == int(pin["bytes"]) and digest(data) == pin["sha256"],
             "frozen numeric SHA/size mismatch: " + str(path))
        return data

    def recheck(self) -> None:
        for pin in list(self.seen.values()):
            self.check(pin)

    def index(self, pins: list[dict]) -> dict[str, dict]:
        key = id(pins)
        if key not in self.pin_indexes:
            index = {str(Path(pin["path"])): pin for pin in pins}
            need(len(index) == len(pins), "duplicate pin identity")
            self.pin_indexes[key] = index
        return self.pin_indexes[key]


def integer(value: object, *, minimum: int | None = None, maximum: int | None = None) -> int:
    text = str(value)
    need(re.fullmatch(r"(?:0|[1-9][0-9]*)", text) is not None, "noncanonical nonnegative integer")
    result = int(text)
    if minimum is not None:
        need(result >= minimum, "integer below minimum")
    if maximum is not None:
        need(result <= maximum, "integer above maximum")
    return result


def finite(value: object, *, positive: bool = False) -> float:
    need(type(value) is not bool, "boolean is not a numeric clock")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise AuditError("invalid numeric clock") from error
    need(math.isfinite(result), "non-finite numeric clock")
    need(not positive or result > 0.0, "non-positive numeric clock")
    return result


def csv_rows(data: bytes, header: Sequence[str]) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    need(reader.fieldnames == list(header), "CSV header differs")
    rows = []
    for row in reader:
        need(None not in row and None not in row.values(), "CSV width differs")
        rows.append(row)
    return rows


def nearest_rank(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    need(ordered and all(math.isfinite(value) for value in ordered), "empty/nonfinite quantile input")
    index = max(1, math.ceil(quantile * len(ordered))) - 1
    return ordered[index]


def _close(actual: object, expected: float, where: str) -> None:
    value = finite(actual)
    need(math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12), where + " numeric mismatch")


def expected_timing_frames(inputs: Mapping) -> list[tuple[int, int]]:
    development = inputs.get("development")
    need(isinstance(development, list) and len(development) == 400, "development schedule must contain 400 rows")
    all_keys: set[tuple[int, int]] = set()
    result = []
    for node in development:
        scene = integer(node["scene_id"], minimum=1)
        image = integer(node["image_id"], minimum=0)
        key = (scene, image)
        need(key not in all_keys, "duplicate development frame")
        all_keys.add(key)
        need(type(node.get("timing")) is bool, "timing flag must be a JSON boolean")
        if node["timing"]:
            result.append(key)
    need(len(result) == EXPECTED_FRAMES, "timing schedule must contain 64 frames")
    return result


def expected_bank_templates(inputs: Mapping) -> dict[tuple[int, str], int]:
    banks = inputs.get("rgb_banks")
    need(isinstance(banks, list) and [integer(item["object_id"]) for item in banks] == list(OBJECTS),
         "bank object order differs")
    expected: dict[tuple[int, str], int] = {}
    for item in banks:
        obj = integer(item["object_id"])
        expected[(obj, "rgb")] = integer(item["rgb_template_count"], minimum=1)
        expected[(obj, "binary_empty_mask")] = 3456
    return expected


def parse_development_counts(data: bytes) -> dict[tuple[int, int, int, str], tuple[int, int]]:
    rows = csv_rows(data, PER_FRAME_HEADER)
    result: dict[tuple[int, int, int, str], tuple[int, int]] = {}
    for row in rows:
        key = (integer(row["object_id"], minimum=1), integer(row["scene"], minimum=1),
               integer(row["image"], minimum=0), row["arm"])
        need(key[0] in OBJECTS and key[3] in ARMS and key not in result, "development per-frame identity differs")
        raw, selected = integer(row["raw"], maximum=1000000), integer(row["selected"])
        need(selected <= raw, "development selected exceeds raw count")
        result[key] = (raw, selected)
    need(len(result) == len(OBJECTS) * 400 * len(ARMS), "development per-frame coverage differs")
    return result


def validate_reference_coverage(inputs: Mapping, counts: Mapping, equality_data: bytes) -> None:
    expected = {(obj, integer(row["scene_id"]), integer(row["image_id"]), arm)
                for obj in OBJECTS for row in inputs["development"] for arm in ARMS}
    need(set(counts) == expected, "development references differ from frozen frame scope")
    seen = set()
    for row in csv_rows(equality_data, EQUALITY_HEADER):
        key = (integer(row["object_id"]), integer(row["scene"]), integer(row["image"]), row["arm"])
        need(key in expected and key not in seen, "development equality reference identity differs")
        seen.add(key)
        need(integer(row["fallback_count"]) == integer(row["fused_count"]) == counts[key][0] and
             row["exact_order_fields_score_bits"] == row["reference_exact"] == "1",
             "development own-arm/path equality or raw count differs")
    need(seen == expected, "development equality reference coverage differs")


def _expected_variant(order: int, round_id: int) -> tuple[str, str]:
    return VARIANTS[(order + round_id) % len(VARIANTS)]


def validate_timing_rows(rows: Sequence[Mapping[str, str]], frame_keys: Sequence[tuple[int, int]],
                        development_counts: Mapping[tuple[int, int, int, str], tuple[int, int]],
                        expected_calls: int = EXPECTED_CALLS,
                        objects: Sequence[int] = OBJECTS) -> dict:
    """Validate row route/order and return formal samples grouped for statistics."""
    need(len(rows) == expected_calls, "timing row count differs from 12,288-call budget")
    expected_rows = len(objects) * len(frame_keys) * 8 * 4
    need(expected_rows == expected_calls, "synthetic schedule does not match call budget")
    formal: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_frame: dict[tuple[int, int, int, int], dict[tuple[str, str], dict]] = {}
    index = 0
    for obj in objects:
        for scene, image in frame_keys:
            for round_id in range(8):
                for order in range(4):
                    row = rows[index]
                    index += 1
                    need(integer(row["object_id"]) == obj and integer(row["scene"]) == scene and
                         integer(row["image"]) == image and integer(row["round"]) == round_id and
                         integer(row["order"]) == order, "timing route/order differs")
                    need(integer(row["warmup"]) == int(round_id == 0), "warmup flag differs")
                    arm, path = _expected_variant(order, round_id)
                    need((row["arm"], row["path"]) == (arm, path), "timing variant route differs")
                    match_ms = finite(row["match_ms"], positive=True)
                    external_ms = finite(row["external_call_ms"], positive=True)
                    need(external_ms >= match_ms, "external clock is below match clock")
                    raw = integer(row["raw"], minimum=0, maximum=1000000)
                    selected = integer(row["selected"], minimum=0)
                    need(selected <= raw, "timing selected exceeds raw count")
                    need(row["exact_own_reference"] == "1", "timed call lacks exact own-reference flag")
                    reference_key = (obj, scene, image, arm)
                    need(reference_key in development_counts, "timing own-arm development reference missing")
                    expected_counts = development_counts[reference_key]
                    need((raw, selected) == expected_counts, "timing raw/selected count differs from development")
                    sample = dict(object_id=obj, scene=scene, image=image, round=round_id,
                                  order=order, arm=arm, path=path, match_ms=match_ms,
                                  external_call_ms=external_ms, raw=raw, selected=selected)
                    by_frame.setdefault((obj, scene, image, round_id), {})[(arm, path)] = sample
                    if round_id in FORMAL_ROUNDS:
                        formal[(arm, path)].append(sample)
    expected_formal = len(objects) * len(frame_keys) * 7
    need(index == expected_calls and all(len(formal[key]) == expected_formal for key in VARIANTS),
         "formal timing sample coverage differs")
    for frame_values in by_frame.values():
        need(set(frame_values) == set(VARIANTS), "timing frame does not contain all four variants")
    return {"formal": dict(formal), "by_frame": by_frame}


def validate_bank_rows(data: bytes, expected_templates: Mapping[tuple[int, str], int],
                       objects: Sequence[int] = OBJECTS) -> list[dict]:
    rows = csv_rows(data, BANK_HEADER)
    expected_order = [(obj, arm) for obj in objects for arm in ARMS]
    need(len(rows) == len(expected_order), "bank timing row count differs")
    result = []
    for row, key in zip(rows, expected_order):
        need((integer(row["object_id"]), row["arm"]) == key, "bank timing order differs")
        need(integer(row["templates"], minimum=1) == expected_templates[key], "bank template count differs")
        result.append({"object_id": key[0], "arm": key[1], "templates": expected_templates[key],
                       "metadata_load_ms": finite(row["metadata_load_ms"], positive=True),
                       "bank_load_ms": finite(row["bank_load_ms"], positive=True)})
    return result


def recompute_statistics(groups: Mapping[tuple[str, str], Sequence[Mapping]]) -> tuple[list[dict], list[dict]]:
    variants = []
    for arm, path in VARIANTS:
        values = groups[(arm, path)]
        variants.append({"arm": arm, "path": path, "samples": len(values),
                         "match_median_ms": nearest_rank((x["match_ms"] for x in values), .5),
                         "match_p95_ms": nearest_rank((x["match_ms"] for x in values), .95),
                         "external_median_ms": nearest_rank((x["external_call_ms"] for x in values), .5),
                         "external_p95_ms": nearest_rank((x["external_call_ms"] for x in values), .95)})
    paired = []
    for path in PATHS:
        ratios_match = []
        ratios_external = []
        left = {(x["object_id"], x["scene"], x["image"], x["round"]): x for x in groups[("rgb", path)]}
        right = {(x["object_id"], x["scene"], x["image"], x["round"]): x for x in groups[("binary_empty_mask", path)]}
        need(set(left) == set(right), "paired timing key coverage differs")
        for key in sorted(left):
            ratios_match.append(right[key]["match_ms"] / left[key]["match_ms"])
            ratios_external.append(right[key]["external_call_ms"] / left[key]["external_call_ms"])
        paired.append({"path": path, "samples": len(ratios_match),
                       "match_ratio_median": nearest_rank(ratios_match, .5),
                       "match_ratio_p95": nearest_rank(ratios_match, .95),
                       "external_ratio_median": nearest_rank(ratios_external, .5),
                       "external_ratio_p95": nearest_rank(ratios_external, .95)})
    return variants, paired


def _summary_match(actual: Mapping, expected: Mapping, where: str) -> None:
    for key, expected_value in expected.items():
        need(key in actual, where + " missing " + key)
        if isinstance(expected_value, float):
            _close(actual[key], expected_value, where + "/" + key)
        elif isinstance(expected_value, int):
            need(type(actual[key]) in (int, float) and actual[key] == expected_value,
                 where + "/" + key + " differs")
        else:
            need(actual[key] == expected_value, where + "/" + key + " differs")


def validate_stage_summary(summary: Mapping, variants: Sequence[Mapping], paired: Sequence[Mapping]) -> None:
    _summary_match(summary, {"passed": 1, "stage": "timing", "objects": list(OBJECTS),
                             "unique_frames": 64, "object_frame_combinations": 384,
                             "matcher_calls": 12288, "warmup_rounds": 1, "measured_rounds": 7,
                             "exact_own_reference_every_call": 1,
                             "decode_and_bank_load_excluded_from_external_call": 1,
                             "paired_performance_benchmark": 1}, "stage_summary")
    finite(summary.get("decode_total_ms"), positive=True)
    rss = finite(summary.get("peak_rss_bytes"), positive=True)
    need(rss.is_integer() and rss <= 1_610_612_736, "timing peak RSS violates fixed resource bound")
    actual_variants = summary.get("variants")
    actual_paired = summary.get("paired_binary_over_rgb")
    need(isinstance(actual_variants, list) and isinstance(actual_paired, list), "timing summary arrays missing")
    need(len(actual_variants) == 4 and len(actual_paired) == 2, "timing summary array count differs")
    for index, expected in enumerate(variants):
        _summary_match(actual_variants[index], expected, "stage_summary/variants[%d]" % index)
    for index, expected in enumerate(paired):
        _summary_match(actual_paired[index], expected, "stage_summary/paired_binary_over_rgb[%d]" % index)


def additional_equal_frame_summary(by_frame: Mapping[tuple[int, int, int, int], Mapping],
                                   objects: Sequence[int] = OBJECTS,
                                   expected_frames: int = EXPECTED_FRAMES) -> dict:
    """Compute frame-pair medians, then equal-frame/object summaries.

    Seven formal samples are reduced per frame by nearest-rank median.  Pair
    ratios are formed at each round before taking their frame median; this is
    explicitly different from a ratio of medians and from the native pooled
    call quantiles.
    """
    frames: dict[tuple[int, int, int, str], dict] = {}
    for (obj, scene, image, round_id), values in by_frame.items():
        if round_id not in FORMAL_ROUNDS:
            continue
        key = (obj, scene, image, "formal")
        entry = frames.setdefault(key, {"samples": defaultdict(lambda: {"match": [], "external": []})})
        for variant, sample in values.items():
            entry["samples"][variant]["match"].append(sample["match_ms"])
            entry["samples"][variant]["external"].append(sample["external_call_ms"])
    frame_values = []
    for (obj, scene, image, _), entry in sorted(frames.items()):
        metrics = {}
        for variant in VARIANTS:
            metrics[variant] = {"match_median_ms": nearest_rank(entry["samples"][variant]["match"], .5),
                                "external_median_ms": nearest_rank(entry["samples"][variant]["external"], .5)}
        ratios = {}
        for path in PATHS:
            match = [entry["samples"][("binary_empty_mask", path)]["match"][i] /
                     entry["samples"][("rgb", path)]["match"][i] for i in range(7)]
            external = [entry["samples"][("binary_empty_mask", path)]["external"][i] /
                        entry["samples"][("rgb", path)]["external"][i] for i in range(7)]
            ratios[path] = {"match_ratio_median": nearest_rank(match, .5),
                            "external_ratio_median": nearest_rank(external, .5)}
        frame_values.append({"object_id": obj, "scene": scene, "image": image,
                             "variants": {f"{arm}/{path}": metrics[(arm, path)] for arm, path in VARIANTS},
                             "paired_binary_over_rgb": ratios})
    need(len(frame_values) == len(objects) * expected_frames, "equal-frame summary coverage differs")
    per_object = []
    for obj in objects:
        subset = [item for item in frame_values if item["object_id"] == obj]
        need(len(subset) == expected_frames, "equal-frame per-object coverage differs")
        per_object.append(_average_frame_items(subset, obj))
    overall = _average_object_items(per_object)
    return {"definition": "formal seven-round nearest-rank frame medians; paired ratio per round then frame median; equal frame then equal object means; distinct from native pooled quantiles",
            "frame_medians": frame_values, "per_object": per_object, "equal_object_overall": overall}


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return math.fsum(values) / len(values)


def _average_frame_items(items: Sequence[Mapping], obj: int) -> dict:
    variants = {key: {"mean_frame_" + field: _mean(item["variants"][key][field] for item in items)
                      for field in ("match_median_ms", "external_median_ms")}
                for key in items[0]["variants"]}
    paired = {path: {"mean_frame_" + field: _mean(item["paired_binary_over_rgb"][path][field] for item in items)
                     for field in ("match_ratio_median", "external_ratio_median")}
              for path in PATHS}
    return {"object_id": obj, "frames": len(items), "variants": variants, "paired_binary_over_rgb": paired}


def _average_object_items(items: Sequence[Mapping]) -> dict:
    variants = {key: {field: _mean(item["variants"][key][field] for item in items)
                      for field in ("mean_frame_match_median_ms", "mean_frame_external_median_ms")}
                for key in items[0]["variants"]}
    paired = {path: {field: _mean(item["paired_binary_over_rgb"][path][field] for item in items)
                     for field in ("mean_frame_match_ratio_median", "mean_frame_external_ratio_median")}
              for path in PATHS}
    return {"objects": len(items), "variants": variants, "paired_binary_over_rgb": paired}


def _pin_stage(reader: Reader, freeze_path: Path, expected_stage: str, expected_calls: int,
               *, verify_all_files: bool = True) -> tuple[dict, Path]:
    freeze_path = freeze_path.resolve(strict=True)
    freeze = reader.json(freeze_path)
    need(freeze.get("stage") == expected_stage and freeze.get("completed") is True and
         freeze.get("native_exit_code") == 0 and freeze.get("actual_matcher_calls") == expected_calls and
         freeze.get("maximum_matcher_calls") == expected_calls and freeze.get("post_verification_passed") is True and
         freeze.get("heldout_images_allowed") is False and freeze.get("missing_frames_are_not_negatives") is True,
         expected_stage + " stage closure differs")
    native = freeze_path.parent / "native"
    pins = freeze.get("files", [])
    paths = [str(Path(item["path"])) for item in pins]
    need(len(set(paths)) == len(paths) and all(Path(path).is_absolute() and Path(path).is_relative_to(native) for path in paths),
         expected_stage + " duplicate/outside native output pin")
    if verify_all_files:
        actual_files = {str(path.resolve()) for path in native.rglob("*") if path.is_file() and path.name != ".gitignore"}
        need(actual_files == set(paths), expected_stage + " native output inventory differs")
        execution_paths = [str(Path(item["path"]).resolve()) for item in freeze["execution_files"]]
        need(len(set(execution_paths)) == len(execution_paths) and
             set(execution_paths) == {str(path.resolve()) for path in freeze_path.parent.iterdir()
                                      if path.is_file() and path != freeze_path}, "execution output inventory differs")
        if expected_stage == "timing":
            need({Path(path).name for path in execution_paths} ==
                 {"execution_provenance.json", "native.stdout", "native.stderr", "verified_before.json", "verified_after.json"},
                 "timing execution output must contain exactly five receipt/log files")
        for item in pins + freeze["execution_files"]:
            reader.check(item)
    return freeze, native


def validate_timing_output_files(native: Path) -> None:
    wanted = {str((native / name).resolve()) for name in
              ("bank_load_timings.csv", "stage_summary.json", "timing_samples.csv")}
    actual = {str(path.resolve()) for path in native.rglob("*") if path.is_file() and path.name != ".gitignore"}
    need(actual == wanted, "timing native output must contain exactly three numeric files")


def _frozen_references(reader: Reader) -> tuple[dict, dict[str, dict]]:
    origin = reader.json(HERE / "ORIGIN.json")
    result = {}
    for key, value in origin["frozen_references"].items():
        pin = {"path": str(ROOT / safe_relative(value["relative_path"])),
               "sha256": value["sha256"], "bytes": value["bytes"]}
        reader.check(pin)
        result[key] = pin
    need(set(result) == {"quality_inputs", "build_manifest", "development", "selftest", "development_audit"},
         "reviewed frozen reference set differs")
    return origin, result


def _stage_read(reader: Reader, stage: Mapping, path: Path, prior_audit: Mapping | None = None) -> bytes:
    resolved = str(path)
    pin = reader.index(stage["files"]).get(resolved)
    need(pin is not None, "numeric file missing from stage pin inventory")
    if prior_audit is not None:
        prior = reader.index(prior_audit["input_pins"]).get(resolved)
        need(prior == pin, "development file not bound to prior independent audit")
    return reader.check(pin)


def validate_execution(reader: Reader, stage: Mapping, stage_path: Path,
                       native: Path, pins: Mapping[str, Mapping]) -> None:
    need(stage["build_manifest"] == pins["build_manifest"] and stage["quality_inputs"] == pins["quality_inputs"] and
         stage["selftest"] == pins["selftest"] and stage["previous_stage"] == pins["development"],
         "timing stage reviewed source/reference bindings differ")
    execution = reader.json(stage_path.parent / "execution_provenance.json")
    expected_command = [str(EXPERIMENT / "build_quality_v1/quality_eval.exe"), "--mode", "timing", "--output", str(native),
                        "--inputs", pins["quality_inputs"]["path"], "--previous", str(Path(pins["development"]["path"]).parent / "native")]
    need(execution["command"] == expected_command and execution["mode"] == "timing" and
         execution["native_exit_code"] == 0 and execution["maximum_matcher_calls"] == EXPECTED_CALLS,
         "timing execution command/mode/count differs")
    for field in ("build_manifest", "quality_inputs", "selftest", "previous_stage", "reservation"):
        need(execution[field] == stage[field], "execution stage binding differs: " + field)
    expected_scripts = [str(EXPERIMENT / name) for name in
                        ("run_quality.py", "quality_contract.py", "prepare_quality_inputs.py",
                         "prepare_input_closure.py", "native_provenance.py")]
    need([pin["path"] for pin in execution["script_pins"]] == expected_scripts, "timing execution script scope differs")
    for pin in execution["script_pins"]:
        reader.check(pin)
    reservation = json.loads(reader.check(stage["reservation"]))
    need(reservation == {"stage": "timing", "run": str(stage_path.parent), "maximum_calls": EXPECTED_CALLS,
                         "previous_stage": "development", "previous_freeze": pins["development"],
                         "total_protocol_maximum": 22176,
                         "policy": "One attempt per fixed stage; reservation survives failure; missing frames are never negatives"},
         "timing reservation differs")
    before = reader.json(stage_path.parent / "verified_before.json")
    after = reader.json(stage_path.parent / "verified_after.json")
    need(before == after and before["inputs"]["passed"] is True and
         before["inputs"]["quality_input_freeze"] == pins["quality_inputs"] and before["images"]["passed"] is True and
         before["images"]["image_phase"] == "development" and before["images"]["image_files_opened"] == 400,
         "timing pre/post verification receipt differs")


def audit(stage_freeze: Path, development_freeze: Path, output: Path) -> dict:
    """Audit a completed timing stage into a fresh contained output folder."""
    stage_freeze = stage_freeze.resolve(strict=True)
    development_freeze = development_freeze.resolve(strict=True)
    need(stage_freeze.is_relative_to(EXPERIMENT) and stage_freeze.name == "QUALITY_STAGE_FREEZE.json",
         "timing stage must belong to the fixed experiment")
    need(output.resolve().is_relative_to(HERE.resolve()) and not output.exists(), "fresh audit output required inside timing review")
    output.mkdir(parents=True)
    # The reader root is the repository root, but only numeric files below it
    # are read.  Image suffixes are refused before bytes are opened.
    reader = Reader(ROOT)
    origin, frozen = _frozen_references(reader)
    source_paths = sorted(HERE.glob("*.py")) + sorted(HERE.glob("*.md")) + [HERE / "ORIGIN.json"]
    for source in source_paths:
        reader.read(source)
    need(str(development_freeze) == frozen["development"]["path"], "unexpected development freeze")
    stage, timing_native = _pin_stage(reader, stage_freeze, "timing", EXPECTED_CALLS)
    development, development_native = _pin_stage(reader, development_freeze, "development", 9600, verify_all_files=False)
    validate_timing_output_files(timing_native)
    validate_execution(reader, stage, stage_freeze, timing_native, frozen)
    need(stage["quality_inputs"] == development["quality_inputs"], "timing/development input freeze differs")
    quality_inputs_path = Path(stage["quality_inputs"]["path"])
    inputs = reader.json(quality_inputs_path)
    need(inputs.get("version") == INPUT_VERSION and inputs.get("objects") == list(OBJECTS) and
         inputs.get("total_matcher_call_budget") == 22176 and inputs.get("dataset_image_reads") == 0 and
         inputs.get("image_decodes") == 0 and inputs.get("matcher_calls") == 0, "quality input scope differs")
    frame_keys = expected_timing_frames(inputs)
    expected_templates = expected_bank_templates(inputs)
    prior_audit = reader.json(Path(frozen["development_audit"]["path"]))
    need(prior_audit["passed"] is True and prior_audit["stage"] == "development" and
         prior_audit["matcher_calls"] == prior_audit["image_decodes"] == 0 and
         prior_audit["object_frame_pairs"] == 2400 and prior_audit["independent_of_target_evaluator_imports"] is True,
         "prior independent development quality audit is incomplete")
    need(reader.index(prior_audit["input_pins"]).get(str(development_freeze)) == frozen["development"],
         "prior independent audit development-freeze binding differs")
    development_counts = parse_development_counts(_stage_read(reader, development,
        development_native / "per_frame_metrics.csv", prior_audit))
    validate_reference_coverage(inputs, development_counts, _stage_read(reader, development,
        development_native / "candidate_equality.csv", prior_audit))
    # Verify all timing-frame raw manifests against development metadata.  The
    # archive payload itself is not needed for a count/route audit and remains
    # gzip numeric evidence; no image bytes are read.
    for obj in OBJECTS:
        for scene, image in frame_keys:
            for arm in ARMS:
                for path in PATHS:
                    manifest_path = development_native / f"obj{obj}" / arm / f"s{scene}_i{image}_{path}_raw_manifest.json"
                    manifest = json.loads(_stage_read(reader, development, manifest_path, prior_audit))
                    need((manifest["scene_id"], manifest["image_id"], manifest["variant"]) == (scene, image, path),
                         "development raw manifest identity differs")
                    need(manifest["class_id"] == "tless_object_" + str(obj) and
                         manifest["class_ids"] == ["tless_object_" + str(obj)], "development raw manifest class differs")
                    need(manifest["raw_candidate_count"] == development_counts[(obj, scene, image, arm)][0],
                         "development raw manifest count differs")
    timing_rows = csv_rows(reader.read(timing_native / "timing_samples.csv"), TIMING_HEADER)
    grouped = validate_timing_rows(timing_rows, frame_keys, development_counts)
    bank_rows = validate_bank_rows(reader.read(timing_native / "bank_load_timings.csv"), expected_templates)
    variants, paired = recompute_statistics(grouped["formal"])
    summary = reader.json(timing_native / "stage_summary.json")
    need(stage["summary"] == summary, "timing freeze/native summary differs")
    validate_stage_summary(summary, variants, paired)
    additional = additional_equal_frame_summary(grouped["by_frame"])
    order_counts = {}
    for arm, path in VARIANTS:
        order_counts[arm + "/" + path] = {str(order): sum(row["order"] == order for row in grouped["formal"][(arm, path)])
                                          for order in range(4)}
    result = {"schema_version": 1, "passed": True, "stage": "timing", "objects": list(OBJECTS),
              "unique_frames": len(frame_keys), "object_frame_pairs": EXPECTED_OBJECT_FRAMES,
              "native_matcher_calls": 0, "image_decodes_in_audit": 0,
              "native_output_files": ["bank_load_timings.csv", "stage_summary.json", "timing_samples.csv"],
              "timing_rows": len(timing_rows), "formal_rows": len(timing_rows) - len(OBJECTS) * len(frame_keys) * 4,
              "bank_rows": bank_rows, "native_variants": variants, "native_paired_binary_over_rgb": paired,
              "formal_order_position_counts": order_counts,
              "additional_equal_frame_pair_median": additional,
              "limitations": ["Timed raw/selected full fields are not archived; exact_own_reference flags and development count binding are audited, but timed full-field equality is not independently reconstructed.",
                              "Timing excludes image decode, bank load, CSV output and own-reference comparison; rounds reuse workspaces and do not represent cold-start latency.",
                              "Seven formal rounds have unequal order-position counts after the first round is removed as warmup.",
                              "Additional frame/object means are distinct from native pooled nearest-rank quantiles.",
                              "Development quality/raw/NMS correctness is inherited from the hash-pinned completed independent V22 audit; this timing audit does not rerun that quality audit."],
              "quality_inputs": stage["quality_inputs"], "timing_stage_freeze": {"path": str(stage_freeze), "sha256": digest(stage_freeze.read_bytes()), "bytes": stage_freeze.stat().st_size},
              "development_stage_freeze": frozen["development"],
              "prior_independent_development_audit": frozen["development_audit"]}
    (output / "source").mkdir()
    source_pins = []
    for source in source_paths:
        data = reader.read(source)
        source_pins.append(reader.seen[str(source.resolve())])
        (output / "source" / source.name).write_bytes(data)
    reader.recheck()
    result["source_pins"] = source_pins
    result["input_pins"] = list(reader.seen.values())
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-freeze", type=Path, required=True)
    parser.add_argument("--development-freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-slot-granted", action="store_true")
    args = parser.parse_args()
    need(args.cpu_slot_granted, "numeric audit awaits coordinated CPU slot after native timing")
    output = args.output.resolve()
    was_absent = not output.exists()
    try:
        result = audit(args.stage_freeze, args.development_freeze, output)
    except Exception as error:
        if was_absent and output.is_relative_to(HERE) and output.is_dir():
            (output / "failure.json").write_text(json.dumps({"incomplete": True, "reason": str(error),
                "native_matcher_calls": 0, "image_decodes_in_audit": 0,
                "no_timing_claim_from_partial_evidence": True}, indent=2) + "\n", encoding="utf-8")
        raise
    print(json.dumps({key: result[key] for key in ("passed", "stage", "timing_rows", "formal_rows", "native_matcher_calls", "image_decodes_in_audit")}))


if __name__ == "__main__":
    main()
