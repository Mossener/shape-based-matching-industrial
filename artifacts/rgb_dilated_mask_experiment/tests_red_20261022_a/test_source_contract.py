"""Standard-library source tests. No compiler, native call or dataset reader."""
from pathlib import Path
import ast
import importlib.util
import json
import unittest

HERE = Path(__file__).resolve().parent


def module(name):
    path = HERE / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    item = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(item)
    return item


class SourceContractTests(unittest.TestCase):
    def test_protocol_exists_and_fixed_factor(self):
        self.assertTrue((HERE/'PROTOCOL.json').is_file(), 'missing fixed dilation protocol')
        p = json.loads((HERE/'PROTOCOL.json').read_text())
        self.assertEqual(p['objects'], [1,2,5,8,12,17])
        self.assertEqual(p['training']['attempts_total'], 20736)
        self.assertEqual(p['change_surface']['third_addTemplate_argument'], 'warped_official_mask')
        self.assertEqual(p['change_surface']['core_changes'], 1)
        self.assertEqual(p['quality']['primary_hypothesis'], 'treatment TP >= 215 AND treatment FP < 42112')
        self.assertEqual(p['geometry_gate']['padding_ltrb'], [64,64,64,228])
        self.assertEqual(p['provenance_counters'], {k:0 for k in p['provenance_counters']})

    def test_exact_one_line_transform_and_second_seam_rejected(self):
        f = module('freeze_private_sources')
        data = b'prefix\n' + f.OLD + b'\nsuffix\n'
        self.assertEqual(f.transform_core(data), b'prefix\n'+f.NEW+b'\nsuffix\n')
        for bad in (b'no seam', data+f.OLD, data+f.NEW):
            with self.assertRaises(ValueError): f.transform_core(bad)

    def test_private_snapshot_has_only_authorized_core_delta(self):
        f = module('freeze_private_sources')
        m = json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text())
        result = f.verify(HERE/'private_v11', m)
        self.assertTrue(result['passed'])
        self.assertEqual(result['changed_files'], ['line2Dup.cpp'])
        self.assertEqual(len(m['files']), 23)

    def test_policy_forwards_same_nonempty_official_mask(self):
        s = (HERE/'rgb_dilated_mask_policy.hpp').read_text()
        self.assertEqual(s.count('detector.addTemplate'), 1)
        self.assertIn('detector.addTemplate(warped_gray, class_id, warped_official_mask)', s)
        self.assertIn('warped_gray.size() != warped_official_mask.size()', s)
        self.assertNotIn('cv::Mat()', s)
        self.assertNotIn('.clone()', s)
        spy = (HERE/'rgb_dilated_mask_source_test.cpp').read_text()
        for token in ('spy.source == &gray', 'spy.mask == &mask', 'spy.calls == 1', 'id == 17', 'rejected_size'):
            self.assertIn(token, spy)

    def test_training_adapter_restores_mask_and_pre_call_snapshot(self):
        s = (HERE/'train_rgb_dilated_mask.cpp').read_text()
        call = 'rgb_dilated_mask_experiment::add_template(detector,source,classForObject(obj),warpedMask)'
        self.assertIn(call, s)
        self.assertLess(s.index('const auto maskBefore=warpedMask.clone();'), s.index(call))
        self.assertEqual(s.count('cv::imread('), 2)
        for token in ('CV_8UC1', 'cv::INTER_LINEAR', 'cv::INTER_NEAREST', 'cv::BORDER_CONSTANT',
                      'id==int(metadata.size())', 'count==3456', 'attempts==20736',
                      'n0>0 && n1>0', 'layers.size()==2', 'featureDiagnostics(features,layers'):
            self.assertIn(token, s)
        self.assertNotIn('rgb_empty_mask', s)

    def test_frozen_helper_matches_original_mask_contract(self):
        s = (HERE/'frozen_helpers/tless_eval.cpp').read_text()
        self.assertIn('detector.addTemplate(warped,classId,warped_mask)', s)

    def test_toy_replicated_3x3_dilation_keeps_boundary(self):
        c = module('source_contract')
        mask = [[0]*5 for _ in range(5)]
        mask[2][2] = 255
        dilated = c.toy_morphology(mask, 'dilate')
        eroded = c.toy_morphology(mask, 'erode')
        self.assertEqual(sum(v != 0 for row in dilated for v in row), 9)
        self.assertEqual(sum(v != 0 for row in eroded for v in row), 0)
        self.assertEqual(c.toy_morphology([[255]], 'dilate'), [[255]])
        self.assertEqual(c.toy_morphology([[255]], 'erode'), [[255]])

    def test_attempt_dense_ids_failures_counts_and_geometry(self):
        c = module('source_contract')
        rows = [dict(pose=(0,0,1.), success=1, template_id=0, geometry=[1,2], features=[44,23], error=''),
                dict(pose=(0,30,1.), success=0, template_id=-1, geometry=[1,2], features=[0,0], error='insufficient_features')]
        expected = {tuple(r['pose']):r['geometry'] for r in rows}
        self.assertEqual(c.validate_attempts(rows,expected), 1)
        for field,value in [('template_id',1), ('features',[0,23]), ('geometry',[9,2])]:
            changed = [dict(rows[0], **{field:value}), rows[1]]
            with self.assertRaises(ValueError): c.validate_attempts(changed,expected)
        for changed in (rows[:1], rows+[rows[0]], [rows[0],dict(rows[1],error='')]):
            with self.assertRaises(ValueError): c.validate_attempts(changed,expected)

    def test_scope_rejects_heldout_reserved_and_private_paths(self):
        c = module('source_contract')
        c.check_declared_scope({'objects':[1,2,5,8,12,17], 'development':[{'scene_id':1}], 'training':[{'object_id':1,'rgb':'train_primesense/000001/rgb/000000.png'}]})
        for d in ({'objects':[25]}, {'objects':[1], 'development':[{'scene_id':11}]},
                  {'objects':[1], 'training':[{'object_id':29}]},
                  {'objects':[1], 'training':[{'object_id':1,'rgb':'private/magnet/a.png'}]}):
            with self.assertRaises(ValueError): c.check_declared_scope(d)

    def test_origin_and_generated_adapter_pins(self):
        p = module('source_contract')
        origin = json.loads((HERE/'SOURCE_ORIGINS.json').read_text())
        for item in origin['generated_files']:
            self.assertEqual(p.pin(HERE/item['destination']), item['result'])
            self.assertEqual(p.pin(HERE.parents[1]/item['source']), item['origin'])
        self.assertEqual(origin['image_decodes'],0)
        self.assertEqual(origin['matcher_calls'],0)

    def test_python_syntax_and_local_adapters_have_no_old_experiment_names(self):
        for path in HERE.glob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for name in ('build_training.py','build_quality.py','run_quality.py','quality_contract.py','quality_eval.cpp','quality_support.hpp'):
            self.assertNotIn('rgb_empty_mask', (HERE/name).read_text())

    def test_future_quality_uses_freeze_counts_and_new_paths(self):
        s = (HERE/'prepare_quality_inputs.py').read_text()
        self.assertIn('int(counts[str(obj)])',s)
        self.assertIn('run_training_v1',s)
        self.assertIn('rgb_dilated_mask_quality_inputs_v1',s)
        self.assertIn('accepted_independent_audit',s)

    def test_build_and_run_have_cpu_gate_and_fresh_output(self):
        for name in ('build_training.py','build_quality.py','run_training.py','run_quality.py'):
            s = (HERE/name).read_text()
            self.assertIn('cpu-slot-granted',s)
            self.assertIn('args.cpu_slot_granted',s)
            self.assertIn('not ',s)
            self.assertIn('exists()',s)
        self.assertFalse(any(HERE.glob('build_*_v*/**/*.exe')))


if __name__ == '__main__': unittest.main(verbosity=2)
