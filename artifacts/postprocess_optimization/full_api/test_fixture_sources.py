"""Synthetic source extraction and fixed development scope; no image access."""
import unittest
import prepare_fixture_sources as f


class FixtureSourceTests(unittest.TestCase):
    def test_exact_unique_block_only(self):
        source = b'#include "core.cpp"\nstruct A {};\nclass D {};\nint main() {}\n'
        value = f.extract(source, b'struct A', b'int main()', 'led')
        self.assertIn(b'struct A {};\nclass D {};\n', value)
        self.assertNotIn(b'#include "core.cpp"', value)
        self.assertNotIn(b'int main()', value)
        self.assertIn(b'namespace postprocess_fixture_sources { namespace led {', value)

    def test_ambiguous_reversed_or_missing_block_fails(self):
        for value in (b'START START END', b'END START', b'START only'):
            with self.assertRaises(ValueError):
                f.extract(value, b'START', b'END', 'magnet')

    def test_scope_is_exact_common25_order_and_development_only(self):
        names = ['LED_' + str(i) for i in range(1, 9)] + ['case1']
        names += ['tiny_s5_i' + str(i) for i in (7,70,127,215,293,353,436,493)]
        names += ['tiny_s2_i' + str(i) for i in (3,92,153,214,295,374,446,494)]
        self.assertEqual(f.COMMON_NAMES, names)
        rows = [{'split':'heldout','scene_id':11,'image_id':0,'rgb':'forbidden.png'},
                {'split':'development','scene_id':5,'image_id':7,'rgb':'test_primesense/000005/rgb/000007.png'}]
        self.assertEqual(f.permitted_tiny(rows), rows[1:])
        for row in ({'split':'development','scene_id':11,'image_id':7,'rgb':'heldout.png'},
                    {'split':'development','scene_id':5,'image_id':8,'rgb':'unknown.png'},
                    rows[1]):
            with self.assertRaises(ValueError):
                f.permitted_tiny([rows[1], row])

    def test_catalog_merges_identical_pins_and_rejects_changed_alias(self):
        first = {'path':'LED/ku.smd','size_bytes':12,'sha256':'a','role':'bank'}
        second = dict(first)
        self.assertEqual(f.merge_pins([first,second]),
                         [{'path':'LED/ku.smd','bytes':12,'sha256':'a','role':'bank'}])
        with self.assertRaises(ValueError):
            f.merge_pins([first, dict(first,sha256='changed')])
        with self.assertRaises(ValueError):
            f.merge_pins([dict(first,path='../escape')])


if __name__ == '__main__':
    unittest.main()
