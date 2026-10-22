import copy
from pathlib import Path
import tempfile
import unittest
import evidence as e

def selftest(red=False):
    s=dict(stage='selftest',completed=True,native_exit_code=1 if red else 0,expected_native_failure=red,actual_full_class_search_replays=0,image_hash_operations=0,unique_dataset_image_files_opened=0,partial_results_are_not_negatives=False,phase2_started=False,image_before=[],image_after=[])
    summary=None if red else dict(passed=1,scalar_native_cells=256,cross_template_representative_fixture=1,dataset_image_reads=0,full_class_search_replays=0,public_detector_match_calls=0)
    failure=dict(reason='Independent scalar/native score mismatch',full_class_search_replays_started=0,public_detector_match_calls=0,phase2_started=0,partial_results_are_not_negatives=1) if red else None
    return s,summary,failure

def build(red=False):
    macro=['-DSCORE_PROBE_ORACLE_RED'] if red else []
    return dict(passed=True,target='score_path_probe_phase1',core_revision='b25df46f6ddf9c24fb43f5836f1414dc38c8caed',red_negative_control=red,image_decodes=0,full_class_search_replays=0,public_detector_match_calls=0,dependency_units=[dict(source='C:/p/probe.cpp',included_private_core='C:/p/private_v11/line2Dup.cpp',object=dict(path='C:/build/adapter.o'))],commands=[dict(label='dependency_before',command=['compiler',*macro,'-M','C:/p/probe.cpp'],exit_code=0),dict(label='compile',command=['compiler',*macro,'-c','C:/p/probe.cpp','-o','C:/build/adapter.o'],exit_code=0),dict(label='link',command=['compiler','C:/build/adapter.o','-o','C:/build/score_probe.exe'],exit_code=0)])

class EvidenceTests(unittest.TestCase):
    def test_pin_integrity_and_numeric_only_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.csv'; p.write_text('a\n'); value=e.pin(p); self.assertEqual(e.verify_pin(value),p.resolve())
            p.write_text('b\n')
            with self.assertRaises(ValueError): e.verify_pin(value)
            p=Path(d)/'forbidden.png'; p.write_bytes(b'not even image')
            with self.assertRaises(ValueError): e.pin(p)

    def test_exact_output_members_reject_added_missing_outside_and_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.csv'; p.write_text('a\n'); value=e.pin(p); e.output_members(d,[value])
            for pins in [[],[value,value],[dict(value,path=str(Path(d).parent/'outside.csv'))]]:
                with self.assertRaises(ValueError): e.output_members(d,pins)
            (Path(d)/'failure.json').write_text('{}')
            with self.assertRaises(ValueError): e.output_members(d,[value])

    def test_green_and_intentional_red_scope(self):
        for red in (False,True): e.validate_stage_fields(*((lambda x:(x[0],red,x[1],x[2]))(selftest(red))))

    def test_green_cannot_carry_failure_or_nonzero_exit(self):
        s,summary,failure=selftest()
        with self.assertRaises(ValueError): e.validate_stage_fields(s,False,summary,{})
        s['native_exit_code']=1
        with self.assertRaises(ValueError): e.validate_stage_fields(s,False,summary,None)

    def test_red_must_fail_for_exact_oracle_reason(self):
        s,summary,failure=selftest(True); failure['reason']='some other failure'
        with self.assertRaises(ValueError): e.validate_stage_fields(s,True,summary,failure)

    def test_partial_heldout_or_phase2_stage_rejected(self):
        for key,value in [('completed',False),('partial_results_are_not_negatives',True),('phase2_started',True),('image_hash_operations',1),('actual_full_class_search_replays',1)]:
            s,summary,failure=selftest(); s[key]=value
            with self.assertRaises(ValueError): e.validate_stage_fields(s,False,summary,failure)

    def test_complete_single_tu_build_and_red_macro(self):
        for red in (False,True): e.validate_build_fields(build(red),red)

    def test_build_rejects_second_unit_failed_command_and_macro_mismatch(self):
        cases=[]; b=build(); b['dependency_units']*=2; cases.append(b)
        b=build(); b['commands'][1]['exit_code']=1; cases.append(b)
        b=build(); b['commands'][1]['command'].append('-DSCORE_PROBE_ORACLE_RED'); cases.append(b)
        b=build(); b['commands'][2]['command'].append('core.o'); cases.append(b)
        for b in cases:
            with self.assertRaises(ValueError): e.validate_build_fields(b,False)

if __name__=='__main__': unittest.main()
