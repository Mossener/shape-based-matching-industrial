"""Pure evidence mutations use in-memory receipts and temporary text only."""
import copy
from pathlib import Path
import tempfile
import unittest
import evidence2 as e


def build(red=False):
    hdr=dict(path=str(Path('generated_preprocess.hpp').resolve()),sha256='0'*64,bytes=10)
    src=dict(path=str(Path('phase2.cpp').resolve()),sha256='1'*64,bytes=20)
    return dict(passed=True,target='score_path_probe_phase2',core_revision='b25df46f6ddf9c24fb43f5836f1414dc38c8caed',red_controls=red,image_decodes=0,full_class_search_replays=0,public_detector_match_calls=0,dependency_units=[dict(source=src['path'],included_private_core='line2Dup.cpp',generated_preprocess_header=hdr,object=dict(path='unit.o'))],project_sources=[src,hdr],compiler_tools_and_link_libraries=[src],commands=[dict(label='dependency_before',command=['g++','-M','phase2.cpp']+(['-DSCORE_PATH_RED_CONTROLS'] if red else []),exit_code=0),dict(label='compile',command=['g++','-c','phase2.cpp']+(['-DSCORE_PATH_RED_CONTROLS'] if red else []),exit_code=0),dict(label='link',command=['g++','unit.o'],exit_code=0)])


def stage(fault='none',mode='selftest'):
    red=fault!='none';phase=mode=='phase2'
    summary=None if red else dict(passed=1,stage=mode,coarse_cells=12,local_cells=256,scalar_native_oracles=1,dataset_image_reads=0,full_class_search_replays=0,public_detector_match_calls=0)
    if phase:summary=dict(e.EXPECTED_PHASE2,passed=1,stage='phase2',numeric_output_bytes=100,peak_rss_bytes=100)
    failure=dict(reason='Independent '+fault+' oracle mismatch',decoded_operations_started=0,full_class_search_replays=0,public_detector_match_calls=0) if red else None
    return dict(stage=mode,fault=fault,completed=True,native_exit_code=1 if red else 0,expected_native_failure=red,partial_results_are_not_negatives=False,accuracy_improvement_claim=False,image_before=[] if not phase else [dict(path='declared.png',bytes=1,sha256='0'*64)]*175,image_after=[] if not phase else [dict(path='declared.png',bytes=1,sha256='0'*64)]*175,image_hash_operations=350 if phase else 0,unique_dataset_image_files_opened=175 if phase else 0,summary=summary,native_failure=failure)


class Evidence(unittest.TestCase):
    def test_image_and_template_bytes_blocked(self):
        for path in ('a.png','b.JPG','c.smd','templates_cls.yml.gz','private.smdx'):
            with self.subTest(path=path),self.assertRaises(ValueError):e.safe(path)

    def test_small_text_hash_and_pin_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.txt';path.write_bytes(b'abc')
            value=e.pin(path)
            self.assertEqual((value['bytes'],value['sha256']),(3,'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'))
            e.validate_pin(value)
            for mutation in (dict(value,bytes=-1),dict(value,sha256='0'),dict(value,extra=1)):
                with self.assertRaises(ValueError):e.validate_pin(mutation)

    def test_stage_synthetic_and_red_contract(self):
        for fault in ('none','coarse','local','winner'):e.validate_stage(stage(fault))
        for field,value in [('completed',False),('native_exit_code',0),('expected_native_failure',False),('image_hash_operations',1),('fault','unknown')]:
            bad=stage('coarse');bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):e.validate_stage(bad)
        bad=stage('winner');bad['native_failure']['reason']='another failure'
        with self.assertRaises(ValueError):e.validate_stage(bad)

    def test_phase2_stage_scope_budgets_and_claim_boundary(self):
        good=stage(mode='phase2');e.validate_stage(good)
        for field,value in [('rgb_positive_controls',214),('coarse_cells',1),('public_detector_match_calls',1),('decoded_operations',214),('peak_rss_bytes',1610612737),('numeric_output_bytes',1073741825)]:
            bad=copy.deepcopy(good);bad['summary'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):e.validate_stage(bad)
        bad=copy.deepcopy(good);bad['accuracy_improvement_claim']=True
        with self.assertRaises(ValueError):e.validate_stage(bad)

    def test_build_single_tu_and_red_macro(self):
        e.validate_build(build(),False);e.validate_build(build(True),True)
        for mutate in ('macro','units','commands','object','core'):
            bad=build()
            if mutate=='macro':bad['commands'][0]['command'].append('-DSCORE_PATH_RED_CONTROLS')
            if mutate=='units':bad['dependency_units']*=2
            if mutate=='commands':bad['commands'][1]['exit_code']=1
            if mutate=='object':bad['commands'][2]['command'].append('other.o')
            if mutate=='core':bad['core_revision']='other'
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):e.validate_build(bad,False)

    def test_build_equivalence_only_header_path_exception(self):
        red,green=build(True),build();e.equivalent_builds(red,green)
        green['dependency_units'][0]['generated_preprocess_header']['path']=str(Path('other/generated_preprocess.hpp').resolve());e.equivalent_builds(red,green)
        for mutation in ('hash','source','extra'):
            bad=copy.deepcopy(green)
            if mutation=='hash':bad['dependency_units'][0]['generated_preprocess_header']['sha256']='2'*64
            if mutation=='source':bad['project_sources'][0]['sha256']='2'*64
            if mutation=='extra':bad['project_sources'].append(dict(bad['project_sources'][0]))
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):e.equivalent_builds(red,bad)

    def test_prior_bank_declarations_are_not_opened(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);text=directory/'numeric.csv';text.write_bytes(b'abc')
            bank=dict(object_id=1,rgb_training=str(directory/'rgb'),binary_training=str(directory/'binary'))
            # These two files deliberately do not exist. Only their immutable
            # declarations may be compared; reading bytes would fail this test.
            declared=[dict(path=str((Path(bank[field])/'templates_tless_object_1.yml.gz').resolve()),sha256='0'*64,bytes=10) for field in ('rgb_training','binary_training')]
            prior=dict(banks=[bank],numeric_pins=[e.pin(text)]+declared)
            closure=e.Closure(directory)
            self.assertEqual(e.prior_numeric(closure,prior),declared)
            self.assertEqual(len(closure.checked),1)
            for values in (prior['numeric_pins'][:-1],prior['numeric_pins']+[declared[0]],[e.pin(text),dict(declared[0],path=str(directory/'other.yml.gz')),declared[1]]):
                bad=dict(prior,numeric_pins=values)
                with self.assertRaises(ValueError):e.prior_numeric(closure,bad)


if __name__=='__main__':unittest.main()
