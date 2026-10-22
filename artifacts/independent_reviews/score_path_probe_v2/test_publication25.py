"""Publication boundary fixtures use temporary source/numeric text only."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import publication25 as p


class Publication(unittest.TestCase):
    def test_exact_two_roots_and_forbidden_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);scopes=(root/'probe',root/'audit')
            for scope in scopes:scope.mkdir()
            source=scopes[0]/'phase2.cpp';source.write_text('source')
            self.assertEqual(p.member(source,root,scopes),source.resolve())
            for relative in ('other/old_v24.py','probe/tool.exe','probe/tool.o','audit/runtime.dll','probe/__pycache__/x.pyc','probe/image.png','audit/model.smd','probe/templates_obj.yml.gz','probe/private/source.cpp','probe/data.csv.gz'):
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'x')
                with self.subTest(relative=relative),self.assertRaises(ValueError):p.member(path,root,scopes)

    def test_sorted_unique_size_hash_and_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);scope=root/'probe';scope.mkdir();a=scope/'a.txt';b=scope/'b.py';a.write_bytes(b'abc');b.write_bytes(b'')
            got=p.records([b,a],root,(scope,))
            self.assertEqual([r['path'] for r in got],['probe/a.txt','probe/b.py'])
            self.assertEqual((got[0]['size_bytes'],got[0]['sha256']),(3,hashlib.sha256(b'abc').hexdigest()))
            pin=dict(path=str(a.resolve()),bytes=3,sha256=got[0]['sha256']);p.verify_pin(pin,root,(scope,))
            with self.assertRaises(ValueError):p.records([a,a],root,(scope,))
            a.write_bytes(b'abd')
            with self.assertRaises(ValueError):p.verify_pin(pin,root,(scope,))


if __name__=='__main__':unittest.main()
