"""Numeric literals for the one-shot geometry runner; no dataset bank reads."""
from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import run_geometry as runner


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def fixture(root):
    """All bank and numeric payloads stay in an in-memory synthetic map."""
    store, opened = {}, []
    def add(path, data):
        path = str(Path(path).resolve())
        store[path] = data
        return dict(path=path, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    def read(path):
        opened.append(str(path))
        if str(path) not in store:
            raise AssertionError('Unexpected source read: ' + str(path))
        return store[str(path)]
    rows, files, originals, outpins, inpins = [], [], [], {}, {}
    run = Path(root) / 'training'
    for obj in runner.OBJECTS:
        cls = 'tless_object_' + str(obj)
        csvfile = io.StringIO(newline='')
        fields = ['class_id','training_image','angle','scale','success','template_id','canvas']
        writer = csv.DictWriter(csvfile, fields, lineterminator='\n'); writer.writeheader()
        writer.writerow(dict(class_id=cls, training_image=7, angle=30, scale=1.0,
                             success=1, template_id=0, canvas=1024))
        op = add(Path(root)/('obj'+str(obj)+'_attempts.csv'), csvfile.getvalue().encode())
        originals.append(dict(object_id=obj, file=op)); inpins[op['path']] = {k:op[k] for k in ('bytes','sha256')}
        row = {'object_id':obj}
        for arm, prefix, native in runner.ARM_ROWS:
            directory = Path(root)/('control'+str(obj)) if arm == 'C0' else run/native/('obj'+str(obj))
            row[prefix+'_training'] = str(directory.resolve()); row[prefix+'_template_count'] = 1
            lines = ['%YAML:1.0','---','class_id: '+cls,'pyramid_levels: 2','template_pyramids:',
                     '   -','      template_id: 0','      templates:']
            for level in (0,1):
                lines.extend(['         -','            width: 16','            height: 16',
                              '            tl_x: '+str(900 >> level),'            tl_y: 0',
                              '            pyramid_level: '+str(level),'            features:',
                              '               - [ 2, 3, 0 ]','               - [ 8, 9, 1 ]'])
            bank = add(directory/('templates_'+cls+'.yml.gz'), gzip.compress(('\n'.join(lines)+'\n').encode(),mtime=0))
            meta = add(directory/'template_metadata.json', canonical({'templates':[
                dict(class_id=cls,template_id=0,training_image_id=7,angle=30,scale=1.,
                     tl_x=900,tl_y=0,warped_mask_bbox=[1.,2.,3.,4.])]}))
            files.append(dict(arm=arm,object_id=obj,bank=bank,metadata=meta))
            if arm != 'C0':
                for pin in (bank,meta):
                    outpins[Path(pin['path']).relative_to(run).as_posix()] = {k:pin[k] for k in ('bytes','sha256')}
        rows.append(row)
    audit = dict(schema='independent_stratified_training_audit_v1',numeric_training_audit_passed=True,
                 public_numeric_training_complete=True,literal_only=False,comparison_feasible=True,
                 successful_templates={'P':[1]*6,'B':[1]*6},
                 counts={'shared_poses':20736,'shared_pools':41472,'layer_status_rows':82944,
                         'arm_attempts':41472},input_pins=inpins,output_pins_before=outpins,
                 output_pins_after=outpins)
    audit_pin = add(Path(root)/'numeric_audit.json',canonical(audit))
    inputs = dict(schema='rgb_stratified_geometry_inputs_v1',banks=rows,bank_files=files,
                  original_attempts=originals,training_run=str(run.resolve()),source_numeric_audit=audit_pin,
                  production_promotion=False)
    return inputs,audit,store,opened,read,add


class GeometryRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.inputs,self.audit,self.store,self.opened,self.read,self.add = fixture(self.temp.name)

    def scan(self):
        return runner.build_geometry(self.inputs,self.audit,read_bytes=self.read)

    def test_complete_union_full_feature_scan_and_correct_pose_canvas(self):
        result = self.scan()
        self.assertEqual(result['plan']['banks'],18)
        self.assertEqual((result['plan']['width'],result['plan']['height']),(848,832))
        self.assertEqual(result['scanned_banks'],18)
        self.assertEqual(result['loaded_layers'],36)
        self.assertEqual(result['actual_features_scanned'],72)
        self.assertEqual(len(result['layer_geometry']),36)
        self.assertEqual(result['layer_geometry'][0]['canvas_width'],1024)
        self.assertEqual(len(self.opened),42)
        self.assertEqual(result['image_decodes'],0)
        self.assertFalse(result['production_promotion'])

    def test_rejected_numeric_audit_opens_no_bank(self):
        for key,value in [('numeric_training_audit_passed',False),('literal_only',True),
                          ('public_numeric_training_complete',False),('comparison_feasible',False)]:
            with self.subTest(key=key):
                broken=copy.deepcopy(self.audit); broken[key]=value
                with self.assertRaises(ValueError):
                    runner.build_geometry(self.inputs,broken,read_bytes=self.read)
                self.assertEqual(self.opened,[])

    def test_bank_pin_not_bound_to_audit_rejected_before_bank_reads(self):
        self.audit['output_pins_after']=dict(self.audit['output_pins_after'])
        first=next(iter(self.audit['output_pins_after']))
        self.audit['output_pins_after'][first]={'bytes':1,'sha256':'0'*64}
        with self.assertRaises(ValueError): self.scan()
        self.assertEqual(self.opened,[])

    def test_missing_bank_and_duplicate_rows_rejected_before_reads(self):
        self.inputs['banks'][-1]=self.inputs['banks'][0]
        with self.assertRaises(ValueError): self.scan()
        self.assertEqual(self.opened,[])

    def test_count_mismatch_cannot_trim_bank(self):
        self.inputs['banks'][0]['control_template_count']=2
        with self.assertRaisesRegex(ValueError,'count'): self.scan()

    def test_all_features_including_last_are_checked(self):
        entry=self.inputs['bank_files'][-1]
        bad=gzip.decompress(self.store[entry['bank']['path']]).replace(b'[ 8, 9, 1 ]',b'[ 9999, 9, 1 ]')
        pin=self.add(entry['bank']['path'],gzip.compress(bad,mtime=0)); entry['bank']=pin
        rel=Path(pin['path']).relative_to(self.inputs['training_run']).as_posix()
        for name in ('output_pins_before','output_pins_after'):
            self.audit[name]=dict(self.audit[name]); self.audit[name][rel]={k:pin[k] for k in ('bytes','sha256')}
        with self.assertRaises(ValueError): self.scan()

    def test_content_pin_is_checked_even_when_declared_audit_matches(self):
        entry=self.inputs['bank_files'][0]; self.store[entry['bank']['path']]+=b'changed'
        with self.assertRaisesRegex(ValueError,'pin'): self.scan()

    def test_original_csv_must_be_bound_to_source_numeric_audit(self):
        self.audit['input_pins']={}
        with self.assertRaises(ValueError): self.scan()
        self.assertEqual(self.opened,[])

    def test_metadata_pose_must_exist_in_original_attempts(self):
        entry=self.inputs['bank_files'][0]
        meta=json.loads(self.store[entry['metadata']['path']]);meta['templates'][0]['angle']=45
        entry['metadata']=self.add(entry['metadata']['path'],canonical(meta))
        with self.assertRaisesRegex(ValueError,'pose'): self.scan()

    def test_limits_and_query_size_cannot_be_overridden_in_input(self):
        self.inputs['source_size']=[100,100]
        with self.assertRaisesRegex(ValueError,'override'): self.scan()
        self.assertEqual(self.opened,[])

    def test_single_use_reservation_and_no_bank_read_to_reserve(self):
        ip=self.add(Path(self.temp.name)/'inputs.json',canonical(self.inputs))
        rp=Path(self.temp.name)/'reservation.json'; output=Path(self.temp.name)/'result'
        reservation=runner.reserve(ip,output,rp,read_bytes=self.read)
        self.assertTrue(reservation['reserved'])
        self.assertFalse(output.exists())
        self.assertEqual(self.opened,[ip['path'],self.inputs['source_numeric_audit']['path']])
        with self.assertRaises(ValueError):runner.reserve(ip,output,rp,read_bytes=self.read)

    def test_failed_execute_is_preserved_and_cannot_repeat(self):
        # Reservation/execution tests patch the pinned byte reader, never read
        # any actual bank payload from disk.
        ip=self.add(Path(self.temp.name)/'inputs.json',canonical(self.inputs))
        rp=Path(self.temp.name)/'reservation.json';output=Path(self.temp.name)/'result'
        runner.reserve(ip,output,rp,read_bytes=self.read)
        self.store[self.inputs['bank_files'][0]['bank']['path']]+=b'changed'
        receipt=runner.execute(rp,read_bytes=self.read)
        self.assertFalse(receipt['passed'])
        self.assertTrue((output/'failure.json').is_file())
        with self.assertRaises(ValueError):runner.execute(rp,read_bytes=self.read)

    def test_successful_execute_writes_fresh_pinned_freeze_without_claiming_independent_acceptance(self):
        ip=self.add(Path(self.temp.name)/'inputs.json',canonical(self.inputs))
        rp=Path(self.temp.name)/'reservation.json';output=Path(self.temp.name)/'result'
        runner.reserve(ip,output,rp,read_bytes=self.read)
        receipt=runner.execute(rp,read_bytes=self.read)
        self.assertTrue(receipt['passed'],receipt)
        for name in ('geometry_freeze','geometry_report','common_padding_plan'):
            self.assertEqual(runner.file_pin(receipt[name]['path']),receipt[name])
        freeze=json.loads((output/'GEOMETRY_FREEZE.json').read_bytes())
        self.assertEqual(freeze['training_freeze'],ip)
        self.assertFalse(freeze['numeric_audit_passed'])
        self.assertTrue(freeze['independent_geometry_audit_required'])
        self.assertEqual(receipt['scanned_banks'],18)
        self.assertTrue(Path(str(rp)+'.consumed.json').exists())
        with self.assertRaises(ValueError):runner.execute(rp,read_bytes=self.read)

    def test_partial_numeric_schedule_rejected_before_any_bank_read(self):
        self.audit['counts']['shared_pools']=41470
        with self.assertRaisesRegex(ValueError,'complete public schedule'):self.scan()
        self.assertEqual(self.opened,[])


if __name__=='__main__':unittest.main()
