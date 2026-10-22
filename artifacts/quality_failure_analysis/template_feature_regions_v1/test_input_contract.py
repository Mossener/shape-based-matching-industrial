from pathlib import Path
import unittest
import input_contract as c


class InputBoundaryTests(unittest.TestCase):
    def test_numeric_paths_reject_images_private_and_escape_before_io(self):
        root=Path.cwd()
        for p in ['datasets/a.png','datasets/a.jpg','artifacts/a.SMD','../escape.json','artifacts/a.exe']:
            with self.subTest(path=p),self.assertRaises(ValueError):c.numeric_path(root/p,root)

    def test_only_explicit_numeric_extensions(self):
        root=Path.cwd()
        self.assertEqual(c.numeric_path(root/'artifacts/bank.yml.gz',root),(root/'artifacts/bank.yml.gz').resolve())
        self.assertEqual(c.numeric_path(root/'artifacts/raw.csv.gz',root),(root/'artifacts/raw.csv.gz').resolve())

    def test_mask_allowlist_rejects_reserved_heldout_rgb_duplicate_and_traversal(self):
        base=dict(object_id=1,image_id=0,path='train_primesense/000001/mask/000000_000000.png',bytes=100,sha256='a'*64)
        root=Path.cwd()/'datasets/tless'
        for changes in [dict(object_id=25),dict(path='test_primesense/000011/rgb/000000.png'),dict(path='train_primesense/000001/rgb/000000.png'),dict(path='../outside.png')]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):c.validate_masks([dict(base,**changes)],root,[1,2,5,8,12,17])
        with self.assertRaises(ValueError):c.validate_masks([base,base],root,[1])

    def test_explicit_training_mask_path_no_byte_access(self):
        root=Path.cwd()/'datasets/tless';q=dict(object_id=1,image_id=6,path='train_primesense/000001/mask/000006_000000.png',bytes=9,sha256='b'*64)
        out=c.validate_masks([q],root,[1])
        self.assertEqual(out[0]['path'],str((root/q['path']).resolve()))


if __name__=='__main__':unittest.main()
