"""Ideal translation-only bounding-box coverage; no image processing."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from read_inputs import development_frames


def ideal_iou(a, b):
    if min(*a, *b) <= 0:
        return 0.0
    intersection = min(a[0], b[0])*min(a[1], b[1])
    return intersection/(a[0]*a[1]+b[0]*b[1]-intersection)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    if not args.cpu_slot_granted:
        raise ValueError('Wait for the exclusive numeric CPU slot')
    args.output.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    protocol_path = here/'SIZE_PROTOCOL.json'
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    sources = [Path(__file__).resolve(), here/'read_inputs.py']
    source_before = {p.name: sha(p) for p in sources}
    for pin in protocol['input_sha256']:
        if sha(root/pin['path']) != pin['sha256']:
            raise ValueError('Frozen size input changed: '+pin['path'])
    frames = development_frames(json.loads((root/'datasets/tless_expanded/index.json').read_bytes()))
    if len(frames) != 400 or protocol['objects'] != [1, 2, 5, 8, 12, 17]:
        raise ValueError('Size analysis scope differs')
    results = []
    with (args.output/'per_gt.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(('object_id', 'scene', 'image', 'gt_id', 'gt_w', 'gt_h',
                         'best_ideal_iou', 'compatible_templates', 'best_template_id',
                         'best_training_image', 'best_angle', 'best_scale', 'best_w', 'best_h'))
        for obj in protocol['objects']:
            path = root/f'artifacts/public_evaluation/expanded_obj{obj}_v11/training/template_metadata.json.gz'
            # Every metadata file is independently pinned by SIZE_PROTOCOL.
            meta = json.loads(gzip.decompress(path.read_bytes()))['templates']
            if not meta or any(t['template_id'] != i or t['class_id'] != f'tless_object_{obj}'
                               for i, t in enumerate(meta)):
                raise ValueError('Unexpected size-template bank')
            count, impossible, bounds = 0, 0, []
            for key, frame in sorted(frames.items()):
                for gt in frame['instances']:
                    if gt['obj_id'] != obj:
                        continue
                    shape = gt['bbox_obj'][2:]
                    values = [ideal_iou(shape, t['warped_mask_bbox'][2:]) for t in meta]
                    best = max(range(len(values)), key=values.__getitem__)
                    compatible = sum(v >= .5 for v in values)
                    t = meta[best]
                    writer.writerow((obj, *key, gt['gt_id'], *shape, values[best],
                                     compatible, best, t['training_image_id'], t['angle'],
                                     t['scale'], *t['warped_mask_bbox'][2:]))
                    count += 1
                    impossible += compatible == 0
                    bounds.append(values[best])
            result = dict(object_id=obj, templates=len(meta), gt=count,
                          gt_without_geometrically_compatible_template=impossible,
                          gt_with_geometrically_compatible_template=count-impossible,
                          min_best_ideal_iou=min(bounds), max_best_ideal_iou=max(bounds))
            results.append(result)
            print(json.dumps(result), flush=True)
    if sum(r['gt'] for r in results) != 400:
        raise ValueError('Unexpected total target GT count')
    for pin in protocol['input_sha256']:
        if sha(root/pin['path']) != pin['sha256']:
            raise ValueError('Size inputs changed during run')
    if source_before != {p.name: sha(p) for p in sources} or protocol_path.read_bytes() != protocol_bytes:
        raise ValueError('Size source/protocol changed during run')
    (args.output/'results.json').write_text(json.dumps(dict(
        per_object=results, protocol_sha256=hashlib.sha256(protocol_bytes).hexdigest(),
        interpretation=protocol['interpretation'], image_files_opened=0,
        heldout_frames_processed=0, matcher_calls=0, source_sha256=source_before,
        input_sha256=protocol['input_sha256'], per_gt_sha256=sha(args.output/'per_gt.csv')),
        indent=2)+'\n', encoding='utf-8')
    (args.output/'SIZE_PROTOCOL.json').write_bytes(protocol_bytes)
    (args.output/'source').mkdir()
    for path in sources:
        (args.output/'source'/path.name).write_bytes(path.read_bytes())


if __name__ == '__main__':
    main()
