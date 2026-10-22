"""Synthetic numeric regression tests. No native or real-data reads."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import quality_audit as a
from evidence import Reader,loads,integer,number
from numeric import float_bits,nms,evaluate,overlap
from contract import (ARMS,OBJECTS,BANK_KEYS,quality_gate,padding,schedule,validate_bank_bindings,
                      validate_accepted_report,receipt_bindings,reference_bindings,stage_gate,parent_stage)


def pin(path):
    b=path.read_bytes(); return dict(path=str(path.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())


def candidate(template=0,pose=7,box=(22.,118.,23.,29.)):
    return ('tless_object_1',template,100,200,float_bits(90),box,(pose,float_bits(30),float_bits(1.5)))


def selected(arm=ARMS[1]):
    return dict(object_id='1',scene='4',image='9',arm=arm,rank='0',class_id='tless_object_1',score='90',
                score_bits=str(float_bits(90)),template_id='0',training_image='7',angle='30',scale='1.5',
                match_x='100',match_y='200',bbox_x='22',bbox_y='118',bbox_w='23',bbox_h='29',
                allGT_label='TP',allGT_id='12',eligible_label='TP',eligible_id='12')


class NumericTests(unittest.TestCase):
    def test_raw_order_and_each_selected_field(self):
        d=candidate(); a.check_path_equality([d],[d])
        for mutant in ('bits','order','extra'):
            x=list(d); x[4]+=1; x=tuple(x)
            wrong=[x] if mutant=='bits' else [x,d] if mutant=='order' else [d,d]
            with self.subTest(mutant=mutant),self.assertRaises(ValueError): a.check_path_equality([d],wrong)
        row=selected(); key=(1,4,9,ARMS[1]); a.check_selected([row],[d],key,[('TP',12)],[('TP',12)])
        changes=dict(object_id='2',scene='5',image='10',arm=ARMS[2],rank='1',class_id='wrong',score='91',
                     score_bits=str(float_bits(91)),template_id='1',training_image='8',angle='60',scale='2',
                     match_x='101',match_y='201',bbox_x='21',bbox_y='117',bbox_w='22',bbox_h='28',
                     allGT_label='FP',allGT_id='11',eligible_label='IGNORE',eligible_id='11')
        self.assertEqual(set(changes),set(row))
        for field,value in changes.items():
            with self.subTest(field=field),self.assertRaises(ValueError):
                a.check_selected([dict(row,**{field:value})],[d],key,[('TP',12)],[('TP',12)])

    def test_metadata_box_uses_each_arms_own_origin(self):
        row=selected(); meta={0:dict(training_image_id=7,angle=30,scale=1.5,tl_x=31,tl_y=37,
                                  warped_mask_bbox=[17,19,23,29])}
        try: observed=a.parse_candidate(row,1,meta)
        except ValueError as error: self.fail('correct own-origin literal rejected: '+str(error))
        self.assertEqual(observed,candidate())
        for field,value in [('tl_x',32),('tl_y',38),('warped_mask_bbox',[18,19,23,29]),('training_image_id',8)]:
            wrong=copy.deepcopy(meta); wrong[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): a.parse_candidate(row,1,wrong)

    def test_three_arm_coverage_keeps_empty_and_negative_frames(self):
        keys={(1,4,i,arm) for i in (9,10) for arm in ARMS}
        per={k:{} for k in keys}; equality=dict(per); chosen={(1,4,9,ARMS[1]):[selected()]}
        a.check_coverage(per,chosen,equality,keys)
        self.assertEqual(chosen[(1,4,10,ARMS[2])],[])
        for field in ('per','equality','selected'):
            p,s,e=copy.deepcopy((per,chosen,equality))
            if field=='per': del p[(1,4,10,ARMS[2])]
            if field=='equality': del e[(1,4,10,ARMS[2])]
            if field=='selected': s[(1,4,11,ARMS[2])]=[]
            with self.subTest(field=field),self.assertRaises(ValueError): a.check_coverage(p,s,e,keys)
        negative=a.frame_result([candidate()],[])
        self.assertEqual((negative['negative_frames'],negative['negative_fp'],negative['allGT']['fp']),(1,1,1))

    def test_nms_gt_ignore_and_threshold_boundaries(self):
        self.assertEqual(overlap((0,0,13,1),(7,0,13,1)),.3)
        x=list(candidate()); x[5]=(0,0,13,1); x=tuple(x)
        y=list(x); y[2]+=7; y[5]=(7,0,13,1); y=tuple(y)
        self.assertEqual(nms([y,x]),[x,y])
        truth=[dict(gt_id=3,bbox_obj=x[5],visib_fract=.2)]
        self.assertEqual(evaluate([x,x],truth,True)[1],[('IGNORE',3),('FP',-1)])
        self.assertEqual(evaluate([x],truth,False)[1],[('TP',3)])

    def retention_fixture(self):
        truth=[dict(gt_id=12,bbox_obj=candidate()[5],visib_fract=.9)]
        results={ARMS[0]:a.frame_result([candidate()],truth),ARMS[1]:a.frame_result([],truth),
                 ARMS[2]:a.frame_result([candidate(pose=8)],truth)}
        expected=a.retention_for_frame(1,(4,9),truth,results)
        rows=[]
        for k,v in expected.items():
            obj,scene,image,metric,gid,arm=k; c0,b,same,status=v
            rows.append(dict(object_id=str(obj),scene=str(scene),image=str(image),metric=metric,gt_id=str(gid),
                             comparison_arm=arm,rgb_control_detected=str(c0),comparison_detected=str(b),
                             same_pose_if_both=str(same),identity_change=status))
        return expected,rows

    def test_retention_P_and_B_separate_with_pose_identity(self):
        expected,rows=self.retention_fixture(); groups=a.check_retention(rows,expected)
        self.assertEqual(expected[(1,4,9,'allGT',12,ARMS[1])],(1,0,-1,'lost'))
        self.assertEqual(expected[(1,4,9,'allGT',12,ARMS[2])],(1,1,0,'retained'))
        self.assertEqual(len(groups),16)
        for mutant in ('omit','duplicate','swap','pose','status'):
            wrong=copy.deepcopy(rows)
            if mutant=='omit': wrong.pop()
            if mutant=='duplicate': wrong.append(wrong[0])
            if mutant=='swap': wrong[0]['comparison_arm']=ARMS[2]
            if mutant=='pose': wrong[-1]['same_pose_if_both']='1'
            if mutant=='status': wrong[0]['identity_change']='gained'
            with self.subTest(mutant=mutant),self.assertRaises(ValueError): a.check_retention(wrong,expected)

    def test_quality_gate_uses_B_and_keeps_P_diagnostic(self):
        pooled={ARMS[0]:{'allGT':dict(tp=215,fp=42112)},ARMS[1]:{'allGT':dict(tp=999,fp=0)},
                ARMS[2]:{'allGT':dict(tp=214,fp=0)}}
        self.assertFalse(quality_gate(pooled)['passed'])
        pooled[ARMS[2]]['allGT']['tp']=215; self.assertTrue(quality_gate(pooled)['passed'])
        pooled[ARMS[2]]['allGT']['fp']=42112; self.assertFalse(quality_gate(pooled)['passed'])
        pooled[ARMS[0]]['allGT']['tp']=216
        with self.assertRaises(ValueError): quality_gate(pooled)

    def test_accepted_report_cannot_be_failed_or_literal_only(self):
        valid=dict(schema='independent_stratified_training_audit_v1',numeric_training_audit_passed=True,
                   public_numeric_training_complete=True,comparison_feasible=True,literal_only=False)
        with self.assertRaises(ValueError): validate_accepted_report(valid)
        with self.assertRaises(ValueError): validate_accepted_report(dict(valid,passed=True))
        validate_accepted_report(dict(schema='root_join',passed=True))
        for field,value in [('numeric_training_audit_passed',False),('public_numeric_training_complete',False),
                            ('comparison_feasible',False),('literal_only',True)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_accepted_report(dict(valid,**{field:value}))
        with self.assertRaises(ValueError): validate_accepted_report(dict(passed=False))

    def test_accepted_receipt_binds_both_original_freezes(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t); path=folder/'freeze.json'; path.write_bytes(b'{}')
            p=pin(path); acceptance=dict(training_freeze=p,geometry_freeze=dict(p,path=str(folder/'geometry.json')))
            receipt=dict(input_pins=[p,acceptance['geometry_freeze']])
            receipt_bindings(receipt,acceptance)
            receipt_bindings(dict(input_pins={p['path']:p,acceptance['geometry_freeze']['path']:acceptance['geometry_freeze']}),acceptance)
            for mutant in ('missing','changed','duplicate','unbound'):
                wrong=copy.deepcopy(receipt)
                if mutant=='missing': wrong['input_pins'].pop()
                if mutant=='changed': wrong['input_pins'][1]['sha256']='0'*64
                if mutant=='duplicate': wrong['input_pins'].append(dict(p))
                if mutant=='unbound': wrong['input_pins'][1]['path']=str(folder/'unrelated.json')
                with self.subTest(mutant=mutant),self.assertRaises(ValueError): receipt_bindings(wrong,acceptance)

    def test_stage_complete_inventory_physical_summary_and_parent_bindings(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); run=root/'run'; native=run/'native'; native.mkdir(parents=True)
            summary=dict(passed=1,stage='pilot',objects=OBJECTS,unique_frames=8,object_frame_combinations=48,
                         matcher_calls=288.,additional_observation=3)
            (native/'stage_summary.json').write_text(json.dumps(summary))
            (run/'provenance.json').write_bytes(b'{}')
            stage=dict(stage='pilot',completed=True,native_exit_code=0,actual_matcher_calls=288.,maximum_matcher_calls=288,
                       post_verification_passed=True,missing_frames_are_not_negatives=True,heldout_images_allowed=False,
                       files=[pin(native/'stage_summary.json')],execution_files=[pin(run/'provenance.json')],summary=summary,
                       quality_inputs={'id':'input'},build_manifest={'id':'build'},selftest={'id':'selftest'})
            freeze=run/'QUALITY_STAGE_FREEZE.json'
            def check(value):
                freeze.write_text(json.dumps(value)); return stage_gate(Reader(root),pin(freeze),'pilot')
            self.assertEqual(check(stage)[1],native)
            for mutant in ('incomplete','calls','boolean','duplicate','embedded','missing'):
                wrong=copy.deepcopy(stage)
                if mutant=='incomplete': wrong['completed']=False
                if mutant=='calls': wrong['actual_matcher_calls']=287
                if mutant=='boolean': wrong['native_exit_code']=False
                if mutant=='duplicate': wrong['files'].append(wrong['files'][0])
                if mutant=='embedded': wrong['summary']['additional_observation']=4
                if mutant=='missing': wrong['files']=[]
                with self.subTest(mutant=mutant),self.assertRaises(ValueError): check(wrong)
            check(stage); child=dict(stage,previous_stage=pin(freeze)); parent_stage(Reader(root),child,'pilot')
            for field in ('quality_inputs','build_manifest','selftest'):
                with self.subTest(parent=field),self.assertRaises(ValueError):
                    parent_stage(Reader(root),dict(child,**{field:{'wrong':True}}),'pilot')
            (native/'extra.csv').write_bytes(b'unexpected')
            with self.assertRaises(ValueError): check(stage)

    def test_inherited_C0_bank_common_and_original_raw_source_closures(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); old_root=root/'old'; common=root/'common'; private={}; common_files=[]
            inputs=dict(development=[],banks=[],bank_input_files=[],raw_reference_files=[],
                        inherited_c0_development_stage=dict(path=str(common/'QUALITY_STAGE_FREEZE.json')))
            inherited=dict(rgb_banks=[])
            def fake(path): return dict(path=str(path.resolve()),bytes=0,sha256=hashlib.sha256(b'').hexdigest())
            for obj in OBJECTS:
                control=old_root/'frozen_inputs'/f'obj{obj}'/'rgb_training'
                original=old_root/'frozen_inputs'/f'obj{obj}'/'original_pilot_raw'
                own=common/'native'/f'obj{obj}'/ARMS[0]
                row=dict(object_id=obj,class_id=f'tless_object_{obj}',control_training=str(control),
                         control_template_count=4,original_pilot_raw=str(original),c0_common_raw=str(own))
                inputs['banks'].append(row)
                inherited['rgb_banks'].append(dict(object_id=obj,rgb_training=str(control),rgb_template_count=4,
                                                  original_pilot_raw=str(original)))
                for name in ('template_metadata.json',f'templates_tless_object_{obj}.yml.gz'):
                    p=fake(control/name); inputs['bank_input_files'].append(p)
                    private[(control/name).relative_to(old_root).as_posix()]={k:p[k] for k in ('bytes','sha256')}
                for path in ('fallback','fused'):
                    for suffix in ('.csv.gz','_manifest.json'):
                        name=f's1_i2_{path}_raw'+suffix
                        p=fake(own/name); common_files.append(p); inputs['raw_reference_files'].append(p)
                        p=fake(original/name); inputs['raw_reference_files'].append(p)
                        private[(original/name).relative_to(old_root).as_posix()]={k:p[k] for k in ('bytes','sha256')}
            closure=dict(inherited_frozen_root=str(old_root),private_files=private)
            common_stage=dict(completed=True,native_exit_code=0,stage='development',files=common_files)
            with mock.patch('contract.schedule',return_value=[(1,2)]):
                reference_bindings(inputs,inherited,closure,common_stage)
                for mutant in ('common_missing','original_missing','bank_sha','common_dir','original_dir','raw_sha','extra'):
                    i,c=copy.deepcopy(inputs),copy.deepcopy(common_stage)
                    if mutant=='common_missing': c['files'].pop()
                    if mutant=='original_missing': i['raw_reference_files'].pop()
                    if mutant=='bank_sha': i['bank_input_files'][0]['sha256']='0'*64
                    if mutant=='common_dir': i['banks'][0]['c0_common_raw']=str(common/'wrong')
                    if mutant=='original_dir': i['banks'][0]['original_pilot_raw']=str(old_root/'wrong')
                    if mutant=='raw_sha': i['raw_reference_files'][0]['sha256']='0'*64
                    if mutant=='extra': i['raw_reference_files'].append(fake(common/'unrelated.csv'))
                    with self.subTest(mutant=mutant),self.assertRaises(ValueError):
                        reference_bindings(i,inherited,closure,c)

    def test_bank_pins_bind_all_18_own_directories_and_counts(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); banks=[]; files=[]; all_pins=[]
            for obj in OBJECTS:
                bank=dict(object_id=obj)
                for token,(_,directory,count) in zip(('C0','P','B'),BANK_KEYS):
                    folder=root/f'obj{obj}'/token; folder.mkdir(parents=True)
                    bank[directory]=str(folder); bank[count]=obj+1
                    metadata=folder/'template_metadata.json'; metadata.write_bytes(b'{}')
                    payload=folder/f'templates_tless_object_{obj}.yml.gz'; payload.write_bytes(b'bank')
                    row=dict(object_id=obj,arm=token,bank=pin(payload),metadata=pin(metadata))
                    files.append(row); all_pins.extend([row['bank'],row['metadata']])
                banks.append(bank)
            inputs=dict(banks=banks,bank_input_files=all_pins); training=dict(banks=copy.deepcopy(banks),bank_files=files)
            validate_bank_bindings(inputs,training)
            for mutant in ('swap_arm','count','directory','missing','duplicate','extra'):
                i,tr=copy.deepcopy((inputs,training))
                if mutant=='swap_arm': tr['bank_files'][1]['metadata'],tr['bank_files'][2]['metadata']=tr['bank_files'][2]['metadata'],tr['bank_files'][1]['metadata']
                if mutant=='count': i['banks'][0]['pooled_template_count']+=1
                if mutant=='directory': i['banks'][0]['pooled_training']=i['banks'][0]['stratified_training']
                if mutant=='missing': i['bank_input_files'].pop()
                if mutant=='duplicate': i['bank_input_files'].append(i['bank_input_files'][0])
                if mutant=='extra': tr['bank_files'].append(tr['bank_files'][0])
                with self.subTest(mutant=mutant),self.assertRaises(ValueError): validate_bank_bindings(i,tr)

    def test_pinned_reader_refuses_unregistered_changed_images_and_dataset(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); path=root/'value.json'; path.write_bytes(b'{}'); reader=Reader(root)
            with self.assertRaises(ValueError): reader.read(path)
            trusted=pin(path); reader.register(trusted); self.assertEqual(reader.read(path),b'{}')
            path.write_bytes(b'{"changed":1}')
            with self.assertRaises(ValueError): reader.read(path)
            image=root/'image.bmp'; image.write_bytes(b'bytes')
            with self.assertRaises(ValueError): reader.register(pin(image))
            with self.assertRaises(ValueError): reader.read(image)
            dataset=root/'datasets'/'secret.json'; dataset.parent.mkdir(); dataset.write_bytes(b'{}')
            with self.assertRaises(ValueError): reader.register(pin(dataset))
        for bad in [b'{"x":1,"x":2}',b'{"x":NaN}']:
            with self.assertRaises(ValueError): loads(bad)
        with self.assertRaises(ValueError): integer(True)
        with self.assertRaises(ValueError): number(float('inf'))

    def test_empty_raw_archive_is_present_and_pinned_not_missing(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); archive=root/'s4_i9_fallback_raw.csv.gz'; manifest=root/'s4_i9_fallback_raw_manifest.json'
            plain=(','.join(a.RAW_HEADER)+'\n').encode(); encoded=gzip.compress(plain)
            archive.write_bytes(encoded)
            manifest.write_text(json.dumps(dict(scene_id=4,image_id=9,variant='fallback',raw_candidate_count=0,
                                                compressed_bytes=float(len(encoded)),uncompressed_bytes=float(len(plain)))))
            reader=Reader(root)
            for p in (archive,manifest): reader.register(pin(p))
            self.assertEqual(a.parse_raw(reader,archive,(4,9),'fallback',1,{}),[])
            with self.assertRaises(ValueError): a.parse_raw(reader,archive,(4,10),'fallback',1,{})

    def test_full_raw_archive_manifest_order_metadata_and_score_bits(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); archive=root/'s4_i9_fallback_raw.csv.gz'; manifest=root/'s4_i9_fallback_raw_manifest.json'
            meta={i:dict(training_image_id=7,angle=30,scale=1.5,tl_x=31,tl_y=37,
                         warped_mask_bbox=[17,19,23,29]) for i in (0,1)}
            base=[]
            for template in (0,1):
                row=dict(selected(),scene='4',image='9',variant='fallback',rank=str(template),template_id=str(template))
                base.append({k:row[k] for k in a.RAW_HEADER})
            def run(rows,change=None):
                plain=(',' .join(a.RAW_HEADER)+'\n'+''.join(','.join(r[k] for k in a.RAW_HEADER)+'\n' for r in rows)).encode()
                encoded=gzip.compress(plain); archive.write_bytes(encoded)
                doc=dict(scene_id=4,image_id=9,variant='fallback',raw_candidate_count=len(rows),
                         compressed_bytes=float(len(encoded)),uncompressed_bytes=float(len(plain)))
                if change: doc.update(change)
                manifest.write_text(json.dumps(doc)); reader=Reader(root)
                for path in (archive,manifest): reader.register(pin(path))
                return a.parse_raw(reader,archive,(4,9),'fallback',1,meta)
            expected=[candidate(),candidate(template=1)]
            self.assertEqual(run(base),expected)
            for mutant in ('rank','order','nan','score_bound','bbox','pose','manifest_count','manifest_bool','decoded_fraction'):
                rows=copy.deepcopy(base); change=None
                if mutant=='rank': rows[0]['rank']='1'
                if mutant=='order': rows.reverse(); rows[0]['rank']='0'; rows[1]['rank']='1'
                if mutant=='nan': rows[0]['score']='NaN'
                if mutant=='score_bound': rows[0]['score']='101'
                if mutant=='bbox': rows[0]['bbox_x']='23'
                if mutant=='pose': rows[0]['training_image']='8'
                if mutant=='manifest_count': change={'raw_candidate_count':3}
                if mutant=='manifest_bool': change={'raw_candidate_count':True}
                if mutant=='decoded_fraction': change={'uncompressed_bytes':3.5}
                with self.subTest(mutant=mutant),self.assertRaises(ValueError): run(rows,change)
            changed=copy.deepcopy(base); changed[0]['score']='90.00000762939453125'
            observed=run(changed)
            self.assertEqual(observed[0][4],expected[0][4]+1)
            with self.assertRaises(ValueError): a.check_path_equality(observed,expected)

    def test_gzip_decoder_caps_expansion_before_materializing_payload(self):
        plain=b'a'*100000
        # A declared short archive must stop after bound+1 bytes, rather than
        # allocating the entire expanded payload and only then rejecting it.
        original_read=a.gzip.GzipFile.read; observed=[]
        def limited_read(archive,size=-1):
            self.assertGreaterEqual(size,0,'unbounded decoded read')
            self.assertLessEqual(size,65,'read exceeded declared bound+1')
            observed.append(size); return original_read(archive,size)
        with mock.patch.object(a.gzip,'decompress',side_effect=AssertionError('unbounded decode')), \
             mock.patch.object(a.gzip.GzipFile,'read',limited_read):
            with self.assertRaises(ValueError): a.bounded_gzip(gzip.compress(plain),64)
            self.assertEqual(a.bounded_gzip(gzip.compress(b'abc'),3),b'abc')
        self.assertEqual(observed,[65,4])

    def test_gt_schedule_rejects_duplicate_identity_class_and_visibility(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); directory=root/'datasets'/'tless_expanded'; directory.mkdir(parents=True)
            path=directory/'index.json'
            gt=dict(gt_id=3,class_id='tless_object_1',obj_id=1,bbox_obj=[0,0,10,10],visib_fract=.6)
            item=dict(scene_id=1,image_id=2,split='development',rgb='x.png',width=720,height=540,instances=[gt])
            inputs=dict(dataset_root=str(directory),development=[dict(scene_id=1,image_id=2,rgb='x.png')])
            def run(value):
                path.write_text(json.dumps(dict(test=[value])))
                reader=Reader(root); reader.register(pin(path)); return a.gt_schedule(reader,inputs)
            self.assertEqual(len(run(item)[(1,2)]),1)
            for mutant in ('duplicate','class','id','extent','visibility'):
                wrong=copy.deepcopy(item)
                if mutant=='duplicate': wrong['instances'].append(dict(gt))
                if mutant=='class': wrong['instances'][0]['class_id']='tless_object_2'
                if mutant=='id': wrong['instances'][0]['gt_id']=True
                if mutant=='extent': wrong['instances'][0]['bbox_obj'][2]=0
                if mutant=='visibility': wrong['instances'][0]['visib_fract']=1.01
                with self.subTest(mutant=mutant),self.assertRaises(ValueError): run(wrong)

    def test_padding_and_frozen_schedule_boundaries(self):
        p=dict(width=848,height=832,padding_ltrb=[64,64,64,228],banks=18,geometry_feasible=1)
        self.assertEqual(padding(p),p)
        with self.assertRaises(ValueError): padding(dict(p,banks=12))
        rows=[dict(scene_id=1,image_id=i,pilot=i<8,timing=i<64) for i in range(400)]
        self.assertEqual(len(schedule({'development':rows})),400)
        self.assertEqual(len(schedule({'development':rows},timing=True)),64)
        self.assertEqual(len(schedule({'development':rows},pilot=True)),8)
        rows[-1]['scene_id']=11
        with self.assertRaises(ValueError): schedule({'development':rows})


if __name__=='__main__': unittest.main(verbosity=2)
