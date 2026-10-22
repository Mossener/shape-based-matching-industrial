"""Synthetic release checks; no repository index mutation or dataset reads."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import publication as p


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.exp = self.root/'artifacts/rgb_dilated_mask_experiment'
        self.review = self.root/'artifacts/independent_reviews/rgb_dilated_mask_training_v1'
        self.exp.mkdir(parents=True); self.review.mkdir(parents=True)
        self.patch = patch.multiple(p, ROOT=self.root, EXPERIMENT=self.exp,
                                    REVIEW=self.review, INVENTORY=self.exp/'PUBLISH_SELECTION_V29.json')
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def make(self, name='README.md', data=b'public\n'):
        path=self.exp/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        return path

    def test_extra_staged_path_rejected(self):
        path=self.make();record=p.pin(path)
        lookup={record['path']:p.object_id(path.read_bytes())}
        with self.assertRaisesRegex(ValueError,'Extra staged'):
            p.verify_index_records([record],lookup,[record['path'],'unrelated.py'])

    def test_index_crlf_conversion_is_rejected(self):
        path=self.make(data=b'one\r\ntwo\r\n');record=p.pin(path)
        lookup={record['path']:p.object_id(b'one\ntwo\n')}
        with self.assertRaisesRegex(ValueError,'index bytes differ'):
            p.verify_index_records([record],lookup,[record['path']])

    def test_missing_index_member_rejected(self):
        path=self.make();record=p.pin(path)
        with self.assertRaisesRegex(ValueError,'index bytes differ'):
            p.verify_index_records([record],{},[])

    def test_exact_index_bytes_and_hash_algorithms(self):
        path=self.make();record=p.pin(path)
        for algorithm in ('sha1','sha256'):
            data=path.read_bytes()
            expected=hashlib.new(algorithm,b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            self.assertEqual(p.object_id(data,algorithm),expected)
            p.verify_index_records([record],{record['path']:expected},[record['path']],algorithm)

    def test_image_smd_binary_cache_and_archive_rejected_before_read(self):
        for name in ('image.png','private.smd','run.exe','lib.dll','bank.zip','__pycache__/fake.py','unexpected.gz'):
            path=self.exp/name
            with patch.object(Path,'read_bytes',side_effect=AssertionError('read forbidden')):
                with self.assertRaises(ValueError):p.pin(path)

    def test_numeric_gzip_requires_known_name(self):
        path=self.make('run_training_v1/obj1/templates_tless_object_1.yml.gz',b'integer bank')
        self.assertEqual(p.pin(path)['bytes'],12)

    def test_other_repository_path_rejected_before_read(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('read forbidden')):
            with self.assertRaisesRegex(ValueError,'Outside V29'):
                p.pin(self.root/'other/receipt.json')

    def test_collect_does_not_descend_into_quality_run(self):
        public=self.make('README.md')
        quality=self.make('run_quality_development_v1/native/summary.json',b'not in this release')
        binary=self.make('build_training_v1/train.exe',b'not public')
        paths,excluded=p.collect()
        self.assertIn(public,paths);self.assertNotIn(quality,paths);self.assertNotIn(binary,paths)
        self.assertIn(binary.relative_to(self.root).as_posix(),excluded)

    def test_freeze_members_require_internal_audit(self):
        directory=self.exp/'run_training_v1';self.make('run_training_v1/training_audit.json',b'{}')
        freeze=dict(files=[],execution_files=[],reservation={})
        with self.assertRaisesRegex(ValueError,'member set differs'):
            p.verify_members(freeze,directory,'BANK_FREEZE.json')

    def test_freeze_pin_mutation_rejected(self):
        path=self.make();record=p.pin(path);path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'SHA/size mismatch'):p.check(record)


if __name__=='__main__':
    unittest.main(verbosity=2)
