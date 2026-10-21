"""Summarize LED paired timings (when present) and ABBA diagnostics; needs Pillow."""
from pathlib import Path
import argparse
import csv
import json
import math
import statistics

from PIL import Image, ImageDraw, ImageFont


RUN_ORDER = ("L2_A", "L3_A", "L3_B", "L2_B")
IMAGES = tuple(f"{i}.bmp" for i in range(1, 9))
PAIRS = {"L2": ("L2_A", "L2_B"), "L3": ("L3_A", "L3_B")}


def number(value):
    """Missing scores/coordinates stay missing rather than becoming zero."""
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def fmt(value, digits=2):
    return "N/A" if value is None else f"{value:.{digits}f}"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def center(row):
    values = (number(row.get("center_x")), number(row.get("center_y")))
    return values if all(v is not None for v in values) else None


def delta(a, b):
    return None if a is None or b is None else b - a


def font(size):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf"):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def load_runs(root):
    runs = {}
    for name in RUN_ORDER:
        directory = root / name
        config = json.loads((directory / "run_config.json").read_text(encoding="utf-8-sig"))
        result_rows = read_csv(directory / "results.csv")
        results = {row["image"]: row for row in result_rows}
        if len(result_rows) != 8 or set(results) != set(IMAGES):
            raise ValueError(f"{name}/results.csv must contain exactly images 1.bmp..8.bmp")
        timings = read_csv(directory / "timings.csv")
        if set(row["image"] for row in timings) != set(IMAGES):
            raise ValueError(f"{name}/timings.csv has missing or unexpected images")
        by_image = {}
        for image in IMAGES:
            raw = [row for row in timings if row["image"] == image]
            times = [number(row.get("match_ms")) for row in raw]
            if len(raw) != 7 or any(value is None or value <= 0 for value in times):
                raise ValueError(f"{name}/{image}: expected seven finite, positive raw match times")
            if len({row["repeat"] for row in raw}) != 7:
                raise ValueError(f"{name}/{image}: duplicate repeat numbers")
            by_image[image] = {
                "raw_records": raw,
                "raw_ms": times,
                "median_ms": statistics.median(times),
                "best_scores": [number(row.get("best_score")) for row in raw],
            }
        runs[name] = {"config": config, "results": results, "timings": by_image}
    return runs


def summarize(runs):
    configs = {}
    for label, names in PAIRS.items():
        medians = {}
        for image in IMAGES:
            raw = [time for name in names for time in runs[name]["timings"][image]["raw_ms"]]
            medians[image] = statistics.median(raw)
        mean_ms = statistics.mean(medians.values())
        configs[label] = {
            "runs": list(names), "samples_per_image": 14,
            "median_ms_by_image": medians,
            "mean_of_image_medians_ms": mean_ms,
            "fps_from_mean_match_ms": 1000.0 / mean_ms,
            "run_configs": {name: runs[name]["config"] for name in names},
        }

    comparisons = []
    for image in IMAGES:
        a, b = (runs[name]["results"][image] for name in ("L2_A", "L3_A"))
        sa, sb = number(a.get("score")), number(b.get("score"))
        ca, cb = center(a), center(b)
        # A coordinate is meaningful only when a match was reported.
        ca, cb = ca if sa is not None else None, cb if sb is not None else None
        distance = math.dist(ca, cb) if ca is not None and cb is not None else None
        aa, ab = number(a.get("angle_deg")), number(b.get("angle_deg"))
        angle_delta = ((ab - aa + 180) % 360 - 180) if aa is not None and ab is not None and ca and cb else None
        m2, m3 = (configs[label]["median_ms_by_image"][image] for label in ("L2", "L3"))
        comparisons.append({
            "image": image, "l2_score": sa, "l3_score": sb,
            "score_delta_l3_minus_l2": delta(sa, sb),
            "l2_center_x": ca[0] if ca else None, "l2_center_y": ca[1] if ca else None,
            "l3_center_x": cb[0] if cb else None, "l3_center_y": cb[1] if cb else None,
            "center_distance_px": distance,
            "l2_angle_deg": aa if ca else None, "l3_angle_deg": ab if cb else None,
            "angle_delta_wrapped_deg": angle_delta,
            "l2_scale": number(a.get("scale")) if ca else None,
            "l3_scale": number(b.get("scale")) if cb else None,
            "l2_median_ms": m2, "l3_median_ms": m3,
            "speedup_l2_over_l3": m2 / m3,
            "l2_match": sa is not None, "l3_match": sb is not None,
        })

    speedup = configs["L2"]["mean_of_image_medians_ms"] / configs["L3"]["mean_of_image_medians_ms"]
    return {
        "model": "LED/ku.smd", "images": list(IMAGES),
        "timing_source": "abba", "samples_per_image": 14,
        "run_order": list(RUN_ORDER),
        "method": "ABBA: L2_A, L3_A, L3_B, L2_B; each run has one excluded warmup and seven measured calls per image. Pool the two runs of each configuration per image, take the median of 14 raw times, then average the eight image medians.",
        "configurations": configs,
        "speedup_l2_over_l3": speedup,
        "change_in_mean_match_time_percent": (1 / speedup - 1) * 100,
        "display_results_from": ["L2_A", "L3_A"],
        "comparisons": comparisons,
        "runs": runs,
        "limitations": [
            "1.bmp is the template source; only seven other positive images are independent of it.",
            "No negative dataset or labeled accuracy evaluation; false-positive rates cannot be estimated.",
            "Scores are similarities, not probabilities; differing pyramid settings can change scores.",
            "Contour symmetry and unsigned gradients can produce approximately 180-degree angle ambiguity.",
            "The reported FPS is 1000 / mean match time, not end-to-end throughput.",
            "ABBA reduces order drift but is a single round and supplies no confidence interval.",
        ],
    }


def apply_paired(root, summary):
    """Use interleaved measurements as primary; retain the complete ABBA result."""
    path = root / "paired" / "timings.csv"
    if not path.is_file():
        return summary
    config = json.loads((path.parent / "run_config.json").read_text(encoding="utf-8-sig"))
    records = read_csv(path)
    if len(records) != 160 or {row["image"] for row in records} != set(IMAGES):
        raise ValueError("paired/timings.csv must contain 8 images x 10 repeats x 2 levels")
    if any(row["levels"] not in ("2", "3") for row in records):
        raise ValueError("paired/timings.csv contains an unexpected levels value")
    medians = {"L2": {}, "L3": {}}
    paired_ratios, checks = {}, {}
    tolerance = 0.01  # Similarity-score units; allows CSV rounding, not an accuracy claim.
    for image in IMAGES:
        grouped = {}
        checks[image] = {}
        for levels in (2, 3):
            raw = [row for row in records if row["image"] == image and row["levels"] == str(levels)]
            by_repeat = {int(row["repeat"]): row for row in raw}
            if len(raw) != 10 or set(by_repeat) != set(range(10)):
                raise ValueError(f"paired/{image}/L{levels}: expected unique repeats 0..9")
            times = [number(by_repeat[i]["match_ms"]) for i in range(10)]
            if any(value is None or value <= 0 for value in times):
                raise ValueError(f"paired/{image}/L{levels}: invalid match time")
            grouped[levels] = times
            medians[f"L{levels}"][image] = statistics.median(times)
            # Check actual physical row order, independently of the producer's order label.
            for repeat in range(10):
                observed = [row["levels"] for row in records if row["image"] == image and int(row["repeat"]) == repeat]
                expected = ["2", "3"] if repeat % 2 == 0 else ["3", "2"]
                if observed != expected:
                    raise ValueError(f"paired/{image}/repeat{repeat}: expected interleaved order {expected}")
            scores = [number(by_repeat[i].get("best_score")) for i in range(10)]
            reference = number(summary["runs"][f"L{levels}_A"]["results"][image].get("score"))
            differences = [delta(reference, score) for score in scores]
            comparable = [abs(value) for value in differences if value is not None]
            checks[image][f"L{levels}"] = {
                "a_group_score": reference, "paired_best_scores": scores,
                "paired_minus_a_score": differences,
                "max_abs_score_difference": max(comparable) if comparable else None,
                "paired_present_score_count": sum(score is not None for score in scores),
                "all_scores_within_tolerance": all(value <= tolerance for value in comparable)
                if reference is not None and len(comparable) == 10 else None,
            }
        ratios = [a / b for a, b in zip(grouped[2], grouped[3])]
        paired_ratios[image] = {"raw_l2_over_l3": ratios, "median_l2_over_l3": statistics.median(ratios)}

    diagnostic = {
        "warning": "Pronounced late-run timing drift was observed, especially in L2_B images 6..8 and L3_B image 8. The ABBA ratio (approximately 1.55 in this round) is diagnostic, not a precise speedup estimate.",
        "method": summary["method"], "run_order": summary["run_order"],
        "configurations": summary["configurations"],
        "comparisons": summary["comparisons"],
        "speedup_l2_over_l3": summary["speedup_l2_over_l3"],
        "change_in_mean_match_time_percent": summary["change_in_mean_match_time_percent"],
        "runs": summary.pop("runs"),
    }
    primary = {}
    for label in ("L2", "L3"):
        mean_ms = statistics.mean(medians[label].values())
        primary[label] = {
            "runs": ["paired"], "samples_per_image": 10,
            "median_ms_by_image": medians[label],
            "mean_of_image_medians_ms": mean_ms,
            "fps_from_mean_match_ms": 1000 / mean_ms,
            "run_configs": {"paired": config},
        }
    summary["comparisons"] = [dict(row) for row in diagnostic["comparisons"]]
    for row in summary["comparisons"]:
        image = row["image"]
        row["l2_median_ms"], row["l3_median_ms"] = medians["L2"][image], medians["L3"][image]
        row["speedup_l2_over_l3"] = row["l2_median_ms"] / row["l3_median_ms"]
        row["median_paired_speedup_l2_over_l3"] = paired_ratios[image]["median_l2_over_l3"]
        for label in ("L2", "L3"):
            check = checks[image][label]
            row[f"{label.lower()}_paired_max_abs_score_delta_vs_a"] = check["max_abs_score_difference"]
    summary.update({
        "timing_source": "paired", "samples_per_image": 10,
        "run_order": ["per image, even repeat: L2 then L3", "per image, odd repeat: L3 then L2"],
        "method": "Same process, interleaved per image and repetition: even repeat L2 then L3; odd repeat L3 then L2. One excluded warmup per image/configuration, then ten measurements. Median of ten raw times per image/configuration, followed by mean of eight image medians.",
        "configurations": primary,
        "speedup_l2_over_l3": primary["L2"]["mean_of_image_medians_ms"] / primary["L3"]["mean_of_image_medians_ms"],
        "abba_diagnostic": diagnostic,
        "paired": {"config": config, "raw_records": records, "paired_ratios_by_image": paired_ratios,
                   "score_comparison_to_a": checks, "score_tolerance": tolerance,
                   "all_160_scores_within_tolerance_of_a": all(checks[image][label]["all_scores_within_tolerance"] is True for image in IMAGES for label in ("L2", "L3"))},
    })
    summary["limitations"].append("The original ABBA runs show timing drift; their approximately 1.55 ratio is retained only as a diagnostic. Interleaved results are primary when available.")
    summary["change_in_mean_match_time_percent"] = (1 / summary["speedup_l2_over_l3"] - 1) * 100
    return summary


def render(root, summary):
    width, height = 420, 360
    sheet = Image.new("RGB", (width * 4, height * 4 + 62), "#171b22")
    draw = ImageDraw.Draw(sheet)
    title_font, small_font = font(21), font(17)
    count = summary["samples_per_image"]
    mode = "interleaved paired" if summary["timing_source"] == "paired" else "ABBA pooled"
    draw.text((14, 10), f"LED pyramid comparison | {mode} median: {count} calls/image/config", fill="white", font=title_font)
    draw.text((14, 36), "L2_A / L3_A detections; same crop per image; main timing method shown above", fill="#b9c4d5", font=small_font)
    for index, row in enumerate(summary["comparisons"]):
        centers = [(row[f"{label}_center_x"], row[f"{label}_center_y"])
                   for label in ("l2", "l3") if row[f"{label}_match"] and row[f"{label}_center_x"] is not None]
        cx, cy = (statistics.mean(p[0] for p in centers), statistics.mean(p[1] for p in centers)) if centers else (384, 288)
        # Shared, 2x enlarged crop makes shifts visible and comparisons spatially consistent.
        box = (round(cx) - 100, round(cy) - 70, round(cx) + 100, round(cy) + 70)
        for offset, label in enumerate(("l2", "l3")):
            x = ((index % 2) * 2 + offset) * width
            y = (index // 2) * height + 62
            color = "#f56b70" if not row[f"{label}_match"] else "#e8edf5"
            draw.text((x + 10, y + 7), f"{row['image']} | {label.upper()} | score {fmt(row[f'{label}_score'])}", fill=color, font=title_font)
            draw.text((x + 10, y + 35), f"median {fmt(row[f'{label}_median_ms'])} ms | n={count}", fill="#b9c4d5", font=small_font)
            path = root / f"{label.upper()}_A" / f"{Path(row['image']).stem}_result.png"
            if path.is_file():
                with Image.open(path) as source:
                    crop = source.convert("RGB").crop(box).resize((400, 280), Image.Resampling.LANCZOS)
                sheet.paste(crop, (x + 10, y + 68))
            else:
                draw.rectangle((x + 10, y + 68, x + 410, y + 348), fill="#272e39")
                draw.text((x + 25, y + 170), "RESULT IMAGE MISSING", fill="#f56b70", font=title_font)
            if not row[f"{label}_match"]:
                draw.rectangle((x + 10, y + 68, x + 410, y + 348), outline="#ff535d", width=4)
                draw.rectangle((x + 14, y + 72, x + 220, y + 105), fill="#661c27")
                draw.text((x + 20, y + 76), "NO MATCH", fill="white", font=title_font)
    sheet.save(root / "comparison.png")


def write_readme(root, summary):
    configs = summary["configurations"]
    l2, l3 = (configs[label]["mean_of_image_medians_ms"] for label in ("L2", "L3"))
    paired = summary["timing_source"] == "paired"
    method_name = "同进程逐图逐次交替测试（主结果）" if paired else "原 ABBA 测试（有时间漂移，仅作参考）"
    method_text = (
        "每图、每配置先预热 1 次，不计入 timings.csv；然后同一进程中做 10 组正式测量。repeat 为偶数时先 L2 后 L3，奇数时先 L3 后 L2。每图每配置对 10 条原始计时取 statistics.median，再对 8 个图像中位数取算术平均。每图另计算 10 个同 repeat 的 t2/t3 比值的中位数供对照，它不等于平均耗时之比。"
        if paired else
        "同一轮按 L2_A → L3_A → L3_B → L2_B（ABBA）顺序运行。每组、每图预热 1 次（不入计时），正式测量 7 次。每配置合并 A、B 两组的 14 条原始计时，每图取 statistics.median，再平均 8 个图像中位数。"
    )
    lines = [
        "# LED 两层与三层金字塔对照", "",
        f"当前耗时依据：**{method_name}**。", "",
        f"两层平均匹配耗时 **{l2:.3f} ms**，三层 **{l3:.3f} ms**；两层/三层耗时比 **{summary['speedup_l2_over_l3']:.3f}×**（大于 1 表示三层更快）。",
        f"由平均匹配耗时换算的 FPS：两层 **{configs['L2']['fps_from_mean_match_ms']:.2f}**，三层 **{configs['L3']['fps_from_mean_match_ms']:.2f}**。这不是完整应用的帧率。", "",
        "## 方法", "",
        method_text, "",
        "timings.csv 的所有原始记录、分数与候选数以及各组 results.csv、run_config.json 全部保留在 summary.json。下表分数、中心和局部图仍来自 L2_A、L3_A；耗时使用上述当前方法。paired 存在时，原 ABBA 数据与计算结果单独放入 abba_diagnostic，交替测试数据放入 paired。各组完整参数以 run_config.json 为准。", "",
        "本实验不提供置信区间。交替测量可减轻缓慢漂移对相邻配置比较的影响，仍不能排除系统噪声。匹配计时不含图像读取、模板生成、补边、绘图和结果保存。", "",
        "## 逐图结果", "",
        "| 图像 | L2 分数 | L3 分数 | 分数差 L3−L2 | 中心距 px | L2 ms | L3 ms | 耗时比 L2/L3 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["comparisons"]:
        lines.append(f"| {row['image']} | {fmt(row['l2_score'])} | {fmt(row['l3_score'])} | {fmt(row['score_delta_l3_minus_l2'])} | {fmt(row['center_distance_px'])} | {fmt(row['l2_median_ms'], 3)} | {fmt(row['l3_median_ms'], 3)} | {fmt(row['speedup_l2_over_l3'], 3)} |")
    if paired:
        checks = summary["paired"]["score_comparison_to_a"]
        all_same = summary["paired"]["all_160_scores_within_tolerance_of_a"]
        lines += [
            "", "## 交替样本与 A 组分数核对", "",
            "实际逐条比较 paired 的 best_score 与同图、同层数 A 组 score，以绝对差 ≤0.01 分作为基本相同的检查标准；这只容许 CSV 舍入差异，不是质量评价标准。",
            "全部 160 条分数均可比较且在容差内。" if all_same else "存在分数差异或缺失，不能直接认定交替结果与 A 组完全相同；请按下表及 summary.json 的逐次差值核对。", "",
            "| 图像 | 成对 t2/t3 中位数 | L2 对 A 最大绝对分差 | L3 对 A 最大绝对分差 | L2/L3 容差检查 |",
            "|---|---:|---:|---:|---|",
        ]
        for row in summary["comparisons"]:
            item = checks[row["image"]]
            statuses = ["通过" if item[label]["all_scores_within_tolerance"] is True else "有差异" if item[label]["all_scores_within_tolerance"] is False else "缺失/不可比较" for label in ("L2", "L3")]
            lines.append(f"| {row['image']} | {fmt(row['median_paired_speedup_l2_over_l3'], 3)} | {fmt(item['L2']['max_abs_score_difference'], 4)} | {fmt(item['L3']['max_abs_score_difference'], 4)} | {' / '.join(statuses)} |")
    abba = summary.get("abba_diagnostic", summary)
    old2, old3 = (abba["configurations"][label]["mean_of_image_medians_ms"] for label in ("L2", "L3"))
    lines += [
        "", "## 原 ABBA 时间漂移诊断", "",
        f"原 ABBA 汇总：两层 {old2:.3f} ms，三层 {old3:.3f} ms，耗时比 {abba['speedup_l2_over_l3']:.3f}×。这些参考数字保留以便审计。",
        "原始计时后段存在明显时间漂移，L2_B 最后 3 图、L3_B 第 8 图尤为明显。**不能把原约 1.55 倍作为精确、可依赖的提升结论**；ABBA 运行顺序并未消除本轮漂移。交替数据存在时，上面的主结果使用交替测量重新计算。", "",
        "| ABBA 组 | 图像 | 7 次原始耗时范围 ms |",
        "|---|---|---:|",
    ]
    for name, images in (("L2_B", ("6.bmp", "7.bmp", "8.bmp")), ("L3_B", ("8.bmp",))):
        for image in images:
            times = abba["runs"][name]["timings"][image]["raw_ms"]
            lines.append(f"| {name} | {image} | {min(times):.3f}–{max(times):.3f} |")
    lines += [
        "", "N/A 表示未匹配或没有可比较的数据；未匹配图在对照图中标红。中心距是两次检测中心的欧氏距离，不是真实定位误差。", "",
        "![每图两层与三层的相同区域放大对照](comparison.png)", "",
        "## 解释与限制", "",
        "- **1.bmp 是模板源图**；SMD 内的原图对应其 x=389、y=225、184×184 裁剪区域，其余 7 张才是独立于模板源的正样本。",
        "- 这些图像均为正样本；没有负样本或完整人工标注，不能据此验证误检率、召回率或普遍准确率。",
        "- 分数表示轮廓相似度，**不是概率**；不同金字塔层数会改变分数，分数变化本身不能证明检测质量改善。",
        "- LED 轮廓对称且使用无符号梯度，角度存在约 180° 的对称歧义；comparison.csv 的角度差已折回 [−180°, 180°)，但仍不能当作真实角度误差。",
        "- 局部图围绕两配置检测中心的平均位置，使用同一裁剪区域放大 2 倍；图中保留各次结果的标记。",
        "- SMD 读取仅针对本次提供文件的已验证布局，不代表支持所有 SMD 版本。", "",
        "复现汇总：`python artifacts/led_pyramid_compare/compare_results.py`（先完成四组运行；如有 paired/timings.csv 则自动采用交替耗时为主结果；需要 Pillow）。", "",
    ]
    (root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    root = parser.parse_args().root.resolve()
    summary = apply_paired(root, summarize(load_runs(root)))
    with (root / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary["comparisons"][0]))
        writer.writeheader()
        writer.writerows(summary["comparisons"])
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    render(root, summary)
    write_readme(root, summary)
    print(json.dumps({"mean_match_ms": {label: data["mean_of_image_medians_ms"] for label, data in summary["configurations"].items()}, "speedup_l2_over_l3": summary["speedup_l2_over_l3"]}, indent=2))


if __name__ == "__main__":
    main()
