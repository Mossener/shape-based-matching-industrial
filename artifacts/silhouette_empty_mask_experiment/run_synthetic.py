"""Run exactly one reviewed native synthetic RED or GREEN with full build gate."""
import argparse
import json
import os
from pathlib import Path
import subprocess

import freeze_private_sources as frozen
import native_provenance as provenance
import prepare_input_closure as inputs

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cpu-slot-granted',action='store_true')
    args=parser.parse_args()
    provenance.require(args.cpu_slot_granted,'Await coordinated native synthetic CPU slot')
    output=args.output.resolve();provenance.require(output.is_relative_to(HERE) and not output.exists(),'Synthetic output must be fresh inside successor')
    output.mkdir();native_exit=None
    try:
        build=json.loads(args.build_manifest.read_text());build_pin=provenance.file_pin(args.build_manifest)
        provenance.require(build['passed'] is True and build['target'] in ('source-test-red','source-test-green') and
                           build['core_revision']==frozen.REV and build['actual_private_core']==str(HERE/'private_v11/line2Dup.cpp'),
                           'Actual private synthetic build required')
        provenance.require(len(build['commands'])==5 and all(c['exit_code']==0 for c in build['commands']) and
                           len(build['dependency_units'])==2,'Both actual dependency builds and link required')
        provenance.require(build['dependency_units'][1]['source']==str(HERE/'empty_mask_source_test.cpp') and
                           Path(build['executable']['path']).name=='empty_mask_source_test.exe','Synthetic translation unit/executable changed')
        red=build['target']=='source-test-red'
        compiled=next(c for c in build['commands'] if c['label']=='adapter_compile')['command']
        provenance.require(('-DEMPTY_MASK_POLICY_RED_TEST' in compiled)==red,'Synthetic RED macro does not match target')
        pins=list(build['project_sources'])+build['compiler_tools_and_link_libraries']
        pins+=build['compiler_runtime_closure']['files']+build['executable_runtime_closure']['files']+[build['executable'],build_pin,
               provenance.file_pin(HERE/'run_synthetic.py')]
        for unit in build['dependency_units']:
            pins+=unit['dependencies']+[unit['object'],unit['dependency_file']]
        for pin in pins:
            provenance.check_pin(pin)
        inputs.verify();frozen.verify(HERE/'private_v11',json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text()))
        env=dict(os.environ);env['PATH']=str(Path(build['compiler']).parent)+';'+str(Path(build['opencv'])/'build/bin')+';'+env.get('PATH','')
        command=[build['executable']['path'],str(output/'native_result.json')]
        execution=dict(command=command,build_manifest=build_pin,expected_red=red,native_exit_code=None,source_pins=pins)
        (output/'execution_provenance.json').write_text(json.dumps(execution,indent=2)+'\n')
        process=subprocess.run(command,cwd=HERE,env=env,capture_output=True);native_exit=process.returncode
        (output/'native.stdout').write_bytes(process.stdout);(output/'native.stderr').write_bytes(process.stderr)
        execution['native_exit_code']=native_exit;(output/'execution_provenance.json').write_text(json.dumps(execution,indent=2)+'\n')
        for pin in pins:
            provenance.check_pin(pin)
        inputs.verify()
        if red:
            provenance.require(native_exit!=0 and b'Feature-selection mask must be empty cv::Mat()' in process.stderr and
                               not (output/'native_result.json').exists(),'RED must fail specifically before native toy extraction')
        else:
            provenance.require(native_exit==0,'GREEN native ownership/toy oracle failed')
            native=json.loads((output/'native_result.json').read_text())
            provenance.require(native['passed']==1 and native['clone_ownership_passed']==1 and native['selection_mask_empty_spy_passed']==1 and
                               native['invalid_masks_rejected']==4 and native['dataset_image_reads']==0 and native['matcher_calls']==0 and
                               [r['toy'] for r in native['toys']]==['rectangle','diagonal_polygon'],'GREEN literal ownership/toy evidence differs')
        result=dict(passed=True,expected_red=red,native_exit_code=native_exit,
                    scope='Native policy/ownership oracles and unchanged two toys; toy addTemplate outcomes are recorded, not tuned',
                    build_manifest=build_pin,dataset_image_reads=0,matcher_calls=0,
                    files=[provenance.file_pin(p) for p in sorted(output.iterdir()) if p.is_file()])
        (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,expected_red=red,native_exit_code=native_exit)))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),native_exit_code=native_exit),indent=2)+'\n');raise


if __name__=='__main__':
    main()
