"""Retain one targeted expected-RED calculation mutation using synthetic tests."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
MUTATIONS={
    'query_canvas':('side=canvas//(2**level)','side=720//(2**level)',
                    'test_literal_complete_union_matches_every_field','feature outside own-layer training canvas'),
    'missing_plus_one':('checked_u64(max(xs)+1)','checked_u64(max(xs))',
                        'test_last_bank_union_and_last_layer_equal_extent_use_literal_formula','16, 17'),
}


def pin(path):
    data=path.read_bytes()
    return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mutation',required=True,choices=sorted(MUTATIONS));parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(HERE) or output.exists():raise ValueError('Fresh mutation evidence inside geometry required')
    output.mkdir();snapshot=output/'source';snapshot.mkdir()
    sources=[HERE/n for n in ('independent_geometry_audit.py','test_independent_geometry.py',
                              'run_independent_geometry_audit.py','run_independent_mutation.py')]
    sources += [HERE.parent/'independent/strict_bank_reader.py',HERE.parent/'PROTOCOL.json',
                HERE.parent/'frozen_helpers/padding_plan.hpp',HERE.parent/'execution_guard.py']
    before=[pin(p) for p in sources]
    for p in sources:(snapshot/p.name).write_bytes(p.read_bytes())
    old,new,test,diagnostic=MUTATIONS[args.mutation]
    original=(HERE/'independent_geometry_audit.py').read_text(encoding='utf-8')
    if original.count(old)!=1:raise ValueError('Mutation target must occur exactly once')
    mutant=snapshot/'mutated_independent_geometry_audit.py'
    mutant.write_text(original.replace(old,new),encoding='utf-8',newline='\n')
    harness=output/'harness.py'
    harness.write_text('''import importlib.util
from pathlib import Path
import sys
import unittest
here=Path(sys.argv[1]);sys.path.insert(0,str(here))
import test_independent_geometry as tests
spec=importlib.util.spec_from_file_location('independent_numeric_mutant',sys.argv[2])
mutant=importlib.util.module_from_spec(spec);spec.loader.exec_module(mutant)
mutant.HERE=here;mutant.EXPERIMENT=here.parent
tests.independent=mutant
suite=unittest.TestSuite([tests.IndependentGeometryTests(sys.argv[3])])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
''',encoding='utf-8',newline='\n')
    command=[sys.executable,'-B',str(harness),str(HERE),str(mutant),test]
    run=subprocess.run(command,cwd=HERE,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    (output/'stdout.txt').write_text(run.stdout,encoding='utf-8',newline='\n')
    (output/'stderr.txt').write_text(run.stderr,encoding='utf-8',newline='\n')
    unchanged=before==[pin(p) for p in sources]
    expected=run.returncode==1 and 'Ran 1 test' in run.stderr and 'FAILED (' in run.stderr and diagnostic in run.stderr
    receipt=dict(schema='independent_geometry_expected_red_mutation_v1',mutation=args.mutation,
                 expected_red=expected,exit=run.returncode,source_pins=before,source_unchanged=unchanged,
                 mutant=pin(mutant),harness=pin(harness),command=command,synthetic_numeric_payloads_only=True,
                 native_executions=0,actual_guard_executions=0,real_bank_reads=0,image_reads=0,image_decodes=0,
                 quality_claim=False,performance_claim=False)
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(expected_red=expected,source_unchanged=unchanged)))
    return 0 if expected and unchanged else 2


if __name__=='__main__':raise SystemExit(main())
