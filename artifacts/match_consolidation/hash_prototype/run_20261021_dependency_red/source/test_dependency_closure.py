"""Synthetic local dependency byte/command binding; no compiler or image access."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from dependency_closure import audit_build_dependencies, parse_depfile


def pin(path, root=None):
    data = path.read_bytes()
    return dict(path=path.relative_to(root).as_posix() if root else str(path),
                sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))


def escaped(path):
    return str(path).replace('\\', '/').replace('$', '$$').replace('#', '\\#').replace(' ', '\\ ')


class LocalDependencyClosure(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.snapshot = self.root/'snapshot'
        self.cwd = self.root/'output/capture_objects'
        self.cwd.mkdir(parents=True)
        self.core = self.snapshot/'captured/line2Dup.cpp'
        self.adapter = self.snapshot/'support/capture_adapter.cpp'
        self.header = self.snapshot/'captured/line2Dup.h'
        self.external = self.root.parent/(self.root.name+'_compiler header $1#x.hpp')
        self.addCleanup(lambda: self.external.unlink(missing_ok=True))
        self.library = self.root/'opencv/build/lib/libopencv_world4120.dll.a'
        for path in (self.core, self.adapter, self.header, self.external, self.library):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('synthetic '+path.name).encode())
        self.sources = {p.relative_to(self.root).as_posix() for p in
                        (self.core, self.adapter, self.header)}
        self.toolchain = dict(import_library=pin(self.library))
        self.built = dict(role='capture', working_directory=str(self.cwd),
                          compile_exits=[0, 0], link_exit=0, dependency_units=[])
        for name, source in (('core', self.core), ('adapter', self.adapter)):
            obj = self.cwd/(name+'.o')
            obj.write_bytes(('object '+name).encode())
            dependencies = [source, self.header, self.external]
            depfile = self.cwd/(name+'.d')
            depfile.write_bytes((name+'.o: '+escaped(dependencies[0])+' \\\n '+
                                 ' '.join(escaped(p) for p in dependencies[1:])+'\n').encode())
            self.built['dependency_units'].append(dict(
                source=source.relative_to(self.root).as_posix(), target=name+'.o',
                object=pin(obj, self.root), depfile=pin(depfile, self.root),
                dependencies=[pin(p) for p in dependencies]))

    def audit(self):
        return audit_build_dependencies(self.root, self.snapshot, self.toolchain,
                                        self.built, self.sources)

    def test_a_complete_depfile_paths_and_metadata_are_bound(self):
        checked = self.audit()
        self.assertGreaterEqual(len(checked), 11)
        self.assertEqual(parse_depfile((self.cwd/'core.d').read_bytes(), 'core.o', self.cwd),
                         [self.core, self.header, self.external])

    def test_omitted_added_duplicate_or_changed_dependency_is_rejected(self):
        original = copy.deepcopy(self.built['dependency_units'][0]['dependencies'])
        for values in (original[:-1], original+[original[0]],
                       original+[pin(self.library)],
                       [dict(p, sha256='0'*64) for p in original]):
            self.built['dependency_units'][0]['dependencies'] = values
            with self.assertRaises(ValueError):
                self.audit()

    def test_changed_header_object_depfile_and_library_are_rejected(self):
        for path in (self.header, self.external, self.cwd/'core.o',
                     self.cwd/'core.d', self.library):
            original = path.read_bytes()
            path.write_bytes(original+b'changed')
            with self.assertRaises(ValueError):
                self.audit()
            path.write_bytes(original)

    def test_missing_reordered_units_source_target_and_exit_are_rejected(self):
        original = copy.deepcopy(self.built)
        for changed in (
                dict(original, dependency_units=original['dependency_units'][:1]),
                dict(original, dependency_units=list(reversed(original['dependency_units']))),
                dict(original, compile_exits=[0, 1]), dict(original, compile_exits=[False, 0]),
                dict(original, link_exit=1), dict(original, working_directory=str(self.root))):
            self.built = changed
            with self.assertRaises(ValueError):
                self.audit()
        self.built = copy.deepcopy(original)
        for key, value in (('target', 'other.o'), ('source', original['dependency_units'][1]['source'])):
            self.built['dependency_units'][0][key] = value
            with self.assertRaises(ValueError):
                self.audit()
            self.built = copy.deepcopy(original)

    def test_depfile_rejects_wrong_target_rules_truncation_and_bad_escapes(self):
        for data in (b'wrong.o: a.h\n', b'core.o a.o: a.h\n', b'core.o: a.h\nother.o: b.h\n',
                     b'core.o: a.h\\', b'core.o: a#comment\n', b'core.o: a$unescaped\n',
                     b'core.o: \x00bad\n', b'core.o: \xff\n', b'core.o:\n'):
            with self.assertRaises(ValueError):
                parse_depfile(data, 'core.o', self.cwd)

    def test_relative_and_make_escaped_paths_are_decoded_in_cwd(self):
        data = b'core.o: ../../snapshot/captured/line2Dup.cpp escaped\\ name\\#x$$1.h\n'
        self.assertEqual(parse_depfile(data, 'core.o', self.cwd), [
            self.core, self.cwd/'escaped name#x$1.h'])

    def test_depfile_cannot_cause_unapproved_repository_image_to_be_read(self):
        # The named heldout file never exists and must be rejected by scope,
        # before a metadata/hash attempt can reach it.
        unit = self.built['dependency_units'][0]
        forbidden = self.root/'datasets/tless_tiny/heldout_never_opened.png'
        depfile = self.cwd/'core.d'
        depfile.write_bytes(('core.o: '+escaped(self.core)+' '+escaped(forbidden)+'\n').encode())
        unit['depfile'] = pin(depfile, self.root)
        unit['dependencies'] = [pin(self.core), dict(path=str(forbidden), size_bytes=0, sha256='0'*64)]
        with self.assertRaisesRegex(ValueError, 'scope|repository|project'):
            self.audit()


if __name__ == '__main__':
    unittest.main()
