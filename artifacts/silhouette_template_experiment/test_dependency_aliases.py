"""Real GCC -M alias regression: retain all ordered dependency occurrences."""
import argparse
import json
from pathlib import Path

import native_provenance as p

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    p.require(not args.output.exists(), 'Output must be fresh');args.output.mkdir()
    try:
        actual = p.parse_dependencies(b'core.o: plain.h ./plain.h next.h plain.h', 'core.o', HERE)
        p.require(actual == [HERE/'plain.h', HERE/'plain.h', HERE/'next.h', HERE/'plain.h'], 'Dependency alias order/multiplicity lost')
        fixture = HERE/'build_adapter_v1/core_before.d'
        paths = p.parse_dependencies(fixture.read_bytes(), 'core.o', fixture.parent)
        p.require(len(paths) == 402 and len(set(paths)) == 399, 'Actual first GCC fixture changed')
        result = dict(passed=True, ordered_multiplicity_retained=True, real_dependency_occurrences=402,
                      real_distinct_paths=399, fixture=p.file_pin(fixture), source=p.file_pin(HERE/'native_provenance.py'),
                      image_files_opened=0, compiler_calls=0, matcher_calls=0)
        (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n');print(json.dumps(result))
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error)), indent=2)+'\n');raise


if __name__ == '__main__':
    main()
