"""Fault checks for the root training progress acceptance; synthetic data only."""
import copy
import unittest
import accept_training_execution as checks


class Progress(unittest.TestCase):
    def fixture(self):
        rows = []
        for pose in range(49):
            for phase, level, arm, complete, pools, layers, collectors, samplers in checks.PHASES:
                rows.append(dict(phase=phase, pose_id=pose, level=level, arm=arm,
                    completed_poses=pose+complete, written_pools=2*pose+pools,
                    written_layer_rows=4*pose+layers, written_attempt_rows=2*pose,
                    rgb_decodes=pose//48+1, mask_decodes=pose//48+1,
                    collector_calls_started=2*pose+collectors,
                    sampler_calls_started=4*pose+samplers, incomplete=False,
                    reserved_logical_bytes=len(rows), reserved_physical_bytes=len(rows)))
        return rows, dict(logical_payload_bytes=1000, physical_bytes_before_summary=1000)

    def test_cross_image_boundary_and_all_phases(self):
        rows, summary = self.fixture()
        self.assertEqual(checks.verify_progress(iter(rows), summary, 49)['rows'], 490)

    def test_missing_extra_phase_call_decode_and_types_rejected(self):
        rows, summary = self.fixture()
        variants = [rows[:-1], rows + [rows[-1]]]
        for index, field, value in [(1, 'phase', 'sampler_call'),
                (4, 'sampler_calls_started', 1), (480, 'rgb_decodes', 1),
                (10, 'written_attempt_rows', 0), (0, 'pose_id', False),
                (12, 'reserved_physical_bytes', 1), (4, 'incomplete', True)]:
            changed = copy.deepcopy(rows)
            changed[index][field] = value
            variants.append(changed)
        for variant in variants:
            with self.subTest(row_count=len(variant)):
                with self.assertRaises(ValueError):
                    checks.verify_progress(iter(variant), summary, 49)


if __name__ == '__main__':
    unittest.main(verbosity=2)
