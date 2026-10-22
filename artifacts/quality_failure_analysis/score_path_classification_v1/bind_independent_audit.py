"""Bind completed classifications to independent Phase2 numeric diagnostics."""
from collections import defaultdict
import json
from pathlib import Path

from classify import HERE, ROOT, V2, check, flag, need, pin, rows

AUDIT = ROOT/'artifacts/independent_reviews/score_path_probe_v2/run_numeric_audit_20261022_v2/result.json'
AUDIT_SHA = '1710a1b3fe934ad73b8484b24527a99c2dddcdc6c20cca82aa2c3860ba724ea8'
OUTPUT = HERE/'audit_binding_20261022_v1.json'


def main():
    need(not OUTPUT.exists(), 'Fresh audit binding required')
    audit_pin = pin(AUDIT);need(audit_pin['sha256'] == AUDIT_SHA, 'Wrong independent audit receipt')
    audit = json.loads(AUDIT.read_bytes());check(audit['diagnostics'])
    result_path = HERE/'run_20261022_v2/result.json';result = json.loads(result_path.read_bytes())
    need(audit['passed'] is True and audit['stage'] == 'score_path_probe_v2_numeric_audit' and
         audit['phase2_freeze'] == result['phase2_completion'] and
         audit['native_calls'] == 0 and audit['dataset_image_bytes_opened'] == 0,
         'Independent audit does not bind this exact completed Phase2 input')
    for value in result['input_pins']+result['source_pins']+result['output_pins']:
        check(value)
    classified = {int(row['job_id']): row for row in rows(HERE/'run_20261022_v2/per_gt_arm.csv')}
    diagnostics = {int(row['job']): row for row in rows(Path(audit['diagnostics']['path']))}
    need(set(classified) == set(diagnostics) == set(range(430)), 'Independent/classified job membership differs')
    links = defaultdict(list)
    for row in rows(V2/'probe_phase2_v1/native/parent_links.csv.gz'):
        links[int(row['job'])].append(row)
    checked_fields = 0
    for job, actual in classified.items():
        independent = diagnostics[job]
        for field in ('object_id', 'scene', 'image', 'arm', 'template_id', 'gt_id'):
            need(actual[field] == independent[field], 'Independent identity differs: '+field);checked_fields += 1
        for field, other in [('physical_on_grid', 'on_grid'), ('physical_in_domain', 'physical_domain'),
                             ('physical_score', 'physical_score'),
                             ('max_neighbor_score_any_parent', 'max_neighbor_fine_score'),
                             ('reachable_parents', 'reachable_parents'),
                             ('coarse_admitted_parents', 'coarse_admitted_parents'),
                             ('traced_occurrence_keys', 'traced_unique_occurrences')]:
            need(float(actual[field]) == float(independent[other]), 'Independent count/score differs: '+field);checked_fields += 1
        for field, other in [('post_support', 'representative_iou_hits'),
                             ('selected_support', 'kept_representative_iou_hits'),
                             ('assigned_target', 'selected_target_tp_hits')]:
            need((actual[field] == 'True') == (int(independent[other]) > 0),
                 'Independent support flag differs: '+field);checked_fields += 1
        emitted = {(row['coarse_row'], row['coarse_col']) for row in links[job] if flag(row, 'predicts_emission')}
        neighbors = {(row['coarse_row'], row['coarse_col']) for row in links[job]
                     if flag(row, 'predicts_emission') and flag(row, 'point_is_winner')}
        need(len(emitted) == int(independent['emitting_parents']) and
             len(neighbors) == int(independent['neighbor_winning_parents']) and
             (int(actual['neighbor_emitted_points']) > 0) == bool(neighbors), 'Independent parent/point emission differs')
        checked_fields += 3
    complete_path = HERE/'complete_pre_20261022_v1/result.json';complete = json.loads(complete_path.read_bytes())
    for value in complete['output_pins']:
        check(value)
    for row in rows(HERE/'complete_pre_20261022_v1/paired_215.csv'):
        job = int(row['binary_job_id'])
        need(int(row['binary_complete_same_pose_pre_rows']) == int(diagnostics[job]['same_template_complete_pre_occurrences']),
             'Complete-pre same-pose total differs from independent audit');checked_fields += 1
    binding = dict(passed=True, independent_numeric_audit=audit_pin, diagnostics=audit['diagnostics'],
                   classification_result=pin(result_path), complete_pre_result=pin(complete_path),
                   source=pin(HERE/'bind_independent_audit.py'), matched_jobs=430, matched_binary_complete_pre_jobs=215,
                   field_checks=checked_fields, differences=0,
                   distinction='emitting_parents counts coarse parent identities, neighbor_emitted_points counts unique grid points; traced occurrences deduplicate identical coordinate/score winners.',
                   previous_reports_unchanged=True, dataset_image_bytes_opened=0, native_calls=0,
                   accuracy_improvement_claim=False, speed_claim=False)
    OUTPUT.write_text(json.dumps(binding, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, matched_jobs=430, field_checks=checked_fields, differences=0)))


if __name__ == '__main__':
    main()
