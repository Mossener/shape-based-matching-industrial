"""Run the retained tiny fixtures into a new directory without replacing RED evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


def pin(path):
    path=Path(path).resolve();data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();output=args.output.resolve()
    if not output.is_relative_to(HERE.parent) or output.exists():
        raise ValueError('fresh contained root_source_tests output required')
    driver=HERE/'review_validate_result.py'
    sources=[pin(driver),pin(__file__)]
    spec=importlib.util.spec_from_file_location('quality_join_tiny_fresh_driver',driver)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    output.mkdir(parents=True,exist_ok=False)
    module.HERE=output
    rc=module.main()
    if sources!=[pin(driver),pin(__file__)]:
        raise ValueError('retained fixture driver or fresh entry changed')
    with (output/'ENTRY_RECEIPT.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(dict(schema='root_quality_join_tiny_fresh_entry_v1',
            driver_and_entry=sources,review=pin(output/'receipt.json'),exit_code=rc,
            pure_validate_result_only=True),stream,indent=2);stream.write('\n')
    return rc


if __name__=='__main__':raise SystemExit(main())
