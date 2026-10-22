"""Root's independent build/synthetic receipt check; no image or native access."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def read(path):
    return json.loads(Path(path).read_bytes())


def verify(value):
    assert pin(value['path']) == value, value['path']


def main():
    results = []
    builds = []
    checked = set()
    for color, red in [('red', True), ('green', False)]:
        directory = HERE/f'probe_build_{color}_v2'
        build = read(directory/'build_manifest.json')
        assert build['passed'] is True and build['red_negative_control'] is red
        assert build['core_revision'] == 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
        assert [r['label'] for r in build['commands']] == ['dependency_before', 'compile', 'link']
        assert all(r['exit_code'] == 0 for r in build['commands'])
        assert all(('-DSCORE_PROBE_ORACLE_RED' in r['command']) is red for r in build['commands'][:2])
        assert len(build['dependency_units']) == 1
        unit = build['dependency_units'][0]
        assert Path(unit['source']).resolve() == HERE/'probe.cpp'
        assert Path(unit['included_private_core']).name == 'line2Dup.cpp'
        link_objects = [r for r in build['commands'][2]['command'] if r.endswith('.o')]
        assert link_objects == [str(directory/'adapter.o')]
        values = build['project_sources'] + build['compiler_tools_and_link_libraries']
        values += build['compiler_runtime_closure']['files'] + build['executable_runtime_closure']['files']
        values += unit['dependencies'] + [unit['object'], unit['dependency_file'], build['executable']]
        for value in values:
            verify(value)
            checked.add((value['path'], value['sha256']))
        builds.append(build)
        run = HERE/f'probe_selftest_{color}_v2'
        stage = read(run/'PROBE_STAGE_FREEZE.json')
        assert stage['completed'] is True and stage['stage'] == 'selftest'
        assert stage['expected_native_failure'] is red
        assert stage['native_exit_code'] == (1 if red else 0)
        assert stage['actual_full_class_search_replays'] == stage['image_hash_operations'] == 0
        assert stage['image_before'] == stage['image_after'] == []
        assert stage['build_manifest'] == pin(directory/'build_manifest.json')
        assert stage['input_plan']['sha256'] == '353615a753a0be27a2665997488301259fe99989858068895870d16fe32de91c'
        for value in stage['files'] + stage['execution_files'] + [stage['build_manifest'], stage['input_plan'], stage['reservation']]:
            verify(value)
        assert {p.resolve() for p in (run/'native').rglob('*') if p.is_file()} == {Path(p['path']).resolve() for p in stage['files']}
        assert {p.resolve() for p in run.iterdir() if p.is_file()} == {Path(p['path']).resolve() for p in stage['execution_files']} | {run/'PROBE_STAGE_FREEZE.json'}
        if red:
            failure = read(run/'native/failure.json')
            assert failure['reason'] == 'Independent scalar/native score mismatch'
            assert failure['full_class_search_replays_started'] == failure['public_detector_match_calls'] == 0
            assert stage['summary'] is None
        else:
            assert stage['negative_control'] == pin(HERE/'probe_selftest_red_v2/PROBE_STAGE_FREEZE.json')
            result = read(run/'native/selftest_result.json')
            assert result == stage['summary']
            assert result['passed'] == result['cross_template_representative_fixture'] == 1
            assert result['scalar_native_cells'] == 256
            assert result['dataset_image_reads'] == result['full_class_search_replays'] == 0
        results.append(pin(run/'PROBE_STAGE_FREEZE.json'))
    assert builds[0]['project_sources'] == builds[1]['project_sources']
    assert builds[0]['compiler_tools_and_link_libraries'] == builds[1]['compiler_tools_and_link_libraries']
    result = dict(passed=True, independent_of_probe_runner=True, checker=pin(__file__),
                  native_processes_started=0, dataset_image_bytes_opened=0,
                  distinct_build_closure_pins_checked=len(checked), synthetic_stages=results,
                  limitation='Checks actual source/tool/runtime/output pins and synthetic receipts; no independent LM reconstruction')
    output = HERE/'ROOT_SYNTHETIC_RECEIPT_20261022.json'
    assert not output.exists()
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
