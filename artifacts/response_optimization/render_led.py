"""Render the current matcher's LED overlays; timings come from the benchmark."""
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

OUT = Path(__file__).resolve().parent / "led_results"
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 19)
rows = list(csv.DictReader((OUT / "results.csv").open(encoding="utf-8-sig", newline="")))
assert len(rows) == 8 and {r["image"] for r in rows} == {f"{i}.bmp" for i in range(1, 9)}
sheet = Image.new("RGB", (1600, 1020), "#171b22")
draw = ImageDraw.Draw(sheet)
draw.text((20, 10), "优化后的 LED 轮廓匹配：绿色为 SMD 模板特征，黄色为位置和范围", font=font, fill="white")
for i, row in enumerate(rows):
    image = Image.open(OUT / f"{i+1}_result.png").convert("RGB")
    assert image.size == (768, 576) and float(row["score"]) >= 75
    x, y = (i % 4)*400, (i // 4)*480+50
    draw.text((x+12, y), f"{row['image']}  匹配分数 {float(row['score']):.1f}", font=font, fill="white")
    thumb = ImageOps.contain(image, (390, 293))
    sheet.paste(thumb, (x+(400-thumb.width)//2, y+32))
    cx, cy = float(row["center_x"]), float(row["center_y"])
    close = image.crop((round(cx)-90, round(cy)-70, round(cx)+90, round(cy)+70))
    sheet.paste(close, (x+110, y+332))
sheet.save(OUT / "overview.png")
print(OUT / "overview.png")
