"""Independent stdlib-only numeric review of the accepted 950-call timing run."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import struct

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "artifacts/postprocess_optimization/full_api"
RUN = HERE / "build/benchmark_v2"
OUT = RUN / "outputs"
REVIEW = Path(__file__).resolve().parent
MANIFEST_SHA = "a97e54bd4159a247a8d5f08b4189f246b39da5ae687ce7552365491dcbd10595"
BASE, CAND = "exact_v11", "index_reserve_copy_actual_match"
FIXTURES = tuple([f"LED_{i}" for i in range(1, 9)] + ["case1"] +
                 [f"tiny_s5_i{i}" for i in (7, 70, 127, 215, 293, 353, 436, 493)] +
                 [f"tiny_s2_i{i}" for i in (3, 92, 153, 214, 295, 374, 446, 494)])


def need(ok, msg):
    if not ok: raise ValueError(msg)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def pin(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": sha(raw)}
def load(path): return json.loads(path.read_text(encoding="utf-8-sig"))


def schedule():
    rows = []
    for i, fixture in enumerate(FIXTURES):
        for phase, rounds, offset in (("cold", 1, 0), ("warm", 2, 1), ("formal", 16, 3)):
            for round_index in range(rounds):
                k = i + round_index + offset
                order = [BASE, CAND]
                if k % 2: order.reverse()
                if (k // 2) % 2: order.reverse()
                for position, variant in enumerate(order):
                    rows.append(dict(call_id=len(rows), fixture=fixture, phase=phase,
                                     round=round_index, position=position, variant=variant))
    need(len(rows) == 950, "Timing schedule budget differs")
    return rows


def decode(raw, call_id):
    need(len(raw) >= 24 and raw[:8] == b"HMOUT001", "Invalid output archive header")
    archive_id, count = struct.unpack_from("<QQ", raw, 8)
    need(archive_id == call_id and count <= (len(raw) - 24) // 24, "Output identity/count differs")
    offset, result = 24, []
    for _ in range(count):
        need(offset + 24 <= len(raw), "Truncated output record")
        x, y, template, score, length = struct.unpack_from("<iiiIQ", raw, offset)
        offset += 24
        need(score & 0x7f800000 != 0x7f800000 and length <= len(raw) - offset, "Invalid score/class bytes")
        result.append((x, y, template, score, raw[offset:offset + length]))
        offset += length
    need(offset == len(raw), "Trailing output bytes")
    return tuple(result)


def nearest(values, q):
    ordered = sorted(values)
    return ordered[math.ceil(q * len(ordered)) - 1]


def reference_records(path):
    raw = path.read_bytes()
    need(len(raw) >= 32 and raw[:8] == b"SBMHASH1", "Historical reference format differs")
    version, endian, n, count = struct.unpack_from("<IIQQ", raw, 8)
    need((version, endian, n) == (1, 0x01020304, 0), "Historical reference header differs")
    offset, result = 32, []
    for _ in range(count):
        need(offset + 24 <= len(raw), "Truncated historical reference")
        x, y, template, score, length = struct.unpack_from("<iiiIQ", raw, offset)
        offset += 24
        need(score & 0x7f800000 != 0x7f800000 and length <= len(raw) - offset, "Invalid historical reference")
        result.append((x, y, template, score, raw[offset:offset + length]))
        offset += length
    need(offset == len(raw), "Trailing historical reference bytes")
    return tuple(result)


def main():
    result = {"schema": "independent_full_api_timing_review_v1", "reviewer": "/root/remote_review",
              "started_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
              "target_auditor_called": False, "native_programs_executed": 0,
              "image_smd_bank_content_reads": 0, "speed_or_accuracy_improvement_claim": False}
    try:
        receipt_path = RUN / "stage_result.json"
        receipt = load(receipt_path)
        result["receipt"] = pin(receipt_path)
        need(receipt["accepted"] is True and receipt["phase"] == "benchmark" and
             receipt["binding"]["source_manifest_sha256"] == MANIFEST_SHA and not receipt["final_recheck_errors"], "Benchmark receipt failed")
        corr_path = HERE / "build/correctness_v2/stage_result.json"
        corr = load(corr_path)
        need(receipt["correctness_evidence"] == pin(corr_path) and corr["accepted"] is True and
             corr["binding"]["source_manifest_sha256"] == MANIFEST_SHA, "Correctness predecessor binding differs")
        expected = schedule()
        rows = load(RUN / "calls.json")
        pairs = {name: row for name, row in []}
        need(len(rows) == 950, "Timing JSON row count differs")
        actual_names = {str(p.relative_to(RUN)).replace("\\", "/") for p in RUN.rglob("*") if p.is_file()}
        expected_names = {"stage_result.json", "calls.csv", "calls.json", "native_benchmark.stdout.txt", "native_benchmark.stderr.txt"} | {f"outputs/call_{i:06d}.bin" for i in range(950)}
        need(actual_names == expected_names, "Timing artifact membership differs")
        pins = {str(Path(item["path"]).resolve().relative_to(RUN.resolve())).replace("\\", "/"): item
                for item in receipt["artifact_pins"]}
        need(set(pins) == expected_names - {"stage_result.json"}, "Timing artifact pin coverage differs")
        for name, item in pins.items():
            path = RUN / name
            need(pin(path) == item, "Timing artifact changed: " + name)
        csv_rows = list(csv.DictReader(io.StringIO((RUN / "calls.csv").read_text(encoding="utf-8"), newline="")))
        need(len(csv_rows) == 950, "Timing CSV row count differs")
        decoded = {}
        routes = {}
        for row, wanted, csv_row in zip(rows, expected, csv_rows):
            for key, value in wanted.items(): need(row[key] == value, "Timing schedule differs: " + key)
            need(set(csv_row) == set(row) - {"output_sha256"}, "Timing CSV fields differ")
            for key, value in csv_row.items():
                actual = row[key]
                parsed = bool(int(value)) if type(actual) is bool else type(actual)(value)
                need(parsed == actual, "Timing CSV/JSON differs: " + key)
            name = f"outputs/call_{row['call_id']:06d}.bin"
            need(row["output_file"] == name and row["output_bytes"] == pins[name]["bytes"] and
                 row["output_sha256"] == pins[name]["sha256"], "Timing row/archive pin differs")
            for clock in ("api_wall_ms", "internal_search_ms", "internal_total_ms"):
                need(type(row[clock]) in (int, float) and math.isfinite(row[clock]) and row[clock] > 0, "Invalid positive clock")
            need(row["has_internal_timing"] is True, "Timing call missing internal clock")
            found = decode((RUN / name).read_bytes(), row["call_id"])
            need(len(found) == row["record_count"], "Timing record count differs")
            decoded[row["call_id"]] = found
            routes[(row["fixture"], row["phase"], row["round"], row["variant"])] = row
        equalities = 0
        for row in rows:
            cold = routes[(row["fixture"], "cold", 0, BASE)]
            pair = routes[(row["fixture"], row["phase"], row["round"], BASE)]
            need(decoded[row["call_id"]] == decoded[cold["call_id"]], "Cold output differs")
            need(decoded[row["call_id"]] == decoded[pair["call_id"]], "Same-round baseline output differs")
            equalities += 2
        per_fixture, formal_positions = {}, {}
        all_ratios = {clock: [] for clock in ("api_wall_ms", "internal_search_ms", "internal_total_ms")}
        for fixture in FIXTURES:
            formal_positions[fixture] = {}
            for variant in (BASE, CAND):
                formal = [routes[(fixture, "formal", i, variant)] for i in range(16)]
                formal_positions[fixture][variant] = [sum(row["position"] == pos for row in formal) for pos in (0, 1)]
                need(formal_positions[fixture][variant] == [8, 8], "Formal position balance differs")
            summary = {}
            for clock in ("api_wall_ms", "internal_search_ms", "internal_total_ms"):
                baseline = [routes[(fixture, "formal", i, BASE)][clock] for i in range(16)]
                candidate = [routes[(fixture, "formal", i, CAND)][clock] for i in range(16)]
                ratios = [candidate[i] / baseline[i] for i in range(16)]
                need(all(math.isfinite(x) and x > 0 for x in ratios), "Invalid ratio")
                all_ratios[clock].extend(ratios)
                summary[clock] = {"baseline_p10": nearest(baseline, .1), "baseline_p50": nearest(baseline, .5),
                                  "baseline_p90": nearest(baseline, .9), "candidate_p10": nearest(candidate, .1),
                                  "candidate_p50": nearest(candidate, .5), "candidate_p90": nearest(candidate, .9),
                                  "paired_median": statistics.median(ratios), "regression_rounds": [i for i, x in enumerate(ratios) if x > 1],
                                  "ratios": ratios}
            per_fixture[fixture] = summary
        # Cold exact_v11 records are independently bound to all 25 frozen references.
        catalog = load(HERE / "HISTORICAL_TRACE_PINS.json")
        need([x["fixture"] for x in catalog["fixtures"]] == list(FIXTURES), "Historical fixture order differs")
        for item in catalog["fixtures"]:
            base = ROOT / "artifacts/match_consolidation/hash_prototype/run_20261022_capture_actual85" / item["fixture"]
            ref_item = item["reference"]
            path = base / ref_item["path"]
            need(pin(path)["bytes"] == ref_item["size_bytes"] and pin(path)["sha256"] == ref_item["sha256"], "Historical ref pin differs")
            cold = routes[(item["fixture"], "cold", 0, BASE)]
            need(decoded[cold["call_id"]] == reference_records(path), "Cold historical truth differs")
        groups = {}
        for name, selected in (("LED", FIXTURES[:8]), ("case1", FIXTURES[8:9]), ("tiny", FIXTURES[9:]), ("all25", FIXTURES)):
            groups[name] = {}
            for clock in ("api_wall_ms", "internal_search_ms", "internal_total_ms"):
                values = [per_fixture[f][clock]["paired_median"] for f in selected]
                groups[name][clock] = {"fixtures": len(values), "median": statistics.median(values),
                    "geometric_mean": math.exp(math.fsum(math.log(v) for v in values) / len(values)),
                    "regression_fixtures": [f for f in selected if per_fixture[f][clock]["paired_median"] > 1]}
        result.update({"passed": True, "source_manifest_sha256": MANIFEST_SHA, "complete_archives": 950,
                       "archive_bytes": sum(item["bytes"] for name, item in pins.items() if name.startswith("outputs/")),
                       "verified_artifact_pins": len(pins), "ordered_equalities": equalities,
                       "formal_rows": 800, "formal_position_counts": formal_positions,
                       "formal_ratio_count": {clock: len(vals) for clock, vals in all_ratios.items()},
                       "formal_ratio_median": {clock: statistics.median(vals) for clock, vals in all_ratios.items()},
                       "formal_ratio_geometric_mean": {clock: math.exp(math.fsum(math.log(v) for v in vals) / len(vals)) for clock, vals in all_ratios.items()},
                       "per_fixture": per_fixture, "groups": groups, "historical_truth_gate_fixtures": 25,
                       "limitation": ["Per-formal-call ratios are descriptive and retain every regression; no run selection or rerun was performed.",
                                      "Cold means first call in a fresh workspace for each fixture, not a fresh process or cleared OS/CPU cache.",
                                      "This review rehashed benchmark artifacts and historical references but not all build/runtime/header/input pins."]})
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    target = REVIEW / "review_benchmark_20261022_v1.json"
    with target.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, indent=2); out.write("\n")
    print(json.dumps({"passed": result["passed"], "result": pin(target), "error": result.get("error")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
