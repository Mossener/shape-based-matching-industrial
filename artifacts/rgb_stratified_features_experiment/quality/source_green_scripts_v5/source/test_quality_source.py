"""Pure Python schedules/gates plus static native-source contracts; no native run."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import quality_contract as c
import prepare_quality_inputs as qinputs
import quality_execution_inputs as qexecution

HERE=Path(__file__).resolve().parent


class QualityContractTest(unittest.TestCase):
    def test_fixed_budgets(self):
        for mode,want in [('old_gate',96),('pilot',288),('development',14400),('timing',29952)]:
            self.assertEqual(c.stage_spec(mode)['maximum_calls'],want)

    def test_full_timing_rotation(self):
        counts=[0]*6;formal=0;calls=0
        for frame in range(64):
            for obj in [1,2,5,8,12,17]:
                positions=[[0]*6 for _ in range(6)]
                for round_index in range(13):
                    order=c.timing_order(frame,round_index)
                    self.assertEqual(sorted(order),list(range(6)))
                    self.assertEqual(order[0],(frame+round_index)%6)
                    calls+=6
                    if round_index:
                        for position,variant in enumerate(order):
                            positions[variant][position]+=1;counts[variant]+=1;formal+=1
                self.assertEqual(positions,[[2]*6 for _ in range(6)])
        self.assertEqual(calls,29952);self.assertEqual(formal,27648)
        self.assertEqual(counts,[4608]*6)

    def test_specs_are_independent_copies(self):
        first=c.stage_spec('pilot');first['arms'].pop()
        self.assertEqual(c.stage_spec('pilot')['arms'],['rgb_control','rgb_pooled_features','rgb_stratified_features'])
        self.assertEqual(c.stage_spec('old_gate')['arms'],['rgb_control'])
        for invalid in ['heldout','private',None]:
            with self.assertRaises(ValueError):c.stage_spec(invalid)

    def test_geometry_is_actual_not_guessed(self):
        for plan in [dict(width=848,height=832,padding_ltrb=[64,64,64,228],banks=18,geometry_feasible=True),
                     dict(width=864,height=848,padding_ltrb=[64,64,80,244],banks=18,geometry_feasible=True)]:
            self.assertEqual(c.validate_padding(plan),plan['padding_ltrb'])
        base=dict(width=848,height=832,padding_ltrb=[64,64,64,228],banks=18,geometry_feasible=True)
        for key,value in [('banks',12),('height',672),('geometry_feasible',False),('width',4096)]:
            bad=copy.deepcopy(base);bad[key]=value
            with self.assertRaises(ValueError):c.validate_padding(bad)
        bad=copy.deepcopy(base);bad['padding_ltrb']=[65,64,63,228]
        with self.assertRaises(ValueError):c.validate_padding(bad)

    def test_reservation_persists_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);pin={'path':'numeric/old_gate.json','bytes':1,'sha256':'a'*64}
            c.reserve(d,'pilot','new_run',pin)
            with self.assertRaises(FileExistsError):c.reserve(d,'pilot','other_run',pin)
            row=json.loads((d/'pilot.json').read_text())
            self.assertEqual(row['maximum_calls'],288);self.assertEqual(row['total_protocol_maximum'],44736)
            with self.assertRaises(ValueError):c.reserve(d,'timing','run',None)

    def test_timing_requires_independent_quality_audit(self):
        d={'accepted_independent_audit':True,'scope':'quality_all_three_arms',
           'development_stage':{'path':'dev.json','bytes':1,'sha256':'a'*64},
           'independent_audit':{'path':'audit.json','bytes':2,'sha256':'b'*64},
           'numeric_audit_passed':True,'primary_accuracy_hypothesis_passed':False,
           'production_promotion':False}
        c.validate_quality_acceptance(d,d['development_stage'])
        for key,value in [('scope','training_and_exact_geometry'),('numeric_audit_passed',False),
                          ('accepted_independent_audit',False),('production_promotion',True)]:
            bad=copy.deepcopy(d);bad[key]=value
            with self.assertRaises(ValueError):c.validate_quality_acceptance(bad,d['development_stage'])
        # Accuracy failure cannot block this fixed timing schedule or promote B.
        self.assertFalse(d['primary_accuracy_hypothesis_passed'])

    def test_native_source_contract(self):
        self.assertTrue(c.validate_native_sources(HERE)['passed'])

    def test_native_source_mutations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            original={name:(HERE/name).read_text() for name in ('quality_eval.cpp','quality_support.hpp')}
            cases=[('quality_eval.cpp','round<13','round<8'),
                   ('quality_eval.cpp','(order+frameOrdinal+round)%6','(order+round)%6'),
                   ('quality_eval.cpp','if(arm==0 && !gate)','if(arm==0 && mode=="pilot")'),
                   ('quality_support.hpp','++calls;','calls+=2;'),
                   ('quality_support.hpp','scoreBits(a.score)==scoreBits(b.score)','a.score==b.score')]
            for name,before,after in cases:
                for filename,text in original.items():(root/filename).write_text(text)
                self.assertEqual(original[name].count(before),1)
                (root/name).write_text(original[name].replace(before,after))
                with self.assertRaises(ValueError):c.validate_native_sources(root)

    def test_quality_preparer_fails_closed_without_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / 'missing_acceptance.json'
            with self.assertRaises((FileNotFoundError, ValueError)):
                qinputs.build(missing)

    def test_quality_preparer_acceptance_requires_exact_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = dict(schema='rgb_stratified_training_geometry_acceptance_v1',
                       accepted_independent_audit=True,
                       scope='training_only', numeric_audit_passed=True,
                       production_promotion=False)
            path = root / 'acceptance.json'
            path.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaises(ValueError):qinputs._acceptance(path)

    def test_training_rows_require_all_three_observed_banks(self):
        row = {'object_id':1, 'control_training':'c', 'control_template_count':1,
               'pooled_training':'p', 'pooled_template_count':1,
               'stratified_training':'b', 'stratified_template_count':1}
        freeze = {'banks':[row]}
        for key in ('stratified_training','stratified_template_count'):
            bad = copy.deepcopy(row);bad.pop(key)
            with self.assertRaises(ValueError):qinputs._training_rows({'banks':[bad]},Path('acceptance.json'))
        with self.assertRaises(ValueError):qinputs._training_rows(freeze,Path('acceptance.json'))

    def test_execution_scope_rejects_unknown_stage_before_reads(self):
        with self.assertRaises(ValueError):
            qexecution.verify('heldout', Path('does-not-exist.json'))

    def test_quality_scripts_keep_acceptance_and_native_slots_gated(self):
        preparer = (HERE / 'prepare_quality_inputs.py').read_text(encoding='utf-8')
        builder = (HERE / 'build_quality.py').read_text(encoding='utf-8')
        runner = (HERE / 'run_quality.py').read_text(encoding='utf-8')
        self.assertIn('accepted_independent_audit', preparer)
        self.assertIn('validate_padding', preparer)
        self.assertIn('Await coordinated actual-build CPU slot', builder)
        self.assertIn('TRAINING_SOURCE_FREEZE.json', builder)
        self.assertNotIn('private_v11/line2Dup.cpp', builder)
        self.assertIn('_quality_audit_gate', runner)
        self.assertIn('Await coordinated native quality CPU slot', runner)


if __name__=='__main__':unittest.main()
