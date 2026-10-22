"""Source-only readiness checks. Never compile, run native or open images."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import input_contract as c


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();c.need(out.is_relative_to(c.HERE) and not out.exists(),'New static receipt inside experiment required')
    c.specification();origins=c.load(c.HERE/'ORIGINS.json')
    for q in origins['copied_helpers']:
        before=c.data(c.ROOT/q['source']);after=c.data(c.HERE/q['destination'])
        c.need(before==after and len(after)==q['bytes'] and hashlib.sha256(after).hexdigest()==q['sha256'],'Copied helper origin differs')
    sources=[]
    for path in sorted(c.HERE.glob('*.py')):
        ast.parse(c.data(path),filename=str(path));sources.append(c.pin(path))
    cpp=c.data(c.HERE/'observer.cpp').decode('utf-8')
    c.need(not re.search(r'#\s*include[^\n]*line2Dup',cpp),'Observer links matcher source')
    c.need(not re.search(r'\b(?:addTemplate|match|quantizedOrientations|hysteresisGradient|extractTemplate)\s*\(',cpp),'Forbidden native extractor/matcher call')
    for literal in ('"M0"','"M1"','"A0"','"A1"','"B1"','cv::INTER_NEAREST','cv::INTER_LINEAR','cv::BORDER_CONSTANT','++decodes','hashFile(path)==before','pc==20736','decodes==432'):
        c.need(literal in cpp,'Missing observer boundary: '+literal)
    c.need('angle==0' not in cpp and 'angle == 0' not in cpp,'Subset-only map saving')
    for name in ('build_observer.py','run_observer.py','run_selftest.py'):
        text=c.data(c.HERE/name).decode('utf-8');c.need('--cpu-slot-granted' in text and 'args.cpu_slot_granted' in text,'Native CPU gate absent')
    for q in ['observer.cpp','DESIGN.md','PROTOCOL.json','README.md','IMPLEMENTATION_PLAN.md','ORIGINS.json']:sources.append(c.pin(c.HERE/q))
    result=dict(passed=True,sources=sources,python_ast_checked=True,source_contract_only=True,
                image_bytes_opened=0,bank_bytes_opened=0,native_builds=0,native_runs=0,matcher_calls=0,
                limitation='Literal source contracts and Python syntax are not C++ compilation, pixel replay or dataset execution evidence')
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,sources=len(sources),native_builds=0,image_bytes_opened=0)))


if __name__=='__main__':main()
