"""Independent owner and parent-link mutation fixtures."""
import copy
import unittest
import numeric2 as n
import traces as t


def fixture():
    key=[1,7,3,'rgb',2]
    point=(5,5);parents=n.reachable(point,(80,80))
    job=dict(key=key,physical_anchors=1,native_grid_points=1,parent_point_links=len(parents),unique_reachable_parents=len(parents),unique_local_windows=len({v[1] for v in parents.values()}),fine_features=1,coarse_features=1,targets=[dict(gt_id=0,physical_anchor=[5,5],off_native_grid=False,points=[[5,5]])],point_plan=[dict(point=[5,5],parents=[dict(row=r,col=c,coarse_x=c*8+3,coarse_y=r*8+3,start=list(center),base=list(base)) for (r,c),(center,base) in parents.items()])])
    meta=dict(template_id=2,class_id='tless_object_1',training_image_id=9,angle=0.,scale=1.,warped_mask_bbox=[0,0,10,10],tl_x=0,tl_y=0)
    layer=dict(width=80,height=80,min_x=0,min_y=0,max_x=0,max_y=0,actual_features=1)
    row=dict(job_id='0',object_id='1',scene='7',image='3',arm='rgb',template_id='2',training_image='9',angle='0',scale='1',fine_features='1',coarse_features='1',gt_id='0',physical_x='5',physical_y='5')
    target=dict(gt_id=0,bbox=[-59,-59,10,10],rgb_tp_box=[-59,-59,10,10],rgb_tp_template=2,rgb_tp_pose=[9,0.,1.],rgb_tp_match=[5,5],rgb_tp_score_bits=0x42c80000)
    return dict(jobs=[job]),[row],{('rgb',1,2,level):dict(layer) for level in (0,1)},{(1,'rgb'):{2:meta}},{(1,7,3):dict(targets=[target])}


def context():return t.job_contexts(*fixture())


class TraceJoins(unittest.TestCase):
    def test_identity_join_and_windows(self):
        contexts,windows,order=context()
        self.assertEqual(contexts[0]['key'],(1,7,3,'rgb',2))
        self.assertEqual(order[0],('coarse',0))
        self.assertEqual(set(windows),set(range(len(windows))))
        self.assertEqual(contexts[0]['points'][(5,5)],set(n.reachable((5,5),(80,80))))

    def test_missing_duplicate_wrong_pose_and_anchor_jobs_rejected(self):
        for field,value in [('template_id','3'),('training_image','8'),('physical_x','9'),('fine_features','2'),('job_id','1')]:
            args=list(fixture());args[1]=copy.deepcopy(args[1]);args[1][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):t.job_contexts(*args)
        for rows in ([],fixture()[1]*2):
            args=list(fixture());args[1]=rows
            with self.assertRaises(ValueError):t.job_contexts(*args)

    def test_parent_plan_missing_duplicate_and_geometry_mutations_rejected(self):
        for mutate in ('missing','duplicate','base','coarse'):
            args=list(fixture());args[0]=copy.deepcopy(args[0]);pp=args[0]['jobs'][0]['point_plan'][0]['parents']
            if mutate=='missing':pp.pop()
            if mutate=='duplicate':pp.append(copy.deepcopy(pp[0]))
            if mutate=='base':pp[0]['base'][0]+=4
            if mutate=='coarse':pp[0]['coarse_x']+=1
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):t.job_contexts(*args)

    def test_owner_mapping_does_not_assume_plan_order(self):
        args=list(fixture());second=copy.deepcopy(args[0]['jobs'][0]);second['key'][4]=1
        args[0]['jobs'].insert(0,second)
        row=copy.deepcopy(args[1][0]);row['job_id']='1';row['template_id']='1';args[1].append(row)
        args[2].update({('rgb',1,1,level):dict(args[2][('rgb',1,2,level)]) for level in (0,1)})
        args[3][(1,'rgb')][1]=dict(args[3][(1,'rgb')][2],template_id=1)
        # The synthetic second target is deliberately binary, whose pose maps
        # to the preserved RGB identity but whose template ID may differ.
        second['key'][3]='binary_empty_mask';row['arm']='binary_empty_mask'
        args[2].update({('binary_empty_mask',1,1,level):dict(args[2][('rgb',1,2,level)]) for level in (0,1)})
        args[3][(1,'binary_empty_mask')]={1:dict(args[3][(1,'rgb')][2],template_id=1)}
        ctx,_,_=t.job_contexts(*args)
        self.assertEqual([ctx[i]['key'][4] for i in ctx],[2,1])

    def test_physical_sums_domain_and_missing_feature_rejected(self):
        ctx,_,_=context();signatures={0:[(0,0,0)]}
        row=dict(job='0',gt_id='0',physical_x='5',physical_y='5',on_grid='1',in_physical_domain='1',raw='4',score_bits=str(0x42c80000),feature_id='0',response='4')
        self.assertEqual(t.check_physical([row],ctx,signatures),1)
        for field,value in [('raw','3'),('score_bits','0'),('response','-1'),('on_grid','0'),('feature_id','1'),('physical_x','9')]:
            bad=dict(row);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):t.check_physical([bad],ctx,signatures)
        with self.assertRaises(ValueError):t.check_physical([],ctx,signatures)

    def test_out_of_domain_physical_has_no_score(self):
        ctx,_,_=context();signatures={0:[(-10,0,0)]}
        row=dict(job='0',gt_id='0',physical_x='5',physical_y='5',on_grid='1',in_physical_domain='0',raw='',score_bits='',feature_id='0',response='-1')
        self.assertEqual(t.check_physical([row],ctx,signatures),1)
        bad=dict(row,raw='0')
        with self.assertRaises(ValueError):t.check_physical([bad],ctx,signatures)

    def test_parent_links_complete_values_and_rgb_control(self):
        ctx,windows,_=context();coarse={0:[4]*2756};local={}
        for wid,win in windows.items():
            raw=[0]*256;row=(5-1-win['base'][1])//4;col=(5-1-win['base'][0])//4;raw[row*16+col]=4
            local[wid]=dict(raw=raw,best=n.maximum(raw,1))
        rows=[]
        for pk,p in ctx[0]['parents'].items():
            rows.append(dict(job='0',gt_id='0',point_x='5',point_y='5',coarse_row=str(pk[0]),coarse_col=str(pk[1]),coarse_raw='4',coarse_score_bits=str(0x42c80000),admitted='1',window=str(p['window']),point_raw='4',point_score_bits=str(0x42c80000),point_fine_pass='1',winner_x='5',winner_y='5',winner_raw='4',winner_score_bits=str(0x42c80000),point_is_winner='1',predicts_emission='1',point_iou_gt='1'))
        self.assertEqual(t.check_links(rows,ctx,coarse,local),dict(parent_links=len(rows),rgb_positive_controls=1))
        self.assertEqual(t.expected_emissions(ctx[0],coarse[0],local),{(5,5,0x42c80000):len(rows)})
        for field,value in [('window','999'),('coarse_score_bits','0'),('predicts_emission','0'),('point_raw','3'),('point_iou_gt','0'),('point_is_winner','0')]:
            bad=copy.deepcopy(rows);bad[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):t.check_links(bad,ctx,coarse,local)
        for bad in (rows[:-1],rows+[dict(rows[0])]):
            with self.assertRaises(ValueError):t.check_links(bad,ctx,coarse,local)
        ctx[0]['original'][0]['rgb_tp_score_bits']=0x42aa0000
        with self.assertRaises(ValueError):t.check_links(rows,ctx,coarse,local)

    def test_streamed_map_join_and_missing_owner_rejected(self):
        # Small pure stream fixture avoids creating images or native maps.
        ctx={0:dict(plan=dict(coarse_features=1,fine_features=1),coarse=dict(width=8,height=8,min_x=1,min_y=1,max_x=1,max_y=1),fine=dict(width=8,height=8,min_x=1,min_y=1,max_x=1,max_y=1))}
        windows={0:dict(job=0,center=(64,64),base=(32,32))};order=[('coarse',0),('local',0)]
        feature=lambda kind,cells:dict(kind=kind,owner='0',feature_id='0',x='1',y='1',label='0',skipped='0',cells=str(cells),response_digits='4'*cells)
        vectors=[(('coarse',0),[feature('coarse',2756)]),(('local',0),[feature('local',256)])]
        def cells(kind,total,width):return [dict(kind=kind,owner='0',row=str(j//width),col=str(j%width),native_raw='4',native_score_bits=str(0x42c80000),computed='1',threshold_pass='1') for j in range(total)]
        cell_groups=[(('coarse',0),cells('coarse',2756,53)),(('local',0),cells('local',256,16))]
        maxima=[dict(window='0',center_x='64',center_y='64',base_x='32',base_y='32',raw='4',score_bits=str(0x42c80000),row='0',col='0',ties='256',tie_mask='1'*256)]
        co,lo,sig,counts=t.check_maps(vectors,cell_groups,maxima,ctx,windows,order)
        self.assertEqual((len(co[0]),len(lo[0]['raw']),sig,counts['digits']),(2756,256,{0:[(1,1,0)]},3012))
        for vg,cg,mx in [(vectors[:1],cell_groups,maxima),(vectors,cell_groups[:1],maxima),(list(reversed(vectors)),cell_groups,maxima),(vectors,cell_groups,[]),(vectors,cell_groups,maxima*2)]:
            with self.assertRaises(ValueError):t.check_maps(vg,cg,mx,ctx,windows,order)

    def test_fullclass_nms_assignment_records_and_blocker_mutations(self):
        post=[dict(cls='tless_object_1',template=2,x=5,y=5,bits=0x42c80000,box=(-59,-59,10,10)),dict(cls='tless_object_1',template=3,x=6,y=5,bits=0x42aa0000,box=(-58,-59,10,10))]
        truths=[dict(id=0,cls='tless_object_1',visibility=.2,box=(-59,-59,10,10))]
        rows=[dict(post_rank='0',template='2',match_x='5',match_y='5',score_bits=str(0x42c80000),selected_rank='0',blocker_post_rank='-1',blocker_iou='0',allGT_label='TP',allGT_id='0'),dict(post_rank='1',template='3',match_x='6',match_y='5',score_bits=str(0x42aa0000),selected_rank='-1',blocker_post_rank='0',blocker_iou=str(9/11),allGT_label='SUPPRESSED',allGT_id='-1')]
        saved=[dict(record=post[0],allGT_label='TP',allGT_id=0,eligible_label='IGNORE',eligible_id=0)]
        self.assertEqual(t.check_nms_frame(rows,post,truths,saved),([0],[-1,0]))
        for field,value in [('blocker_post_rank','-1'),('blocker_iou','0'),('allGT_label','FP'),('selected_rank','0')]:
            bad=copy.deepcopy(rows);bad[1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):t.check_nms_frame(bad,post,truths,saved)
        bad=copy.deepcopy(saved);bad[0]['eligible_label']='FP'
        with self.assertRaises(ValueError):t.check_nms_frame(rows,post,truths,bad)
        with self.assertRaises(ValueError):t.check_nms_frame(rows[:1],post,truths,saved)

    def test_occurrence_metadata_boxes_minimum_representative_and_multiplicity(self):
        contexts,_,_=context();ctx=contexts[0];ctx['id']=0
        key=(5,5,0x42c80000);predicted={key:2};pre={key:3}
        post=[dict(cls='tless_object_1',template=1,x=5,y=5,bits=0x42c80000,box=(-58,-59,10,10))]
        row=dict(job='0',gt_id='0',match_x='5',match_y='5',score_bits=str(0x42c80000),traced_parents='2',full_pre_multiplicity='3',post_representative_template='1',post_rank='0',nms_selected_rank='0',nms_blocker='-1',pre_box_x='-59',pre_box_y='-59',pre_box_w='10',pre_box_h='10',rep_box_x='-58',rep_box_y='-59',rep_box_w='10',rep_box_h='10',pre_iou_gt='1',rep_iou_gt=str(9/11))
        self.assertEqual(t.check_occurrences([row],ctx,predicted,pre,{key:1},post,[0],[-1]),1)
        for field,value in [('traced_parents','4'),('full_pre_multiplicity','2'),('post_representative_template','2'),('rep_box_x','-59'),('rep_iou_gt','1'),('nms_selected_rank','-1')]:
            bad=dict(row);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):t.check_occurrences([bad],ctx,predicted,pre,{key:1},post,[0],[-1])
        with self.assertRaises(ValueError):t.check_occurrences([],ctx,predicted,pre,{key:1},post,[0],[-1])
        with self.assertRaises(ValueError):t.check_occurrences([row],ctx,predicted,pre,{key:0},post,[0],[-1])


if __name__=='__main__':unittest.main()
