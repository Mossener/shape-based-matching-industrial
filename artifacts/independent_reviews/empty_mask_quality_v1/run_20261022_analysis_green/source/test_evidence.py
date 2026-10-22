"""Tiny generated provenance/tar corruptions; real archives are never read."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from evidence import Reader, members


def tiny_archive(names=('a.csv.gz',)):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name in names:
            member = tarfile.TarInfo(name)
            member.size = 3
            archive.addfile(member, io.BytesIO(b'abc'))
    return stream.getvalue()


PIN = dict(name='a.csv.gz', bytes=3, sha256=hashlib.sha256(b'abc').hexdigest())


class ProvenanceChecks(unittest.TestCase):
    def test_tar_exact_inventory_bytes_and_duplicate_mutations(self):
        self.assertEqual(members(tiny_archive(), [PIN]), {'a.csv.gz': b'abc'})
        for names, expected in [(('a.csv.gz', 'a.csv.gz'), [PIN]), (('../a.csv.gz',), [PIN]),
                                ((), [PIN]), (('a.csv.gz',), [dict(PIN, bytes=4)])]:
            with self.assertRaises(ValueError):
                members(tiny_archive(names), expected)

    def test_changed_pin_and_dataset_image_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file = root/'numeric.json'
            file.write_bytes(b'abc')
            reader = Reader(root)
            pin = dict(path=str(file.resolve()), bytes=3, sha256=hashlib.sha256(b'abc').hexdigest())
            self.assertEqual(reader.check(pin), b'abc')
            with self.assertRaises(ValueError):
                reader.check(dict(pin, sha256='0'*64))
            image = root/'datasets/test_primesense/000001/rgb/000001.png'
            image.parent.mkdir(parents=True)
            image.write_bytes(b'abc')
            with self.assertRaises(ValueError):
                reader.check(dict(pin, path=str(image.resolve())))


if __name__ == '__main__':
    unittest.main()
