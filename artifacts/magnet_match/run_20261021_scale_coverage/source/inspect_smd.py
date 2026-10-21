"""Read-only, sample-specific SMD inspection. No matcher or training is run."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import math
import shutil
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / "磁片"
EXPECTED = "6335f11e6b3c806bbd2e0b4fd2ab5150c015d3e9d18908b78ef6e316aeb06166"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inspect():
    b = (SOURCE / "moban.smd").read_bytes()
    assert sha(b) == EXPECTED and len(b) == 652672, "Unsupported sample"
    def read(fmt, offset):
        assert 0 <= offset <= len(b) - struct.calcsize(fmt), "Truncated field"
        return struct.unpack_from(fmt, b, offset)
    magic, x0, y0, x1, y1 = read("<5I", 0)
    assert magic == 0x00444d53 and (x0,y0,x1,y1) == (121,108,535,383)
    version, w, h, channels, stride, n = read("<6I", 20)
    assert (version,w,h,channels,stride,n) == (20161201,640,480,1,640,307200)
    image_end = 44+n
    assert read("<6I", image_end) == (version,w,h,channels,stride,n)
    second_start = image_end+24
    model = second_start+n
    assert read("<I", model)[0] == 20171201
    levels = read("<I", model+48)[0]
    assert levels == 6
    cursor = model+52
    expected = [(414,275,1214),(207,137,605),(104,69,301),(52,35,149),(25,18,73),(13,9,35)]
    records, summaries = [], []
    for level, (lw,lh,count) in enumerate(expected):
        offset = cursor
        assert read("<5I",cursor) == (2,level,lw,lh,count)
        cursor += 20
        points=[]
        for i in range(count):
            flag,x,y,angle = read("<I3f",cursor)
            assert flag <= 3 and all(math.isfinite(v) for v in (x,y,angle))
            # SMD subpixel fitting can extend <half a pixel beyond a level edge.
            # Preserve floats; never use these directly as memory indices.
            assert -.5 <= x < lw+.5 and -.5 <= y < lh+.5 and 0 <= angle <= 360
            points.append((flag,x,y,angle))
            records.append((level,flag,x,y,angle))
            cursor += 16
        summaries.append(dict(level=level,header_offset=offset,width=lw,height=lh,
                              point_count=count,end_offset=cursor,
                              flags=dict(Counter(p[0] for p in points)),
                              x_range=[min(p[1] for p in points),max(p[1] for p in points)],
                              y_range=[min(p[2] for p in points),max(p[2] for p in points)],
                              angle_range=[min(p[3] for p in points),max(p[3] for p in points)]))
    assert cursor == len(b), "Unparsed trailing bytes"
    im = Image.frombytes("L",(w,h),b[44:image_end])
    secondary = Image.frombytes("L",(w,h),b[second_start:model])
    im.save(OUT/"smd_template.png")
    secondary.save(OUT/"smd_mask.png")
    overlay=im.convert("RGB"); draw=ImageDraw.Draw(overlay)
    for level,flag,x,y,angle in records:
        if level: continue
        px,py=x+x0,y+y0
        draw.ellipse((px-1,py-1,px+1,py+1),fill=(40,255,70))
    draw.rectangle((x0,y0,x1-1,y1-1),outline=(255,190,0),width=2)
    overlay.save(OUT/"smd_contours.png")
    with (OUT/"smd_contours.csv").open("w",newline="",encoding="utf-8") as f:
        out=csv.writer(f);out.writerow(["level","flag","x","y","smd_angle_deg"]);out.writerows(records)
    original=np.asarray(im)
    input_records=[];tiles=[]
    ascii_inputs=OUT/"build"/"input";ascii_inputs.mkdir(parents=True,exist_ok=True)
    for path in [SOURCE/"moban.smd"]+sorted(SOURCE.glob("M*.bmp")):
        data=path.read_bytes();copy=ascii_inputs/path.name;copy.write_bytes(data)
        assert sha(copy.read_bytes())==sha(data)
        r=dict(path=str(path.relative_to(ROOT)),bytes=len(data),sha256=sha(data),ascii_copy=str(copy.relative_to(ROOT)))
        if path.suffix.lower()==".bmp":
            q=Image.open(path).convert("L");a=np.asarray(q)
            assert a.shape==(h,w)
            r.update(width=w,height=h,embedded_image_equal=bool(np.array_equal(a,original)),
                     role="template_source_selfcheck" if np.array_equal(a,original) else "non_source_positive_sample")
            tile=q.convert("RGB");ImageDraw.Draw(tile).text((10,8),path.name,fill=(255,0,0));tiles.append(tile.resize((400,300)))
        input_records.append(r)
    tiles.append(overlay.resize((400,300)))
    canvas=Image.new("RGB",(1600,600),(25,25,25))
    for i,tile in enumerate(tiles):canvas.paste(tile,(i%4*400,i//4*300))
    canvas.save(OUT/"input_overview.png")
    # Independent image-coordinate direction check: Gaussian(radius=1), Sobel,
    # nearest pixel. Compare both signs modulo 360 without refitting points.
    a=np.array(im.filter(ImageFilter.GaussianBlur(1)),dtype=float)
    gx=(a[:-2,2:]+2*a[1:-1,2:]+a[2:,2:])-(a[:-2,:-2]+2*a[1:-1,:-2]+a[2:,:-2])
    gy=(a[2:,:-2]+2*a[2:,1:-1]+a[2:,2:])-(a[:-2,:-2]+2*a[:-2,1:-1]+a[:-2,2:])
    p=np.array([r[2:] for r in records if r[0]==0])
    xx=np.rint(p[:,0]+x0).astype(int)-1; yy=np.rint(p[:,1]+y0).astype(int)-1
    theta=np.degrees(np.arctan2(gy[yy,xx],gx[yy,xx]))%360
    magnitude=np.hypot(gy[yy,xx],gx[yy,xx]);keep=magnitude>=20
    direction={"method":"Pillow GaussianBlur(1), independent numpy Sobel, nearest rounded coordinates, magnitude>=20, circular 360-degree difference",
               "selected_points":int(keep.sum())}
    for name,sign in [("positive_smd",1),("negative_smd",-1)]:
        errors=np.abs((theta-sign*p[:,2]+180)%360-180)[keep]
        direction[name] = {"median_deg":float(np.median(errors)),"p90_deg":float(np.quantile(errors,.9))}
    mask_array=np.asarray(secondary);ys,xs=np.nonzero(mask_array)
    report=dict(source_sha256=sha(b),sample_specific=True,total_bytes=len(b),roi_xyxy=[x0,y0,x1,y1],
                roi_size=[x1-x0,y1-y0],embedded_image=dict(header_offset=20,data_offset=44,width=w,height=h,bytes=n),
                secondary_image=dict(header_offset=image_end,data_offset=second_start,width=w,height=h,bytes=n,
                                     values={str(k):v for k,v in Counter(mask_array.ravel().tolist()).items()},
                                     nonzero_bbox_xyxy=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)],
                                     semantics="unknown; do not assume nonzero means included training mask"),
                model_offset=model,model_header_u32=list(read("<13I",model)),levels=summaries,
                parsed_end=cursor,direction_check=direction,inputs=input_records,
                limitations=["Only supplied moban.smd layout is recognized.","Unknown header parameters and flag meaning are preserved, not interpreted.",
                             "Per-level dimensions are explicit; they do not equal repeated integer right shifts.",
                             "No ground-truth localization or negative images supplied; no accuracy claim."])
    (OUT/"smd_manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"parsed_bytes":cursor,"levels":[q[2] for q in expected],"source_image":"M01.bmp","direction_check":direction},ensure_ascii=False,indent=2))

if __name__ == "__main__":inspect()
