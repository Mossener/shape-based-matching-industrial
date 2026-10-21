"""Local literal dependency/PE-import/file-change oracles; no native process."""
import argparse
import json
from pathlib import Path
import tempfile

import native_provenance as p

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def need(value, message):
    if not value:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'Output must be fresh')
    args.output.mkdir()
    rejected = []
    try:
        def reject(name, call, fragment):
            try:
                call()
            except ValueError as error:
                need(fragment in str(error), 'Wrong rejection '+name+': '+str(error));rejected.append(name)
            else:
                raise AssertionError('Accepted invalid '+name)
        with tempfile.TemporaryDirectory(prefix='silhouette-native-fixture-', dir=HERE) as directory:
            cwd = Path(directory)
            paths = p.parse_dependencies(b'core.o: plain.h a\\ b.h \\\n dollar$$.h escaped\\#hash.h\n', 'core.o', cwd)
            need(paths == [cwd/'plain.h', cwd/'a b.h', cwd/'dollar$.h', cwd/'escaped#hash.h'], 'Literal Make escaping differs')
            reject('wrong_target', lambda: p.parse_dependencies(b'other.o: a.h', 'core.o', cwd), 'target')
            reject('two_rules', lambda: p.parse_dependencies(b'core.o: a.h\nother.o: b.h', 'core.o', cwd), 'rules')
            need(p.parse_dependencies(b'core.o: a.h ./a.h', 'core.o', cwd) == [cwd/'a.h', cwd/'a.h'], 'Real dependency aliases must retain multiplicity')
            reject('unescaped_dollar', lambda: p.parse_dependencies(b'core.o: $VAR.h', 'core.o', cwd), 'dollar')
            reject('comment', lambda: p.parse_dependencies(b'core.o: a.h #hidden.h', 'core.o', cwd), 'comment')
            reject('null', lambda: p.parse_dependencies(b'core.o: a.h\0', 'core.o', cwd), 'data')
            # Missing forbidden path distinguishes pre-open scope validation
            # from a later FileNotFoundError, without opening any dataset path.
            reject('scope_before_open', lambda: p.dependency_pins(b'core.o: ../../datasets/never_open_heldout.png', 'core.o', cwd, ROOT, []), 'scope')
            source = cwd/'source.h';source.write_bytes(b'original bytes\n')
            pin = p.file_pin(source);p.check_pin(pin)
            source.write_bytes(b'changed bytes\n')
            reject('changed_file', lambda: p.check_pin(pin), 'changed')
            allowed = p.dependency_pins(b'core.o: source.h', 'core.o', cwd, ROOT, [source])
            need(len(allowed) == 1 and allowed[0]['path'] == str(source), 'Allowed real file omitted')
        names = p.imports('PE fixture\n\tDLL Name: KERNEL32.dll\n\tDLL Name: libgomp-1.dll\n')
        need(names == ['KERNEL32.dll', 'libgomp-1.dll'], 'Literal PE import names differ')
        reject('duplicate_import', lambda: p.imports('DLL Name: one.dll\nDLL Name: ONE.DLL\n'), 'Duplicate')
        reject('unsafe_import', lambda: p.imports('DLL Name: ../escape.dll\n'), 'Unsafe')
        result = dict(passed=True, rejecting_cases=rejected, literal_make_and_pe_oracles=2,
                      file_change_rejected=True, dataset_image_reads=0, compiler_calls=0, matcher_calls=0,
                      source=p.file_pin(HERE/'native_provenance.py'), test=p.file_pin(Path(__file__)))
        (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n');print(json.dumps(result))
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error)), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
