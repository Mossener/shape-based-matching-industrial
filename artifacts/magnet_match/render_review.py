"""Add independent coarse GT and post-NMS point boxes without rerunning matching."""
import argparse
import csv
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw

def render(run,annotations):
    report=json.loads((run/'coarse_localization.json').read_text())
    ann={r['file']:r for r in json.loads(annotations.read_text(encoding='utf-8'))['images']}
    with (run/'results.csv').open() as f:top={r['image']:r for r in csv.DictReader(f)}
    with Path(__file__).with_name('smd_contours.csv').open() as f:points=[r for r in csv.DictReader(f) if int(r['level'])==0]
    source=Path(__file__).resolve().parents[2]/'磁片'
    tiles=[]
    for row in report['images']:
        frame=Image.open(source/row['image']).convert('RGB');d=ImageDraw.Draw(frame)
        best=top[row['image']];angle=float(best['angle_deg'])*math.pi/180;scale=float(best['scale']);cs,sn=math.cos(angle),math.sin(angle)
        ox=float(best['center_x'])-207*scale;oy=float(best['center_y'])-137.5*scale
        for p in points:
            x=(float(p['x'])-207)*scale;y=(float(p['y'])-137.5)*scale
            px=round(cs*x+sn*y+207*scale)+ox;py=round(-sn*x+cs*y+137.5*scale)+oy
            d.ellipse((px-1,py-1,px+1,py+1),fill=(40,255,70))
        for g in ann[row['image']]['objects']:
            x,y,w,h=g['bbox_xywh'];d.rectangle((x,y,x+w,y+h),outline=(50,170,255),width=2)
        for p in row['detections']:
            x,y,w,h=p['box'];d.rectangle((x,y,x+w,y+h),outline=(255,190,0),width=2)
        d.rectangle((0,0,640,35),fill=(22,24,28))
        d.text((10,10),f'{row["image"]} score {float(best["score"]):.2f} angle {float(best["angle_deg"]):.0f} scale {float(best["scale"]):.2f} | IoU {row["best_iou"]:.3f}',fill=(240,240,240))
        d.text((10,460),'green: SMD features | blue: manual GT | yellow: NMS point box',fill=(255,255,255))
        frame.save(run/f'{Path(row["image"]).stem}_review.png');frame.thumbnail((400,300));tiles.append(frame)
    canvas=Image.new('RGB',(1600,600),(22,24,28))
    for i,t in enumerate(tiles):canvas.paste(t,(i%4*400,i//4*300))
    d=ImageDraw.Draw(canvas);d.text((1210,330),'L3 | threshold75 | 3060 poses',fill='white');d.text((1210,350),'scale .60..1.40 step .05 | angle2',fill='white');d.text((1210,370),'source: 1/1 TP; non-source:6/6 TP',fill='white');d.text((1210,390),'7 positives; no general accuracy claim',fill='white')
    canvas.save(run/'overview.png')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--annotations',type=Path,default=Path(__file__).with_name('manual_boxes.json'));a=p.parse_args();render(a.run,a.annotations)
