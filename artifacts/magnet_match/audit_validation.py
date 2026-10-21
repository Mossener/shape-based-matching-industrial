"""Read-only independent consistency audit for the supplied magnet regression."""
import argparse
import csv
import hashlib
import importlib.util
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run):
    from PIL import Image

    provenance = read_json(run / "provenance.json")
    checks = {}
    for group in ("input_sha256", "source_sha256"):
        checks[group] = []
        for name, expected in provenance[group].items():
            path = Path(name)
            if not path.is_absolute():
                path = ROOT / path
            actual = sha256(path)
            assert actual.lower() == expected.lower(), name
            checks[group].append({"path": name, "sha256": actual})

    checks["frozen_harness"] = []
    for name in ("magnet_demo.cpp", "inspect_smd.py", "evaluate.py", "run.ps1"):
        path = run / "source" / name
        actual = sha256(path)
        expected = provenance["source_sha256"]["artifacts/magnet_match/" + name]
        assert actual.lower() == expected.lower(), name
        checks["frozen_harness"].append({"path": str(path.relative_to(ROOT)), "sha256": actual})

    manifest = read_json(BASE / "smd_manifest.json")
    checks["original_inputs"] = []
    for item in manifest["inputs"]:
        original, copied = ROOT / item["path"], ROOT / item["ascii_copy"]
        actual = sha256(original)
        assert actual == item["sha256"] == sha256(copied)
        checks["original_inputs"].append({"path": item["path"], "sha256": actual})

    smd = (ROOT / manifest["inputs"][0]["path"]).read_bytes()
    assert smd[:4] == b"SMD\0" and len(smd) == 652672
    assert struct.unpack_from("<4I", smd, 4) == (121, 108, 535, 383)
    offset = 20
    embedded = None
    for _ in range(2):
        version, width, height, channels, stride, size = struct.unpack_from("<6I", smd, offset)
        assert (version, width, height, channels, stride, size) == (20161201, 640, 480, 1, 640, 307200)
        if embedded is None:
            embedded = smd[offset + 24:offset + 24 + size]
        offset += 24 + size
    assert offset == manifest["model_offset"] == 614468
    assert struct.unpack_from("<I", smd, offset)[0] == 20171201
    assert struct.unpack_from("<I", smd, offset + 48)[0] == 6
    offset += 52
    for level in manifest["levels"]:
        kind, number, width, height, count = struct.unpack_from("<5I", smd, offset)
        assert (kind, number, width, height, count) == (2, level["level"], level["width"], level["height"], level["point_count"])
        offset += 20 + count * 16
        assert offset == level["end_offset"]
    assert offset == len(smd)
    source = Image.open(ROOT / manifest["inputs"][1]["path"]).convert("L")
    assert source.size == (640, 480) and source.tobytes() == embedded

    with (run / "padding_preflight.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6120
    for row in rows:
        level = int(row["level"])
        tw, th, border = (int(row[k]) for k in ("template_width", "template_height", "border"))
        pw, ph = (int(row[k]) for k in ("padded_width", "padded_height"))
        max_x, max_y = (int(row[k]) for k in ("max_x", "max_y"))
        assert max_x == (pw >> level) - tw - border
        assert max_y == (ph >> level) - th - border
        assert int(row["required_full_width"]) == (tw + 2 * border) * (1 << level)
        assert int(row["required_full_height"]) == (th + 2 * border) * (1 << level)
        assert row["feasible"] == "1" and max_x >= border and max_y >= border

    spec = importlib.util.spec_from_file_location("magnet_evaluator", BASE / "evaluate.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    evaluator.selftest()
    prediction = lambda box, score, tid: dict(box=box, score=score, template_id=tid,
                                            match_x=box[0], match_y=box[1])
    a = prediction([0, 0, 13, 10], 99, 0)
    b = prediction([7, 0, 13, 10], 98, 1)
    assert evaluator.iou(a["box"], b["box"]) == .3
    assert len(evaluator.nms([a, b], .3)) == 2  # IoU exactly at threshold survives.
    b["box"][0] = 6.999
    assert len(evaluator.nms([a, b], .3)) == 1
    duplicates = [prediction([0, 0, 10, 10], 99, 0), prediction([0, 0, 10, 10], 98, 1)]
    assert evaluator.count(duplicates, [[0, 0, 10, 10]]) == dict(tp=1, fp=1, fn=0, gt=1)
    assert evaluator.count([prediction([0, 0, 5, 10], 99, 0)], [[0, 0, 10, 10]])["tp"] == 1

    report = read_json(run / "coarse_localization.json")
    assert report["annotation_sha256"] == sha256(BASE / "manual_boxes.json")
    assert report["raw_csv_sha256"] == sha256(run / "matcher_candidates.csv")
    assert report["results_csv_sha256"] == sha256(run / "results.csv")
    assert report["evaluator_sha256"] == sha256(BASE / "evaluate.py")
    assert sum(item["raw_count"] for item in report["images"]) == 23
    assert sum(item["raw_duplicate_hypotheses"] for item in report["images"]) == 16
    assert sum(item["after_nms"] for item in report["images"]) == 7
    with (run / "results.csv").open(newline="") as handle:
        frames = list(csv.DictReader(handle))
    assert len(frames) == len(report["images"]) == 7
    for row, item in zip(frames, report["images"]):
        assert row["image"] == item["image"]
        assert int(row["candidates"]) == item["raw_count"]
        assert abs(float(row["score"]) - item["detections"][0]["score"]) < 1e-6
        assert item["counts"] == dict(tp=1, fp=0, fn=0, gt=1)

    return dict(
        purpose="Independent consistency audit; no matcher execution or performance estimate",
        run=str(run.relative_to(ROOT)), audit_sha256=sha256(Path(__file__)),
        checks=checks, smd_structure_independently_read=True, source_image_equal=True,
        preflight_rows=len(rows), preflight_formula_recalculated=True, all_preflight_feasible=True,
        required_width=max(int(row["required_full_width"]) for row in rows),
        required_height=max(int(row["required_full_height"]) for row in rows),
        literal_iou_nms_count_checks=True, exact_nms_boundary_checked=True,
        one_to_one_duplicate_checked=True, equality_match_iou_checked=True,
        raw_candidates=23, raw_duplicate_hypotheses=16, nms_detections=7,
        source_selfcheck=report["groups"]["source_selfcheck"],
        same_group_non_source=report["groups"]["non_source_regression"],
        coarse_csv_report_consistent=True,
        limitation="Observed supplied positives only; not heldout, no negative set, no industrial accuracy/speed claim")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=BASE / "run_20261021_scale_coverage")
    parser.add_argument("--output", type=Path, default=BASE / "INDEPENDENT_VALIDATION.json")
    args = parser.parse_args()
    result = audit(args.run.resolve())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: original/input/source/snapshot SHA, SMD structure/source image, 6120 preflight rows, exact NMS/count boundaries, CSV/report consistency")
