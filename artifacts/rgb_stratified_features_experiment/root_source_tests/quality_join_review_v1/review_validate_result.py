"""Independent tiny-only review of root validate_result; never opens real evidence."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
TARGET = EXPERIMENT / 'complete_quality_evidence.py'
FILES = [TARGET,
    EXPERIMENT / 'independent_quality/run_audit.py',
    EXPERIMENT / 'independent_quality/quality_audit.py',
    EXPERIMENT / 'independent_quality/contract.py',
    EXPERIMENT / 'quality/run_quality.py',
    EXPERIMENT / 'quality/quality_contract.py',
    EXPERIMENT / 'independent_timing/evidence.py',
    EXPERIMENT / 'independent_timing/audit.py', Path(__file__)]


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write_new(path, data):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def fixture(stage, tp=187, fp=11116):
    passed = tp >= 215 and fp < 42112
    arms = ['rgb_control', 'rgb_pooled_features', 'rgb_stratified_features']
    return dict(schema='independent_three_arm_quality_audit_v1', passed=True,
        numeric_audit_passed=True, scope='quality_all_three_arms', stage='development',
        development_stage=stage, production_promotion=False, unique_frames=400,
        object_frame_pairs=2400, arms=arms,
        raw_and_selected_numeric_equality=True, common_padding_C0_full_raw_exact=True,
        pilot_overlap_full_raw_exact=True, original_padding_C0_full_raw_exact=True,
        matcher_calls=0, image_reads=0, image_decodes=0, input_pins=[stage],
        pooled={arms[0]:dict(allGT=dict(tp=215,fp=42112,fn=185,gt=400)),
                arms[1]:dict(allGT=dict(tp=178,fp=10102,fn=222,gt=400)),
                arms[2]:dict(allGT=dict(tp=tp,fp=fp,fn=400-tp,gt=400))},
        quality_gate=dict(passed=passed, comparison_arm=arms[2], metric='allGT',
            required_tp_minimum=215, required_fp_strictly_below=42112,
            observed_tp=tp, observed_fp=fp, production_promotion=False),
        primary_accuracy_hypothesis_passed=passed)


def main():
    started = time.monotonic()
    before = list(map(pin, FILES))
    spec = importlib.util.spec_from_file_location('quality_join_review_target', TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = []
    with tempfile.TemporaryDirectory(prefix='v31_quality_join_tiny_') as temporary:
        temporary = Path(temporary)
        stage_file = temporary / 'stage.json'
        stage_file.write_text('{"tiny_synthetic_only":true}\n', encoding='utf-8')
        stage = pin(stage_file)
        tests = []
        def case(name, report, expect_accept):
            tests.append((name, report, stage, expect_accept))
        for name,tp,fp in [('failed_B_is_valid_evidence',187,11116),
                           ('pass_B_equal_tp_lower_fp',215,42111),
                           ('pass_B_more_tp',216,42111),
                           ('fail_B_tp_boundary',214,11116),
                           ('fail_B_fp_strict_boundary',215,42112)]:
            case(name,fixture(stage,tp,fp),True)
        for name,tp,fp in [('false_claim_on_passing_B',215,42111),
                           ('true_claim_on_failed_B',187,11116)]:
            report=fixture(stage,tp,fp)
            report['primary_accuracy_hypothesis_passed']=not report['primary_accuracy_hypothesis_passed']
            report['quality_gate']['passed']=report['primary_accuracy_hypothesis_passed']
            case(name,report,False)
        for field,value in [('tp',214),('fp',42111),('fn',184),('gt',399)]:
            report=fixture(stage);report['pooled']['rgb_control']['allGT'][field]=value
            case('wrong_C0_'+field,report,False)
        report=fixture(stage);report['stage']='timing';case('wrong_stage_mode',report,False)
        report=fixture(stage);report['development_stage']=dict(stage,sha256='1'*64)
        case('wrong_stage_pin',report,False)
        report=fixture(stage);report['input_pins']=[];case('missing_stage_input_pin',report,False)
        for field in ('raw_and_selected_numeric_equality','common_padding_C0_full_raw_exact',
                      'pilot_overlap_full_raw_exact','original_padding_C0_full_raw_exact'):
            report=fixture(stage);report[field]=False;case('wrong_'+field,report,False)
        for value in (0,1,'false','true',None):
            report=fixture(stage);report['primary_accuracy_hypothesis_passed']=value
            case('nonbool_primary_'+repr(value),report,False)
        for tp,fp,value in [(187,11116,0),(215,42111,1),(187,11116,'false'),
                            (215,42111,'true'),(187,11116,None)]:
            report=fixture(stage,tp,fp);report['quality_gate']['passed']=value
            case('nonbool_quality_gate_'+repr(value),report,False)
        for ordinal,(name,report,expected_stage,expect_accept) in enumerate(tests):
            # Exercise a serialized, independently authored tiny JSON fixture.
            path=temporary/('%02d.json'%ordinal)
            path.write_text(json.dumps(report,allow_nan=False),encoding='utf-8')
            error=None
            try:
                module.validate_result(json.loads(path.read_text(encoding='utf-8')),expected_stage)
                accepted=True
            except Exception as caught:
                accepted=False;error=repr(caught)
            cases.append(dict(name=name,expected_accept=expect_accept,actual_accept=accepted,
                passed=accepted is expect_accept,error=error,fixture=report))
    after=list(map(pin,FILES))
    assert before==after,'reviewed sources changed during tiny tests'
    result=dict(schema='root_quality_join_source_review_v1',
        passed=all(c['passed'] for c in cases), cases=len(cases),
        passed_cases=sum(c['passed'] for c in cases),
        failed_cases=[c['name'] for c in cases if not c['passed']],
        elapsed_seconds=time.monotonic()-started,source_pins_before=before,source_pins_after=after,
        matcher_calls=0,image_reads=0,image_decodes=0,bank_reads=0,raw_reads=0,
        heldout_reads=0,real_evidence_reads=0,
        limitations=['Pure validate_result fixtures only; no quality_acceptance/timing_inputs execution',
                     'Source/CLI review is static, not a native/runtime/evidence attestation'])
    write_new(HERE/'cases.json',cases)
    write_new(HERE/'receipt.json',result)
    print(json.dumps({k:result[k] for k in ('passed','cases','passed_cases','failed_cases','elapsed_seconds')}))
    return 0 if result['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
