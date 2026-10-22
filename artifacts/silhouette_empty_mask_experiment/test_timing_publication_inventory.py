"""Tiny source-only checks of V23 publication completeness and verify-only mode."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import prepare_timing_publication_inventory as inventory


class TimingPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.here = self.root / 'experiment'
        self.review = self.root / 'review'
        self.stage = self.here / 'stage'
        self.stage.mkdir(parents=True)
        self.review.mkdir()
        (self.here / 'source.py').write_text('# source\n')
        (self.review / 'review.py').write_text('# reviewer\n')
        (self.stage / 'timing.csv').write_text('clock\n1\n')
        (self.review / 'completed').mkdir()
        (self.review / 'completed/result.json').write_text('{}')
        self.output = self.here / 'inventory.json'
        patch = mock.patch.multiple(inventory, ROOT=self.root, HERE=self.here, REVIEW=self.review,
            STAGE=self.stage, OUTPUT=self.output, ROOT_FILES=('source.py',),
            REVIEW_FILES=('review.py',), REVIEW_DIRS=('completed',), STAGE_NAMES={'timing.csv'}, PINS={})
        patch.start()
        self.addCleanup(patch.stop)

    def run_inventory(self, *arguments):
        with mock.patch('sys.argv', ['inventory', *arguments]), contextlib.redirect_stdout(io.StringIO()):
            inventory.main()

    def test_valid_selection_verify_no_write_and_explicit_refresh(self):
        self.run_inventory()
        original = self.output.read_bytes(), self.output.stat().st_mtime_ns
        self.run_inventory('--verify')
        self.assertEqual(original, (self.output.read_bytes(), self.output.stat().st_mtime_ns))
        self.assertEqual(json.loads(original[0])['file_count'], 4)
        with self.assertRaisesRegex(ValueError, 'requires --refresh'):
            self.run_inventory()
        self.run_inventory('--refresh')

    def test_exact_stage_rejects_extra_even_eligible_file(self):
        (self.stage / 'diagnostic.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'nine-file'):
            self.run_inventory()

    def test_missing_required_source_and_tampered_inventory_rejected(self):
        self.run_inventory()
        altered = json.loads(self.output.read_text())
        altered['formal_timing_rows'] = 0
        self.output.write_text(json.dumps(altered))
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.run_inventory('--verify')
        self.run_inventory('--refresh')
        (self.here / 'source.py').write_text('# changed\n')
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.run_inventory('--verify')
        (self.here / 'source.py').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or forbidden'):
            self.run_inventory('--verify')

    def test_image_archive_executable_and_bytecode_excluded(self):
        for name in ('x.png', 'x.jpg.gz', 'x.exe', 'x.pyc', 'private.smd'):
            path = self.review / 'completed' / name
            path.write_bytes(b'fixture')
            self.assertFalse(inventory.safe(path))
        self.run_inventory()
        self.assertEqual(json.loads(self.output.read_text())['file_count'], 4)

    def test_reviewed_reference_sha_cannot_drift(self):
        source = self.here / 'source.py'
        with mock.patch.object(inventory, 'PINS', {'historical': ('source.py', '0' * 64)}):
            with self.assertRaisesRegex(ValueError, 'historical/stage pin'):
                self.run_inventory()


if __name__ == '__main__':
    unittest.main()
