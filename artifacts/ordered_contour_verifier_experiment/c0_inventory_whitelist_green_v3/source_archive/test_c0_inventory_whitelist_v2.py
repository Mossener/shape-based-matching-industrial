"""Inventory selection regression: metadata only, no input-payload access."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import prepare_c0_payload_inventory_v2 as inventory

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'C0_INPUT_PLAN_V1.json').read_bytes())


class InventoryWhitelistTests(unittest.TestCase):
    def reject(self, change):
        value = deepcopy(PLAN)
        change(value)
        with self.assertRaises(ValueError):
            inventory.build_whitelist(value)

    def test_complete_inventory_retains_all_combinations(self):
        rows = inventory.build_whitelist(PLAN)
        self.assertEqual(len(rows), 6094)
        self.assertEqual(sum(row['declared'] is not None for row in rows), 6082)
        self.assertEqual(sum(row['declared']['bytes'] for row in rows if row['declared']), 333585840)
        self.assertEqual(sum(row['role'] == 'candidate_raw' for row in rows), 2400)
        self.assertEqual(sum(row['role'] == 'training_mask' for row in rows), 432)

    def test_missing_zero_candidate_combination_is_rejected(self):
        self.reject(lambda plan: plan['candidates'].remove(next(
            row for row in plan['candidates'] if row['candidate_count_declared'] == 0)))

    def test_foreign_arm_raw_pin_is_rejected(self):
        self.reject(lambda plan: plan['candidates'][0]['raw_declared'].update(
            path=plan['candidates'][0]['raw_declared']['path'].replace('rgb_control', 'rgb_pooled_features')))

    def test_heldout_object_is_rejected(self):
        self.reject(lambda plan: plan['training_declared'][0].update(object_id=25))

    def test_heldout_scene_is_rejected(self):
        self.reject(lambda plan: plan['development_declared'][0].update(scene_id=11))

    def test_duplicate_training_identity_is_rejected(self):
        self.reject(lambda plan: plan['training_declared'].__setitem__(1, deepcopy(plan['training_declared'][0])))

    def test_other_bank_arm_is_rejected(self):
        self.reject(lambda plan: plan['own_banks_declared'][0].update(arm='P'))

    def test_invalid_hash_is_rejected(self):
        self.reject(lambda plan: plan['candidates'][0]['raw_declared'].update(sha256='0'))

    def test_query_padding_from_old_stage_is_rejected(self):
        self.reject(lambda plan: plan.update(query_height=832, padding_ltrb=[64, 64, 64, 228]))


if __name__ == '__main__':
    unittest.main()
