"""Tests first for full numeric training acceptance; synthetic inputs only."""
import copy
import csv
import hashlib
import importlib.util
import gzip
import json
import io
from pathlib import Path
import struct
import tempfile
import unittest

SPEC=importlib.util.find_spec("training_audit")
if SPEC is not None:
    import training_audit as audit
    import numeric_oracle as oracle


class Availability(unittest.TestCase):
    def test_independent_training_auditor_exists(self):
        self.assertIsNotNone(SPEC,"independent training_audit is missing")


@unittest.skipIf(SPEC is None,"missing training auditor; availability is the RED")
class TrainingLiterals(unittest.TestCase):
    def selected(self, points):
        return [{"ordinal":i,"x":x,"y":y,"label":i%8,"magnitude_bits":0x3F800000,
                 "theta_bits":0x7FC00001+i,"stratum":"S"} for i,(x,y) in enumerate(points)]

    def test_cross_layer_crop_even_origin_no_plus_one_and_order(self):
        layers=[self.selected([(5,7),(12,15)]),self.selected([(1,2),(8,9)])]
        crop,bank=audit.crop_selected(layers)
        self.assertEqual(crop,[2,4,14,14])
        self.assertEqual(bank,[{"width":14,"height":14,"tl_x":2,"tl_y":4,"pyramid_level":0,
                                "features":[(3,3,0),(10,11,1)]},
                               {"width":7,"height":7,"tl_x":1,"tl_y":2,"pyramid_level":1,
                                "features":[(0,0,0),(7,7,1)]}])
        zero_crop,zero_bank=audit.crop_selected([self.selected([(4,4)]),self.selected([(2,2)])])
        self.assertEqual(zero_crop,[4,4,0,0])
        self.assertEqual([row["width"] for row in zero_bank],[0,0])
        odd_crop,odd_bank=audit.crop_selected([self.selected([(5,7),(12,15)]),self.selected([(3,4),(8,9)])])
        self.assertEqual(odd_crop,[4,6,12,12])
        self.assertEqual([(layer['tl_x'],layer['tl_y']) for layer in odd_bank],[(4,6),(2,3)])

    def test_mask_bbox_nonzero_and_layer_exact_bytes(self):
        mask=bytes([0,0,0,0,0,0,0,1,0,7,0,0,0,0,0,0,0,0,128,0,0,0,0,0,0])
        self.assertEqual(audit.mask_bbox(mask,5,5),[2,1,3,3])
        self.assertEqual(audit.mask_bbox(bytes(25),5,5),[0,0,0,0])
        lower=bytes([0,0,0,0])
        audit.verify_layer_masks(mask,5,5,lower,2,2)
        with self.assertRaises(ValueError): audit.verify_layer_masks(mask,5,5,bytes([0,0,0,1]),2,2)
        with self.assertRaises(ValueError): audit.verify_layer_masks(mask,5,5,bytes(9),3,3)

    def toy(self):
        original=[]
        for scale in [.75,1.]:
            for angle in [0,30]:
                original.append({"class_id":"tless_object_1","training_image":"7","angle":str(angle),
                                 "scale":str(scale),"source_crop_x":"3","source_crop_y":"4",
                                 "source_crop_w":"5","source_crop_h":"6","canvas":"25",
                                 "mask_x":"0","mask_y":"0","mask_w":"25","mask_h":"25"})
        freeze={"objects":[1],"training":[{"object_id":1,"image_id":7}]}
        policy={"objects":[1],"views_per_object":1,"scales":[.75,1.],"angles":[0,30],"literal_only":True}
        return freeze,{1:original},policy

    def test_schedule_independent_order_pose_ids_and_geometry(self):
        freeze,original,policy=self.toy()
        schedule=audit.build_schedule(freeze,original,policy)
        self.assertEqual([(p["pose_id"],p["scale"],p["angle_degrees"],p["pool_ids"])
                          for p in schedule],[(0,.75,0,[0,1]),(1,.75,30,[2,3]),(2,1.,0,[4,5]),(3,1.,30,[6,7])])
        self.assertEqual(schedule[0]["source_roi"],[3,4,5,6])
        for mutant in ["missing","order","duplicate","wrong_class","views"]:
            f,o,p=copy.deepcopy((freeze,original,policy))
            if mutant=="missing": o[1].pop()
            if mutant=="order": o[1][0],o[1][1]=o[1][1],o[1][0]
            if mutant=="duplicate": o[1][-1]=o[1][0]
            if mutant=="wrong_class": o[1][0]["class_id"]="tless_object_2"
            if mutant=="views": f["training"].append(f["training"][0])
            with self.subTest(mutant=mutant),self.assertRaises(ValueError): audit.build_schedule(f,o,p)
        with self.assertRaises(ValueError): audit.build_schedule(freeze,original)

    def pool(self,pose,level,failed=False):
        size=pose["canvas"] >> level
        # All-full actual mask allows independent byte relation and known bbox.
        mask=bytes([7]*(size*size))
        coordinates=[(2,2),(3,2),(4,2),(5,2),(6,2)]
        if failed: coordinates=coordinates[:4]
        candidates=[oracle.Candidate(i,x,y,i,0x41200000-i,0x7FC00001+i)
                    for i,(x,y) in enumerate(coordinates)]
        payload=oracle.encode_candidates(candidates)
        return {"header":{"pool_id":2*pose["pose_id"]+level,"obj":pose["object_id"],"image":pose["image_id"],
                          "angle":pose["angle_degrees"],"scale_bits":struct.unpack("<I",struct.pack("<f",pose["scale"]))[0],
                          "level":level,"width":size,"height":size,"K":32 if level==0 else 16,
                          "N":len(candidates),"mask_len":len(mask),"candidate_len":len(payload)},
                "mask":mask,"candidate_payload":payload,"mask_sha256":hashlib.sha256(mask).hexdigest(),
                "candidate_sha256":hashlib.sha256(payload).hexdigest()}

    def records(self):
        import pool_stream
        freeze,original,policy=self.toy()
        schedule=audit.build_schedule(freeze,original,policy)
        pools=[]; selections=[]; attempts=[]
        next_ids={"P":0,"B":0}
        for pose in schedule:
            results=[]
            for level in [0,1]:
                pool=self.pool(pose,level,failed=(pose["pose_id"]==1 and level==0))
                pools.append(pool)
                result=pool_stream.audit_pool(pool)
                results.append(result)
                for arm in ["P","B"]:
                    selections.append({"pose_id":pose["pose_id"],"pool_id":pool["header"]["pool_id"],"arm":arm,
                                       "candidate_sha256":pool["candidate_sha256"],"result":result[arm]})
            for arm in ["P","B"]:
                success=all(result[arm]["status"]=="ok" for result in results)
                crop=audit.crop_selected([result[arm]["selected"] for result in results])[0] if success else [0,0,0,0]
                attempts.append({"pose_id":pose["pose_id"],"object_id":pose["object_id"],"image_id":pose["image_id"],
                                 "angle_degrees":pose["angle_degrees"],"scale":pose["scale"],"arm":arm,
                                 "success":success,"template_id":next_ids[arm] if success else -1,
                                 "source_roi":pose["source_roi"],"canvas":pose["canvas"],
                                 "warped_mask_bbox":pose["warped_mask_bbox"],"pool_ids":pose["pool_ids"],"crop_xywh":crop})
                next_ids[arm]+=int(success)
        return schedule,pools,selections,attempts

    def test_full_stream_recomputes_claims_failures_both_layers_and_banks(self):
        schedule,pools,selections,attempts=self.records()
        report=audit.audit_training_stream(schedule,iter(pools),iter(selections),iter(attempts))
        self.assertEqual(report["counts"],{"shared_poses":4,"shared_pools":8,"arm_attempts":8,"layer_status_rows":16,
                                            "successful_arm_attempts":6,"failed_arm_attempts":2,
                                            "insufficient_layer_status_rows":2})
        self.assertEqual(report["successful_templates"],{"P":[3],"B":[3]})
        self.assertEqual(len(report["banks"]["P"][1]),3)
        self.assertEqual(report["banks"]["P"][1][0]["metadata"]["warped_mask_bbox"],[0,0,25,25])
        self.assertEqual(report["banks"]["P"][1][0]["metadata"]["template_id"],0)

    def test_training_claim_tamper_omission_order_hash_geometry_and_status(self):
        original=self.records()
        for mutant in ["omit_L1","omit_selection","omit_attempt","extra_pool","order","hash","distance",
                       "mask_byte","mask_size","pose","crop","bbox","template_id","success","summary_bool"]:
            schedule,pools,selections,attempts=copy.deepcopy(original)
            if mutant=="omit_L1": pools.pop(3)
            if mutant=="omit_selection": selections.pop()
            if mutant=="omit_attempt": attempts.pop()
            if mutant=="extra_pool": pools.append(pools[0])
            if mutant=="order": selections[0],selections[1]=selections[1],selections[0]
            if mutant=="hash": selections[0]["candidate_sha256"]="0"*64
            if mutant=="distance": selections[0]["result"]["trace"][1]["minimum_squared_distance"]+=1
            if mutant=="mask_byte":
                pools[1]["mask"]=bytes([255]*144); pools[1]["mask_sha256"]=hashlib.sha256(pools[1]["mask"]).hexdigest()
            if mutant=="mask_size": pools[1]["header"]["width"]=13
            if mutant=="pose": pools[0]["header"]["image"]=8
            if mutant=="crop": attempts[0]["crop_xywh"][2]+=1
            if mutant=="bbox": attempts[0]["warped_mask_bbox"]=[1,1,2,2]
            if mutant=="template_id": attempts[2]["template_id"]=0
            if mutant=="success": attempts[2]["success"]=True
            if mutant=="summary_bool": attempts[0]["success"]=1
            with self.subTest(mutant=mutant),self.assertRaises(ValueError):
                audit.audit_training_stream(schedule,iter(pools),iter(selections),iter(attempts))

    def test_attempt_scale_numeric_token_equivalence_keeps_bool_strict(self):
        schedule,pools,selections,attempts=self.records()
        for row in attempts:
            if row['scale']==1.0: row['scale']=1
        try:
            audit.audit_training_stream(schedule,iter(pools),iter(selections),iter(attempts))
        except ValueError as error:
            self.fail('valid integral scale token rejected: '+str(error))
        for value in [True,1.01,'1.0']:
            wrong=copy.deepcopy(attempts); wrong[-1]['scale']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                audit.audit_training_stream(schedule,iter(pools),iter(selections),iter(wrong))

    def bank_text(self,layers):
        text='%YAML:1.0\n---\nclass_id: tless_object_1\npyramid_levels: 2\ntemplate_pyramids:\n'
        for template_id,template in enumerate(layers):
            text+='   -\n      template_id: '+str(template_id)+'\n      templates:\n'
            for layer in template:
                text+='         -\n'
                for key in ['width','height','tl_x','tl_y','pyramid_level']:
                    text+='            '+key+': '+str(layer[key])+'\n'
                text+='            features:\n'
                for x,y,label in layer['features']:
                    text+='               - [ '+str(x)+', '+str(y)+', '+str(label)+' ]\n'
        return text

    def test_strict_serialized_bank_and_metadata_full_order_fields(self):
        self.assertTrue(hasattr(audit,'verify_serialized_object'),'serialized bank verifier is missing')
        _,bank=audit.crop_selected([self.selected([(5,7),(12,15)]),self.selected([(1,2),(8,9)])])
        metadata={"class_id":"tless_object_1","template_id":0,"training_image_id":7,
                  "angle":0,"scale":1.0,"tl_x":2,"tl_y":4,"warped_mask_bbox":[3,4,8,9]}
        expected=[{"sha256":audit.layer_digest(bank),"metadata":metadata,"canvas":25,"feature_counts":[2,2]}]
        text=self.bank_text([bank])
        audit.verify_serialized_object(text,[metadata],1,expected)
        native_metadata=copy.deepcopy(metadata)
        native_metadata['angle']=0.0
        native_metadata['warped_mask_bbox']=[3.0,4.0,8.0,9.0]
        try:
            audit.verify_serialized_object(text,[native_metadata],1,expected)
        except ValueError as error:
            self.fail('valid V11 float metadata representation was rejected: '+str(error))
        for old,new in [('width: 14','width: 15'),('tl_x: 2','tl_x: 3'),('[ 3, 3, 0 ]','[ 3, 3, 1 ]'),
                        ('template_id: 0','template_id: 1'),('class_id: tless_object_1','class_id: tless_object_2')]:
            with self.subTest(old=old),self.assertRaises(ValueError):
                audit.verify_serialized_object(text.replace(old,new),[metadata],1,expected)
        for field,value in [('training_image_id',8),('angle',30),('scale',.75),('tl_x',3),
                            ('warped_mask_bbox',[3,4,8,8]),('template_id',1)]:
            wrong=dict(metadata); wrong[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit.verify_serialized_object(text,[wrong],1,expected)
        with self.assertRaises(ValueError): audit.verify_serialized_object(text,[metadata,metadata],1,expected)
        audit.verify_serialized_object(None,[],1,[])
        with self.assertRaises(ValueError): audit.verify_serialized_object(text,[],1,[])

    def test_all_artifact_inventory_rejects_extra_missing_bank_and_config(self):
        self.assertTrue(hasattr(audit,'verify_bank_artifacts'),'bank directory verifier is missing')
        _,bank=audit.crop_selected([self.selected([(5,7),(12,15)]),self.selected([(1,2),(8,9)])])
        metadata={"class_id":"tless_object_1","template_id":0,"training_image_id":7,
                  "angle":0,"scale":1.0,"tl_x":2,"tl_y":4,"warped_mask_bbox":[3,4,8,9]}
        expected=[{"sha256":audit.layer_digest(bank),"metadata":metadata,"canvas":25,"feature_counts":[2,2]}]
        report={"objects":[1],"banks":{"P":{1:expected},"B":{1:expected}},"successful_templates":{"P":[1],"B":[1]}}
        configs={arm:{1:{"features":32,"pyramid_T":[4,8],"scales":[.75,1.,1.5,2.],"angle_step":30,
                          "weak_threshold":20,"strong_threshold":40,"training_border":16,
                          "target_objects":[1],"attempts":4,"template_count":1,"arm":arm}}
                 for arm in ['P','B']}
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            for arm in ['P','B']:
                target=folder/audit.ARM_NAMES[arm]/'obj1'; target.mkdir(parents=True)
                (target/'templates_tless_object_1.yml.gz').write_bytes(gzip.compress(self.bank_text([bank]).encode(),mtime=0))
                (target/'template_metadata.json').write_text(json.dumps({'templates':[metadata]}),encoding='utf-8')
                (target/'training_config.json').write_text(json.dumps(configs[arm][1]),encoding='utf-8')
            audit.verify_bank_artifacts(folder,report,configs)
            target=folder/audit.ARM_NAMES['P']/'obj1'
            config_path=target/'training_config.json'
            original=config_path.read_text()
            wrong=copy.deepcopy(configs['P'][1]); wrong['template_count']=2
            config_path.write_text(json.dumps(wrong),encoding='utf-8')
            with self.assertRaises(ValueError): audit.verify_bank_artifacts(folder,report,configs)
            config_path.write_text(original,encoding='utf-8')
            (target/'unmanifested.yml').write_text('extra',encoding='utf-8')
            with self.assertRaises(ValueError): audit.verify_bank_artifacts(folder,report,configs)
            (target/'unmanifested.yml').unlink()
            (target/'templates_tless_object_1.yml.gz').unlink()
            with self.assertRaises(ValueError): audit.verify_bank_artifacts(folder,report,configs)

    def test_numeric_input_freeze_csv_pins_and_strict_stream_jsonl(self):
        self.assertTrue(hasattr(audit,'load_frozen_schedule'),'pinned schedule loader is missing')
        self.assertTrue(hasattr(audit,'iter_jsonl_pinned'),'strict JSONL stream is missing')
        freeze,original,policy=self.toy()
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            text=io.StringIO(); writer=csv.DictWriter(text,fieldnames=list(original[1][0])); writer.writeheader(); writer.writerows(original[1])
            csv_path=directory/'template_attempts.csv'; csv_path.write_text(text.getvalue(),encoding='utf-8')
            csv_bytes=csv_path.read_bytes()
            freeze['original_attempts']=[{'object_id':1,'pin':{'path':str(csv_path),'bytes':len(csv_bytes),
                                                              'sha256':hashlib.sha256(csv_bytes).hexdigest()}}]
            freeze_path=directory/'TRAINING_INPUT_FREEZE.json'; freeze_path.write_text(json.dumps(freeze),encoding='utf-8')
            freeze_sha=hashlib.sha256(freeze_path.read_bytes()).hexdigest()
            schedule,pins=audit.load_frozen_schedule(freeze_path,freeze_sha,policy)
            self.assertEqual(len(schedule),4); self.assertEqual(len(pins),2)
            with self.assertRaises(ValueError): audit.load_frozen_schedule(freeze_path,'0'*64,policy)
            csv_path.write_bytes(csv_bytes.replace(b',3,4,5,6,',b',4,4,5,6,'))
            with self.assertRaises(ValueError): audit.load_frozen_schedule(freeze_path,freeze_sha,policy)
            jsonl=directory/'observations.jsonl'
            for payload,valid in [(b'{"x":1}\n{"x":2}\n',True),(b'{"x":1,"x":2}\n',False),
                                  (b'{"x":NaN}\n',False),(b'{"x":1}\n\n',False),(b'[]\n',False)]:
                jsonl.write_bytes(payload); pin={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
                if valid: self.assertEqual(list(audit.iter_jsonl_pinned(jsonl,pin)),[{'x':1},{'x':2}])
                else:
                    with self.assertRaises(ValueError): list(audit.iter_jsonl_pinned(jsonl,pin))

    def test_dilation_sidecar_target_raw_map_hash_and_scan_validation(self):
        self.assertTrue(hasattr(audit,'verify_pool_observation'),'pool validation sidecar verifier is missing')
        self.assertTrue(hasattr(audit,'dilated_mask_bytes'),'independent raw dilation is missing')
        mask=bytearray(121); mask[5*11+5]=7
        expected=bytes(255 if 1<=x<=9 and 1<=y<=9 else 0 for y in range(11) for x in range(11))
        self.assertEqual(audit.dilated_mask_bytes(bytes(mask),11,11),expected)
        self.assertEqual(audit.dilated_mask_bytes(bytes([1]*121),11,11),bytes([255]*121))
        self.assertEqual(audit.dilated_mask_bytes(bytes(121),11,11),bytes(121))
        pose={'pose_id':0,'canvas':25,'object_id':1,'image_id':7,'angle_degrees':0,'scale':1.0}
        pool=self.pool(pose,0)
        flags={key:True for key in ['dense_ordinals','unique_rowmajor_coords','finite_magnitudes','labels_0_to_7',
                                  'inside_scan_domain','source_order_preserved']}
        observation={'pool_id':0,'target':5,'dilated_mask_sha256':hashlib.sha256(bytes([255]*625)).hexdigest(),
                     'nms_maxima':99,'validation':flags}
        result=audit.verify_pool_observation(pool,observation)
        self.assertEqual(result['nms_maxima_native_observation'],99)
        for field,value in [('pool_id',1),('target',32),('dilated_mask_sha256','0'*64),('nms_maxima',-1)]:
            wrong=copy.deepcopy(observation); wrong[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): audit.verify_pool_observation(pool,wrong)
        wrong=copy.deepcopy(observation); wrong['validation']['source_order_preserved']=False
        with self.assertRaises(ValueError): audit.verify_pool_observation(pool,wrong)
        wrong=copy.deepcopy(observation); wrong['domain_sha256']=wrong.pop('dilated_mask_sha256')
        with self.assertRaises(ValueError): audit.verify_pool_observation(pool,wrong)

    def test_sidecar_stream_requires_all_pools_and_keeps_native_observations_limited(self):
        schedule,pools,selections,attempts=self.records()
        observations=[]
        for pool in pools:
            header=pool['header']
            observations.append({'pool_id':header['pool_id'],'target':min(header['K'],header['N']),
                'dilated_mask_sha256':hashlib.sha256(bytes([255]*header['mask_len'])).hexdigest(),'nms_maxima':99,
                'validation':{key:True for key in ['dense_ordinals','unique_rowmajor_coords','finite_magnitudes','labels_0_to_7',
                                                 'inside_scan_domain','source_order_preserved']}})
        try:
            report=audit.audit_training_stream(schedule,iter(pools),iter(selections),iter(attempts),observations=iter(observations))
        except TypeError:
            self.fail('full pool observation stream is not accepted by auditor')
        self.assertTrue(report['pool_observations_verified'])
        self.assertEqual(report['native_nms_maxima_observed_sum'],792)
        for mutant in ['omit','extra','target','order']:
            wrong=copy.deepcopy(observations)
            if mutant=='omit': wrong.pop()
            if mutant=='extra': wrong.append(wrong[0])
            if mutant=='target': wrong[0]['target']=32
            if mutant=='order': wrong[0],wrong[1]=wrong[1],wrong[0]
            with self.subTest(mutant=mutant),self.assertRaises(ValueError):
                audit.audit_training_stream(schedule,iter(pools),iter(selections),iter(attempts),observations=iter(wrong))

    def test_inherited_config_builder_and_full_observed_summary_contract(self):
        self.assertTrue(hasattr(audit,'expected_training_configs'),'independent config builder is missing')
        self.assertTrue(hasattr(audit,'verify_training_summary'),'full native summary verifier is missing')
        report={'objects':[1],'counts':{'shared_poses':1,'shared_pools':2,'arm_attempts':2,'layer_status_rows':4},
                'banks':{'P':{1:[{}]},'B':{1:[{}]}},'successful_templates':{'P':[1],'B':[1]}}
        configs=audit.expected_training_configs(report)
        config=configs['P'][1]
        self.assertEqual([config['features'],config['angle_step'],config['exact_feature_budgets'],
                          config['target_objects'],config['template_count'],config['shared_candidate_pool']],
                         [32,30,[32,16],[1],1,1])
        self.assertEqual(config['pyramid_T'],[4,8]); self.assertEqual(config['scales'],[.75,1.,1.5,2.])
        self.assertEqual(config['weak_threshold'],20); self.assertEqual(config['strong_threshold'],40)
        summary={'schema':'rgb_stratified_training_observation_v1','complete':True,'literal_only':True,
                 'shared_poses':1,'shared_pools':2,'arm_attempts':2,'arm_layer_rows':4,'gradient_pyramids':1,
                 'pyramid_downs':1,'rgb_decodes':0,'mask_decodes':0,'total_imread_calls':0,'matcher_calls':0,
                 'peak_rss_bytes':1048576,'logical_payload_bytes':1234,'physical_bytes_before_summary':800,
                 'successful_templates':{'P':[1],'B':[1]}}
        audit.verify_training_summary(summary,report,True,1234,800)
        for field,value in [('complete',False),('literal_only',False),('gradient_pyramids',2),('pyramid_downs',0),
                            ('arm_layer_rows',2),('rgb_decodes',1),('total_imread_calls',1),('matcher_calls',1),
                            ('logical_payload_bytes',1235),('physical_bytes_before_summary',801),
                            ('peak_rss_bytes',1610612737),('shared_poses',True),('unknown',0)]:
            wrong=copy.deepcopy(summary); wrong[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit.verify_training_summary(wrong,report,True,1234,800)
        wrong=copy.deepcopy(summary); wrong['successful_templates']['B']=[2]
        with self.assertRaises(ValueError): audit.verify_training_summary(wrong,report,True,1234,800)

    def native_fixture(self,directory):
        import pool_stream
        pose={'pose_id':0,'object_id':1,'image_id':0,'angle_degrees':0,'scale':1.0,'source_roi':[0,0,256,256],
              'canvas':256,'warped_mask_bbox':[16,16,224,224],'pool_ids':[0,1]}
        pools=[]; results=[]; claims=[]; observations=[]; members=[]; rows=[]
        for level in [0,1]:
            size=256>>level; start=16>>level; extent=224>>level
            mask=bytes(255 if start<=x<start+extent and start<=y<start+extent else 0
                       for y in range(size) for x in range(size))
            candidates=[oracle.Candidate(i,start+i,start,i,0x41200000-i,0x7FC00001+i) for i in range(5)]
            payload=oracle.encode_candidates(candidates)
            header={'pool_id':level,'obj':1,'image':0,'angle':0,'scale_bits':0x3F800000,'level':level,
                    'width':size,'height':size,'K':32 if level==0 else 16,'N':5,'mask_len':len(mask),'candidate_len':len(payload)}
            pool={'header':header,'mask':mask,'candidate_payload':payload,'mask_sha256':hashlib.sha256(mask).hexdigest(),
                  'candidate_sha256':hashlib.sha256(payload).hexdigest()}
            pools.append(pool); result=pool_stream.audit_pool(pool); results.append(result)
            for arm in ['P','B']:
                claims.append({'pose_id':0,'pool_id':level,'arm':arm,'candidate_sha256':pool['candidate_sha256'],'result':result[arm]})
            observations.append({'pool_id':level,'target':5,'dilated_mask_sha256':hashlib.sha256(
                audit.dilated_mask_bytes(mask,size,size)).hexdigest(),'nms_maxima':5,
                'validation':{key:True for key in ['dense_ordinals','unique_rowmajor_coords','finite_magnitudes','labels_0_to_7',
                                                 'inside_scan_domain','source_order_preserved']}})
            binary=struct.pack('<8sIIIiIIIIIIQQ',b'RGBPOOL1',*header.values())+mask+payload
            member=gzip.compress(binary,mtime=0)
            rows.append({'pool_id':level,'object_id':1,'image_id':0,'angle_degrees':0,'scale_float32_bits':0x3F800000,
                         'level':level,'width':size,'height':size,'K':header['K'],'N':5,'shard':0,
                         'offset':sum(map(len,members)),'compressed_bytes':len(member),'logical_bytes':len(binary),
                         'mask_sha256':pool['mask_sha256'],'candidate_sha256':pool['candidate_sha256'],
                         'payload_sha256':hashlib.sha256(binary).hexdigest(),'compressed_sha256':hashlib.sha256(member).hexdigest()})
            members.append(member)
        attempts=[]
        for arm in ['P','B']:
            crop,_=audit.crop_selected([result[arm]['selected'] for result in results])
            attempts.append(dict(pose,arm=arm,success=True,template_id=0,crop_xywh=crop))
        report=audit.audit_training_stream([pose],iter(pools),iter(claims),iter(attempts),observations=iter(observations))
        def jsonl(name,records):
            (directory/name).write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in records),encoding='utf-8')
        joined=b''.join(members); (directory/'pools_000000.bin.gz').write_bytes(joined)
        jsonl('pools.jsonl',rows)
        jsonl('shards.jsonl',[{'shard':0,'path':'pools_000000.bin.gz','compressed_bytes':len(joined),
                             'logical_bytes':sum(r['logical_bytes'] for r in rows),'sha256':hashlib.sha256(joined).hexdigest(),'pool_ids':[0,1]}])
        jsonl('layer_selections.jsonl',claims); jsonl('attempts.jsonl',attempts); jsonl('pool_observations.jsonl',observations)
        jsonl('progress.jsonl',[{'phase':'synthetic_only'}]); (directory/'loaded_modules.json').write_text('{}',encoding='utf-8')
        configs=audit.expected_training_configs(report)
        for arm in ['P','B']:
            target=directory/audit.ARM_NAMES[arm]/'obj1'; target.mkdir(parents=True)
            _,bank=audit.crop_selected([result[arm]['selected'] for result in results])
            (target/'templates_tless_object_1.yml.gz').write_bytes(gzip.compress(self.bank_text([bank]).encode(),mtime=0))
            (target/'template_metadata.json').write_text(json.dumps({'templates':[report['banks'][arm][1][0]['metadata']]}),encoding='utf-8')
            (target/'training_config.json').write_text(json.dumps(configs[arm][1]),encoding='utf-8')
        physical=logical=0
        for path in directory.rglob('*'):
            if path.is_file():
                data=path.read_bytes(); physical+=len(data); logical+=len(gzip.decompress(data)) if path.suffix=='.gz' else len(data)
        summary={'schema':'rgb_stratified_training_observation_v1','complete':True,'literal_only':True,
                 'shared_poses':1,'shared_pools':2,'arm_attempts':2,'arm_layer_rows':4,'gradient_pyramids':1,
                 'pyramid_downs':1,'rgb_decodes':0,'mask_decodes':0,'total_imread_calls':0,'matcher_calls':0,
                 'peak_rss_bytes':1048576,'logical_payload_bytes':logical,'physical_bytes_before_summary':physical,
                 'successful_templates':{'P':[1],'B':[1]}}
        (directory/'training_summary.json').write_text(json.dumps(summary),encoding='utf-8')
        return {path.relative_to(directory).as_posix():{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in directory.rglob('*') if path.is_file()}

    def test_full_directory_cli_boundary_pins_inventory_summary_and_literal_scope(self):
        self.assertTrue(hasattr(audit,'audit_native_directory'),'full directory auditor is missing')
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary); pins=self.native_fixture(folder)
            report=audit.audit_native_directory(folder,pins,literal_only=True)
            self.assertTrue(report['numeric_training_audit_passed'])
            self.assertFalse(report['real_training_accepted'])
            self.assertTrue(report['literal_only']); self.assertEqual(report['summary']['shared_poses'],1)
            for kind in ['pin','extra','missing','summary','scope','metadata']:
                if kind=='pin':
                    wrong=copy.deepcopy(pins); wrong['attempts.jsonl']['sha256']='0'*64
                    with self.assertRaises(ValueError): audit.audit_native_directory(folder,wrong,literal_only=True)
                elif kind=='extra':
                    path=folder/'native_failure.json'; path.write_text('{}',encoding='utf-8')
                    wrong=dict(pins); wrong['native_failure.json']={'bytes':2,'sha256':hashlib.sha256(b'{}').hexdigest()}
                    with self.assertRaises(ValueError): audit.audit_native_directory(folder,wrong,literal_only=True)
                    path.unlink()
                elif kind=='missing':
                    wrong=dict(pins); del wrong['pool_observations.jsonl']
                    with self.assertRaises(ValueError): audit.audit_native_directory(folder,wrong,literal_only=True)
                elif kind=='scope':
                    with self.assertRaises(ValueError): audit.audit_native_directory(folder,pins,literal_only=False)
                else:
                    path=folder/('training_summary.json' if kind=='summary' else 'rgb_pooled_features/obj1/template_metadata.json')
                    original=path.read_bytes(); value=json.loads(original)
                    if kind=='summary': value['logical_payload_bytes']+=1
                    else: value['templates'][0]['warped_mask_bbox'][0]+=1
                    path.write_text(json.dumps(value),encoding='utf-8')
                    wrong=copy.deepcopy(pins); wrong[path.relative_to(folder).as_posix()]={
                        'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                    with self.assertRaises(ValueError): audit.audit_native_directory(folder,wrong,literal_only=True)
                    path.write_bytes(original)


if __name__=="__main__": unittest.main(verbosity=2)
