#!/usr/bin/env python3
"""Compare already-recorded CSVs without rerunning matching or inspecting heldout."""
import argparse
import collections
import csv
import hashlib
import gzip
import json
from pathlib import Path
import struct


def load(path):
    strict, semantic, scores = collections.Counter(), collections.Counter(), collections.Counter()
    predicted = {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            score = float(row["score"])
            # Exact original float bits, not a rounded or tolerance-based score.
            bits = struct.unpack("<I", struct.pack("<f", score))[0]
            xy_score = (int(row["match_x"]), int(row["match_y"]), bits)
            key = xy_score + (int(row["template_id"]),)
            strict[key] += 1
            semantic[xy_score] += 1
            scores[bits] += 1
            predicted[key] = tuple(float(row[k]) for k in ("bbox_x", "bbox_y", "bbox_w", "bbox_h"))
    return strict, semantic, scores, predicted


def difference(left, right):
    a, b = left - right, right - left
    return {
        "set_equal": left.keys() == right.keys(),
        "multiset_equal": left == right,
        "left_unique_keys": len(left), "right_unique_keys": len(right),
        "left_only_keys": len(left.keys() - right.keys()),
        "right_only_keys": len(right.keys() - left.keys()),
        "left_excess_occurrences": sum(a.values()),
        "right_excess_occurrences": sum(b.values()),
        "left_excess_examples": [[*key, count] for key, count in a.most_common(5)],
        "right_excess_examples": [[*key, count] for key, count in b.most_common(5)],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = {
        "source_directory": str(args.directory.resolve()),
        "semantic_key": "(class=tless_object_1, match_x, match_y, IEEE754_float32_score_bits)",
        "strict_key": "semantic_key + template_id; bbox compared independently for common strict keys",
        "scores": "CSV had 17 significant decimal digits; repacked into float32 exact score bits",
        "frames": [],
    }
    equality_path = args.directory / "candidate_equality.csv"
    with equality_path.open(newline="", encoding="utf-8") as stream:
        frames = list(csv.DictReader(stream))
    for frame in frames:
        key = f"s{frame['scene']}_i{frame['image']}"
        paths = [args.directory / f"{key}_{variant}_raw.csv" for variant in ("fallback", "fused")]
        paths = [path if path.is_file() else path.with_suffix(path.suffix + ".gz") for path in paths]
        left = load(paths[0]); right = load(paths[1])
        strict, semantic = difference(left[0], right[0]), difference(left[1], right[1])
        common = left[3].keys() & right[3].keys()
        item = {
            "scene_id": int(frame["scene"]), "image_id": int(frame["image"]),
            "fallback_count": sum(left[0].values()), "fused_count": sum(right[0].values()),
            "strict": strict, "semantic": semantic,
            "score_histogram_equal": left[2] == right[2],
            "common_strict_keys": len(common),
            "common_strict_keys_with_bbox_difference": sum(left[3][k] != right[3][k] for k in common),
            "raw_csv": [{"path": str(path.resolve()), "bytes": path.stat().st_size,
                         "sha256": hashlib.file_digest(path.open("rb"), "sha256").hexdigest()} for path in paths],
        }
        result["frames"].append(item)
        print(key, "counts", item["fallback_count"], item["fused_count"],
              "semantic set", semantic["set_equal"], "semantic multiset", semantic["multiset_equal"],
              "strict set", strict["set_equal"], "strict multiset", strict["multiset_equal"], flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    result["summary"] = {
        "frames": len(result["frames"]),
        "counts_equal_frames": sum(f["fallback_count"] == f["fused_count"] for f in result["frames"]),
        "semantic_set_equal_frames": sum(f["semantic"]["set_equal"] for f in result["frames"]),
        "semantic_multiset_equal_frames": sum(f["semantic"]["multiset_equal"] for f in result["frames"]),
        "strict_set_equal_frames": sum(f["strict"]["set_equal"] for f in result["frames"]),
        "strict_multiset_equal_frames": sum(f["strict"]["multiset_equal"] for f in result["frames"]),
        "common_strict_bbox_differences": sum(f["common_strict_keys_with_bbox_difference"] for f in result["frames"]),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
