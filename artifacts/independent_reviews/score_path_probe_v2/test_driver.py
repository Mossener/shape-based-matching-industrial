"""Eight complete numeric gzip streams, synthesized without native/images."""
from collections import Counter
import csv
import gzip
from pathlib import Path
import tempfile
import unittest
import audit_main as a
import numeric2 as n
import traces as t
from test_traces import fixture


def write_table(directory,kind,rows):
    with gzip.open(directory/(kind+'.csv.gz'),'wt',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=a.HEADERS[kind].split(','));writer.writeheader();writer.writerows(rows)


class Driver(unittest.TestCase):
    def test_complete_eight_stream_synthetic_path(self):
        plan,jobrows,layers,metadata,frames=fixture();ctx,windows,order=t.job_contexts(plan,jobrows,layers,metadata,frames)
        prior=dict(frames=[dict(object_id=1,scene=7,image=3,targets=frames[(1,7,3)]['targets'])])
        vectorrows=[];cellrows=[];maxrows=[];coarse={};local={};key=(5,5,0x42c80000)
        for kind,owner in order:
            if kind=='coarse':
                height,width,tail=n.coarse_span(424,416,80,80);raw=[4]*tail+[0]*(height*width-tail);base=(0,0)
                coarse[0]=raw
            else:
                height=width=16;tail=256;base=windows[owner]['base'];raw=[0]*256;raw[((5-1-base[1])//4)*16+(5-1-base[0])//4]=4
                best=n.maximum(raw,1);local[owner]=dict(raw=raw,best=best)
                maxrows.append(dict(window=owner,center_x=windows[owner]['center'][0],center_y=windows[owner]['center'][1],base_x=base[0],base_y=base[1],raw=best['raw'],score_bits=best['bits'],row=best['row'],col=best['col'],ties=best['ties'],tie_mask=best['tie_mask']))
            vectorrows.append(dict(kind=kind,owner=owner,feature_id=0,x=0,y=0,label=0,skipped=0,cells=len(raw),response_digits=''.join(map(str,raw))))
            for j,value in enumerate(raw):cellrows.append(dict(kind=kind,owner=owner,row=j//width,col=j%width,native_raw=value,native_score_bits=n.score_bits(value,1),computed=int(j<tail),threshold_pass=int(n.score_value(value,1)>85 if kind=='coarse' else n.score_value(value,1)>=85)))
        linkrows=[]
        for pk,p in ctx[0]['parents'].items():linkrows.append(dict(job=0,gt_id=0,point_x=5,point_y=5,coarse_row=pk[0],coarse_col=pk[1],coarse_raw=4,coarse_score_bits=0x42c80000,admitted=1,window=p['window'],point_raw=4,point_score_bits=0x42c80000,point_fine_pass=1,winner_x=5,winner_y=5,winner_raw=4,winner_score_bits=0x42c80000,point_is_winner=1,predicts_emission=1,point_iou_gt=1))
        count=len(linkrows)
        post=[dict(cls='tless_object_1',template=2,x=5,y=5,bits=0x42c80000,box=(-59.,-59.,10.,10.))]
        saved={(1,7,3,'rgb'):[dict(record=post[0],allGT_label='TP',allGT_id=0,eligible_label='TP',eligible_id=0)]}
        truths={(1,7,3):[dict(id=0,cls='tless_object_1',visibility=1.,box=(-59.,-59.,10.,10.))]}
        nmsrows=[dict(object_id=1,scene=7,image=3,arm='rgb',post_rank=0,template=2,match_x=5,match_y=5,score_bits=0x42c80000,selected_rank=0,blocker_post_rank=-1,blocker_iou=0,allGT_label='TP',allGT_id=0)]
        occrows=[dict(job=0,gt_id=0,match_x=5,match_y=5,score_bits=0x42c80000,traced_parents=count,full_pre_multiplicity=count,post_representative_template=2,post_rank=0,nms_selected_rank=0,nms_blocker=-1,pre_box_x=-59,pre_box_y=-59,pre_box_w=10,pre_box_h=10,rep_box_x=-59,rep_box_y=-59,rep_box_w=10,rep_box_h=10,pre_iou_gt=1,rep_iou_gt=1)]
        physical=[dict(job=0,gt_id=0,physical_x=5,physical_y=5,on_grid=1,in_physical_domain=1,raw=4,score_bits=0x42c80000,feature_id=0,response=4)]
        streams=dict(jobs=jobrows,feature_vectors=vectorrows,native_cells=cellrows,local_maxima=maxrows,physical_anchors=physical,parent_links=linkrows,occurrences=occrows,fullclass_nms_assignment=nmsrows)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            for kind,rows in streams.items():write_table(path,kind,rows)
            loader=lambda frame,tids,keys:({2:Counter({key:count})},{key:2},post,count)
            counts,diagnostics,arms=a.audit_numeric(plan,prior,path,metadata,layers,saved,truths,loader)
            self.assertEqual((counts['jobs'],counts['rgb_positive_controls'],counts['parent_links'],counts['occurrence_rows']),(1,1,count,1))
            self.assertEqual(arms['rgb']['any_traced_selected_target_tp'],1)
            self.assertEqual(diagnostics[0]['physical_score'],100.)
            # A complete actual runner rejects corruption from any table.
            for kind,field,value in [('jobs','template_id',3),('feature_vectors','label',8),('native_cells','native_raw',0),('local_maxima','ties',0),('physical_anchors','response',-1),('parent_links','predicts_emission',0),('occurrences','traced_parents',count+1),('fullclass_nms_assignment','allGT_label','FP')]:
                bad=[dict(row) for row in streams[kind]];bad[0][field]=value;write_table(path,kind,bad)
                with self.subTest(kind=kind),self.assertRaises(ValueError):a.audit_numeric(plan,prior,path,metadata,layers,saved,truths,loader)
                write_table(path,kind,streams[kind])

    def test_csv_schema_and_width_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.csv';path.write_text('job_id,wrong\n0,1\n')
            with self.assertRaises(ValueError):list(a.table(path,'jobs'))
            path.write_text(a.HEADERS['jobs']+'\n'+','.join(['0']*15)+'\n')
            with self.assertRaises(ValueError):list(a.table(path,'jobs'))


if __name__=='__main__':unittest.main()
