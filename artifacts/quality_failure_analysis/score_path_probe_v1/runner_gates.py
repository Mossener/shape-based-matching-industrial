"""Synthetic-tested, standard-library completion/output gates."""
from pathlib import Path

from probe_contract import check, require


def validate_native(mode, red, exit_code, summary, failure):
    require(mode in ('selftest', 'phase1'), 'Unknown native stage')
    if red:
        require(mode == 'selftest' and exit_code != 0 and summary is None and failure is not None,
                'RED requires a failed synthetic run and no successful summary')
        require(failure.get('reason') == 'Independent scalar/native score mismatch' and
                failure.get('full_class_search_replays_started') == 0 and
                failure.get('public_detector_match_calls') == 0 and failure.get('phase2_started') == 0 and
                failure.get('partial_results_are_not_negatives') == 1, 'RED failed for an unintended reason')
        return dict(expected_native_failure=True, actual_full_class_search_replays=0)
    require(exit_code == 0 and summary is not None and failure is None and summary.get('passed') == 1,
            'Native stage did not complete successfully')
    require(summary.get('public_detector_match_calls') == 0, 'Public match calls are outside this diagnostic')
    if mode == 'selftest':
        require(summary.get('scalar_native_cells') == 256 and summary.get('cross_template_representative_fixture') == 1 and
                summary.get('dataset_image_reads') == 0 and summary.get('full_class_search_replays') == 0,
                'Independent native synthetic fixture is incomplete')
        return dict(expected_native_failure=False, actual_full_class_search_replays=0)
    require(summary.get('stage') == 'phase1' and summary.get('full_class_search_replays') == 426 and
            summary.get('decoded_operations') == 213 and summary.get('unique_image_files') == 175 and
            summary.get('rgb_tp_identities') == 215, 'Fixed Phase1 native scope is incomplete')
    require(summary.get('pre_matches', -1) >= summary.get('post_matches', 0) and
            summary.get('post_matches') == 227816 and
            summary.get('independent_scalar_fine_score_rows') == summary.get('pre_matches') and
            summary.get('all_saved_raw_exact') == 1 and summary.get('all_fine_score_bits_exact') == 1,
            'Exact saved-raw/scalar-score gate is incomplete')
    require(0 <= summary.get('numeric_output_bytes', -1) <= 1073741824 and
            0 < summary.get('peak_rss_bytes', -1) <= 1610612736 and
            summary.get('phase2_started') == 0 and summary.get('accuracy_improvement_claim') == 0,
            'Phase1 resource or claim scope differs')
    return dict(expected_native_failure=False, actual_full_class_search_replays=426)


def verify_output(directory, pins):
    directory = Path(directory).resolve(strict=True)
    declared = [Path(value['path']).resolve() for value in pins]
    require(all(path.is_relative_to(directory) for path in declared) and len(declared) == len(set(declared)),
            'Output manifest contains duplicate/outside members')
    actual = {path.resolve() for path in directory.rglob('*') if path.is_file()}
    require(actual == set(declared), 'Complete output member set changed')
    for value in pins:
        check(value)
    return True
