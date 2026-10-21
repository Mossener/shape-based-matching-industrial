"""Literal capacity/assignment oracles and persisted rejecting fixtures."""
import argparse
import copy
import csv
import gzip
import io
import json
from pathlib import Path

import audit_capacity as audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit.need(not args.output.exists(), 'Fixture output must be new')
    args.output.mkdir(parents=True)
    outcomes = []

    def row(identity, box, label='FP', gt_id=-1):
        return dict(box=tuple(box), identity=('tless_object_8', identity, audit.bits(90-identity*.01), tuple(box)), label=label, gt_id=gt_id)

    def reject(name, payload, call, message):
        directory = args.output/name
        directory.mkdir()
        (directory/'fixture.json').write_text(json.dumps(payload, indent=2, default=lambda b: {'float32_hex': b.hex()})+'\n')
        caught = None
        try:
            call()
        except ValueError as error:
            caught = str(error)
            audit.need(message in caught, 'Unexpected fixture rejection: '+name+' '+caught)
        audit.need(caught is not None, 'Invalid fixture accepted: '+name)
        result = dict(case=name, rejected=True, expected=message, observed=caught)
        (directory/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        outcomes.append(result)

    target = [dict(gt_id=10, bbox_obj=[0, 0, 10, 10]), dict(gt_id=11, bbox_obj=[5, 0, 10, 10])]
    first = row(0, [2, 0, 10, 10], 'TP', 10)
    second = row(1, [0, 0, 10, 10], 'FP', -1)
    raw = [first, second]
    assigned, ids = audit.analyze(raw, raw, target, [])
    audit.need((assigned['raw_capacity'], assigned['selected_capacity'], assigned['actual_tp'], assigned['assignment_capacity_loss']) == (2, 2, 1, 1) and ids == [10], 'Literal greedy-vs-capacity oracle')
    selection_loss, _ = audit.analyze(raw, [first], target, [])
    audit.need((selection_loss['raw_capacity'], selection_loss['selected_capacity'], selection_loss['selected_capacity_loss']) == (2, 1, 1), 'Literal selection-loss oracle')
    hall, _ = audit.analyze([first], [first], target, [])
    audit.need((hall['raw_capacity_deficit'], hall['gt_without_raw_overlap']) == (1, 0), 'Literal Hall-bottleneck oracle')

    # One TP consumes the target; five subsequent FPs cover every ordered class.
    target_one = [dict(gt_id=10, bbox_obj=[0, 0, 10, 10])]
    other = [dict(gt_id=20, bbox_obj=[100, 0, 10, 10])]
    category_rows = [row(0, [0, 0, 10, 10], 'TP', 10), row(1, [0, 0, 10, 10]),
                     row(2, [100, 0, 10, 10]), row(3, [6, 0, 10, 10]),
                     row(4, [106, 0, 10, 10]), row(5, [200, 0, 10, 10])]
    categories, _ = audit.analyze(category_rows, category_rows, target_one, other)
    audit.need(categories['fp_associations'] == dict.fromkeys(audit.CATEGORIES, 1) and categories['actual_tp'] == 1 and categories['fp'] == 5, 'Literal FP-category priority oracle')
    wrong_id = copy.deepcopy(raw)
    wrong_id[0]['gt_id'] = 999
    reject('wrong_tp_gt_id', wrong_id, lambda: audit.analyze(raw, wrong_id, target, []), 'Independent GT labels/IDs differ')
    duplicated = copy.deepcopy(raw)
    duplicated[1].update(label='TP', gt_id=10)
    reject('duplicate_tp_assignment', duplicated, lambda: audit.analyze(raw, duplicated, target, []), 'Independent GT labels/IDs differ')
    foreign = [row(99, [2, 0, 10, 10], 'TP', 10)]
    reject('foreign_selected_score_template', foreign, lambda: audit.analyze(raw, foreign, target, []), 'Selected identity absent from raw')
    changed = copy.deepcopy(assigned)
    changed['fn'] += 1
    reject('changed_frame_fn', changed, lambda: audit.check(changed, assigned, 'Synthetic'), 'Synthetic numeric result differs')
    changed_category = copy.deepcopy(categories)
    changed_category['fp_associations']['target_ge_0_5'] -= 1
    changed_category['fp_associations']['other_ge_0_5'] += 1
    reject('redistributed_fp_categories', changed_category, lambda: audit.check(changed_category, categories, 'Synthetic'), 'Synthetic numeric result differs')
    for name, masks, count in [('outside_graph', [4], 2), ('negative_adjacency', [-1], 1), ('nonempty_zero_gt', [1], 0), ('target_budget', [], 21)]:
        reject(name, dict(adjacencies=masks, target_count=count), lambda masks=masks, count=count: audit.capacity(masks, count), 'DP ')

    metadata = [dict(warped_mask_bbox=[0, 0, 10, 10], tl_x=0, tl_y=0, training_image_id=0, angle=0, scale=1)]
    source_row = dict(zip(audit.RAW_HEADER, [1, 2, 'fallback', 'tless_object_8', 0, 90, 0, 0, 0, 1, 64, 64, 0, 0, 10, 10]))
    def encoded(row):
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=audit.RAW_HEADER, lineterminator='\n')
        writer.writeheader()
        writer.writerow(row)
        return gzip.compress(stream.getvalue().encode(), mtime=0)
    audit.need(len(audit.parse_raw(encoded(source_row), (1, 2), 8, metadata)) == 1, 'Literal metadata/source-origin raw oracle')
    origin = dict(source_row, bbox_x=1)
    reject('raw_origin', origin, lambda: audit.parse_raw(encoded(origin), (1, 2), 8, metadata), 'Raw metadata/source-origin box')
    pose = dict(source_row, angle=30)
    reject('raw_pose', pose, lambda: audit.parse_raw(encoded(pose), (1, 2), 8, metadata), 'Raw training/pose metadata')
    byte_flip = bytearray(encoded(source_row))
    byte_flip[-5] ^= 1
    byte_rejected = False
    try:
        audit.parse_raw(bytes(byte_flip), (1, 2), 8, metadata)
    except (OSError, EOFError):
        byte_rejected = True
    audit.need(byte_rejected, 'Corrupted gzip checksum accepted')
    (args.output/'corrupt_raw_gzip.bin').write_bytes(byte_flip)
    result = dict(passed=True, literal_core_oracles=5, dp_selftest=audit.selftest(),
                  rejecting_semantic_fixtures=len(outcomes), results=outcomes, corrupted_gzip_rejected=byte_rejected,
                  auditor_sha256=audit.digest(Path(audit.__file__).read_bytes()),
                  test_sha256=audit.digest(Path(__file__).read_bytes()), image_files_opened=0, matcher_calls=0)
    (args.output/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, rejecting_semantic_fixtures=len(outcomes), corrupted_gzip_rejected=byte_rejected)))


if __name__ == '__main__':
    main()
