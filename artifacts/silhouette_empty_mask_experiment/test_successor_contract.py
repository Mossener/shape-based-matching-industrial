"""Static literal successor gates; no dataset image access or native process.

These do not substitute for the native ownership/toy checks. They make the
inheritance contract independently executable before any implementation exists.
"""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def need(value, message):
    if not value:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    need(not args.output.exists(), 'Output must be fresh')
    args.output.mkdir()
    try:
        source = HERE/'prepare_input_closure.py'
        need(source.exists(), 'Successor input inheritance implementation is missing')
        spec = importlib.util.spec_from_file_location('empty_mask_inputs', source)
        c = importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        rejected = []
        for value in ('/x', '../x', 'a/../x', 'C:/x', 'a\\..\\x', '', 'a//b'):
            try:
                c.relative(value)
            except ValueError:
                rejected.append(value)
            else:
                raise AssertionError('Unsafe relative path accepted: '+value)
        need(c.relative('obj1/rgb_training/template_metadata.json') == 'obj1/rgb_training/template_metadata.json', 'Valid path changed')
        old = dict(version='silhouette_input_closure_v1', objects=[1,2,5,8,12,17],
                   training=[dict(object_id=o, image_id=i, rgb=f'train/{o}/rgb/{i}.png', mask=f'train/{o}/mask/{i}.png',
                                  rgb_sha256='1'*64, rgb_bytes=123, mask_sha256='2'*64, mask_bytes=456)
                             for o in [1,2,5,8,12,17] for i in range(72)],
                   development=[dict(scene_id=i//50, image_id=i%50, rgb=f'dev/{i}.png', rgb_sha256='3'*64,
                                     rgb_bytes=789, pilot=i%50==0, timing=i%50<8) for i in range(400)],
                   rgb_banks=[dict(object_id=o) for o in [1,2,5,8,12,17]])
        c.validate_parent_scope(old)
        for label, changed in [('reserved_object',dict(old,objects=[1,2,5,8,12,25])),
                               ('missing_training',dict(old,training=old['training'][:-1])),
                               ('duplicate_development',dict(old,development=old['development'][:-1]+[old['development'][0]])),
                               ('wrong_version',dict(old,version='unexpected'))]:
            try:
                c.validate_parent_scope(changed)
            except ValueError:
                rejected.append(label)
            else:
                raise AssertionError('Changed parent scope accepted: '+label)
        need(c.rebase_private('frozen_inputs/obj1/rgb_training/a.json') == HERE/'frozen_inputs/obj1/rgb_training/a.json', 'Private numeric input origin changed')
        for name in ('../outside', 'private_v11/line2Dup.cpp', 'datasets/heldout.png'):
            try:
                c.rebase_private(name)
            except ValueError:
                rejected.append(name)
            else:
                raise AssertionError('Forbidden copy scope accepted '+name)
        result = dict(passed=True, scope='static inheritance literal oracles only', rejecting_cases=rejected,
                      training_records=432, development_records=400, image_files_opened=0, image_decodes=0,
                      compiler_calls=0, native_processes=0, matcher_calls=0)
        (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),image_files_opened=0,native_processes=0),indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
