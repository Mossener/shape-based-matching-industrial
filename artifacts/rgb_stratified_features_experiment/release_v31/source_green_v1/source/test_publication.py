"""Synthetic publication fixtures; no real index or actual evidence is read."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('v31_selection_under_test',Path(__file__).with_name('verify_selection.py'))
VERIFY=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(VERIFY)


class Result:
    def __init__(self,stdout=b'',returncode=0): self.stdout=stdout; self.returncode=returncode


class PublicationTests(unittest.TestCase):
    def fixture(self,root):
        member=root/'evidence.json'; member.write_bytes(b'{"v":1}\n')
        data=member.read_bytes()
        selection=dict(file_count=1,selected_bytes=len(data),files=[dict(path='evidence.json',bytes=len(data),
                       sha256=hashlib.sha256(data).hexdigest())])
        path=root/'publication'/'selection.json'; path.parent.mkdir()
        self.save(path,selection)
        return member,path,selection

    def save(self,path,value): path.write_text(json.dumps(value),encoding='utf-8')

    def verify(self,root,path,staged=False,git=None):
        args=['verify','--selection',str(path)]+(['--staged'] if staged else [])
        captured=io.StringIO()
        with patch.object(VERIFY,'HERE',root),patch.object(sys,'argv',args),contextlib.redirect_stdout(captured), \
             patch.object(VERIFY.subprocess,'run',side_effect=git or AssertionError('offline check invoked Git')):
            VERIFY.main()
        return json.loads(captured.getvalue())

    def test_explicit_selection_without_git_or_default_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); _,path,_=self.fixture(root)
            try: result=self.verify(root,path)
            except SystemExit as error: self.fail('valid explicit selection rejected: '+str(error))
            self.assertTrue(result['passed']); self.assertFalse(result['staged']); self.assertEqual(result['file_count'],1)

    def test_path_escape_and_noncanonical_paths_rejected(self):
        for relative in ('../outside.json','/outside.json','C:/outside.json','a\\b.json','./evidence.json',
                         'a//b.json','a/../evidence.json','evidence.json:stream','evidence.json\n',
                         'evidence.json.','evidence.json '):
            with self.subTest(path=relative),tempfile.TemporaryDirectory() as t:
                root=Path(t); _,path,selection=self.fixture(root); selection['files'][0]['path']=relative
                self.save(path,selection)
                with self.assertRaisesRegex(SystemExit,'invalid path'): self.verify(root,path)

    def test_duplicate_members_and_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); _,path,selection=self.fixture(root)
            selection['files'].append(dict(selection['files'][0])); selection['file_count']=2
            self.save(path,selection)
            with self.assertRaisesRegex(SystemExit,'duplicate selected path'): self.verify(root,path)
            path.write_text('{"files":[],"file_count":0,"file_count":0,"selected_bytes":0}')
            with self.assertRaisesRegex(SystemExit,'duplicate JSON key'): self.verify(root,path)

    def test_changed_sha_and_size_rejected(self):
        for data in (b'{"v":2}\n',b'{"changed":true}\n'):
            with self.subTest(data=data),tempfile.TemporaryDirectory() as t:
                root=Path(t); member,path,_=self.fixture(root); member.write_bytes(data)
                with self.assertRaisesRegex(SystemExit,'selected bytes changed'): self.verify(root,path)

    def test_forbidden_and_oversize_members_rejected_before_read(self):
        for suffix in ('.PNG','.smd','.exe','.dll','.pyc','.zip','oversize'):
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as t:
                root=Path(t); member,path,selection=self.fixture(root)
                if suffix!='oversize':
                    new=root/('fixture'+suffix); member.rename(new); member=new
                    selection['files'][0]['path']=member.name
                else: selection['files'][0]['bytes']=100*1024**2
                self.save(path,selection); original=Path.read_bytes; opened=[]
                def read(p):
                    if p==member: opened.append(p)
                    return original(p)
                with patch.object(Path,'read_bytes',read):
                    with self.assertRaises(SystemExit): self.verify(root,path)
                self.assertEqual(opened,[],'forbidden/oversize selected payload was opened')

    def test_selection_must_be_inside_repository(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); _,path,_=self.fixture(root); other=root/'different_repo'; other.mkdir()
            with self.assertRaisesRegex(SystemExit,'selection.*repository'): self.verify(other,path)

    def test_exact_index_blobs_for_sha1_and_sha256(self):
        for fmt in ('sha1','sha256'):
            for fault in ('green','prepublished','wrong_member','wrong_inventory','unrelated','unmerged','missing'):
                with self.subTest(format=fmt,fault=fault),tempfile.TemporaryDirectory() as t:
                    root=Path(t); member,path,_=self.fixture(root)
                    def oid(data): return hashlib.new(fmt,b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                    def git(command,**kwargs):
                        self.assertEqual(kwargs['cwd'],root); self.assertEqual(command[0],'git'); args=command[1:]
                        if args==['rev-parse','--show-object-format']: return Result(fmt+'\n')
                        if args==['diff','--cached','--name-only','-z']:
                            if fault=='prepublished': return Result(b'publication/selection.json\0')
                            return Result(b'evidence.json\0publication/selection.json\0'+(b'outside.json\0' if fault=='unrelated' else b''))
                        if args==['ls-tree','-r','--name-only','-z','HEAD']:
                            return Result(b'evidence.json\0' if fault=='prepublished' else b'')
                        if args==['ls-files','--stage','-z']:
                            member_oid='0'*len(oid(b'')) if fault=='wrong_member' else oid(member.read_bytes())
                            inventory_oid='0'*len(oid(b'')) if fault=='wrong_inventory' else oid(path.read_bytes())
                            stage='1' if fault=='unmerged' else '0'
                            rows='' if fault=='missing' else f'100644 {member_oid} {stage}\tevidence.json\0'
                            return Result((rows+f'100644 {inventory_oid} 0\tpublication/selection.json\0').encode())
                        if args==['diff','--cached','--check']: return Result()
                        self.fail('unexpected Git command: '+repr(command))
                    if fault in ('green','prepublished'): self.assertTrue(self.verify(root,path,True,git)['passed'])
                    else:
                        error={'wrong_member':'index bytes differ','wrong_inventory':'index bytes differ',
                               'unrelated':'staged path set mismatch','unmerged':'unmerged index entry',
                               'missing':'selected path is absent'}[fault]
                        with self.assertRaisesRegex(SystemExit,error): self.verify(root,path,True,git)


if __name__=='__main__': unittest.main(verbosity=2)
