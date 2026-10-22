"""Lossless export/restore and corruption rejection on numeric fixtures."""
import json
from pathlib import Path
import tempfile
import unittest
import preserve_training_evidence as evidence


class Export(unittest.TestCase):
    def fixture(self, root, large=False):
        source = root/'run'
        source.mkdir()
        (source/'records.jsonl').write_bytes(b'{}\n' * (5592406 if large else 2))
        (source/'bank.yml.gz').write_bytes(b'numeric opaque stored gzip fixture')
        provenance = root/'provenance.json'
        provenance.write_text(json.dumps(dict(mode='train', passed=True, files=[
            dict(path=str(path.resolve()), **evidence.pin(path)) for path in sorted(source.iterdir())])))
        acceptance = root/'acceptance.json'
        acceptance.write_text(json.dumps(dict(real_training_accepted=True, numeric_audit_passed=True,
            training_provenance=dict(path=str(provenance.resolve()), **evidence.pin(provenance)))))
        return source, provenance, acceptance

    def test_complete_roundtrip_compressed_text_and_identity_bank(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, provenance, acceptance = self.fixture(root, large=True)
            manifest = evidence.package(source, provenance, acceptance, root/'public')
            self.assertEqual({row['original_path']:row['encoding'] for row in manifest['files']},
                             {'bank.yml.gz':'identity', 'records.jsonl':'gzip'})
            self.assertTrue(evidence.restore(root/'public', root/'restored')['passed'])
            for path in source.iterdir():
                self.assertEqual(evidence.pin(path), evidence.pin(root/'restored'/path.name))

    def test_changed_original_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source, provenance, acceptance = self.fixture(root)
            (source/'records.jsonl').write_bytes(b'{"changed":true}\n')
            with self.assertRaisesRegex(ValueError, 'original training file changed'):
                evidence.package(source, provenance, acceptance, root/'public')

    def test_changed_stored_member_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source, provenance, acceptance = self.fixture(root)
            evidence.package(source, provenance, acceptance, root/'public')
            (root/'public'/'records.jsonl').write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'stored member bytes changed'):
                evidence.restore(root/'public', root/'restored')
            self.assertFalse((root/'restored').exists())

    def test_missing_extra_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source, provenance, acceptance = self.fixture(root)
            evidence.package(source, provenance, acceptance, root/'public')
            (root/'public'/'extra.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'export inventory differs'):
                evidence.restore(root/'public', root/'restored')
            for name in ('../leak.json','C:/escape.json','/escape.json','binary.exe'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    evidence.relative(name)


if __name__=='__main__':
    unittest.main(verbosity=2)
