"""Independent V28 numeric review; stdlib only, no evaluator imports.

Newly saved from earlier unsaved temporary here-string logic, then freshly
rerun. This is not a historical executed-source snapshot of that command.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import traceback

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = next(p for p in HERE.parents if (p / ".git").exists())
NATIVE = ROOT / "artifacts/rgb_empty_mask_experiment/run_quality_development_v1/native"
OBJECTS = [1, 2, 5, 8, 12, 17]
ARMS = ["rgb_control", "rgb_empty_mask"]
CATEGORIES = ["matched", "raw_gap", "nms_loss", "assignment_competition"]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Inputs:
    """Pin every source/numeric input on first read and re-read all at exit."""

    def __init__(self):
        self.pins = {}
        self.after = []

    def read(self, path, kind="numeric"):
        path = Path(path).resolve(strict=True)
        check(path.is_relative_to(ROOT / "artifacts"), "Input outside artifacts")
        allowed = {".py", ".json"} if kind == "source" else {".json", ".csv", ".gz"}
        check(path.suffix.lower() in allowed, "Unapproved source/numeric input")
        check(not any(p.casefold() in {"datasets", "heldout", "magnet_match", "磁片"}
                      for p in path.relative_to(ROOT).parts), "Forbidden input path")
        data = path.read_bytes()
        name = path.relative_to(ROOT).as_posix()
        pin = dict(path=name, bytes=len(data), sha256=digest(data), kind=kind)
        if name in self.pins:
            check(self.pins[name] == pin, "Input changed while reading: " + name)
        else:
            self.pins[name] = pin
        return data

    def json(self, path, kind="numeric"):
        return json.loads(self.read(path, kind).decode("utf-8-sig"))

    def table(self, path, compressed=False):
        data = self.read(path)
        if compressed:
            data = gzip.decompress(data)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        values = list(reader)
        check(reader.fieldnames is not None and
              all(None not in r and None not in r.values() for r in values), "Malformed CSV")
        return values

    def recheck(self):
        before = [self.pins[k] for k in sorted(self.pins)]
        for pin in before:
            self.read(ROOT / pin["path"], pin["kind"])
        self.after = [dict(self.pins[k]) for k in sorted(self.pins)]
        check(before == self.after, "Before/after input closure")
        return before


def rect(row):
    return tuple(float(row["bbox_" + a]) for a in ("x", "y", "w", "h"))


def overlap(a, b):
    if min(a[2], a[3], b[2], b[3]) <= 0:
        return 0.
    area = max(min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]), 0) * max(
        min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]), 0)
    return area / (a[2] * a[3] + b[2] * b[3] - area)


def scorebits(value):
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def signature(row):
    return (row["class_id"], int(row["template_id"]), int(row["match_x"]), int(row["match_y"]),
            scorebits(row["score"]), rect(row),
            (int(row["training_image"]), float(row["angle"]), float(row["scale"])))


def canonical(row):
    b = rect(row)
    return (-float(row["score"]), row["class_id"], int(row["template_id"]),
            int(row["match_y"]), int(row["match_x"]), b[1], b[0], b[2], b[3])


def frame_key(row):
    return (int(row["object_id"]), int(row["scene"]), int(row["image"]), row["arm"])


def gt_key(row):
    return tuple(int(row[k]) for k in ("object_id", "scene", "image", "gt_id"))


def assign(candidates, truths, eligible):
    labels = [["FP", -1] for _ in candidates]
    used = set()
    for ignored in ([False, True] if eligible else [False]):
        for index, candidate in enumerate(candidates):
            if labels[index][0] != "FP":
                continue
            choices = []
            for truth in truths:
                identity = int(truth["gt_id"])
                if identity in used or (eligible and (float(truth["visibility"]) < .5) != ignored):
                    continue
                value = overlap(rect(candidate), rect(truth))
                if value >= .5:
                    choices.append((-value, identity))
            if choices:
                identity = min(choices)[1]
                labels[index] = ["IGNORE" if ignored else "TP", identity]
                used.add(identity)
    return labels


def normalized(values):
    return {a: {c: values.get(a, {}).get(c, 0) for c in CATEGORIES} for a in ARMS}


def run(target, evidence):
    evidence.read(Path(__file__), "source")
    source_matches = []
    for name in ["numeric.py", "run_analysis.py", "test_diagnostic.py", "PROTOCOL.json", "ORIGIN.json"]:
        live = evidence.read(BASE / name, "source")
        snapshot = evidence.read(target / "source" / name, "source")
        source_matches.append(dict(name=name, live_matches_target_snapshot=live == snapshot))
    for pin in evidence.json(target / "source_pins.json"):
        data = evidence.read(target / "source" / pin["name"], "source")
        check(len(data) == pin["bytes"] and digest(data) == pin["sha256"], "Target source snapshot differs")
    result = evidence.json(target / "result.json")
    freeze = evidence.json(ROOT / "artifacts/rgb_empty_mask_experiment/QUALITY_INPUT_FREEZE.json")
    frames = {(r["scene_id"], r["image_id"]) for r in freeze["development"]}
    check(len(freeze["development"]) == len(frames) == 400, "400 unique development frames")
    check({s for s, _ in frames} == {1, 4, 6, 7, 8, 10, 12, 13}, "Development scenes")
    expected = {(o, s, i, a) for o in OBJECTS for s, i in frames for a in ARMS}
    per_frame = evidence.table(target / "per_frame.csv")
    gt_arms = evidence.table(target / "per_gt_arm.csv")
    gt_pairs = evidence.table(target / "per_gt.csv")
    edges = evidence.table(target / "suppression_edges.csv")
    competitions = evidence.table(target / "assignment_competition.csv")
    truth_rows = evidence.table(NATIVE / "ground_truth.csv")
    selections = evidence.table(NATIVE / "selected_detections.csv")
    native_rows = evidence.table(NATIVE / "per_frame_metrics.csv")
    check(len(per_frame) == len({frame_key(r) for r in per_frame}) == 4800 and
          {frame_key(r) for r in per_frame} == expected, "Complete frame-arm output")
    check(len(native_rows) == len({frame_key(r) for r in native_rows}) == 4800 and
          {frame_key(r) for r in native_rows} == expected, "Complete native metrics")
    check(len(truth_rows) == len({gt_key(r) for r in truth_rows}) == 400, "400 unique GT")
    check(all((*gt_key(r)[:3], ARMS[0]) in expected for r in truth_rows), "GT scope")
    check(len(gt_pairs) == len({gt_key(r) for r in gt_pairs}) == 400 and
          {gt_key(r) for r in gt_pairs} == {gt_key(r) for r in truth_rows}, "Per-GT closure")
    check(len(gt_arms) == len({(*gt_key(r), r["arm"]) for r in gt_arms}) == 800 and
          {(*gt_key(r), r["arm"]) for r in gt_arms} ==
          {(*gt_key(t), a) for t in truth_rows for a in ARMS}, "800 GT-arm closure")
    per = {frame_key(r): r for r in per_frame}
    arms = {(*gt_key(r), r["arm"]): r for r in gt_arms}
    truths_by_id = {gt_key(r): r for r in truth_rows}
    native = {frame_key(r): r for r in native_rows}
    truths, selected, edge_map = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in truth_rows:
        truths[gt_key(row)[:3]].append(row)
    for row in selections:
        check(frame_key(row) in expected, "Selected scope")
        selected[frame_key(row)].append(row)
    for row in edges:
        check((*gt_key(row), row["arm"]) in arms, "Suppression edge scope")
        edge_map[(*gt_key(row), row["arm"])].append(row)
    totals = {a: Counter() for a in ARMS}
    labels_by_frame, eligible_by_frame = {}, {}
    for key in sorted(expected):
        truth, candidates = truths[key[:3]], selected[key]
        labels, eligible = assign(candidates, truth, False), assign(candidates, truth, True)
        check([int(r["rank"]) for r in candidates] == list(range(len(candidates))), "Selected ranks")
        check(labels == [[r["allGT_label"], int(r["allGT_id"])] for r in candidates],
              "Independent all-GT assignment")
        check(eligible == [[r["eligible_label"], int(r["eligible_id"])] for r in candidates],
              "Independent eligible assignment")
        labels_by_frame[key], eligible_by_frame[key] = labels, eligible
        tp, etp = sum(x[0] == "TP" for x in labels), sum(x[0] == "TP" for x in eligible)
        ng = sum(float(t["visibility"]) >= .5 for t in truth)
        # Negative raw counts are compared with frozen metrics, not recounted.
        counts = dict(raw=int(native[key]["raw"]), selected=len(candidates), tp=tp,
                      fp=len(candidates)-tp, fn=len(truth)-tp, gt=len(truth),
                      eligible_tp=etp, eligible_fp=sum(x[0] == "FP" for x in eligible),
                      eligible_fn=ng-etp, eligible_gt=ng,
                      ignored=sum(x[0] == "IGNORE" for x in eligible),
                      negative_fp=len(candidates) if not truth else 0)
        check({n: int(per[key][n]) for n in counts} == counts, "Per-frame independent totals")
        check(all(int(native[key][n]) == v for n, v in counts.items()), "Native metrics totals")
        totals[key[3]].update(counts)
    for arm in ARMS:
        check(dict(totals[arm]) == result["full_selected_totals"][arm], "Pooled frame closure")
    status = Counter()
    by_category = {a: Counter() for a in ARMS}
    by_status = defaultdict(lambda: {a: Counter() for a in ARMS})
    by_object = defaultdict(lambda: {a: Counter() for a in ARMS})
    by_scene = defaultdict(lambda: {a: Counter() for a in ARMS})
    for row in gt_pairs:
        key = gt_key(row)
        left, right = arms[(*key, ARMS[0])], arms[(*key, ARMS[1])]
        group = ("retained" if left["matched"] == right["matched"] == "True" else
                 "lost" if left["matched"] == "True" else "gained" if right["matched"] == "True" else "neither")
        check(row["status"] == left["status"] == right["status"] == group, "Cross-arm identity group")
        check(float(row["visibility"]) == float(truths_by_id[key]["visibility"]), "Paired GT visibility")
        status[group] += 1
        for arm, diagnostic in [(ARMS[0], left), (ARMS[1], right)]:
            check(row[arm + "_category"] == diagnostic["category"] and
                  float(row[arm + "_best_raw_iou"]) == float(diagnostic["best_raw_iou"]), "Cross-arm fields")
            check(float(diagnostic["visibility"]) == float(truths_by_id[key]["visibility"]), "GT visibility")
            by_category[arm][diagnostic["category"]] += 1
            by_status[group][arm][diagnostic["category"]] += 1
            by_object[key[0]][arm][diagnostic["category"]] += 1
            by_scene[key[1]][arm][diagnostic["category"]] += 1
    check(dict(status) == result["identity_status"] ==
          dict(retained=156, lost=59, gained=27, neither=158), "Four identity groups")
    check(normalized(by_category) == normalized(result["categories"]), "Category report")
    for group in status:
        check(normalized(by_status[group]) == normalized(result["by_status"][group]), "Group report")
    check({r["object_id"] for r in result["per_object"]} == set(OBJECTS), "Object report scope")
    check({r["scene"] for r in result["per_scene"]} == {s for s, _ in frames}, "Scene report scope")
    for row in result["per_object"]:
        check(normalized(by_object[row["object_id"]]) == normalized(row["categories"]), "Object report")
    for row in result["per_scene"]:
        check(normalized(by_scene[row["scene"]]) == normalized(row["categories"]), "Scene report")
    check(by_status["lost"][ARMS[1]] == dict(raw_gap=53, nms_loss=6), "53 + 6 lost split")
    check(not competitions and result["assignment_competition_edges"] == 0, "Zero assignment competition")
    replayed = raw_rows = checked_edges = 0
    blocker_labels, edge_stats = Counter(), Counter()
    for obj in OBJECTS:
        for scene, image in sorted(frames):
            truth = truths[(obj, scene, image)]
            if not truth:
                continue
            for arm in ARMS:
                key = (obj, scene, image, arm)
                raw = evidence.table(NATIVE / f"obj{obj}" / arm / f"s{scene}_i{image}_fallback_raw.csv.gz", True)
                check(len(raw) == int(per[key]["raw"]), "Positive frame raw count")
                check(raw == sorted(raw, key=canonical), "Canonical raw order")
                check([int(r["rank"]) for r in raw] == list(range(len(raw))), "Raw ranks")
                identities = defaultdict(list)
                for index, candidate in enumerate(raw):
                    identities[signature(candidate)].append(index)
                kept = [identities[signature(c)][0] for c in selected[key]]
                check(kept == sorted(kept) and len(set(kept)) == len(kept), "Retained raw identities")
                kept_set = set(kept)
                labels, eligible = dict(zip(kept, labels_by_frame[key])), dict(zip(kept, eligible_by_frame[key]))
                boxes, first = [rect(r) for r in raw], {}
                for rank in range(len(raw)):
                    blocker = next((p for p in kept if p < rank and
                                    raw[p]["class_id"] == raw[rank]["class_id"] and
                                    overlap(boxes[p], boxes[rank]) > .3), None)
                    check((blocker is None) == (rank in kept_set), "Positive-frame raw NMS closure")
                    first[rank] = blocker
                for target_truth in truth:
                    identity = (*gt_key(target_truth), arm)
                    row, box = arms[identity], rect(target_truth)
                    values = [overlap(b, box) for b in boxes]
                    hits = [j for j, v in enumerate(values) if v >= .5]
                    hit_set = set(hits)
                    selected_hits = [j for j in kept if j in hit_set]
                    matched = next((j for j in kept if labels[j] == ["TP", int(target_truth["gt_id"])]), None)
                    category = ("matched" if matched is not None else "raw_gap" if not hits else
                                "nms_loss" if not selected_hits else "assignment_competition")
                    best = max(range(len(raw)), key=lambda j: (values[j], -j)) if raw else None
                    check(row["category"] == category and (row["matched"] == "True") == (matched is not None),
                          "GT stage classification")
                    calculated = dict(raw_has_hit=bool(hits), raw_hit_count=len(hits),
                                      best_raw_iou=values[best] if best is not None else 0.,
                                      best_raw_rank=best, selected_has_hit=bool(selected_hits),
                                      selected_hit_count=len(selected_hits), matched_raw_rank=matched)
                    for name, value in calculated.items():
                        actual = row[name]
                        actual = (None if actual == "" else actual == "True" if isinstance(value, bool) else
                                  float(actual) if isinstance(value, float) else int(actual))
                        check(actual == value, "GT diagnostic field: " + name)
                    suppressed = [j for j in hits if j not in kept_set]
                    gt_edges = edge_map[identity]
                    check([int(e["raw_rank"]) for e in gt_edges] == suppressed, "Complete suppression edges")
                    counts = Counter()
                    for edge, rank in zip(gt_edges, suppressed):
                        blocker = first[rank]
                        check(blocker is not None and blocker == int(edge["blocker_raw_rank"]), "First blocker")
                        check(edge["category"] == category and
                              float(edge["visibility"]) == float(target_truth["visibility"]), "Edge context")
                        check([edge["blocker_label"], int(edge["blocker_gt_id"])] == labels[blocker],
                              "Blocker all-GT label")
                        check([edge["blocker_eligible_label"], int(edge["blocker_eligible_gt_id"])] == eligible[blocker],
                              "Blocker eligible label")
                        check((edge["blocker_is_fp"] == "True") == (labels[blocker][0] == "FP"), "Blocker FP flag")
                        for name, value in [("candidate_gt_iou", values[rank]), ("blocker_gt_iou", values[blocker]),
                                            ("candidate_blocker_iou", overlap(boxes[rank], boxes[blocker]))]:
                            check(float(edge[name]) == value, "Edge IoU")
                        for prefix, candidate_rank in [("candidate_", rank), ("blocker_", blocker)]:
                            candidate = raw[candidate_rank]
                            sig = signature(candidate)
                            check(int(edge[prefix+"rank"]) == candidate_rank, "Edge candidate rank")
                            check(edge[prefix+"class_id"] == sig[0] and int(edge[prefix+"template_id"]) == sig[1] and
                                  int(edge[prefix+"match_x"]) == sig[2] and int(edge[prefix+"match_y"]) == sig[3] and
                                  int(edge[prefix+"score_bits"]) == sig[4] and
                                  float(edge[prefix+"score"]) == float(candidate["score"]) and
                                  tuple(json.loads(edge[prefix+"box"])) == sig[5] and
                                  tuple(json.loads(edge[prefix+"pose"])) == sig[6], "Edge complete candidate identity")
                        label = labels[blocker][0]
                        counts[label] += 1
                        blocker_labels[label] += 1
                        checked_edges += 1
                        edge_stats[(arm, row["status"], category, label)] += 1
                    check(int(row["nms_blocker_fp_edges"]) == counts["FP"] and
                          int(row["nms_blocker_tp_edges"]) == counts["TP"], "GT blocker edge totals")
                replayed += 1
                raw_rows += len(raw)
        print(json.dumps(dict(object_id=obj, positive_frame_arms_replayed=replayed,
                              raw_rows_replayed=raw_rows, edges_checked=checked_edges)), flush=True)
    check(checked_edges == len(edges) == result["suppression_edges"] == 15179, "Suppression closure")
    check(dict(blocker_labels) == result["suppression_edges_by_blocker_label"] ==
          dict(TP=15030, FP=149), "Blocker label totals")
    check(result["full_object_frame_arm_replays"] == len(per_frame) and
          result["development_frames"] == len(frames) and result["object_frame_pairs"] == len(expected)//2 and
          result["gt_identities"] == len(gt_pairs) and result["gt_arm_rows"] == len(gt_arms), "Result scope constants")
    check({a: totals[a]["raw"] for a in ARMS} == result["full_raw_rows_per_path"], "Pooled raw count report")
    check(replayed == 700 and raw_rows == 134524, "Positive raw coverage")
    before = evidence.recheck()
    return dict(
        passed=True, version="v28_independent_numeric_review_v1", target=target.relative_to(ROOT).as_posix(),
        origin="Newly saved review derived from an earlier unsaved here-string; freshly executed",
        target_source_matches_live=source_matches, development_frames=len(frames),
        object_frame_pairs=len(expected)//2, frame_arm_rows=len(per_frame),
        gt_identities=len(gt_pairs), gt_arm_rows=len(gt_arms),
        independent_positive_raw_scope=dict(object_frames=replayed//2, frame_arms=replayed,
                                            gt_identities=len(gt_pairs), raw_rows=raw_rows, path="fallback"),
        negative_scope=dict(object_frames=2050, frame_arms=4100,
                            selected_assignment_and_per_frame_closure=True, raw_archives_replayed=False),
        fused_raw_archives_replayed=False, identity_status=dict(status), categories=normalized(by_category),
        lost_treatment=dict(by_status["lost"][ARMS[1]]), suppression_edges=checked_edges,
        blocker_labels=dict(blocker_labels),
        lost_treatment_edges=[dict(arm=k[0], status=k[1], category=k[2], blocker_label=k[3], count=v)
                              for k, v in edge_stats.items() if k[0] == ARMS[1] and k[1] == "lost"],
        assignment_competition_edges=0, matcher_calls=0, image_decodes=0, dataset_files_opened=0,
        limits=[
            "Raw replay covers all 700 positive frame-arms, 350 object-frames, and all 400 GT.",
            "The other 4100 negative frame-arms use complete selected assignment and per-frame closure; raw archives are not replayed.",
            "Fused raw archives and template-metadata box reprojection are not independently replayed.",
            "Negative raw counts are compared with frozen native metrics, not independently recounted.",
            "Raw evidence starts at score85; raw_gap is not proof of a threshold or pyramid-pruning cause.",
            "Suppression edges include redundant hits of matched GT; edges do not count lost GT.",
            "First-blocker provenance does not prove that removing it is a corrective intervention.",
            "Zero native/image/dataset operations refer to this standard-library script and its explicit reads."
        ],
        input_pins_before=before, input_pins_after=evidence.after,
        inputs_unchanged_before_after=True, source_and_numeric_input_count=len(before))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target, output = args.target.resolve(strict=True), args.output.resolve()
    check(target.is_relative_to(BASE) and target != HERE, "Target outside V28 diagnosis")
    check(output.is_relative_to(HERE) and output != HERE and not output.exists(), "Fresh contained output required")
    output.mkdir(parents=False)
    evidence = Inputs()
    try:
        receipt = run(target, evidence)
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: receipt[k] for k in ["passed", "frame_arm_rows", "gt_identities", "gt_arm_rows",
                                                 "identity_status", "lost_treatment", "suppression_edges",
                                                 "blocker_labels"]}), flush=True)
    except Exception as error:
        (output / "failure.json").write_text(json.dumps(dict(passed=False, error=str(error)), indent=2) + "\n",
                                             encoding="utf-8")
        (output / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
