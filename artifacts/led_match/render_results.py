"""Render this one-off LED experiment. Requires Python with Pillow."""
from pathlib import Path
import csv
import hashlib
import json
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
model = (ROOT / "LED/ku.smd").read_bytes()
template = Image.frombytes("L", (184, 184), model[44:33900])
template.save(OUT / "smd_template.png")
template_rgb = template.convert("RGB").resize((736, 736))
draw = ImageDraw.Draw(template_rgb)
contours = list(csv.DictReader((OUT / "smd_contours.csv").open()))
for p in contours:
    if p["level"] == "0":
        x, y = (float(p["x"]) + 32) * 4, (float(p["y"]) + 32) * 4
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill="#42ff53")
template_rgb.save(OUT / "smd_contours.png")

rows = list(csv.DictReader((OUT / "results.csv").open()))
assert len(rows) == 8 and {r["image"] for r in rows} == {f"{i}.bmp" for i in range(1, 9)}
sheet = Image.new("RGB", (1600, 940), "#171b22")
for i, row in enumerate(rows):
    im = Image.open(OUT / f"{i + 1}_result.png").convert("RGB")
    assert im.size == (768, 576)
    tile = Image.new("RGB", (400, 470), "#171b22")
    d = ImageDraw.Draw(tile)
    d.text((12, 10), f"{row['image']} | score {float(row['score']):.1f} | {float(row['match_ms']):.1f} ms", fill="white")
    small = ImageOps.contain(im, (390, 293))
    tile.paste(small, ((400 - small.width) // 2, 34))
    cx, cy = float(row["center_x"]), float(row["center_y"])
    crop = im.crop((round(cx) - 90, round(cy) - 70, round(cx) + 90, round(cy) + 70))
    tile.paste(crop, (110, 324))
    sheet.paste(tile, ((i % 4) * 400, (i // 4) * 470))
sheet.save(OUT / "overview.png")

scores = [float(row["score"]) for row in rows]
times = [float(row["match_ms"]) for row in rows]
summary = {
    "model": "LED/ku.smd",
    "model_sha256": hashlib.sha256(model).hexdigest(),
    "template_source": "1.bmp, exact pixel match to crop x=389,y=225,width=184,height=184",
    "independent_positive_images": 7,
    "source_images": 8,
    "matches_above_threshold": sum(s >= 75 for s in scores),
    "threshold": 75,
    "score_min": min(scores), "score_max": max(scores),
    "repetitions_per_image": 5,
    "time_statistic": "Median of five detector.match calls per image; mean of these medians",
    "mean_ms": sum(times) / len(times), "min_ms": min(times), "max_ms": max(times),
    "approx_fps_from_mean": 1000 / (sum(times) / len(times)),
    "input_size": [768, 576], "padded_match_size": [896, 704],
    "template_poses": 900, "angle_step_degrees": 2,
    "cpu": "13th Gen Intel(R) Core(TM) i5-13500HX",
    "scales": [0.9, 0.95, 1.0, 1.05, 1.1],
    "contour_points_per_pyramid": [236, 111, 46, 22],
    "pyramids_used": [0, 1], "openmp_threads": 4, "opencv_threads": 1,
    "limits": ["Template image is a crop of 1.bmp; the other seven images are positive examples only",
               "No labeled accuracy or false-positive rate",
               "Scores are similarities, not calibrated probabilities",
               "Angles may be ambiguous due to contour symmetry and unsigned gradients",
               "SMD decoder supports only this supplied file layout",
               "Timing excludes image I/O, template generation, padding, drawing and saving"],
}
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
