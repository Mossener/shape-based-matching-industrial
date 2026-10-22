"""Small scope/reservation/float boundary tests; no native or dataset access."""
import json
from pathlib import Path
import tempfile
import unittest

import probe_contract as c


class ContractTests(unittest.TestCase):
    def test_call_budget_deduplicates_multiple_gt_per_object_frame(self):
        identities = [(1, 7, 3, 0), (2, 1, 1, 0), (2, 1, 1, 4)]
        self.assertEqual(c.scope(identities), dict(identities=3, object_frames=2, image_frames=2, full_class_search_replays=4))

    def test_invalid_or_reserved_scope_is_rejected(self):
        for identities in [[(25, 1, 1, 0)], [(1, 11, 1, 0)], [(1, 7, 3, 0), (1, 7, 3, 0)]]:
            with self.assertRaises(ValueError):
                c.scope(identities)

    def test_strict_coarse_threshold_and_inclusive_fine_threshold(self):
        self.assertEqual(c.score(34, 10), 85.)
        self.assertEqual(c.thresholds(34, 10), (False, True))
        self.assertEqual(c.thresholds(35, 10), (True, True))
        self.assertEqual(c.thresholds(33, 10), (False, False))

    def test_reservation_is_one_shot_even_after_incomplete_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path = c.reserve(base, 'phase1', base/'failed', {'input': 'abc'})
            self.assertEqual(json.loads(path.read_text())['stage'], 'phase1')
            with self.assertRaises(FileExistsError):
                c.reserve(base, 'phase1', base/'new', {'input': 'abc'})
            with self.assertRaises(ValueError):
                c.reserve(base, '../escape', base/'new', {})

    def test_exact_input_pins_reject_byte_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'number.json'
            path.write_bytes(b'{"x":1}')
            pin = c.pin(path)
            c.check(pin)
            path.write_bytes(b'{"x":2}')
            with self.assertRaises(ValueError):
                c.check(pin)


if __name__ == '__main__':
    unittest.main()
