"""Independently check every literal native geometry-fixture output pixel."""
import argparse
import gzip
import json
import math
from pathlib import Path
import input_contract as c
import independent_numeric as n


def reflection(index,size):
    while index<0 or index>=size:
        index=-index if index<0 else 2*size-index-2
    return index


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--native',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();c.need(out.is_relative_to(c.HERE) and not out.exists(),'Fresh selftest audit receipt required')
    stage=c.load(args.native.parent/'SELFTEST_FREEZE.json');c.need(stage['passed'] and stage['native_exit']==0,'Native fixture stage gate')
    for q in stage['files']+[stage['build']]:c.check(q)
    fixture=c.load(args.native/'selftest.json');c.need(fixture==dict(passed=True,fixtures=7,image_decodes=0,matcher_calls=0),'Native fixture receipt')
    with gzip.open(c.numeric_path(args.native/'fixtures.jsonl.gz'),'rt') as stream:records=[json.loads(line) for line in stream]
    c.need(len(records)==35,'Native fixture maps incomplete');weights=[1,4,6,4,1]
    for fixture in range(7):
        group=records[fixture*5:fixture*5+5];c.need([q['name'] for q in group]==['M0','M1','B1','A0','A1'],'Native fixture map order')
        maps={q['name']:n.read_map(q['map']) for q in group}
        def crop(x,y):
            if fixture in (0,4,6):return 255
            if fixture in (1,5):return 0 if (x,y)==(1,1) else 255
            if fixture==2:return 255 if x==y else 0
            return 255 if x==0 or y==0 else 0
        def initial(x,y,alpha=False):
            width,height=(5,3) if fixture==4 else (4,4)
            if fixture==5:sx,sy=10-y,x-6
            elif fixture==6:sx,sy=(x-4)/2,(y-4)/2
            elif fixture==4:sx,sy=x-5.5,y-6.5
            else:sx,sy=x-6,y-6
            if not alpha:
                ix,iy=math.floor(sx+.5),math.floor(sy+.5)
                return crop(ix,iy) if 0<=ix<width and 0<=iy<height else 0
            ix,iy=math.floor(sx),math.floor(sy);fx,fy=sx-ix,sy-iy
            return sum(weight for xx,yy,weight in [(ix,iy,(1-fx)*(1-fy)),(ix+1,iy,fx*(1-fy)),(ix,iy+1,(1-fx)*fy),(ix+1,iy+1,fx*fy)] if 0<=xx<width and 0<=yy<height)
        for y in range(16):
            for x in range(16):
                c.need(n.value_at(maps['M0'],x,y)==initial(x,y),'Literal affine mask pixel')
                c.need(n.float_value(n.value_at(maps['A0'],x,y))==initial(x,y,True),'Literal affine support pixel')
        for y in range(8):
            for x in range(8):
                c.need(n.value_at(maps['M1'],x,y)==initial(2*x,2*y),'Literal nearest pixel')
                mask_sum=alpha_sum=0
                for dy in range(-2,3):
                    for dx in range(-2,3):
                        weight=weights[dx+2]*weights[dy+2];sx=reflection(2*x+dx,16);sy=reflection(2*y+dy,16)
                        mask_sum+=weight*initial(sx,sy);alpha_sum+=weight*initial(sx,sy,True)
                c.need(n.value_at(maps['B1'],x,y)==(mask_sum+128)//256,'Literal uint8 pyrDown pixel')
                c.need(n.float_value(n.value_at(maps['A1'],x,y))==alpha_sum/256,'Literal alpha pyrDown pixel')
    result=dict(passed=True,fixtures=7,pixel_maps=35,build=stage['build'],selftest_stage=c.pin(args.native.parent/'SELFTEST_FREEZE.json'),sources=[c.pin(c.HERE/'verify_selftest.py'),c.pin(c.HERE/'independent_numeric.py')],
                inputs=[c.pin(args.native/'fixtures.jsonl.gz'),c.pin(args.native/'selftest.json')],image_bytes_opened=0,matcher_calls=0,
                limitation='Literal rectangle/hole/diagonal/concave,odd-crop,90-degree and2x-scale toys; not exhaustive affine geometry or gradient-selection support proof')
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,pixel_maps=35,image_bytes_opened=0)))


if __name__=='__main__':main()
