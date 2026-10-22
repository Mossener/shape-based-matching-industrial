"""Literal transformation and fresh-output policy tests; no native programs."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_sources import candidate_bytes, fresh_destination, safe_relative


class SourceGeneration(unittest.TestCase):
    def test_exact_two_seam_transform_and_unchanged_surrounding_bytes(self):
        original = (b"before\x00\xff\n#include \"line2Dup_matches.hpp\"\n"
                    b"middle\r\n detail::consolidateMatches(matches);\nend\x00")
        expected = (b"before\x00\xff\n#include \"line2Dup_matches.hpp\"\n"
                    b"#include \"hash_consolidation.hpp\"\n"
                    b"middle\r\n postprocess_hash::consolidateMatches(matches);\nend\x00")
        self.assertEqual(candidate_bytes(original), expected)

    def test_rejects_missing_duplicate_or_pretransformed_seams(self):
        original = b'#include "line2Dup_matches.hpp"\ndetail::consolidateMatches(matches);\n'
        bad = [original.replace(b'line2Dup_matches.hpp', b'other.hpp'),
               original.replace(b'detail::consolidateMatches', b'other'),
               original + b'#include "line2Dup_matches.hpp"\n',
               original + b'detail::consolidateMatches(matches);',
               b'#include "hash_consolidation.hpp"\n' + original,
               original + b'postprocess_hash::consolidateMatches(matches);']
        for value in bad:
            with self.assertRaises(ValueError):
                candidate_bytes(value)

    def test_canonical_source_relative_names_only(self):
        self.assertEqual(safe_relative("MIPP/math/x.hxx"), Path("MIPP/math/x.hxx"))
        for name in ("", ".", "../x", "MIPP/../x", "./x", "MIPP//x", "MIPP\\x",
                     "/private", "D:/private", "x:", "x\x00y"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_relative(name)

    def test_output_must_be_fresh_direct_generated_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            here = Path(temporary).resolve()
            self.assertEqual(fresh_destination(here, here / "generated"), here / "generated")
            for wrong in (here, here / "other", here / "generated" / "nested", here.parent / "generated"):
                with self.assertRaises(ValueError):
                    fresh_destination(here, wrong)
            (here / "generated").mkdir()
            with self.assertRaises(ValueError):
                fresh_destination(here, here / "generated")


if __name__ == "__main__":
    unittest.main()
