"""Targeted source-only mutants proving geometry guards have detecting tests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
MUTATIONS={
    'query-canvas': ('planner',
        'row, _ = _layer_geometry(layer, source_size=tuple(canvas_size),',
        'row, _ = _layer_geometry(layer, source_size=(source_w, source_h),',
        'test_pose_training_canvas_differs_from_query_source_size'),
    'ignore-audited-bank-pin': ('run_geometry',
        "require(audit['output_pins_after'].get(relative)==_small(pin),",
        'require(True,',
        'test_bank_pin_must_match_even_when_audit_closure_before_after_agree'),
}


def pin(path):
    data=Path(path).read_bytes()
    return dict(path=str(Path(path).resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mutation',choices=tuple(MUTATIONS),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(HERE):raise ValueError('Fresh contained mutation evidence required')
    out.mkdir();name,old,new,test=MUTATIONS[args.mutation]
    origin=HERE/(name+'.py');original=origin.read_text(encoding='utf-8')
    if original.count(old)!=1:raise ValueError('Unique reviewed mutation seam differs')
    mutated=original.replace(old,new)
    (out/'mutated_source.py').write_text(mutated,encoding='utf-8',newline='\n')
    for filename in ('planner.py','run_geometry.py','test_geometry.py','test_run_geometry.py','run_tests.py'):
        (out/('original_'+filename)).write_bytes((HERE/filename).read_bytes())
    driver='''import importlib.util, pathlib, sys, unittest
sys.dont_write_bytecode=True
here=pathlib.Path(sys.argv[1]); name=sys.argv[2]; mutant=pathlib.Path(sys.argv[3])
sys.path.insert(0,str(here))
origin=here/(name+'.py')
spec=importlib.util.spec_from_file_location(name,origin)
module=importlib.util.module_from_spec(spec);sys.modules[name]=module
exec(compile(mutant.read_text(encoding='utf-8'),str(origin),'exec'),module.__dict__)
suite=unittest.defaultTestLoader.discover(str(here),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
'''
    (out/'driver.py').write_text(driver,encoding='utf-8',newline='\n')
    before=[pin(HERE/n) for n in ('planner.py','run_geometry.py','test_geometry.py','test_run_geometry.py')]
    command=[sys.executable,'-B',str(out/'driver.py'),str(HERE),name,str(out/'mutated_source.py')]
    run=subprocess.run(command,capture_output=True,timeout=60)
    (out/'stdout.txt').write_bytes(run.stdout);(out/'stderr.txt').write_bytes(run.stderr)
    unchanged=before==[pin(row['path']) for row in before]
    passed=run.returncode==1 and test.encode() in run.stderr and unchanged
    receipt=dict(schema='rgb_stratified_geometry_mutation_receipt_v1',passed=passed,mutation=args.mutation,
                 command=command,exit=run.returncode,expected_detecting_test=test,old_seam=old,new_seam=new,
                 source_pins=before,source_unchanged_during_execution=unchanged,
                 synthetic_payloads_only=True,bank_files_opened=0,image_reads=0,image_decodes=0,
                 native_executions=0,matcher_calls=0)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=passed,mutation=args.mutation,expected_test_detected=test.encode() in run.stderr)))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
