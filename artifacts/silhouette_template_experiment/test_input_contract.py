"""Synthetic input-closure tests; no dataset image bytes are accessed."""
import argparse
import copy
import gzip
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def need(value, message):
    if not value:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'Output must be fresh')
    args.output.mkdir(parents=True)
    try:
        source = HERE/'prepare_input_closure.py'
        need(source.exists(), 'input closure implementation is missing')
        spec = importlib.util.spec_from_file_location('silhouette_input_closure', source)
        c = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(c)
        rejected = []
        for value in ['/absolute.png', '../escape.png', 'a/../escape.png', 'C:/escape.png', 'a\\..\\escape.png', '']:
            try:
                c.relative(value)
            except ValueError:
                rejected.append(value)
            else:
                raise AssertionError('unsafe input path accepted '+value)
        need(c.relative('train_primesense/000001/rgb/000000.png') == 'train_primesense/000001/rgb/000000.png', 'valid relative path changed')
        original = b'{"templates": [1,2,3]}\n'
        compressed = gzip.compress(original, mtime=0)
        need(c.unpack_copy('template_metadata.json.gz', compressed, c.digest(original)) == ('template_metadata.json', original), 'copied metadata original SHA not verified')
        need(c.unpack_copy('templates_tless_object_1.yml.gz', compressed, c.digest(compressed)) == ('templates_tless_object_1.yml.gz', compressed), 'bank gzip must remain byte-identical')
        for name, encoded, sha in [('template_metadata.json.gz', compressed, '0'*64), ('templates_tless_object_1.yml.gz', compressed, c.digest(original))]:
            try:
                c.unpack_copy(name, encoded, sha)
            except ValueError:
                rejected.append(name)
            else:
                raise AssertionError('wrong copied content accepted')
        index = dict(development_objects=[1, 2, 5, 8, 12, 17], strict_object_generalization=[25, 29], training=[])
        sources = []
        for obj in [1, 2, 5, 8, 12, 17]:
            for image in range(72):
                rgb = f'train_primesense/{obj:06d}/rgb/{image:06d}.png'
                mask = f'train_primesense/{obj:06d}/mask/{image:06d}_000000.png'
                index['training'].append(dict(target_obj_id=obj, image_id=image, rgb=rgb, instances=[dict(gt_id=0, obj_id=obj, mask=mask)]))
                sources.extend([dict(local_path=rgb, bytes=123, sha256='1'*64), dict(local_path=mask, bytes=456, sha256='2'*64)])
        # Reserved objects are metadata-only and must not enter the allowlist.
        index['training'].append(dict(target_obj_id=25, image_id=0, rgb='sealed/reserved.png', instances=[]))
        actual = c.training_records(index, dict(files=sources))
        need(len(actual) == 432 and actual[0] == dict(object_id=1, image_id=0,
             rgb='train_primesense/000001/rgb/000000.png', mask='train_primesense/000001/mask/000000_000000.png',
             rgb_sha256='1'*64, rgb_bytes=123, mask_sha256='2'*64, mask_bytes=456), 'literal training allowlist differs')
        need(all(r['object_id'] != 25 for r in actual), 'reserved object entered training allowlist')
        for name, x, manifest in [('missing_view', dict(index, training=index['training'][:-2]), dict(files=sources)),
                                  ('duplicate_view', dict(index, training=index['training']+[index['training'][0]]), dict(files=sources)),
                                  ('missing_source', index, dict(files=sources[1:]))]:
            try:
                c.training_records(x, manifest)
            except ValueError:
                rejected.append(name)
            else:
                raise AssertionError('bad training allowlist accepted '+name)
        result = dict(passed=True, unsafe_paths_rejected=6, training_records=432, image_allowlist_members=864,
                      rejecting_cases=rejected, image_files_opened=0, image_decodes=0, matcher_calls=0,
                      source_sha256=c.digest(source.read_bytes()))
        (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error), image_files_opened=0, matcher_calls=0), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
