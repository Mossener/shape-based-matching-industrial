"""Prepare source adapters and declarations only; never copy execution output."""
import argparse
import json
from pathlib import Path
import freeze_private_sources as f
from source_contract import check_declared_scope, pin, require

HERE=Path(__file__).resolve().parent
BASE=f.BASE
PINS={
 'PROTOCOL.json':'c107f651aba89bcc0c731b4f2b6d02afd9f899a339657c3db2856f1d71746fce',
 'INPUT_CLOSURE.json':'c98625c7f83c443577393363f9a1e575148af9668258179efd4caa3936d422e6',
 'train_rgb_empty_mask.cpp':'1e3c13420571938855bb399bb4c63c905bc5cb9401162ef10caedbb84182d514',
 'build_training.py':'ae087ce26a24a140519b226cee3465f3b2398602e5564913710fac5d06a090ad',
 'build_quality.py':'97122c279b16148cf095c41a1c860dda8c1f3d0684414c833402df67aafc16ed',
 'run_quality.py':'5293b8c12b9ad7df5c013f9109be68e44cc9306aa3dd2e35548d7821f25e4385',
 'prepare_quality_inputs.py':'c9bdc0d8a37d0017a6cefb9d474c3a4b25e4e3010dbe8196b6ffdfff5a099f89',
 'quality_support.hpp':'bb0ac9eaf6e5ad4fbd57ddc4e3c3001b994f143e9309cddaa105c73c1a838b52',
 'quality_eval.cpp':'9593b8fda2d65370dfad85c220deae3c7ac7caaeeeacc775fc65d3d4d8ab8ee6',
 'quality_contract.py':'8f8164dc5a09869b8d63c243680b37af340a3330c1c82a7f0348f1578c2a02ca',
 'native_provenance.py':'1ad3bb79fbe1647d6d125d2a49c584dc856a5f41fcbaf2a57a60d37cfeba8a10'}


def read(name):
    require(pin(BASE/name)['sha256']==PINS[name],'Pinned V27 source changed: '+name)
    return (BASE/name).read_text(encoding='utf-8')


def replace_once(text,old,new):
    require(text.count(old)==1,'Source transformation seam changed: '+old)
    return text.replace(old,new,1)


def write_json(name,value):
    path=HERE/name;require(not path.exists(),'Fresh generated source/declaration required: '+name)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    require(not (HERE/'SOURCE_ORIGINS.json').exists(),'Preparation already ran; preserve old evidence')
    protocol=json.loads(read('PROTOCOL.json'))
    protocol['schema']='rgb_dilated_mask_experiment_design_v1'
    protocol['experiment']='RGB_grayscale_source_official_mask_per_layer_dilation'
    protocol['parent_experiment']='artifacts/rgb_empty_mask_experiment'
    protocol['change_surface']['third_addTemplate_argument']='warped_official_mask'
    protocol['change_surface']['core_changes']=1
    protocol['change_surface']['core_old']=f.OLD.decode()
    protocol['change_surface']['core_new']=f.NEW.decode()
    protocol['change_surface']['unchanged']=[s.replace('V11 pyramid/gradient/blur/orientation/NMS/scattered selector','V11 pyramid/gradient/blur/orientation/NMS/scattered selector except the declared one-line local-mask morphology') for s in protocol['change_surface']['unchanged']]
    protocol['quality']['arms']=['frozen_rgb_control','rgb_dilated_mask_treatment']
    protocol['quality']['historical_v27_groups']={'retained':156,'lost':59,'gained':27,'neither':158}
    protocol['geometry_gate']['risk']='Original tight crop and black affine border retained; dilation may admit artificial boundary features'
    protocol['input_pins']=[]
    write_json('PROTOCOL.json',protocol)
    f.create()
    closure=json.loads(read('INPUT_CLOSURE.json'));check_declared_scope(closure)
    closure['version']='rgb_dilated_mask_input_closure_v1'
    closure['inherited_frozen_root']=str(BASE)
    closure['inherited_closure_origin']=dict(path=str(BASE/'INPUT_CLOSURE.json'),**pin(BASE/'INPUT_CLOSURE.json'))
    closure['protocol_sha256']=pin(HERE/'PROTOCOL.json')['sha256']
    closure['private_source_freeze_sha256']=pin(HERE/'PRIVATE_SOURCE_FREEZE.json')['sha256']
    closure['preparer_sha256']=pin(Path(__file__))['sha256']
    closure['inherited_declarations_only']=True
    write_json('INPUT_CLOSURE.json',closure)
    generated=[]
    for old in PINS:
        if old in ('PROTOCOL.json','INPUT_CLOSURE.json'): continue
        text=read(old)
        name=old.replace('rgb_empty_mask','rgb_dilated_mask')
        text=text.replace('rgb_empty_mask','rgb_dilated_mask').replace('RGB_EMPTY_MASK','RGB_DILATED_MASK').replace('rgb_empty_quality','rgb_dilated_quality').replace('RGB EMPTY MASK','RGB DILATED MASK').replace('RGB empty-mask','RGB dilated-mask').replace('RGB-empty-mask','RGB-dilated-mask').replace('RGB EMPTY-MASK','RGB DILATED-MASK')
        if old=='train_rgb_empty_mask.cpp':
            text=replace_once(text,'// Isolated RGB-source/empty-selection-mask treatment. The frozen V11 core\n// and public evaluator helper are included unchanged; only addTemplate\'s\n// third argument is changed through rgb_dilated_mask_policy.hpp.',
                '// Isolated RGB-source/official-mask dilation treatment. The helper is\n// unchanged; private V11 has exactly one erode-to-dilate line. The policy\n// preserves the original nonempty third addTemplate mask argument.')
            text=replace_once(text,'// The official mask remains the geometry/ROI source. It is never\n        // passed as the feature-selection mask in this treatment.',
                '// The official warped mask remains both geometry and selection input.')
            text=replace_once(text,'try{id=rgb_dilated_mask_experiment::add_template(detector,source,classForObject(obj));',
                'const auto maskBefore=warpedMask.clone();\n            try{id=rgb_dilated_mask_experiment::add_template(detector,source,classForObject(obj),warpedMask);')
            text=replace_once(text,'            const auto maskBefore=warpedMask.clone();\n            ensure(cv::countNonZero', '            ensure(cv::countNonZero')
            text=text.replace('trainRgbEmptyMask','trainRgbDilatedMask').replace('empty cv::Mat()','official warped mask; per-layer 3x3 dilation')
        if old=='build_training.py':
            text=replace_once(text,"choices=['training','source-test']", "choices=['training','source-test','literal-test']")
            text=replace_once(text,"    parser.add_argument('--cpu-slot-granted'", "    parser.add_argument('--core-arm', choices=['treatment','control'], default='treatment')\n    parser.add_argument('--expected-morphology', choices=['dilate','erode'], default='dilate')\n    parser.add_argument('--cpu-slot-granted'")
            text=replace_once(text,"        inputs.verify()\n        env =", "        inputs.verify()\n        provenance.require(args.target=='literal-test' or args.core_arm=='treatment', 'Control core is literal-test only')\n        private=HERE/('private_v11' if args.core_arm=='treatment' else 'control_v11')\n        env =")
            text=replace_once(text,"[HERE/'private_v11'/n for n in manifest['files']]", "[private/n for n in manifest['files']]")
            text=replace_once(text,"adapter = HERE/('train_rgb_dilated_mask.cpp' if args.target=='training' else 'rgb_dilated_mask_source_test.cpp')", "adapter = HERE/{'training':'train_rgb_dilated_mask.cpp','source-test':'rgb_dilated_mask_source_test.cpp','literal-test':'literal_mask_test.cpp'}[args.target]")
            text=replace_once(text,"flags = manifest['compile_flags']+", "flags = frozen.private_flags(private)+")
            text=replace_once(text,"        units = []", "        if args.target=='literal-test': flags += ['-DEXPECT_DILATION='+str(int(args.expected_morphology=='dilate'))]\n        units = []")
            text=replace_once(text,"('core', HERE/'private_v11/line2Dup.cpp')", "('core', private/'line2Dup.cpp')")
            text=replace_once(text,"exe = out/('train_rgb_dilated_mask.exe' if args.target=='training' else 'rgb_dilated_mask_source_test.exe')", "exe = out/{'training':'train_rgb_dilated_mask.exe','source-test':'rgb_dilated_mask_source_test.exe','literal-test':'literal_mask_test.exe'}[args.target]")
            text=replace_once(text,"actual_private_core=str(HERE/'private_v11/line2Dup.cpp'),", "actual_private_core=str(private/'line2Dup.cpp'), core_arm=args.core_arm, expected_morphology=args.expected_morphology,")
            text=text.replace('Independent RGB grayscale-source empty-feature-mask training/planner or policy selftest; actual private V11 and actual two-TU GCC -MD dependencies; no quality/default promotion', 'Independent RGB grayscale-source official-mask per-layer erode-to-dilate training/planner or literal/spy selftest; pinned V11 origin with declared one-line treatment and actual two-TU GCC -MD dependencies; no quality/default promotion')
        if old=='prepare_quality_inputs.py':
            text=text.replace(PINS['PROTOCOL.json'],pin(HERE/'PROTOCOL.json')['sha256'])
            text=replace_once(text,'        row["rgb_training"] = str(HERE / "frozen_inputs" / f"obj{obj}" / "rgb_training")\n        row["original_pilot_raw"] = str(HERE / "frozen_inputs" / f"obj{obj}" / "original_pilot_raw")\n','')
            text=replace_once(text,'    counts = bank["successful_templates"]','    p.require(bank.get("accepted_independent_audit") is True and plan.get("accepted_independent_audit") is True, "Independent training and plan acceptance required")\n    counts = bank["successful_templates"]')
            text=replace_once(text,'    p.require(bank.get("accepted_independent_audit") is True and plan.get("accepted_independent_audit") is True, "Independent training and plan acceptance required")',
                '    acceptance = read(HERE / "AUDIT_ACCEPTANCE.json")\n    p.require(acceptance["accepted_independent_audit"] is True and acceptance["scope"] == "training_and_exact_geometry", "Independent training and plan acceptance required")\n    p.require(acceptance["training_freeze"] == p.file_pin(HERE / "run_training_v1" / "BANK_FREEZE.json") and\n              acceptance["plan_freeze"] == p.file_pin(HERE / "run_plan_v1" / "COMMON_PADDING_FREEZE.json"), "Acceptance binds another training/geometry freeze")\n    p.check_pin(acceptance["independent_audit"])\n    p.require(read(acceptance["independent_audit"]["path"])["passed"] is True, "Independent audit did not pass")')
            text=replace_once(text,'               p.file_pin(HERE / "run_plan_v1" / "plan_audit.json")]',
                '               p.file_pin(HERE / "run_plan_v1" / "plan_audit.json"),\n               p.file_pin(HERE / "AUDIT_ACCEPTANCE.json"), acceptance["independent_audit"]]')
        if old=='build_quality.py':
            text=replace_once(text,"('build_quality.py', 'native_provenance.py', 'freeze_private_sources.py',",
                "('build_quality.py', 'source_contract.py', 'quality_execution_inputs.py', 'native_provenance.py', 'freeze_private_sources.py',")
        if old=='run_quality.py':
            text=replace_once(text,'import quality_contract as contract','import quality_contract as contract\nimport quality_execution_inputs as execution_inputs')
            text=replace_once(text,"['run_quality.py','quality_contract.py','prepare_quality_inputs.py','prepare_input_closure.py','native_provenance.py']",
                "['run_quality.py','quality_contract.py','prepare_quality_inputs.py','prepare_input_closure.py','native_provenance.py','freeze_private_sources.py','source_contract.py','quality_execution_inputs.py']")
            text=replace_once(text,'before=inputs.verify();image_before=inherited.verify()','before=inputs.verify();image_before=execution_inputs.verify(args.mode)')
            text=replace_once(text,'after=inputs.verify();image_after=inherited.verify()','after=inputs.verify();image_after=execution_inputs.verify(args.mode)')
        dest=HERE/name;require(not dest.exists(),'Fresh adapter source required: '+name);dest.write_text(text,encoding='utf-8',newline='\n')
        generated.append(dict(source=(BASE/old).relative_to(f.ROOT).as_posix(),destination=name,origin=pin(BASE/old),result=pin(dest),
                              transformation='explicit source preparation rename and declared bounded adaptations; no execution outputs'))
    write_json('SOURCE_ORIGINS.json',dict(generated_files=generated,source_freeze_origin=dict(path=str(BASE/'PRIVATE_SOURCE_FREEZE.json'),**pin(BASE/'PRIVATE_SOURCE_FREEZE.json')),
       official_rgb_helper_origin=dict(path=str(BASE/'frozen_helpers/tless_eval.cpp'),**pin(BASE/'frozen_helpers/tless_eval.cpp')),
       image_decodes=0,matcher_calls=0,native_compilations=0,bank_byte_reads=0))
    write_json('source_status.json',dict(status='source_only_no_native_or_dataset_reads',native_compilations=0,native_runs=0,matcher_calls=0,image_decodes=0,bank_byte_reads=0,private_smd_reads=0,
        source_snapshot='private_v11',literal_control_snapshot='control_v11',source_only_grant=True,production_modified=False))
    print(json.dumps(dict(passed=True,generated_source_files=len(generated),native_compilations=0,image_decodes=0,matcher_calls=0)))


if __name__=='__main__': main()
