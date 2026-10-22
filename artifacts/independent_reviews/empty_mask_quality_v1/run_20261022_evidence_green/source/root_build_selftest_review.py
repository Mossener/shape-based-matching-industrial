"""Parent saved-artifact build/recipe/selftest gate; no native run or image read."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT/'artifacts/silhouette_empty_mask_experiment'
sys.path.insert(0, str(HERE))
import run_quality as q
import native_provenance as p


def main():
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build_path = HERE/'build_quality_v1/build_manifest.json'
    built, build_pin = q.build_gate(build_path)
    private = q.load(HERE/'PRIVATE_SOURCE_FREEZE.json')
    q.frozen.verify(HERE/'private_v11', private)
    flags = private['compile_flags']+['-I'+str(Path(built['opencv'])/'build')]
    flags += ['-I'+str(Path(built['opencv'])/'modules'/module/'include')
              for module in ('core','imgproc','highgui','imgcodecs','videoio')]
    directory = build_path.parent
    commands, counts, logs = [], [], []
    for name, unit in zip(('core','adapter'), built['dependency_units']):
        source, target = Path(unit['source']), name+'.o'
        commands += [[built['compiler'], *flags, '-M','-MT',target,str(source)],
                     [built['compiler'], *flags, '-c',str(source),'-o',str(directory/target),
                      '-MD','-MF',str(directory/(name+'.d')),'-MT',target]]
        before = (directory/(name+'_before.d')).read_bytes()
        actual = (directory/(name+'.d')).read_bytes()
        allow = [Path(pin['path']) for pin in built['project_sources']]
        reconstructed = p.dependency_pins(actual,target,directory,ROOT,allow)
        p.require(reconstructed == unit['dependencies'] ==
                  p.dependency_pins(before,target,directory,ROOT,allow),'Ordered actual depfile differs')
        counts.append(len(reconstructed))
    libraries = [str(Path(built['opencv'])/'build/lib/libopencv_world4120.dll.a'),
                 str(Path(built['compiler']).parent.parent/'lib/libz.dll.a'),
                 str(Path(built['compiler']).parent.parent/'lib/libpsapi.a')]
    commands.append([built['compiler'],'-fopenmp',str(directory/'core.o'),str(directory/'adapter.o'),
                     *libraries,'-o',str(directory/'quality_eval.exe')])
    p.require([c['command'] for c in built['commands']] == commands and
              all(c['working_directory'] == str(directory) and c['exit_code']==0
                  for c in built['commands']),'Exact five-command recipe differs')
    for command in built['commands']:
        logs += [p.file_pin(directory/(command['label']+suffix)) for suffix in ('.stdout','.stderr')]
    stage, stage_pin = q.stage_gate(HERE/'run_quality_selftest_v1','selftest',build_pin,
                                   p.file_pin(HERE/'QUALITY_INPUT_FREEZE.json'))
    expected = dict(passed=1,exact_raw_rows=2048,score_bits_and_order_oracles=1,
                    actual_arm_origin_box_oracle=1,dataset_image_reads=0,matcher_calls=0)
    p.require(stage['summary'] == expected and stage['post_verification_passed'] is True,
              'Exact successful numeric selftest required')
    q.inputs.verify()
    p.require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==source_sha,'Review source changed')
    output = Path(__file__).with_name('root_build_selftest_20261022.json')
    result = dict(passed=True,build_manifest=build_pin,selftest_freeze=stage_pin,
                  actual_command_count=5,ordered_dependency_occurrences=counts,
                  log_pins=logs,audit_source_sha256=source_sha,matcher_calls=0,image_decodes=0,
                  limitation='Saved byte/recipe/selftest checks; native selftest supplies numeric oracles, no quality or speed claim')
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='log_pins'}))


if __name__=='__main__':
    main()
