"""Decompose preserved six-object development errors without image access."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile

from diagnose import analyze_frame, iou
from read_inputs import development_frames, parse_raw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OBJECTS = [1, 2, 5, 8, 12, 17]


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_numeric(directory, name):
    path = directory/name
    if path.exists():
        return path.read_bytes()
    return gzip.decompress(path.with_name(name+'.gz').read_bytes())


def sum_results(rows):
    result = defaultdict(int)
    associations = Counter()
    for row in rows:
        for key, value in row.items():
            if key == 'fp_associations':
                associations.update(value)
            else:
                result[key] += value
    result['fp_associations'] = dict(associations)
    require(result['fn'] == sum(result[k] for k in (
        'raw_capacity_deficit', 'selected_capacity_loss',
        'assignment_capacity_loss')), 'FN decomposition does not add up')
    require(result['fp'] == sum(associations.values()), 'FP categories do not add up')
    return dict(result)


def run(output):
    sources = [HERE/'run_diagnosis.py', HERE/'diagnose.py', HERE/'read_inputs.py']
    source_before = {p.name: digest(p) for p in sources}
    protocol_bytes = (HERE/'PROTOCOL.json').read_bytes()
    protocol = json.loads(protocol_bytes)
    require(protocol['objects'] == OBJECTS, 'Unexpected object set')
    pins = protocol['input_sha256']
    for pin in pins:
        require(digest(ROOT/pin['path']) == pin['sha256'],
                'Frozen numeric input changed: '+pin['path'])
    index = json.loads((ROOT/'datasets/tless_expanded/index.json').read_bytes())
    frames = development_frames(index)
    require(len(frames) == 400 and {s for s, _ in frames} ==
            {1, 4, 6, 7, 8, 10, 12, 13}, 'Development frame scope differs')
    summary = json.loads((ROOT/'artifacts/public_evaluation/baseline_summary_all_six.json').read_bytes())
    # Reuse the frozen, independently reviewed preservation auditor only for
    # bytes/tar/member integrity. Capacity analysis above is independent.
    spec = importlib.util.spec_from_file_location('frozen_numeric_preservation',
        ROOT/'artifacts/public_evaluation/audit_preservation.py')
    preservation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preservation)
    audits, per_object, all_rows, audited_files = [], [], [], {}
    with (output/'per_frame.csv').open('w', newline='', encoding='utf-8') as file:
        writer = None
        for obj in OBJECTS:
            directory = ROOT/f'artifacts/public_evaluation/expanded_obj{obj}_v11/development'
            audits.append(preservation.audit(directory/'preservation_manifest.json', ROOT))
            package_manifest = json.loads((directory/'preservation_manifest.json').read_bytes())
            for item in package_manifest['files']:
                audited_files[item['copy'].replace('\\', '/')] = item['copy_sha256']
            metrics = json.loads(read_numeric(directory, 'metrics.json'))
            expected = {(f['scene_id'], f['image_id']): f for f in metrics['frames']}
            require(set(expected) == set(frames), 'Metric development keys differ')
            selected = defaultdict(list)
            for row in csv.DictReader(io.StringIO(read_numeric(directory, 'selected_detections.csv').decode('utf-8'))):
                key = (int(row['scene']), int(row['image']))
                require(key in frames and row['class_id'] == f'tless_object_{obj}',
                        'Selected frame/class differs')
                require(int(row['rank']) == len(selected[key]), 'Selected rank differs')
                selected[key].append(dict(
                    box=tuple(float(row['bbox_'+v]) for v in ('x', 'y', 'w', 'h')),
                    label=row['allGT_label'], gt_id=int(row['allGT_id']),
                    template_id=int(row['template_id'])))
            raw, raw_rows = {}, 0
            with tarfile.open(directory/'raw_numeric.tar.gz', 'r:gz') as archive:
                for member in archive:
                    match = re.fullmatch(r's(\d+)_i(\d+)_fallback_raw\.csv\.gz', member.name)
                    if match is None:
                        continue
                    key = tuple(map(int, match.groups()))
                    require(key in frames and key not in raw, 'Raw frame differs/duplicates')
                    encoded = archive.extractfile(member).read()
                    raw[key] = parse_raw(gzip.decompress(encoded), key, obj)
                    require(len(raw[key]) == expected[key]['raw_count'], 'Raw frame count differs')
                    raw_rows += len(raw[key])
            require(set(raw) == set(frames), 'Missing raw development frame')
            object_rows, scenes = [], defaultdict(list)
            for key, frame in sorted(frames.items()):
                targets = [g['bbox_obj'] for g in frame['instances'] if g['obj_id'] == obj]
                other = [g['bbox_obj'] for g in frame['instances'] if g['obj_id'] != obj]
                gt_by_id = {g['gt_id']: g['bbox_obj'] for g in frame['instances']
                            if g['obj_id'] == obj}
                tp_ids = set()
                for d in selected[key]:
                    if d['label'] == 'TP':
                        require(d['gt_id'] in gt_by_id and d['gt_id'] not in tp_ids
                                and iou(d['box'], gt_by_id[d['gt_id']]) >= .5,
                                'Frozen TP GT assignment is not valid one-to-one')
                        tp_ids.add(d['gt_id'])
                    else:
                        require(d['gt_id'] == -1, 'FP has a target GT assignment')
                require(not (Counter((d['template_id'], d['box']) for d in selected[key]) -
                             Counter((d['template_id'], d['box']) for d in raw[key])),
                        'Selected template/box identity absent from raw')
                data = analyze_frame([d['box'] for d in raw[key]], selected[key], targets, other)
                counts = expected[key]['allGT']
                tp = data['actual_tp']
                require((tp, len(selected[key])-tp, len(targets)-tp, len(targets)) ==
                        tuple(counts[k] for k in ('tp', 'fp', 'fn', 'gt')),
                        'Counts disagree with independently audited baseline')
                data.update(gt=len(targets), fp=len(selected[key])-tp,
                            fn=len(targets)-tp, raw=len(raw[key]),
                            selected=len(selected[key]), negative_frames=int(not targets))
                object_rows.append(data)
                scenes[key[0]].append(data)
                flat = dict(object_id=obj, scene=key[0], image=key[1], **data)
                categories = flat.pop('fp_associations')
                flat.update({'fp_'+k: v for k, v in categories.items()})
                if writer is None:
                    writer = csv.DictWriter(file, fieldnames=list(flat))
                    writer.writeheader()
                writer.writerow(flat)
            totals = sum_results(object_rows)
            baseline = next(r for r in summary['per_object'] if r['object_id'] == obj)
            require(all(totals['actual_tp' if k == 'tp' else k] == baseline['allGT'][k]
                        for k in ('tp', 'fp', 'fn', 'gt')), 'Object totals differ')
            per_object.append(dict(object_id=obj, frames=400, totals=totals,
                per_scene=[dict(scene_id=s, totals=sum_results(rows))
                           for s, rows in sorted(scenes.items())]))
            all_rows.extend(object_rows)
            print(json.dumps(dict(object_id=obj, raw_rows=raw_rows, totals=totals)), flush=True)
    totals = sum_results(all_rows)
    require(totals['actual_tp'] == 215 and totals['fp'] == 42098 and
            totals['fn'] == 185 and totals['raw'] == 457376,
            'Six-object frozen totals differ')
    for pin in pins:
        require(digest(ROOT/pin['path']) == pin['sha256'], 'Numeric inputs changed during run')
    for path, expected_hash in audited_files.items():
        require(digest(ROOT/path) == expected_hash, 'Audited numeric bytes changed during run')
    require(source_before == {p.name: digest(p) for p in sources}, 'Analysis sources changed during run')
    require((HERE/'PROTOCOL.json').read_bytes() == protocol_bytes, 'Protocol changed during run')
    result = dict(protocol_sha256=hashlib.sha256(protocol_bytes).hexdigest(),
        objects=OBJECTS, unique_development_frames=400, object_frame_pairs=2400,
        image_files_opened=0, heldout_frames_processed=0, matcher_calls=0,
        all_input_pins_unchanged=True, interpretation=protocol['interpretation'],
        totals=totals, per_object=per_object, preservation_audits=audits,
        input_sha256=pins, source_sha256=source_before,
        audited_numeric_sha256=audited_files,
        per_frame_sha256=digest(output/'per_frame.csv'))
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    (output/'PROTOCOL.json').write_bytes(protocol_bytes)
    (output/'source').mkdir()
    for path in sources:
        (output/'source'/path.name).write_bytes(path.read_bytes())
    print(json.dumps(dict(passed=True, totals=totals)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Wait for the exclusive numeric audit CPU slot')
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        run(args.output)
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(
            incomplete=True, reason=str(error), missing_frames_are_not_negatives=True), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
