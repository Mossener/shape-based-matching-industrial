"""Independent stdlib-only source and numeric evidence review; no target imports.

Only the 85 declared source members, prerequisite text/JSON evidence, fixed
build/replay/correctness receipts, correctness numeric artifacts and 25 pinned
historical numeric references are read. Images, SMDs and banks are not opened.
"""
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "artifacts/postprocess_optimization/full_api"
REVIEW = Path(__file__).resolve().parent
MANIFEST_SHA = "a97e54bd4159a247a8d5f08b4189f246b39da5ae687ce7552365491dcbd10595"
BASE = "exact_v11"
CAND = "index_reserve_copy_actual_match"
COMMON = tuple([f"LED_{i}" for i in range(1, 9)] + ["case1"] +
               [f"tiny_s5_i{i}" for i in (7, 70, 127, 215, 293, 353, 436, 493)] +
               [f"tiny_s2_i{i}" for i in (3, 92, 153, 214, 295, 374, 446, 494)])
INPUTS = COMMON + ("LED_two_classes", "synthetic_zero_maxima", "LED_zero_mask",
                   "LED_full_mask", "LED_partial_mask", "LED_empty_candidates",
                   "LED_larger_same_detector")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pin(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": digest(raw)}


def source_review():
    path = HERE / "FULL_API_SOURCE_MANIFEST_v2.json"
    manifest_pin = pin(path)
    need(manifest_pin["sha256"] == MANIFEST_SHA, "Reviewed v2 manifest differs")
    current = load(path)
    previous = load(HERE / "FULL_API_SOURCE_MANIFEST.json")
    need(current["schema"] == "whole_api_sources_v1" and
         current["baseline_commit"] == "b25df46f6ddf9c24fb43f5836f1414dc38c8caed", "Source baseline differs")
    before = {item["relative"]: item for item in previous["sources"]}
    after = {item["relative"]: item for item in current["sources"]}
    need(len(current["sources"]) == len(after) == 85 and list(before) == list(after), "Source membership differs")
    need(previous["prerequisites"] == current["prerequisites"], "Prerequisite declarations changed")
    changed = [name for name in after if before[name] != after[name]]
    need(changed == ["run_full_api.py", "tests/test_runner_contract.py"], "Unexpected v2 change")
    verified = []
    for name, item in after.items():
        target = (HERE / name).resolve(strict=True)
        need(target.is_relative_to(HERE.resolve()) and target.is_file(), "Source escaped scope")
        actual = pin(target)
        need((actual["bytes"], actual["sha256"]) == (item["bytes"], item["sha256"]), "Source pin differs: " + name)
        verified.append(actual)
    for item in current["prerequisites"]:
        target = (ROOT / item["relative"]).resolve(strict=True)
        need(target.is_relative_to(ROOT), "Prerequisite escaped scope")
        actual = pin(target)
        need((actual["bytes"], actual["sha256"]) == (item["bytes"], item["sha256"]), "Prerequisite pin differs")
    return {"manifest": manifest_pin, "sources": verified, "source_count": 85,
            "prerequisite_count": len(current["prerequisites"]), "changed_from_v1": changed,
            "v1_manifest": pin(HERE / "FULL_API_SOURCE_MANIFEST.json"), "blocking_findings": [],
            "static_conclusions": [
                "V2 grants only the exact current Python executable, not its directory; regression tests cover neighbor and forged role rejection.",
                "Each phase is separately gated, uses a fresh output directory, and binds accepted same-source same-build predecessors.",
                "Baseline/candidate private core wrappers share clock and materialization logic; the candidate core has only the frozen two-seam helper transform.",
                "All 2722 correctness outputs and 950 timing outputs require complete ordered fields and score-bit equality.",
                "Runner adds a 25-fixture historical truth gate to timing cold baselines after audit_timing's cold and same-round equality checks.",
                "Actual returned U-vector destruction and neutral-record copying are outside both API wall clocks; original N-vector destruction remains inside helper."]}


def expected_schedule():
    calls, pairs = [], []
    def emit(stage, route, idx, variant=BASE, flags=127, threads=4, turn=0, repeat=0, worker=-1, step=0):
        name = INPUTS[idx] if type(idx) is int else idx
        calls.append(dict(call_id=len(calls), stage=stage, route=route, input=name,
                          variant=variant, flags=flags, threads=threads, repeat=repeat,
                          worker=worker, step=step, **{"pass": turn}))
        return len(calls) - 1
    def pair(actual, oracle):
        pairs.append(dict(comparison_id=len(pairs), actual_call_id=actual,
                          expected_call_id=oracle, full_ordered_equal=True, first_mismatch=None))
    for turn, threads in enumerate((1, 4, 2, 4)):
        for flags in (63, 127):
            for idx in range(32):
                first = emit("core", "oracle", idx, flags=flags, threads=threads, turn=turn)
                pair(emit("core", "baseline_repeat", idx, flags=flags, threads=threads, turn=turn, repeat=1), first)
                for repeat in range(2):
                    pair(emit("core", "candidate", idx, CAND, flags, threads, turn, repeat), first)
    for flags in range(128):
        for idx in (0, 27, 8, 1, 26, 31):
            first = emit("flags", "all_flags", idx, flags=flags)
            pair(emit("flags", "all_flags", idx, CAND, flags), first)
    for idx in (28, 29, 30, 0):
        for flags in (0, 55, 127):
            first = emit("flags", "mask_restore", idx, flags=flags)
            pair(emit("flags", "mask_restore", idx, CAND, flags), first)
    first = emit("flags", "log_flag", 0)
    pair(emit("flags", "log_flag", 0, CAND), first)
    oracle127 = [emit("lifetime", "oracle", idx) for idx in range(32)]
    for idx, route in ((0, "pre_move"), (8, "move_constructed"), (1, "moved_from_reused"),
                       (8, "assignment_destination_populated"), (0, "move_assigned"), (31, "assignment_source_reused")):
        pair(emit("lifetime", route, idx, CAND), oracle127[idx])
    for step, idx in enumerate((0, 8, 1, 0)):
        first = emit("lifetime", "legacy_default", idx, step=step)
        for route in ("legacy_default", "explicit_default"):
            pair(emit("lifetime", route, idx, CAND, step=step), first)
    oracle55 = [emit("lifetime", "oracle", idx, flags=55) for idx in range(32)]
    forward = (0, 8, 1, 27, 31, 0)
    for worker, sequence in enumerate((forward, forward[::-1])):
        for step, idx in enumerate(sequence):
            for flags, oracles in ((127, oracle127), (55, oracle55)):
                pair(emit("lifetime", "concurrent", idx, CAND, flags, 1, worker=worker, step=step), oracles[idx])
    for step in range(8):
        first = emit("class_filter", "filter", 25, step=step)
        pair(emit("class_filter", "filter", 25, CAND, step=step), first)
    for idx in range(1, 8):
        first = emit("magnet_local", "regression", f"M{idx:02d}")
        pair(emit("magnet_local", "regression", f"M{idx:02d}", CAND), first)
    need(len(calls) == 2722 and len(pairs) == 1602, "Independent schedule budget error")
    return calls, pairs


def records(raw, count, offset):
    need(count <= (len(raw) - offset) // 24, "Record count exceeds bytes")
    result = []
    for _ in range(count):
        need(offset + 24 <= len(raw), "Truncated record")
        x, y, template, score, length = struct.unpack_from("<iiiIQ", raw, offset)
        offset += 24
        need(score & 0x7f800000 != 0x7f800000 and length <= len(raw) - offset, "Invalid score/class")
        result.append((x, y, template, score, raw[offset:offset + length]))
        offset += length
    need(offset == len(raw), "Trailing archive bytes")
    return tuple(result)


def archive(raw, call_id):
    need(len(raw) >= 24 and raw[:8] == b"HMOUT001", "Invalid output header")
    actual, count = struct.unpack_from("<QQ", raw, 8)
    need(actual == call_id, "Archive call identity differs")
    return records(raw, count, 24)


def numeric_review():
    directory = HERE / "build/correctness_v2"
    receipt_path = directory / "stage_result.json"
    receipt_pin = pin(receipt_path)
    receipt = load(receipt_path)
    need(receipt["accepted"] is True and receipt["phase"] == "correctness" and
         receipt["binding"]["source_manifest_sha256"] == MANIFEST_SHA and not receipt["final_recheck_errors"], "Correctness receipt failed")
    linked = {}
    for field, phase in (("build_evidence", "build"), ("replay_evidence", "replay")):
        target = HERE / f"build/{phase}_v2/stage_result.json"
        actual = pin(target)
        need(receipt[field] == actual, "Linked predecessor pin differs")
        value = load(target)
        need(value["accepted"] is True and value["phase"] == phase and not value["final_recheck_errors"] and
             value["binding"]["source_manifest_sha256"] == MANIFEST_SHA, "Prior receipt failed")
        if phase == "replay":
            need(value["build_evidence"] == linked["build"], "Replay bound to different build")
        linked[phase] = actual
    names = {f"outputs/call_{i:06d}.bin" for i in range(2722)} | {
        "calls.csv", "calls.json", "comparisons.csv", "comparisons.json", "magnet_preflight.csv",
        "native_correctness.stdout.txt", "native_correctness.stderr.txt"}
    actual_names = {str(path.relative_to(directory)).replace("\\", "/") for path in directory.rglob("*") if path.is_file()}
    need(actual_names == names | {"stage_result.json"}, "Actual artifact membership differs")
    pinned = {}
    for item in receipt["artifact_pins"]:
        path = Path(item["path"]).resolve(strict=True)
        need(path.is_relative_to(directory.resolve()), "Artifact path escaped correctness directory")
        name = str(path.relative_to(directory.resolve())).replace("\\", "/")
        need(name in names and name not in pinned, "Unexpected/duplicate artifact pin")
        need(pin(path) == item, "Artifact bytes changed")
        pinned[name] = item
    need(set(pinned) == names, "Artifact pin coverage differs")
    rows, pairs = load(directory / "calls.json"), load(directory / "comparisons.json")
    expected, expected_pairs = expected_schedule()
    need(len(rows) == len(expected) and pairs == expected_pairs, "Calls/comparison schedule differs")
    csv_rows = list(csv.DictReader(io.StringIO((directory / "calls.csv").read_text(encoding="utf-8"), newline="")))
    csv_pairs = list(csv.DictReader(io.StringIO((directory / "comparisons.csv").read_text(encoding="utf-8"), newline="")))
    need(len(csv_rows) == 2722 and len(csv_pairs) == 1602, "Raw CSV row budget differs")
    decoded, stable, core, filter_outputs = {}, {}, {}, {}
    for row, wanted, csv_row in zip(rows, expected, csv_rows):
        for key, value in wanted.items():
            need(type(row[key]) is type(value) and row[key] == value, "Exact route metadata differs")
        need(set(csv_row) == set(row) - {"output_sha256"}, "CSV fields differ")
        for key, value in csv_row.items():
            actual = row[key]
            parsed = bool(int(value)) if type(actual) is bool else type(actual)(value)
            need(parsed == actual, "CSV/JSON field differs")
        call_id = row["call_id"]
        name = f"outputs/call_{call_id:06d}.bin"
        need(row["output_file"] == name and row["output_bytes"] == pinned[name]["bytes"] and
             row["output_sha256"] == pinned[name]["sha256"], "Output row/pin differs")
        found = archive((directory / name).read_bytes(), call_id)
        need(len(found) == row["record_count"], "Record count differs")
        for clock in ("api_wall_ms", "internal_search_ms", "internal_total_ms"):
            need(type(row[clock]) in (int, float) and math.isfinite(row[clock]) and row[clock] >= 0, "Invalid clock")
        internal = row["route"] not in ("legacy_default", "explicit_default")
        need(row["has_internal_timing"] is internal and row["internal_total_ms"] + 1e-8 >= row["internal_search_ms"], "Clock domain differs")
        need(internal or row["internal_total_ms"] == row["internal_search_ms"] == 0, "Legacy clocks fabricated")
        if row["input"] in ("LED_zero_mask", "LED_empty_candidates"):
            need(not found, "Negative control nonempty")
        if row["input"] == "synthetic_zero_maxima":
            need(found and all(record[3] == 0 for record in found), "Zero control differs")
        decoded[call_id] = found
        if row["variant"] == BASE:
            if row["stage"] == "class_filter":
                filter_outputs[row["step"]] = found
            else:
                key = (row["input"], row["flags"])
                need(key not in stable or stable[key] == found, "Baseline thread/route stability differs")
                stable[key] = found
            if row["stage"] == "core" and row["route"] == "oracle" and row["pass"] == 0 and row["flags"] == 127:
                core[row["input"]] = found
    for pair, csv_pair in zip(pairs, csv_pairs):
        need(set(csv_pair) == set(pair), "Comparison CSV fields differ")
        need(all(csv_pair[key] == ("1" if value is True else "" if value is None else str(value)) for key, value in pair.items()), "Comparison CSV/JSON differs")
        need(decoded[pair["actual_call_id"]] == decoded[pair["expected_call_id"]], "Complete ordered comparison differs")
    for flags in (0, 55, 63, 127):
        need(stable[("LED_full_mask", flags)] == stable[("LED_1", flags)], "Full mask differs")
    renamed = {name: tuple(rec[:4] + (name,) for rec in core["LED_1"]) for name in (b"LED_A", b"LED_B")}
    key = lambda rec: (-struct.unpack("<f", struct.pack("<I", rec[3]))[0], rec[2], rec[4], rec[1], rec[0])
    two = tuple(sorted(renamed[b"LED_A"] + renamed[b"LED_B"], key=key))
    need(core["LED_two_classes"] == two, "Renamed two-class relation differs")
    need(all(filter_outputs[step] == two for step in (0, 3, 4)), "All-class filters differ")
    need(all(filter_outputs[step] == renamed[b"LED_A"] for step in (1, 6, 7)) and
         filter_outputs[2] == renamed[b"LED_B"] and not filter_outputs[5], "Single/missing/duplicate class filters differ")
    catalog = load(HERE / "HISTORICAL_TRACE_PINS.json")
    need([item["fixture"] for item in catalog["fixtures"]] == list(COMMON), "Historical catalog membership differs")
    reference_pins = []
    for item in catalog["fixtures"]:
        base = ROOT / "artifacts/match_consolidation/hash_prototype/run_20261022_capture_actual85" / item["fixture"]
        for role in ("manifest", "protocol"):
            path = base / (role + ".json")
            need(pin(path) == item[role], "Historical declaration pin differs")
        manifest = load(base / "manifest.json")
        ref = item["reference"]
        need(manifest["reference"] == ref and ref["path"] == "reference.bin", "Historical reference declaration differs")
        path = base / "reference.bin"
        raw = path.read_bytes()
        actual = pin(path)
        need(len(raw) == ref["size_bytes"] and digest(raw) == ref["sha256"], "Historical reference changed")
        need(len(raw) >= 32 and raw[:8] == b"SBMHASH1", "Historical magic differs")
        version, endian, n, u = struct.unpack_from("<IIQQ", raw, 8)
        need((version, endian, n) == (1, 0x01020304, 0) and u == ref["output_count"], "Historical header differs")
        need(core[item["fixture"]] == records(raw, u, 32), "Historic complete truth gate differs")
        reference_pins.append(actual)
    preflight = list(csv.DictReader((directory / "magnet_preflight.csv").open(encoding="utf-8", newline="")))
    need(len(preflight) == 6120, "Magnet preflight rows differ")
    for idx, text in enumerate(preflight):
        row = {key: int(value) for key, value in text.items()}
        level = idx % 2
        border = 32 if level == 0 else 64
        need(row["template_id"] == idx // 2 and row["level"] == level and row["border"] == border and
             row["required_width"] == (row["width"] + 2 * border) * (1 << level) and
             row["required_height"] == (row["height"] + 2 * border) * (1 << level) and
             row["max_x"] == (896 >> level) - row["width"] - border and row["max_x"] >= border and
             row["max_y"] == (832 >> level) - row["height"] - border and row["max_y"] >= border, "Magnet interval differs")
    counts = dict(Counter(row["variant"] for row in rows))
    need(counts == {BASE: 1376, CAND: 1346}, "Variant call totals differ")
    need(pin(receipt_path) == receipt_pin, "Receipt changed during review")
    return {"receipt": receipt_pin, "predecessor_receipts": linked, "complete_archives": len(decoded),
            "archive_bytes": sum(item["bytes"] for name, item in pinned.items() if name.startswith("outputs/")),
            "verified_artifact_pins": len(pinned), "complete_ordered_comparisons": len(pairs),
            "historical_reference_fixtures": 25, "historical_reference_pins": reference_pins,
            "variant_calls": counts, "stage_calls": dict(Counter(row["stage"] for row in rows)),
            "magnet_preflight_rows": len(preflight), "full_mask_negative_zero_class_and_stability_checks": True,
            "target_auditor_called": False, "native_programs_executed": 0,
            "image_smd_bank_content_reads": 0, "speed_or_accuracy_improvement_claim": False,
            "limits": ["Predecessor receipt identities are bound; native executable/runtime/header input pins were not independently rehashed here.",
                       "Private source image/SMD pins were deliberately not read or rehashed.",
                       "Numeric equality establishes tested output preservation, not detector accuracy or peak memory.",
                       "Source conclusions are static inspection; this independent reviewer did not run the target pure unit tests."]}


def main():
    target = REVIEW / "review_correctness_20261022_v1.json"
    result = {"schema": "independent_full_api_v2_review_v1", "reviewer": "/root/remote_review",
              "started_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
              "review_script": pin(Path(__file__))}
    try:
        result["source_review"] = source_review()
        result["numeric_correctness_review"] = numeric_review()
        result["passed"] = True
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    with target.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps({"passed": result["passed"], "result": pin(target), "error": result.get("error")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
