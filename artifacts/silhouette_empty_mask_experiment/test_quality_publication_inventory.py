"""Source-only checks of publication selection and verify-only behavior."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import prepare_quality_publication_inventory as inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.here = self.root / 'experiment'
        self.review = self.root / 'review'
        (self.here / 'native').mkdir(parents=True)
        (self.review / 'audit').mkdir(parents=True)
        (self.here / 'source.py').write_text('source\n', encoding='utf-8')
        (self.here / 'native' / 'trace.csv.gz').write_bytes(b'numeric fixture')
        (self.review / 'source.py').write_text('review\n', encoding='utf-8')
        (self.review / 'audit' / 'result.json').write_text('{}\n', encoding='utf-8')
        self.output = self.here / 'inventory.json'
        self.patch = mock.patch.multiple(
            inventory, ROOT=self.root, HERE=self.here, REVIEW_ROOT=self.review,
            OUTPUT=self.output, ROOT_FILES=('source.py',), STAGE_DIRS=('native',),
            REVIEW_FILES=('source.py',), REVIEW_DIRS=('audit',))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def run_inventory(self, *options):
        with mock.patch('sys.argv', ['inventory', *options]), contextlib.redirect_stdout(io.StringIO()):
            inventory.main()

    def test_verify_preserves_existing_inventory_bytes_and_mtime(self):
        self.run_inventory()
        previous = (self.output.read_bytes(), self.output.stat().st_mtime_ns)
        self.run_inventory('--verify')
        self.assertEqual(previous, (self.output.read_bytes(), self.output.stat().st_mtime_ns))

    def test_verify_rejects_changed_selected_bytes(self):
        self.run_inventory()
        (self.here / 'source.py').write_text('different\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Inventory differs'):
            self.run_inventory('--verify')

    def test_verify_rejects_new_eligible_file(self):
        self.run_inventory()
        (self.here / 'native' / 'extra.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Inventory differs'):
            self.run_inventory('--verify')

    def test_verify_rejects_missing_required_source(self):
        self.run_inventory()
        (self.here / 'source.py').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or forbidden'):
            self.run_inventory('--verify')

    def test_verify_rejects_tampered_metadata(self):
        self.run_inventory()
        data = json.loads(self.output.read_text(encoding='utf-8'))
        data['native_matcher_calls'] += 1
        self.output.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Inventory differs'):
            self.run_inventory('--verify')

    def test_excludes_images_binaries_and_non_numeric_archive_names(self):
        forbidden = ('image.png', 'image.png.gz', 'payload.exe', 'cache.pyc', 'model.smd', '.gitignore')
        for name in forbidden:
            path = self.here / 'native' / name
            path.write_bytes(b'fixture')
            self.assertFalse(inventory.safe(path), name)
        self.run_inventory()
        result = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(result['file_count'], 4)

    def test_existing_inventory_requires_explicit_refresh(self):
        self.run_inventory()
        with self.assertRaisesRegex(ValueError, 'requires --refresh'):
            self.run_inventory()
        self.run_inventory('--refresh')

    def test_required_file_cannot_escape_repository(self):
        outside = self.root.parent / (self.root.name + '_outside.py')
        outside.write_text('outside\n', encoding='utf-8')
        self.addCleanup(outside.unlink)
        with mock.patch.object(inventory, 'ROOT_FILES', (str(outside),)):
            with self.assertRaisesRegex(ValueError, 'escaped repository'):
                self.run_inventory()


if __name__ == '__main__':
    unittest.main()
