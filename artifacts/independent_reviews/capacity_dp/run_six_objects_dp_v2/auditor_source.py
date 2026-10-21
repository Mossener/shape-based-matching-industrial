"""Independent development-capacity audit with GT-bitmask dynamic programming.

No import from quality_failure_analysis or the public evaluator. No image I/O.
The DP processes candidate adjacency masks, never augmenting paths or Kuhn's
algorithm. Published selected rows are checked against raw identities and
independently reassigned to GT before capacity/error totals are compared.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OBJECTS = [1, 2, 5, 8, 12, 17]
CATEGORIES = ['target_ge_0_5', 'other_ge_0_5', 'target_ge_0_1', 'other_ge_0_1', 'no_overlap_ge_0_1']
RAW_HEADER = 'scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')
SEEN_FILES = {}


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    path = Path(path)
    data = path.read_bytes()
    SEEN_FILES[path.relative_to(ROOT).as_posix()] = dict(sha256=digest(data), bytes=len(data))
    return data


def load(path):
    return json.loads(read(path).decode('utf-8-sig'))


def floats(row):
    box = tuple(float(row['bbox_'+axis]) for axis in ('x', 'y', 'w', 'h'))
    need(all(math.isfinite(v) for v in box) and min(box[2:]) > 0, 'Invalid candidate box')
    return box


def bits(value):
    return struct.pack('<f', float(value))


def overlap(a, b):
    if min(a[2], a[3], b[2], b[3]) <= 0:
        return 0.0
    intersection = max(0., min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) * max(0., min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    return intersection/(a[2]*a[3]+b[2]*b[3]-intersection)


def capacity(adjacencies, target_count):
    """Reachable subsets after each candidate; at most one new GT per row."""
    need(isinstance(target_count, int) and 0 <= target_count <= 20, 'DP target budget')
    full = (1 << target_count)-1
    masks = Counter()
    union = 0
    for adjacency in adjacencies:
        need(isinstance(adjacency, int) and 0 <= adjacency <= full, 'DP adjacency outside target set')
        if adjacency:
            masks[adjacency] += 1
            union |= adjacency
    states = {0}
    for adjacency, count in masks.items():
        for _ in range(min(count, target_count)):
            following = set(states)
            for occupied in states:
                available = adjacency & ~occupied
                while available:
                    bit = available & -available
                    following.add(occupied | bit)
                    available -= bit
            states = following
    return max(mask.bit_count() for mask in states), target_count-union.bit_count()


def graph(boxes, gt):
    return [sum(1 << i for i, g in enumerate(gt) if overlap(box, g['bbox_obj']) >= .5) for box in boxes]


def reassign(selected, targets):
    used = set()
    assigned = []
    for row in selected:
        options = [(-overlap(row['box'], g['bbox_obj']), g['gt_id']) for g in targets
                   if g['gt_id'] not in used and overlap(row['box'], g['bbox_obj']) >= .5]
        if options:
            _, identity = min(options)
            used.add(identity)
            assigned.append(('TP', identity))
        else:
            assigned.append(('FP', -1))
    return assigned


def analyze(raw, selected, targets, other):
    need(not (Counter(d['identity'] for d in selected)-Counter(d['identity'] for d in raw)), 'Selected identity absent from raw')
    assigned = reassign(selected, targets)
    need(assigned == [(d['label'], d['gt_id']) for d in selected], 'Independent GT labels/IDs differ')
    raw_cap, unreachable = capacity(graph([d['box'] for d in raw], targets), len(targets))
    selected_cap, _ = capacity(graph([d['box'] for d in selected], targets), len(targets))
    actual = sum(label == 'TP' for label, _ in assigned)
    need(actual <= selected_cap <= raw_cap <= len(targets), 'Impossible capacities')
    associations = dict.fromkeys(CATEGORIES, 0)
    for d, (label, _) in zip(selected, assigned):
        if label == 'TP':
            continue
        target_best = max((overlap(d['box'], g['bbox_obj']) for g in targets), default=0.)
        other_best = max((overlap(d['box'], g['bbox_obj']) for g in other), default=0.)
        values = [target_best >= .5, other_best >= .5, target_best >= .1, other_best >= .1, True]
        associations[CATEGORIES[next(i for i, passed in enumerate(values) if passed)]] += 1
    result = dict(raw_capacity=raw_cap, selected_capacity=selected_cap, actual_tp=actual,
                  raw_capacity_deficit=len(targets)-raw_cap, selected_capacity_loss=raw_cap-selected_cap,
                  assignment_capacity_loss=selected_cap-actual, gt_without_raw_overlap=unreachable,
                  gt=len(targets), fp=len(selected)-actual, fn=len(targets)-actual,
                  raw=len(raw), selected=len(selected), negative_frames=int(not targets),
                  fp_associations=associations)
    return result, [identity for label, identity in assigned if label == 'TP']


def add(destination, values):
    for name, value in values.items():
        if isinstance(value, dict):
            destination.setdefault(name, dict.fromkeys(CATEGORIES, 0))
            add(destination[name], value)
        else:
            destination[name] = destination.get(name, 0)+value


def check(actual, expected, where):
    need(actual == expected, where+' numeric result differs')
    need(actual['fn'] == actual['raw_capacity_deficit']+actual['selected_capacity_loss']+actual['assignment_capacity_loss'], where+' FN decomposition')
    need(actual['fp'] == sum(actual['fp_associations'].values()), where+' FP decomposition')


def parse_raw(encoded, key, obj, metadata):
    reader = csv.DictReader(io.StringIO(gzip.decompress(encoded).decode()))
    need(reader.fieldnames == RAW_HEADER, 'Raw schema')
    rows = []
    for row in reader:
        need((int(row['scene']), int(row['image']), row['variant'], row['class_id'], int(row['rank'])) ==
             (*key, 'fallback', 'tless_object_'+str(obj), len(rows)), 'Raw identity/rank')
        score = float(row['score'])
        need(math.isfinite(score) and 85 <= score <= 100, 'Raw score')
        template_id = int(row['template_id'])
        meta = metadata[template_id]
        sx, sy, w, h = meta['warped_mask_bbox']
        box = floats(row)
        need(box == (int(row['match_x'])-64+sx-meta['tl_x'], int(row['match_y'])-64+sy-meta['tl_y'], w, h), 'Raw metadata/source-origin box')
        need(int(row['training_image']) == meta['training_image_id'] and bits(row['angle']) == bits(meta['angle']) and
             bits(row['scale']) == bits(meta['scale']), 'Raw training/pose metadata')
        rows.append(dict(box=box, identity=(row['class_id'], template_id, bits(score), box)))
    return rows


def checked_selected(row, full):
    """Bind lossy CSV projection to metrics JSON before comparing raw bits."""
    box = floats(row)
    score = float(full['score'])
    need(math.isfinite(score) and 85 <= score <= 100, 'Selected metrics score')
    need(row['score'] == format(score, '.6g'), 'Selected CSV/metrics score projection')
    need((int(row['rank']), row['class_id'], int(row['template_id']), box) ==
         (full['rank'], full['class_id'], full['template_id'], tuple(full['bbox_obj'])), 'Selected CSV/metrics identity')
    need((row['allGT_label'], int(row['allGT_id']), row['eligible_label'], int(row['eligibleGT_id'])) ==
         (full['allGT_label'], full['allGT_id'], full['eligible_label'], full['eligibleGT_id']), 'Selected CSV/metrics labels')
    need(row['allGT_label'] in ('TP', 'FP'), 'Selected allGT label')
    return dict(box=box, label=row['allGT_label'], gt_id=int(row['allGT_id']),
                identity=(row['class_id'], int(row['template_id']), bits(score), box))


def read_stage(directory, manifest, name):
    for relative in (name, name+'.gz'):
        path = directory/relative
        if path.exists():
            item = next(i for i in manifest['files'] if i['copy'].replace('\\', '/') == path.relative_to(ROOT).as_posix())
            data = read(path)
            need(digest(data) == item['copy_sha256'] and len(data) == item['bytes'], 'Copied stage byte/SHA mismatch')
            return gzip.decompress(data) if relative.endswith('.gz') else data
    raise ValueError('Missing published stage numeric file '+name)


def run(output):
    protocol_bytes = read(HERE/'PROTOCOL.json')
    protocol = json.loads(protocol_bytes)
    source_before = digest(read(Path(__file__).resolve()))
    for pin in protocol['input_sha256']:
        need(digest(read(ROOT/pin['path'])) == pin['sha256'], 'Frozen input pin '+pin['path'])
    root_run = ROOT/protocol['root_run']
    root_results = load(root_run/'results.json')
    need(root_results['protocol_sha256'] == protocol['diagnosis_protocol_sha256'], 'Root protocol binding')
    expected_frames = list(csv.DictReader(io.StringIO(read(root_run/'per_frame.csv').decode())))
    per = {(int(r['object_id']), int(r['scene']), int(r['image'])): r for r in expected_frames}
    need(len(expected_frames) == len(per) == 2400, 'Root per-frame coverage/duplicates')
    index = load(ROOT/'datasets/tless_expanded/index.json')
    development = {(f['scene_id'], f['image_id']): f for f in index['test'] if f['split'] == 'development'}
    need(len(development) == 400 and set(s for s, _ in development) == {1, 4, 6, 7, 8, 10, 12, 13}, 'Development scope')
    totals, objects, output_rows, tp_rows, archives = {}, [], [], [], []
    max_gt = 0
    for obj in OBJECTS:
        directory = ROOT/f'artifacts/public_evaluation/expanded_obj{obj}_v11/development'
        manifest = load(directory/'preservation_manifest.json')
        need(manifest['object_id'] == obj and manifest['stage'] == 'development' and manifest['raw_archives'] == 800, 'Published manifest scope')
        metadata = json.loads(gzip.decompress(read(directory.parent/'training/template_metadata.json.gz')))['templates']
        need(0 < len(metadata) <= 3456 and all(m['template_id'] == i and m['class_id'] == 'tless_object_'+str(obj) for i, m in enumerate(metadata)), 'Metadata bank identity')
        metrics = json.loads(read_stage(directory, manifest, 'metrics.json'))
        metric_frames = {(f['scene_id'], f['image_id']): f for f in metrics['frames']}
        need(len(metrics['frames']) == len(metric_frames) == 400 and set(metric_frames) == set(development), 'Baseline metric frame coverage')
        selected = defaultdict(list)
        for row in csv.DictReader(io.StringIO(read_stage(directory, manifest, 'selected_detections.csv').decode())):
            key = (int(row['scene']), int(row['image']))
            need(key in development and row['class_id'] == 'tless_object_'+str(obj) and int(row['rank']) == len(selected[key]), 'Selected frame/class/rank')
            need(len(selected[key]) < len(metric_frames[key]['detections']), 'Selected CSV/metrics rank coverage')
            selected[key].append(checked_selected(row, metric_frames[key]['detections'][len(selected[key])]))
        need(all(len(selected[key]) == len(metric_frames[key]['detections']) == metric_frames[key]['selected_count']
                 for key in development), 'Selected CSV/metrics complete coverage')
        expected_members = {r['name']: r for r in manifest['raw_archive_members']}
        need(len(expected_members) == len(manifest['raw_archive_members']) == 1600, 'Tar expected member count/duplicates')
        archive_path = directory/'raw_numeric.tar.gz'
        archive_pin = next(r for r in manifest['files'] if r['copy'].replace('\\', '/') == archive_path.relative_to(ROOT).as_posix())
        encoded_archive = read(archive_path)
        need(len(encoded_archive) == archive_pin['bytes'] and digest(encoded_archive) == archive_pin['copy_sha256'], 'Candidate tar SHA/bytes')
        raw, seen = {}, set()
        with tarfile.open(fileobj=io.BytesIO(encoded_archive), mode='r:gz') as archive:
            for member in archive:
                need(member.isfile() and PurePosixPath(member.name).name == member.name and member.name in expected_members and member.name not in seen, 'Unsafe/unexpected/duplicate tar member')
                seen.add(member.name)
                payload = archive.extractfile(member).read()
                pin = expected_members[member.name]
                need(len(payload) == member.size == pin['bytes'] and digest(payload) == pin['sha256'], 'Candidate member SHA/bytes')
                matched = re.fullmatch(r's(\d+)_i(\d+)_fallback_raw\.csv\.gz', member.name)
                if matched:
                    key = tuple(map(int, matched.groups()))
                    need(key in development and key not in raw, 'Raw scope/duplicate frame')
                    raw[key] = parse_raw(payload, key, obj, metadata)
        need(seen == set(expected_members) and set(raw) == set(development), 'Incomplete tar/frame set')
        archives.append(dict(object_id=obj, tar_sha256=digest(encoded_archive), members=len(seen), candidate_paths=400,
                             metadata_sha256=SEEN_FILES[(directory.parent/'training/template_metadata.json.gz').relative_to(ROOT).as_posix()]['sha256']))
        object_total, scenes = {}, defaultdict(dict)
        for key, frame in sorted(development.items()):
            targets = [g for g in frame['instances'] if g['obj_id'] == obj]
            other = [g for g in frame['instances'] if g['obj_id'] != obj]
            max_gt = max(max_gt, len(targets))
            data, identities = analyze(raw[key], selected[key], targets, other)
            expected = dict(per[(obj, *key)])
            for field in ('object_id', 'scene', 'image'):
                expected.pop(field)
            expected = {k: int(v) for k, v in expected.items()}
            expected['fp_associations'] = {c: expected.pop('fp_'+c) for c in CATEGORIES}
            check(data, expected, 'Frame '+str((obj, *key)))
            frame_metric = metric_frames[key]
            need(data['raw'] == frame_metric['raw_count'] and
                 tuple(data[k] for k in ('actual_tp', 'fp', 'fn', 'gt')) == tuple(frame_metric['allGT'][k] for k in ('tp', 'fp', 'fn', 'gt')), 'Independent baseline metric counts')
            add(object_total, data)
            add(scenes[key[0]], data)
            flat = dict(object_id=obj, scene=key[0], image=key[1], **data)
            flat.update({'fp_'+c: flat['fp_associations'][c] for c in CATEGORIES})
            flat.pop('fp_associations')
            output_rows.append(flat)
            tp_rows.extend(dict(object_id=obj, scene=key[0], image=key[1], gt_id=identity) for identity in identities)
        expected_object = next(o for o in root_results['per_object'] if o['object_id'] == obj)
        check(object_total, expected_object['totals'], 'Object '+str(obj))
        need(expected_object['frames'] == 400, 'Object frame total')
        for item in expected_object['per_scene']:
            check(scenes[item['scene_id']], item['totals'], 'Scene '+str((obj, item['scene_id'])))
        add(totals, object_total)
        objects.append(dict(object_id=obj, totals=object_total, per_scene=[dict(scene_id=s, totals=t) for s, t in sorted(scenes.items())]))
        print(json.dumps(dict(object_id=obj, status='numeric_match', raw=object_total['raw'], raw_capacity=object_total['raw_capacity'], selected_capacity=object_total['selected_capacity'])), flush=True)
    check(totals, root_results['totals'], 'Six objects')
    for name, value in list(SEEN_FILES.items()):
        need(digest((ROOT/name).read_bytes()) == value['sha256'], 'Input changed during independent audit: '+name)
    need(digest(Path(__file__).read_bytes()) == source_before, 'Independent auditor source changed')
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in [('per_frame.csv', output_rows), ('effective_tp_ids.csv', tp_rows)]:
        with (output/name).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output/'auditor_source.py').write_bytes(Path(__file__).read_bytes())
    (output/'PROTOCOL.json').write_bytes(protocol_bytes)
    result = dict(passed=True, algorithm='GT subset bitmask dynamic programming; no augmenting paths',
                  unique_development_frames=400, object_frame_pairs=2400, raw_candidates=totals['raw'],
                  target_gt_max_per_frame=max_gt, totals=totals, per_object=objects, archives=archives,
                  effective_tp_ids=len(tp_rows), image_files_opened=0, image_decodes=0,
                  selected_score_binding='CSV exact .6g projection of metrics JSON; metrics binary32 score identity is a multiset subset of full-precision raw',
                  heldout_frames_processed=0, matcher_calls=0, root_code_imported=False,
                  auditor_sha256=source_before, protocol_sha256=digest(protocol_bytes), input_sha256=SEEN_FILES,
                  per_frame_sha256=digest((output/'per_frame.csv').read_bytes()),
                  effective_tp_ids_sha256=digest((output/'effective_tp_ids.csv').read_bytes()),
                  limitation='Optimistic box assignment capacity; does not prove raw coexistence through NMS, physical contour identity, improved detector quality or industrial generalization.')
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, object_frame_pairs=2400, totals=totals)), flush=True)


def selftest():
    assertions = 0
    cases = [([], 0, (0, 0)), ([], 3, (0, 3)), ([3], 2, (1, 0)), ([3, 1], 2, (2, 0)),
             ([1, 1, 1], 3, (1, 2)), ([3, 3, 6, 8], 4, (4, 0)), ([0, 1], 2, (1, 1))]
    for graph_masks, count, expected in cases:
        need(capacity(graph_masks, count) == expected, 'Literal DP oracle')
        assertions += 1
    rejected = []
    for masks, count in [([4], 2), ([-1], 1), ([1], 0), ([], 21)]:
        try:
            capacity(masks, count)
        except ValueError as error:
            rejected.append(str(error))
        else:
            raise AssertionError('Invalid DP graph accepted')
    need(overlap([0, 0, 10, 10], [0, 0, 10, 10]) == 1 and
         overlap([0, 0, 10, 10], [20, 0, 10, 10]) == 0, 'Literal IoU oracle')
    return dict(passed=True, literal_dp_cases=assertions, invalid_dp_cases_rejected=len(rejected), rejected=rejected,
                image_files_opened=0, matcher_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    need(not args.output.exists(), 'Output must be new')
    if args.self_test:
        args.output.write_text(json.dumps(selftest(), indent=2)+'\n')
    else:
        need(args.cpu_slot_granted, 'Await numeric CPU slot')
        try:
            run(args.output)
        except Exception as error:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error), missing_frames_are_not_negatives=True), indent=2)+'\n')
            raise


if __name__ == '__main__':
    main()
