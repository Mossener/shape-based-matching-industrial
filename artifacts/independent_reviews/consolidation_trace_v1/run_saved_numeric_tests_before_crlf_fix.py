"""Save the independent readers/arithmetic synthetic tests, with zero native calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    output=HERE/'root_numeric_tests_20261022.json'
    if output.exists():
        raise ValueError('Fresh receipt required')
    specifications=[(HERE,'test_trace.py',4),(HERE,'test_replay_arithmetic.py',3),
                    (HERE.parent/'direct16_correctness_v2','test_benchmark_arithmetic.py',3)]
    sources=[Path(__file__),HERE/'audit_trace.py',HERE/'audit_replay_statistics.py',
             HERE.parent/'direct16_correctness_v2/audit_benchmark.py']
    sources += [directory/pattern for directory,pattern,_ in specifications]
    pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    runs=[]
    for directory,pattern,count in specifications:
        command=[sys.executable,'-m','unittest','discover','-s',str(directory),'-p',pattern,'-v']
        run=subprocess.run(command,cwd=ROOT,capture_output=True)
        stdout,stderr=run.stdout.decode(),run.stderr.decode()
        passed=(run.returncode==0 and ('Ran '+str(count)+' tests') in stderr and '\nOK\n' in stderr)
        runs.append(dict(command=command,expected_tests=count,exit_code=run.returncode,
                         stdout=stdout,stderr=stderr,passed=passed))
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in pins.items())
    result=dict(passed=unchanged and all(r['passed'] for r in runs),tests=10,source_unchanged=unchanged,
                source_sha256=pins,runs=runs,matcher_calls=0,image_decodes=0,synthetic_only=True)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_sha256','runs')}))
    if not result['passed']:
        raise ValueError('Synthetic numeric checks failed; receipt retained')


if __name__=='__main__':
    main()
