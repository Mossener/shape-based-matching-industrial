"""Independent geometry numeric literals; all bank bytes are synthetic memory."""
import ast
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import independent_geometry_audit as independent
import run_independent_geometry_audit as guarded


def encoded(value):
    return (json.dumps(value,separators=(',',':'),sort_keys=True)+'\n').encode()


def fixture(root):
    root=Path(root).resolve(); store={};opened=[]
    def add(path,data):
        path=str(Path(path).resolve());store[path]=data
        return dict(path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    def read(path):
        path=str(path);opened.append(path)
        if path not in store:raise AssertionError('Unexpected numeric source read: '+path)
        return store[path]
    objects=(1,2,5,8,12,17); arms=(('C0','control','rgb_control'),('P','pooled','rgb_pooled_features'),('B','stratified','rgb_stratified_features'))
    files=[];rows=[];originals=[];outputs={};inputpins={};bank_reports=[];layers=[];flatpins=[]
    for obj in objects:
        cls='tless_object_'+str(obj);row={'object_id':obj}
        original=add(root/('obj'+str(obj)+'_attempts.csv'),
            ('class_id,training_image,angle,scale,success,template_id,canvas\n'+cls+',7,30,1,1,0,1024\n').encode())
        originals.append(dict(object_id=obj,file=original));inputpins[original['path']]={k:original[k] for k in ('bytes','sha256')}
        for arm,prefix,native in arms:
            directory=root/('c0_obj'+str(obj)) if arm=='C0' else root/'training'/native/('obj'+str(obj))
            row[prefix+'_training']=str(directory);row[prefix+'_template_count']=1
            text=['%YAML:1.0','---','class_id: '+cls,'pyramid_levels: 2','template_pyramids:','   -','      template_id: 0','      templates:']
            for level,origin in ((0,900),(1,450)):
                text+=['         -','            width: 16','            height: 16','            tl_x: '+str(origin),'            tl_y: 0','            pyramid_level: '+str(level),'            features:','               - [ 2, 3, 0 ]','               - [ 8, 9, 1 ]']
            raw=('\n'.join(text)+'\n').encode();bank=add(directory/('templates_'+cls+'.yml.gz'),gzip.compress(raw,mtime=0))
            meta=add(directory/'template_metadata.json',encoded({'templates':[dict(class_id=cls,template_id=0,training_image_id=7,angle=30,scale=1,tl_x=900,tl_y=0,warped_mask_bbox=[1,2,3,4])]}))
            files.append(dict(arm=arm,object_id=obj,bank=bank,metadata=meta))
            if arm!='C0':
                for pin in (bank,meta):outputs[Path(pin['path']).relative_to(root/'training').as_posix()]={k:pin[k] for k in ('bytes','sha256')}
            bank_reports.append(dict(arm=arm,object_id=obj,class_id=cls,templates=1,layers=2,bank=bank,metadata=meta,logical_bank_bytes=len(raw)))
            for level,origin,side,need,project in ((0,900,1024,80,80),(1,450,512,16,32)):
                layers.append(dict(level=level,width=16,height=16,tl_x=origin,tl_y=0,actual_features=2,
                    min_x=2,min_y=3,max_x=8,max_y=9,min_absolute_x=origin+2,min_absolute_y=3,
                    max_absolute_x=origin+8,max_absolute_y=9,canvas_width=side,canvas_height=side,
                    arm=arm,object_id=obj,class_id=cls,template_id=0,needed_width=need,needed_height=need,
                    projected_width=project,projected_height=project))
        rows.append(row)
    order={(arm,obj):(ai,oi) for ai,(arm,_,_) in enumerate(arms) for oi,obj in enumerate(objects)}
    bank_reports.sort(key=lambda r:order[(r['arm'],r['object_id'])]);layers.sort(key=lambda r:(*order[(r['arm'],r['object_id'])],r['level']))
    for row in bank_reports:flatpins.extend((row['bank'],row['metadata']))
    audit=dict(schema='independent_stratified_training_audit_v1',numeric_training_audit_passed=True,public_numeric_training_complete=True,literal_only=False,comparison_feasible=True,
        counts=dict(shared_poses=20736,shared_pools=41472,arm_attempts=41472,layer_status_rows=82944),successful_templates={'P':[1]*6,'B':[1]*6},input_pins=inputpins,output_pins_before=outputs,output_pins_after=outputs)
    ap=add(root/'numeric_audit.json',encoded(audit))
    inputs=dict(schema='rgb_stratified_geometry_inputs_v1',production_promotion=False,training_run=str(root/'training'),source_numeric_audit=ap,banks=rows,bank_files=files,original_attempts=originals)
    ip=add(root/'GEOMETRY_INPUT_FREEZE.json',encoded(inputs))
    plan=dict(source_size=[720,540],width=848,height=832,alignment=16,padding_ltrb=[64,64,64,228],pixels=705536,estimated_dynamic_bytes=361234432,banks=18,loaded_layers=36,geometry_feasible=1,development_images_decoded=0,matcher_calls=0)
    report=dict(schema='rgb_stratified_bank_geometry_report_v1',plan=plan,banks=bank_reports,scanned_banks=18,loaded_layers=36,actual_features_scanned=72,layer_geometry=layers,
        all_features_scanned=True,feature_filtering=False,pose_filtering=False,input_bank_files=flatpins,original_attempts=[r['file'] for r in originals],source_numeric_audit=ap,image_reads=0,image_decodes=0,native_executions=0,matcher_calls=0,production_promotion=False)
    rp=add(root/'scanner/bank_geometry_report.json',encoded(report));pp=add(root/'scanner/common_padding_plan.json',encoded(plan));reservation=add(root/'scanner_reservation.json',encoded({'reserved':True}))
    sources=[add(root/'scanner_sources'/name,('synthetic source '+name).encode()) for name in ('run_geometry.py','planner.py','strict_bank_reader.py','PROTOCOL.json')]
    freeze=dict(schema='rgb_stratified_common_geometry_freeze_v1',plan=plan,training_freeze=ip,source_numeric_audit=ap,geometry_report=rp,common_padding_plan=pp,reservation=reservation,source_pins=sources,
        exact_geometry_computed=True,independent_geometry_audit_required=True,numeric_audit_passed=False,production_promotion=False,image_reads=0,image_decodes=0,native_executions=0,matcher_calls=0)
    fp=add(root/'scanner/GEOMETRY_FREEZE.json',encoded(freeze))
    return dict(root=root,store=store,opened=opened,add=add,read=read,inputs=inputs,input_pin=ip,audit=audit,report=report,freeze=freeze,scanner_pin=fp)


class IndependentGeometryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.f=fixture(self.temp.name)

    def audit(self):
        return independent.audit_geometry(self.f['input_pin'],self.f['scanner_pin'],read_bytes=self.f['read'])

    def repin(self,name,value):
        key={'report':'geometry_report','plan':'common_padding_plan'}[name]
        pin=self.f['add'](self.f['freeze'][key]['path'],encoded(value));self.f['freeze'][key]=pin
        self.f['scanner_pin']=self.f['add'](self.f['scanner_pin']['path'],encoded(self.f['freeze']))

    def test_literal_complete_union_matches_every_field(self):
        r=self.audit();self.assertTrue(r['numeric_audit_passed']);self.assertEqual(r['scope'],'exact_geometry_only')
        self.assertTrue(r['passed'])
        for pin in (self.f['input_pin'],self.f['scanner_pin'],self.f['inputs']['source_numeric_audit']):
            self.assertEqual(r['input_pins'][pin['path']],{k:pin[k] for k in ('bytes','sha256')})
        self.assertEqual((r['scanned_banks'],r['loaded_layers'],r['actual_features_scanned']),(18,36,72))
        self.assertEqual(r['computed_plan'],self.f['report']['plan']);self.assertFalse(r['production_promotion'])

    def test_altered_last_layer_absolute_max_is_rejected(self):
        self.f['report']['layer_geometry'][-1]['max_absolute_x']+=1;self.repin('report',self.f['report'])
        with self.assertRaisesRegex(ValueError,'max_absolute_x'):self.audit()

    def test_missing_layer_and_changed_order_are_rejected(self):
        self.f['report']['layer_geometry'].pop();self.repin('report',self.f['report'])
        with self.assertRaises(ValueError):self.audit()

    def test_valid_but_unnecessary_enlargement_is_not_exact_geometry(self):
        bad=copy.deepcopy(self.f['report']['plan']);bad.update(width=864,padding_ltrb=[64,64,80,228],pixels=718848,estimated_dynamic_bytes=368050176)
        self.f['freeze']['plan']=bad;self.f['report']['plan']=bad;self.repin('report',self.f['report']);self.repin('plan',bad)
        with self.assertRaisesRegex(ValueError,'plan'):self.audit()

    def test_own_training_canvas_is_rebuilt_from_csv(self):
        # Fixture tl_x900 is outside the query width720 but inside training1024.
        r=self.audit();self.assertEqual(r['computed_plan']['width'],848)
        original=self.f['inputs']['original_attempts'][0]['file'];self.f['store'][original['path']]=self.f['store'][original['path']].replace(b'1024',b'256')
        with self.assertRaisesRegex(ValueError,'pin'):self.audit()

    def test_all_feature_coordinates_are_checked_not_report_bounds(self):
        record=self.f['inputs']['bank_files'][-1];path=record['bank']['path']
        raw=gzip.decompress(self.f['store'][path]).replace(b'[ 8, 9, 1 ]',b'[ 9999, 9, 1 ]')
        pin=self.f['add'](path,gzip.compress(raw,mtime=0));record['bank']=pin
        relative=Path(path).relative_to(self.f['root']/'training').as_posix()
        for key in ('output_pins_before','output_pins_after'):
            self.f['audit'][key]=dict(self.f['audit'][key]);self.f['audit'][key][relative]={k:pin[k] for k in ('bytes','sha256')}
        ap=self.f['add'](self.f['inputs']['source_numeric_audit']['path'],encoded(self.f['audit']));self.f['inputs']['source_numeric_audit']=ap
        self.f['input_pin']=self.f['add'](self.f['input_pin']['path'],encoded(self.f['inputs']));self.f['freeze']['training_freeze']=self.f['input_pin'];self.f['freeze']['source_numeric_audit']=ap
        self.f['scanner_pin']=self.f['add'](self.f['scanner_pin']['path'],encoded(self.f['freeze']))
        with self.assertRaisesRegex(ValueError,'feature'):self.audit()

    def test_wrong_source_audit_and_counts_rejected_before_bank_reads(self):
        self.f['audit']['counts']['shared_pools']=1
        self.f['store'][self.f['inputs']['source_numeric_audit']['path']]=encoded(self.f['audit'])
        with self.assertRaises(ValueError):self.audit()
        self.assertFalse(any('.yml.gz' in p for p in self.f['opened']))

    def test_unknown_report_field_is_rejected(self):
        self.f['report']['unverified_extra']=True;self.repin('report',self.f['report'])
        with self.assertRaisesRegex(ValueError,'fields'):self.audit()

    def test_numeric_type_change_is_not_silently_equal(self):
        self.f['report']['layer_geometry'][0]['width']=16.0;self.repin('report',self.f['report'])
        with self.assertRaisesRegex(ValueError,'type'):self.audit()

    def test_source_uses_no_scanner_or_planner_calculation_import(self):
        tree=ast.parse(Path(independent.__file__).read_text())
        names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names += [x.name for x in node.names]
            if isinstance(node,ast.ImportFrom):names.append(node.module or '')
        self.assertFalse(any(n in ('planner','run_geometry') for n in names))
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='geometry' for n in ast.walk(tree)))

    def test_checked_uint64_and_resource_boundaries(self):
        with self.assertRaises(OverflowError):independent.checked_u64(1<<64)
        self.assertEqual(independent.checked_u64((1<<64)-1),(1<<64)-1)
        with self.assertRaises(ValueError):independent.common_plan(2049,832,36)
        with self.assertRaises(ValueError):independent.common_plan(1536,1536,36)

    def test_last_bank_union_and_last_layer_equal_extent_use_literal_formula(self):
        record=self.f['inputs']['bank_files'][-1];path=record['bank']['path']
        raw=gzip.decompress(self.f['store'][path]).replace(b'width: 16',b'width: 1000',1)
        head,tail=raw.rsplit(b'[ 8, 9, 1 ]',1);raw=head+b'[ 16, 16, 1 ]'+tail
        pin=self.f['add'](path,gzip.compress(raw,mtime=0));record['bank']=pin
        relative=Path(path).relative_to(self.f['root']/'training').as_posix()
        for name in ('output_pins_before','output_pins_after'):
            self.f['audit'][name]=dict(self.f['audit'][name]);self.f['audit'][name][relative]={k:pin[k] for k in ('bytes','sha256')}
        report=independent.recompute(self.f['inputs'],self.f['audit'],
            lambda pin,maximum:independent.read_pin(pin,maximum,read_bytes=self.f['read']))
        expected=copy.deepcopy(self.f['report']['plan'])
        expected.update(width=1072,padding_ltrb=[64,64,288,228],pixels=891904,estimated_dynamic_bytes=456654848)
        self.assertEqual(report['plan'],expected)
        self.assertEqual(report['layer_geometry'][-2]['needed_width'],1064)
        last=report['layer_geometry'][-1]
        self.assertEqual((last['max_x'],last['max_y'],last['needed_width'],last['needed_height'],
                          last['projected_width'],last['projected_height']),(16,16,17,17,34,34))

    def test_reserve_is_single_use_and_opens_no_bank_payload(self):
        reservation=self.f['root']/'audit_reservation.json';evidence=self.f['root']/'audit_evidence';execution=self.f['root']/'audit_execution'
        r=guarded.reserve(self.f['input_pin'],self.f['scanner_pin'],reservation,evidence,execution,read_bytes=self.f['read'])
        self.assertTrue(r['reserved']);self.assertFalse(any('.yml.gz' in p for p in self.f['opened']))
        with self.assertRaises(ValueError):guarded.reserve(self.f['input_pin'],self.f['scanner_pin'],reservation,evidence,execution,read_bytes=self.f['read'])

    def test_guard_call_is_frozen_and_failure_consumes_reservation(self):
        reservation=self.f['root']/'audit_reservation.json';evidence=self.f['root']/'audit_evidence';execution=self.f['root']/'audit_execution'
        guarded.reserve(self.f['input_pin'],self.f['scanner_pin'],reservation,evidence,execution,read_bytes=self.f['read'])
        calls=[]
        def fake_guard(command,env,cwd,native_output,execution,**limits):
            calls.append((command,limits));return {'passed':False,'exit_code':2,'reason':'synthetic_guard_failure'}
        r=guarded.execute(reservation,read_bytes=self.f['read'],guard=fake_guard)
        self.assertFalse(r['passed']);self.assertEqual(len(calls),1);self.assertEqual(calls[0][1],guarded.GUARD_LIMITS)
        self.assertIn('--scanner-freeze',calls[0][0]);self.assertTrue((evidence/'RUNNER_RECEIPT.json').exists())
        with self.assertRaises(ValueError):guarded.execute(reservation,read_bytes=self.f['read'],guard=fake_guard)

    def test_guard_success_requires_complete_independently_recomputed_receipt(self):
        reservation=self.f['root']/'success_reservation.json';evidence=self.f['root']/'success_evidence';execution=self.f['root']/'success_execution'
        guarded.reserve(self.f['input_pin'],self.f['scanner_pin'],reservation,evidence,execution,read_bytes=self.f['read'])
        def fake_guard(command,env,cwd,native_output,execution,**limits):
            native_output.mkdir();execution.mkdir()
            independent.write_fresh_json(native_output/'INDEPENDENT_GEOMETRY_AUDIT.json',self.audit())
            return {'passed':True,'exit_code':0}
        r=guarded.execute(reservation,read_bytes=self.f['read'],guard=fake_guard)
        self.assertTrue(r['passed'],r);self.assertEqual(r['actual_launches'],1)

    def test_stale_direct_source_consumes_reservation_without_launch(self):
        reservation=self.f['root']/'stale_reservation.json';evidence=self.f['root']/'stale_evidence';execution=self.f['root']/'stale_execution'
        guarded.reserve(self.f['input_pin'],self.f['scanner_pin'],reservation,evidence,execution,read_bytes=self.f['read'])
        value=json.loads(reservation.read_text());value['execution_source_pins'][0]['sha256']='0'*64
        reservation.write_text(json.dumps(value))
        def forbidden(*args,**kwargs):raise AssertionError('Stale source must not launch')
        r=guarded.execute(reservation,read_bytes=self.f['read'],guard=forbidden)
        self.assertFalse(r['passed']);self.assertEqual(r['actual_launches'],0)
        self.assertTrue(Path(str(reservation)+'.consumed.json').exists())

    def test_every_report_layer_field_is_compared(self):
        original=copy.deepcopy(self.f['report'])
        for key,value in original['layer_geometry'][-1].items():
            with self.subTest(field=key):
                self.f['report']=copy.deepcopy(original)
                self.f['report']['layer_geometry'][-1][key]=(value+1 if type(value) is int else value+'_bad')
                self.repin('report',self.f['report'])
                with self.assertRaisesRegex(ValueError,key):self.audit()


if __name__=='__main__':unittest.main()
