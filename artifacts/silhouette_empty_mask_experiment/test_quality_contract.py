"""Literal stage-budget/dependency oracles; no native calls or image reads."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile

HERE=Path(__file__).resolve().parent


def need(value,message):
    if not value:
        raise AssertionError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    need(not args.output.exists(),'Output must be fresh');args.output.mkdir()
    try:
        source=HERE/'quality_contract.py';need(source.exists(),'Quality stage contract implementation is missing')
        spec=importlib.util.spec_from_file_location('literal_quality_contract',source);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        need(c.CALLS=={'old_gate':96,'pilot':192,'development':9600,'timing':12288} and sum(c.CALLS.values())==22176,'Frozen call budget differs')
        need(c.PREVIOUS=={'old_gate':None,'pilot':'old_gate','development':'pilot','timing':'development'},'Stage order differs')
        need(c.stage_spec('old_gate')==dict(frames=8,arms=['rgb'],paths=['fallback','fused'],rounds=1,maximum_calls=96,soft_minutes=20),'Literal RGB old-padding gate differs')
        need(c.stage_spec('pilot')['frames']==8 and c.stage_spec('development')['frames']==400 and c.stage_spec('timing')['frames']==64 and c.stage_spec('timing')['rounds']==8,'Fixed frame/round scope differs')
        rejected=[]
        with tempfile.TemporaryDirectory(prefix='quality-contract-',dir=args.output) as directory:
            base=Path(directory)
            c.reserve(base,'old_gate','new-run')
            need(json.loads((base/'old_gate.json').read_text())['maximum_calls']==96,'Reservation budget differs')
            for name,call in [('repeat_old_gate',lambda:c.reserve(base,'old_gate','other-run')),('unknown_stage',lambda:c.stage_spec('heldout')),('pilot_missing_gate',lambda:c.reserve(base,'pilot','pilot-run'))]:
                try:
                    call()
                except ValueError:
                    rejected.append(name)
                else:
                    raise AssertionError('Accepted invalid stage '+name)
        result=dict(passed=True,maximum_calls=22176,rejecting_cases=rejected,dataset_image_reads=0,native_processes=0,matcher_calls=0)
        (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),dataset_image_reads=0,native_processes=0),indent=2)+'\n');raise


if __name__=='__main__':
    main()
