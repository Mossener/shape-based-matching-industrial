"""Synthetic exact-Git/build-recipe closure; no real toolchain or image access."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import capture_source
from capture_manifest import CORE_REVISION
from real_capture_audit import audit_real_capture
import test_capture_manifest as generic_tests
import test_capture_source as source_tests


SUPPORT = ('record.hpp', 'trace_io.hpp', 'capture_hook.hpp', 'capture_adapter.cpp', 'led_demo.cpp')
PROVENANCE = ('capture_source.py', 'capture_manifest.py', 'real_capture_audit.py',
              'dependency_closure.py', 'real_capture_build.py', 'real_capture_build.ps1',
              'run_capture.py', 'CAPTURE_PROTOCOL.json')


def metadata(root, path):
    data = path.read_bytes()
    return dict(path=path.relative_to(root).as_posix(),
                size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def command(root, snapshot, compiler, opencv, role, exe):
    # Independent literal fixture for the only approved one-command build.
    core = snapshot/('captured' if role == 'capture' else 'original')
    argv = [str(compiler), '-std=c++17', '-O3', '-mssse3', '-msse4.1', '-fopenmp',
            '-Wall', '-Wextra', '-Wno-sign-compare',
            '-DSBM_CAPTURE='+('1' if role == 'capture' else '0'),
            '-I'+str(core), '-I'+str(core/'MIPP'), '-I'+str(snapshot/'support'),
            '-I'+str(opencv/'build')]
    argv += ['-I'+str(opencv/'modules'/module/'include')
             for module in ('core', 'imgproc', 'highgui', 'imgcodecs', 'videoio')]
    work = exe.parent/(role+'_objects')
    commands = [argv+['-c', '-MD', '-MF', str(work/(name+'.d')), '-MT', name+'.o',
                     str(source), '-o', str(work/(name+'.o'))]
                for name, source in (('core', core/'line2Dup.cpp'),
                                      ('adapter', snapshot/'support/capture_adapter.cpp'))]
    return commands+[[str(compiler), str(work/'core.o'), str(work/'adapter.o'), '-fopenmp',
                       str(opencv/'build/lib/libopencv_world4120.dll.a'), '-o', str(exe)]]


class RealCaptureClosure(unittest.TestCase):
    def setUp(self):
        self.generic = generic_tests.CaptureManifestContracts()
        self.generic.setUp()
        self.addCleanup(self.generic.doCleanups)
        self.root, self.out = self.generic.root, self.generic.out
        self.protocol = self.generic.protocol
        self.manifest = self.generic.manifest
        self.data, self.git = source_tests.CaptureSourceContracts().fixture()
        self.snapshot = self.root/'snapshot'
        capture_source.make_snapshot(self.root, self.snapshot, self.git)
        self.support_root = self.root/'author_sources'
        self.support_root.mkdir()
        for name in SUPPORT:
            original = self.support_root/name
            original.write_bytes((name+' synthetic support\x00\xff').encode('latin1'))
            copied = (self.snapshot/'captured/capture_hook.hpp' if name == 'capture_hook.hpp'
                      else self.snapshot/'support'/name)
            copied.parent.mkdir(exist_ok=True)
            copied.write_bytes(original.read_bytes())
        for name in PROVENANCE:
            (self.support_root/name).write_bytes((name+' synthetic provenance').encode())
        led_origin = self.root/'artifacts/led_match/led_demo.cpp'
        led_origin.parent.mkdir(parents=True, exist_ok=True)
        led_origin.write_bytes((self.support_root/'led_demo.cpp').read_bytes())
        compiler = self.root/'toolchain/bin/g++.exe'
        compiler.parent.mkdir(parents=True)
        compiler.write_bytes(b'synthetic compiler')
        self.external = tempfile.TemporaryDirectory()
        self.addCleanup(self.external.cleanup)
        opencv = Path(self.external.name).resolve()/'opencv'
        runtime_paths = [opencv/'build/bin/libopencv_world4120.dll'] + [
            compiler.parent/name for name in
            ('libgomp-1.dll', 'libstdc++-6.dll', 'libgcc_s_seh-1.dll')]
        for path in runtime_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('synthetic '+path.name).encode())
        # External toolchain pins are explicit absolute paths, never dataset paths.
        def external(path):
            data = path.read_bytes()
            return dict(path=str(path), size_bytes=len(data),
                        sha256=hashlib.sha256(data).hexdigest())
        library = opencv/'build/lib/libopencv_world4120.dll.a'
        library.parent.mkdir(parents=True)
        library.write_bytes(b'synthetic import library')
        opencv_header = opencv/'modules/core/include/opencv2/core.hpp'
        opencv_header.parent.mkdir(parents=True)
        opencv_header.write_bytes(b'synthetic OpenCV header')
        self.protocol['real_build_closure'] = dict(
            source_manifest=metadata(self.root, self.snapshot/'source_manifest.json'),
            toolchain=dict(compiler=external(compiler), opencv_root=str(opencv),
                           import_library=external(library),
                           runtimes=[external(path) for path in runtime_paths]))
        self.builds = {}
        source_pins = {led_origin: dict(metadata(self.root, led_origin), role='source')}
        for role in ('capture', 'reference'):
            kind = 'captured' if role == 'capture' else 'original'
            paths = [self.snapshot/kind/name for name in self.data]
            paths += [self.snapshot/'support'/name for name in SUPPORT if name != 'capture_hook.hpp']
            if role == 'capture':
                paths.append(self.snapshot/'captured/capture_hook.hpp')
            for path in paths:
                source_pins[path] = dict(metadata(self.root, path), role='source')
            exe = self.out/(role+'.exe')
            exe.write_bytes(('synthetic '+role+' executable').encode())
            work = self.out/(role+'_objects')
            work.mkdir()
            commands = command(self.root, self.snapshot, compiler, opencv, role, exe)
            units = []
            for name, source in (('core', self.snapshot/kind/'line2Dup.cpp'),
                                 ('adapter', self.snapshot/'support/capture_adapter.cpp')):
                obj = work/(name+'.o')
                obj.write_bytes(('synthetic '+role+' '+name+' object').encode())
                dependencies = [source, self.snapshot/kind/'line2Dup.h', opencv_header]
                depfile = work/(name+'.d')
                depfile.write_bytes((name+'.o: '+' '.join(
                    str(p).replace('\\', '/').replace(' ', '\\ ') for p in dependencies)+'\n').encode())
                scan = work/(name+'_scan.d')
                scan.write_bytes(depfile.read_bytes())
                compile_command = commands[0 if name == 'core' else 1]
                units.append(dict(source=source.relative_to(self.root).as_posix(), target=name+'.o',
                                  object=metadata(self.root, obj), depfile=metadata(self.root, depfile),
                                  discovery_depfile=metadata(self.root, scan),
                                  discovery_command=compile_command[:compile_command.index('-c')]+[
                                      '-M', '-MF', str(scan), '-MT', name+'.o', str(source)],
                                  dependencies=[external(p) for p in dependencies]))
            built = dict(schema_version=1, passed=True, role=role, core_revision=CORE_REVISION,
                         source_manifest_sha256=self.protocol['real_build_closure']['source_manifest']['sha256'],
                         source_files=[metadata(self.root, p) for p in paths],
                         compiler=external(compiler), runtimes=[external(p) for p in runtime_paths],
                         executable=metadata(self.root, exe),
                         working_directory=str(work), compile_exits=[0, 0], link_exit=0,
                         dependency_units=units,
                         command=commands,
                         compile_exit=0, sources_unchanged=True)
            self.builds[role] = built
            path = self.out/(role+'_build.json')
            path.write_text(json.dumps(built))
            pin = next(p for p in self.protocol['pins'] if p['role'] == role+'_build')
            pin.update(metadata(self.root, path))
        for name in SUPPORT+PROVENANCE:
            path = self.support_root/name
            source_pins[path] = dict(metadata(self.root, path), role='source')
        path = self.snapshot/'source_manifest.json'
        source_pins[path] = dict(metadata(self.root, path), role='source')
        self.protocol['pins'] = [p for p in self.protocol['pins'] if p['role'] != 'source']+list(source_pins.values())
        self.generic.repin_protocol()

    def audit(self):
        return audit_real_capture(self.generic.manifest_path, self.generic.protocol_path,
                                  self.root, self.git, self.support_root)

    def save_build(self, role):
        path = self.out/(role+'_build.json')
        path.write_text(json.dumps(self.builds[role]))
        pin = next(p for p in self.protocol['pins'] if p['role'] == role+'_build')
        pin.update(metadata(self.root, path))
        self.generic.repin_protocol()

    def test_a_omitted_mipp_build_dependency_is_rejected_even_after_repinning(self):
        self.builds['capture']['source_files'] = [
            p for p in self.builds['capture']['source_files'] if 'MIPP/fixture0.h' not in p['path']]
        self.save_build('capture')
        with self.assertRaisesRegex(ValueError, 'closure|source|depend'):
            self.audit()

    def test_complete_fixed_source_and_two_build_closure_is_verified(self):
        result = self.audit()
        self.assertTrue(result['verified'])
        self.assertTrue(result['real_build_closure_verified'])
        self.assertEqual(result['git_source_files'], 23)
        self.assertEqual(result['builds_verified'], 2)
        self.assertEqual((result['image_decodes'], result['matcher_calls']), (0, 0))

    def test_build_rejects_each_missing_support_or_core_and_extra_dependency(self):
        original = copy.deepcopy(self.builds['capture']['source_files'])
        for suffix in ('line2Dup.h', 'record.hpp', 'trace_io.hpp',
                       'capture_hook.hpp', 'capture_adapter.cpp'):
            self.builds['capture']['source_files'] = [p for p in original if not p['path'].endswith('/'+suffix)]
            self.save_build('capture')
            with self.assertRaises(ValueError):
                self.audit()
        self.builds['capture']['source_files'] = original+[copy.deepcopy(original[0])]
        self.save_build('capture')
        with self.assertRaises(ValueError):
            self.audit()

    def test_protocol_cannot_omit_a_required_source_pin(self):
        original = copy.deepcopy(self.protocol['pins'])
        for suffix in ('/captured/line2Dup_search.hpp', 'author_sources/capture_source.py'):
            self.protocol['pins'] = [p for p in original if not p['path'].endswith(suffix)]
            self.generic.repin_protocol()
            with self.assertRaises(ValueError):
                self.audit()

    def test_build_recipe_cannot_change_flags_core_adapter_or_executable(self):
        original = self.builds['capture']['command']
        for replacement in (
                [[v.replace('-O3', '-O0') for v in command] for command in original],
                [[v.replace('-DSBM_CAPTURE=1', '-DSBM_CAPTURE=0') for v in command] for command in original],
                [[v.replace('captured/line2Dup.cpp', 'original/line2Dup.cpp').replace(
                    'captured\\line2Dup.cpp', 'original\\line2Dup.cpp') for v in command] for command in original],
                [original[0]+['-ffast-math'], *original[1:]],
                [*original[:-1], original[-1][:-1]+[str(self.out/'reference.exe')]],
                [[v.replace('-MD', '-MMD') for v in command] for command in original],
                [[v.replace('adapter.d', 'core.d') for v in command] for command in original]):
            self.builds['capture']['command'] = replacement
            self.save_build('capture')
            with self.assertRaises(ValueError):
                self.audit()

    def test_source_manifest_cannot_hide_changed_git_payload_or_seam(self):
        path = self.snapshot/'captured/line2Dup_matches.hpp'
        path.write_bytes(path.read_bytes()+b'changed helper')
        # Re-pin every declared source and the build, so a generic pin auditor
        # would accept it. Exact fixed-Git verification must still reject.
        for pin in self.protocol['pins']:
            if pin['path'] == path.relative_to(self.root).as_posix():
                pin.update(metadata(self.root, path))
        for entry in self.builds['capture']['source_files']:
            if entry['path'] == path.relative_to(self.root).as_posix():
                entry.update(metadata(self.root, path))
        self.save_build('capture')
        with self.assertRaisesRegex(ValueError, 'Git|source|snapshot|helper'):
            self.audit()

    def test_changed_author_support_is_not_accepted_as_snapshot_source(self):
        path = self.snapshot/'support/trace_io.hpp'
        path.write_bytes(b'changed support')
        for pin in self.protocol['pins']:
            if pin['path'] == path.relative_to(self.root).as_posix():
                pin.update(metadata(self.root, path))
        for role in ('capture', 'reference'):
            for entry in self.builds[role]['source_files']:
                if entry['path'] == path.relative_to(self.root).as_posix():
                    entry.update(metadata(self.root, path))
            self.save_build(role)
        with self.assertRaises(ValueError):
            self.audit()

    def test_missing_or_changed_runtime_compiler_and_executable_rejected(self):
        for key in ('runtimes', 'compiler', 'executable'):
            built = self.builds['reference']
            old = copy.deepcopy(built[key])
            if key == 'runtimes':
                built[key] = built[key][:-1]
            else:
                built[key]['sha256'] = '0'*64
            self.save_build('reference')
            with self.assertRaises(ValueError):
                self.audit()
            built[key] = old
        self.save_build('reference')

    def test_failed_or_unbound_build_manifest_rejected(self):
        for key, value in (('passed', False), ('compile_exit', 1),
                           ('sources_unchanged', False), ('role', 'capture'),
                           ('source_manifest_sha256', '0'*64)):
            old = self.builds['reference'][key]
            self.builds['reference'][key] = value
            self.save_build('reference')
            with self.assertRaises(ValueError):
                self.audit()
            self.builds['reference'][key] = old
        self.save_build('reference')


if __name__ == '__main__':
    unittest.main()
