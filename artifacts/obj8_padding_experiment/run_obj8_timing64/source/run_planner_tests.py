"""Compile/run isolated planner GREEN and semantic mutation tests; no images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Evidence directory must be new')
    args.output.mkdir(parents=True)
    source = (HERE/'padding_plan.hpp').read_text()
    test = (HERE/'padding_plan_test.cpp').read_bytes()
    cases = [('green', source, 0)]
    mutations = [
        ('red_half_refinement_margin', 'const U margin=multiply(16,t[level]);', 'const U margin=multiply(8,t[level]);'),
        ('red_missing_feature_plus_one', 'height=std::max(U(row.height),add(U(row.max_y),1));', 'height=std::max(U(row.height),U(row.max_y));'),
        ('red_missing_alignment', 'result.height=align(required_height,alignment);', 'result.height=required_height;'),
        ('red_moved_origin', 'result.padding={{base[0],base[1],', 'result.padding={{base[0]+1,base[1],'),
        ('red_unchecked_sum', 'if(b>std::numeric_limits<U>::max()-a)throw std::overflow_error("Padding sum overflow");', '// Deliberately removed checked sum'),
        ('red_missing_pose_level', 'if(pose.second.size()!=t.size())throw std::invalid_argument("Incomplete loaded pose pyramid");', 'if(pose.second.empty())throw std::invalid_argument("Incomplete loaded pose pyramid");'),
        ('red_missing_memory_budget', ' || result.estimated_bytes>limits.dynamic_bytes', '')]
    for name, before, after in mutations:
        if source.count(before) != 1:
            raise ValueError('Nonunique mutation: '+name)
        cases.append((name, source.replace(before, after), 1))
    env = dict(os.environ)
    env['PATH'] = str(args.compiler.parent)+';'+env.get('PATH', '')
    results = []
    for name, header, expected in cases:
        folder = args.output/name
        folder.mkdir()
        (folder/'padding_plan.hpp').write_text(header)
        (folder/'padding_plan_test.cpp').write_bytes(test)
        exe = folder/'planner_test.exe'
        argv = [str(args.compiler), '-std=c++14', '-O2', '-Wall', '-Wextra', '-Werror', str(folder/'padding_plan_test.cpp'), '-o', str(exe)]
        compiled = subprocess.run(argv, env=env, capture_output=True)
        (folder/'compiler_stdout.txt').write_bytes(compiled.stdout)
        (folder/'compiler_stderr.txt').write_bytes(compiled.stderr)
        if compiled.returncode:
            raise RuntimeError('All planner cases must compile: '+name+'\n'+compiled.stderr.decode(errors='replace'))
        result = subprocess.run([str(exe.resolve())], env=env, capture_output=True)
        (folder/'stdout.txt').write_bytes(result.stdout)
        (folder/'stderr.txt').write_bytes(result.stderr)
        if (result.returncode == 0) != (expected == 0):
            raise RuntimeError('Unexpected semantic result: '+name)
        results.append(dict(name=name, compile_exit=compiled.returncode, test_exit=result.returncode, expected_pass=int(expected == 0), header_sha256=sha(folder/'padding_plan.hpp'), test_sha256=sha(folder/'padding_plan_test.cpp'), executable_sha256=sha(exe), argv=argv))
    if (HERE/'padding_plan.hpp').read_text() != source or (HERE/'padding_plan_test.cpp').read_bytes() != test:
        raise ValueError('Planner sources changed during test run')
    summary = dict(passed=1, script_sha256=sha(Path(__file__)), compiler=str(args.compiler), cases=results, all_cases_compiled=1, semantic_green=1, semantic_mutation_red=len(mutations), original_stub_red_evidence='build/planner_red_final/result.json', source_unchanged=1, images_read=0, matcher_calls=0)
    (args.output/'validation.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
