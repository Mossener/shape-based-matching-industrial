"""Independent standard-library numeric contract; no target imports."""
from array import array
import math
import struct

def need(condition, message):
    if not condition:
        raise ValueError(message)

def integer(value):
    need(not isinstance(value,bool),'Boolean is not an integer field')
    number=float(value)
    need(math.isfinite(number) and number==math.floor(number) and abs(number)<2**53,'Unsafe/noninteger field')
    return int(number)


def finite(value):
    number=float(value);need(math.isfinite(number),'Nonfinite numeric field');return number


def bits_value(bits):
    value=struct.unpack('<f',struct.pack('<I',integer(bits)))[0]
    need(math.isfinite(value),'Nonfinite binary32 field');return value


def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]


def value_bits(value):return struct.unpack('<I',struct.pack('<f',finite(value)))[0]


def score_value(raw,count):
    raw,count=integer(raw),integer(count)
    need(0<count<8192 and 0<=raw<=4*count,'Invalid actual feature denominator/raw')
    # C++ converts the product to binary32 before the binary32 division.
    return f32(f32(raw*100.)/(4*count))


def score_bits(raw,count):return value_bits(score_value(raw,count))


def coarse_span(width,height,template_width,template_height,step=8):
    width,height,tw,th,step=map(integer,(width,height,template_width,template_height,step))
    need(min(width,height,tw,th,step)>0 and width%step==height%step==0,'Invalid coarse dimensions')
    rows,cols=height//step,width//step
    wf,hf=(tw-1)//step+1,(th-1)//step+1
    count=(rows-hf)*cols+(cols-wf)+1
    need(0<=count<=rows*cols,'Unsupported flat coarse span')
    return rows,cols,count


def sum_features(rows,count,cells,size,base=(0,0),tail=None):
    need(0<count<8192 and cells>0,'Invalid feature/cell count')
    if tail is None:tail=cells
    need(0<=tail<=cells,'Invalid zero tail')
    raw=array('H',[0])*cells;signature=[];seen=0
    for index,row in enumerate(rows):
        need(index<count and integer(row['feature_id'])==index,'Feature index/order/count differs')
        x,y,label=map(integer,(row['x'],row['y'],row['label']))
        need(0<=label<8,'Invalid orientation label')
        skipped=not(0<=x+base[0]<size[0] and 0<=y+base[1]<size[1])
        need(integer(row['skipped'])==int(skipped) and integer(row['cells'])==cells,'Whole-stream skip/cell declaration differs')
        digits=row['response_digits']
        need(len(digits)==cells and not(set(digits)-set('01234')),'Invalid response digit/length')
        need(not any(c!='0' for c in digits[tail:]),'Nonzero coarse tail')
        if skipped:need(not any(c!='0' for c in digits),'Skipped feature has nonzero contributions')
        else:
            for j,c in enumerate(digits):raw[j]+=ord(c)-48
        signature.append((x,y,label));seen+=1
    need(seen==count,'Missing feature rows')
    return raw,signature


def verify_cells(rows,raw,count,shape,kind,tail=None):
    height,width=shape;need(len(raw)==height*width and kind in ('coarse','local'),'Cell shape/kind differs')
    if tail is None:tail=len(raw)
    seen=0;score_cache={}
    for j,row in enumerate(rows):
        need(j<len(raw) and (integer(row['row']),integer(row['col']))==divmod(j,width),'Cell order/position differs')
        value=integer(raw[j])
        if value not in score_cache:score_cache[value]=(score_bits(value,count),score_value(value,count))
        bits,score=score_cache[value]
        expected=(value,bits,int(j<tail),int(score>85 if kind=='coarse' else score>=85))
        actual=tuple(integer(row[k]) for k in ('native_raw','native_score_bits','computed','threshold_pass'))
        need(actual==expected,'Cell raw/binary32/computed/threshold differs');seen+=1
    need(seen==len(raw),'Missing native cells')


def maximum(raw,count):
    need(len(raw)==256,'Local maximum needs 256 cells')
    highest=max(raw);need(highest<=4*count,'Local raw exceeds feature count')
    row,col=divmod(raw.index(highest),16) if highest else (-1,-1)
    mask=''.join('1' if value==highest else '0' for value in raw)
    return dict(raw=highest,bits=score_bits(highest,count),row=row,col=col,ties=mask.count('1'),tie_mask=mask)


def trunc4(value):return (abs(value)//4)*(1 if value>=0 else -1)


def base_for(center):return tuple((trunc4(integer(value))-8)*4 for value in center)


def verify_maximum(row,raw,count,center):
    expected=maximum(raw,count)
    for key in ('raw','row','col','ties'):
        need(integer(row[key])==expected[key],'Local maximum '+key+' differs')
    need(integer(row['score_bits'])==expected['bits'] and row['tie_mask']==expected['tie_mask'],'Local maximum score/tie mask differs')
    need(tuple(integer(row['center_'+axis]) for axis in ('x','y'))==tuple(center),'Local center differs')
    need(tuple(integer(row['base_'+axis]) for axis in ('x','y'))==base_for(center),'Local base differs')
    return expected


def parent(row,col,template_size,fine_size=(848,832)):
    row,col=integer(row),integer(col)
    need(row>=0 and col>=0 and min(template_size)>0,'Invalid parent dimensions')
    center=tuple(min(max(2*(axis*8+3)+1,32),size-template-32) for axis,size,template in zip((col,row),fine_size,template_size))
    return center,base_for(center)


def reachable(point,template_size,fine_size=(848,832),coarse_shape=(52,53)):
    x,y=map(integer,point);need((x-1)%4==(y-1)%4==0,'Point off native grid')
    result={}
    for row in range(coarse_shape[0]):
        for col in range(coarse_shape[1]):
            center,base=parent(row,col,template_size,fine_size)
            if base[0]+1<=x<=base[0]+61 and base[1]+1<=y<=base[1]+61:result[(row,col)]=(center,base)
    return result


def neighbors(anchor):
    x,y=map(integer,anchor)
    axes=[]
    for value in (x,y):
        low=1+4*((value-1)//4);axes.append([low] if low==value else [low,low+4])
    return [(u,v) for u in axes[0] for v in axes[1]]


def iou(a,b):
    x,y,w,h=map(finite,a);u,v,q,r=map(finite,b)
    need(min(w,h,q,r)>0,'Nonpositive IoU box')
    intersection=max(0.,min(x+w,u+q)-max(x,u))*max(0.,min(y+h,v+r)-max(y,v))
    return intersection/(w*h+q*r-intersection)


def canonical(row):
    x,y,w,h=row['box']
    return (-bits_value(row['bits']),row['cls'],row['template'],row['y'],row['x'],y,x,w,h)


def nms(records):
    need(records==sorted(records,key=canonical),'Noncanonical full-frame record order')
    selected=[];blocked=[]
    for rank,row in enumerate(records):
        blocker=next((old for old in selected if row['cls']==records[old]['cls'] and iou(row['box'],records[old]['box'])>.3),-1)
        blocked.append(blocker)
        if blocker<0:selected.append(rank)
    return selected,blocked


def assign(records,truths,eligible=False):
    need(records==sorted(records,key=canonical),'Noncanonical selected order')
    need(len({row['id'] for row in truths})==len(truths),'Duplicate GT ID')
    result=[('FP',-1) for row in records];used=set()
    def pass_for(ignored):
        for index,row in enumerate(records):
            if result[index][0]!='FP':continue
            choices=[]
            for gt in truths:
                if gt['id'] in used or (row['cls'] and gt['cls'] and row['cls']!=gt['cls']):continue
                if eligible and ((gt['visibility']<.5)!=ignored):continue
                value=iou(row['box'],gt['box'])
                if value>=.5:choices.append((-value,gt['id']))
            if choices:
                _,identity=min(choices);used.add(identity);result[index]=('IGNORE' if ignored else 'TP',identity)
    pass_for(False)
    if eligible:pass_for(True)
    return result


def reconcile_occurrences(predicted,pre,points):
    need(all(integer(count)>0 for count in predicted.values()),'Nonpositive emission multiplicity')
    for key,count in predicted.items():need(pre.get(key,0)>=count,'Traced emission exceeds complete pre multiplicity')
    for key,count in pre.items():
        if count>0 and key[:2] in points:need(predicted.get(key,0)>0,'Actual probed-point occurrence lacks traced parent')
    return len(predicted)
