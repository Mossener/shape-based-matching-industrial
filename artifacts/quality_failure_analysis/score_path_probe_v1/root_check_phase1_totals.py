"""Independent root count/GT check of saved Phase1 numerics; no target imports."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE/'probe_phase1_v2'
PRIOR = HERE.parent/'v22_empty_mask_lost_gt/run_20261022_v1/per_gt.csv'


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        result = list(reader)
    assert all(None not in r and None not in r.values() for r in result)
    return result


def key(row):
    return tuple(int(row[f]) for f in ('object_id', 'scene', 'image'))


def main():
    inputs = [HERE/'PROBE_INPUTS_V1.json', RUN/'PROBE_STAGE_FREEZE.json',
              RUN/'native/stage_summary.json', RUN/'native/per_frame.csv',
              RUN/'native/gt_support.csv', PRIOR]
    before = [pin(p) for p in inputs]
    assert before[1]['sha256'] == 'f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed'
    plan, freeze, summary = [json.loads(p.read_bytes()) for p in inputs[:3]]
    assert freeze['completed'] is True and freeze['summary'] == summary
    expected = {(f['object_id'], f['scene'], f['image']) for f in plan['frames']}
    per = rows(inputs[3])
    assert len(per) == len(expected)*2 == 426
    assert len({(*key(r), r['arm']) for r in per}) == 426
    arms = ['rgb', 'binary_empty_mask']
    totals = {}
    for arm in arms:
        members = [r for r in per if r['arm'] == arm]
        assert {key(r) for r in members} == expected
        assert all(int(r['fine_oracle_rows']) == int(r['pre']) and int(r['exact_saved_raw']) == 1 for r in members)
        totals[arm] = {f: sum(int(r[f]) for r in members) for f in
                       ('pre', 'post', 'cross_template_groups', 'same_template_duplicate_occurrences')}
    assert sum(v['pre'] for v in totals.values()) == summary['pre_matches'] == 1312006
    assert totals['rgb']['post'] == 71178 and totals['binary_empty_mask']['post'] == 156638
    assert sum(v['post'] for v in totals.values()) == summary['post_matches'] == 227816
    assert sum(v['cross_template_groups'] for v in totals.values()) == summary['cross_template_collision_groups'] == 41581
    support = rows(inputs[4])
    prior = {(*key(r), int(r['gt_id'])): r for r in rows(PRIOR)}
    ids = {(*key(f), t['gt_id']) for f in plan['frames'] for t in f['targets']}
    assert len(ids) == 215 and len(support) == 430
    assert {(*key(r), int(r['gt_id']), r['arm']) for r in support} == {(*k, arm) for k in ids for arm in arms}
    support_totals = {}
    for arm in arms:
        members = [r for r in support if r['arm'] == arm]
        assert all(int(r['candidate_support_lost_at_consolidation']) == 0 for r in members)
        assert all((int(r['pre_hits']) > 0) == (int(r['post_hits']) > 0) for r in members)
        assert all(float(r['pre_best_iou']) >= float(r['post_best_iou']) for r in members)
        support_totals[arm] = dict(identities=len(members),
            has_pre_support=sum(int(r['pre_hits']) > 0 for r in members),
            has_post_support=sum(int(r['post_hits']) > 0 for r in members),
            best_iou_decreases=sum(float(r['pre_best_iou']) > float(r['post_best_iou']) for r in members),
            maximum_best_iou_decrease=max(float(r['pre_best_iou'])-float(r['post_best_iou']) for r in members))
    losses = Counter()
    lost = 0
    for row in support:
        if row['arm'] != 'binary_empty_mask':
            assert int(row['post_hits']) > 0
            continue
        old = prior[(*key(row), int(row['gt_id']))]
        assert int(row['post_hits']) == int(old['binary_raw_hit_count'])
        assert float(row['post_best_iou']) == float(old['binary_best_raw_iou'])
        assert old['status'] in ('retained', 'lost')
        if old['status'] == 'lost':
            lost += 1
            losses[old['binary_category']] += 1
    assert lost == 67
    assert losses == {'no_raw_candidate_ge_0_5': 57, 'all_overlapping_raw_suppressed_by_nms': 10}
    assert before == [pin(p) for p in inputs]
    result = dict(passed=True, checker=pin(__file__), input_pins=before,
                  matcher_calls=0, image_bytes_opened=0, per_arm_totals=totals,
                  gt_support_totals=support_totals, lost_rgb_identity_categories=dict(losses),
                  limitation='Independent count and existing GT-row consistency check; full archive and provenance audit is separate; no LM reconstruction')
    output = HERE/'ROOT_PHASE1_TOTALS_20261022.json'
    assert not output.exists()
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('input_pins', 'checker')}, indent=2))


if __name__ == '__main__':
    main()
