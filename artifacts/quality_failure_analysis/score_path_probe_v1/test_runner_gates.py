"""Failure/scope/output gates with synthetic numerics; no native or images."""
from pathlib import Path
import tempfile
import unittest

import runner_gates as g
from probe_contract import pin


class RunnerGateTests(unittest.TestCase):
    def test_red_requires_the_deliberate_scalar_failure(self):
        failure = dict(reason='Independent scalar/native score mismatch', full_class_search_replays_started=0,
                       public_detector_match_calls=0, phase2_started=0, partial_results_are_not_negatives=1)
        self.assertTrue(g.validate_native('selftest', True, 1, None, failure)['expected_native_failure'])
        for exit_code, summary, changed in [(0, {'passed': 1}, failure), (1, None, dict(failure, reason='wrong compiler')),
                                            (1, None, dict(failure, full_class_search_replays_started=1))]:
            with self.assertRaises(ValueError):
                g.validate_native('selftest', True, exit_code, summary, changed)

    def test_green_requires_complete_independent_native_fixture(self):
        result = dict(passed=1, scalar_native_cells=256, cross_template_representative_fixture=1,
                      dataset_image_reads=0, full_class_search_replays=0, public_detector_match_calls=0)
        self.assertEqual(g.validate_native('selftest', False, 0, result, None)['actual_full_class_search_replays'], 0)
        for changed in [dict(result, scalar_native_cells=255), dict(result, dataset_image_reads=1)]:
            with self.assertRaises(ValueError):
                g.validate_native('selftest', False, 0, changed, None)

    def test_phase1_requires_exact_scope_and_scores_not_only_exit_zero(self):
        result = dict(passed=1, stage='phase1', full_class_search_replays=426, public_detector_match_calls=0,
                      decoded_operations=213, unique_image_files=175, rgb_tp_identities=215, pre_matches=300000,
                      post_matches=227816, independent_scalar_fine_score_rows=300000, all_saved_raw_exact=1,
                      all_fine_score_bits_exact=1, numeric_output_bytes=123, peak_rss_bytes=100000,
                      phase2_started=0, accuracy_improvement_claim=0)
        self.assertEqual(g.validate_native('phase1', False, 0, result, None)['actual_full_class_search_replays'], 426)
        for changed in [dict(result, full_class_search_replays=425), dict(result, independent_scalar_fine_score_rows=299999),
                        dict(result, all_saved_raw_exact=0), dict(result, post_matches=227815)]:
            with self.assertRaises(ValueError):
                g.validate_native('phase1', False, 0, changed, None)
        with self.assertRaises(ValueError):
            g.validate_native('phase1', True, 0, result, None)

    def test_complete_output_member_set_and_bytes_are_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory/'result.csv'
            artifact.write_bytes(b'1,2\n')
            pins = [pin(artifact)]
            self.assertTrue(g.verify_output(directory, pins))
            unexpected = directory/'unexpected.json'
            unexpected.write_bytes(b'{}')
            with self.assertRaises(ValueError):
                g.verify_output(directory, pins)
            unexpected.unlink()
            artifact.write_bytes(b'1,3\n')
            with self.assertRaises(ValueError):
                g.verify_output(directory, pins)


if __name__ == '__main__':
    unittest.main()
