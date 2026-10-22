"""Literal source-anchor checks; no matcher, compiler or dataset access."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from capture_source import CORE_FILES, CORE_REVISION, instrument_core, make_snapshot


class CaptureSourceContracts(unittest.TestCase):
    def source(self, newline=b'\n'):
        return newline.join([
            b'#include "line2Dup.h"', b'#include "line2Dup_matches.hpp"',
            b'namespace line2Dup {', b'void run() {',
            b'    detail::consolidateMatches(matches);', b'}', b'}', b''])

    def test_a_exactly_one_call_redirected_and_only_include_added(self):
        source = self.source()
        generated = instrument_core(source)
        expected = source.replace(
            b'#include "line2Dup_matches.hpp"',
            b'#include "line2Dup_matches.hpp"\n#include "capture_hook.hpp"').replace(
                b'    detail::consolidateMatches(matches);',
                b'    capture_trace::consolidate(matches);')
        self.assertEqual(generated, expected)
        self.assertEqual(source, self.source())

    def test_windows_newlines_preserved(self):
        source = self.source(b'\r\n')
        generated = instrument_core(source)
        self.assertEqual(generated.count(b'\n'), generated.count(b'\r\n'))
        self.assertIn(b'#include "capture_hook.hpp"\r\n', generated)

    def test_missing_duplicate_or_preinstrumented_anchors_rejected(self):
        source = self.source()
        for invalid in (
                source.replace(b'    detail::consolidateMatches(matches);', b''),
                source+b'    detail::consolidateMatches(matches);\n',
                source.replace(b'#include "line2Dup_matches.hpp"', b''),
                source+b'#include "line2Dup_matches.hpp"\n',
                source+b'#include "capture_hook.hpp"\n',
                source+b'capture_trace::consolidate(matches);\n'):
            with self.assertRaises(ValueError):
                instrument_core(invalid)

    def fixture(self):
        data = {name: (name.encode()+b'\x00\xff\r\n') for name in CORE_FILES}
        data['line2Dup.cpp'] = self.source()
        data.update({'MIPP/fixture'+str(i)+'.h': bytes([i, 255, 0, 10])
                     for i in range(16)})

        def blob(value):
            return hashlib.sha1(b'blob '+str(len(value)).encode()+b'\x00'+value).hexdigest()

        inventory = b''.join(b'100644 blob '+blob(value).encode()+b'\t'+
                             name.encode()+b'\x00' for name, value in sorted(data.items()))

        def git(*arguments):
            if arguments == ('rev-parse', '--verify', CORE_REVISION):
                return CORE_REVISION.encode()+b'\n'
            if arguments == ('ls-tree', '-r', '-z', CORE_REVISION):
                return inventory
            if len(arguments) == 2 and arguments[0] == 'show':
                revision, name = arguments[1].split(':', 1)
                self.assertEqual(revision, CORE_REVISION)
                return data[name]
            raise AssertionError(arguments)

        return data, git

    def test_snapshot_preserves_every_git_byte_and_only_changes_core_call(self):
        data, loader = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root/'new_snapshot'
            make_snapshot(root, destination, loader)
            for name, original in data.items():
                self.assertEqual((destination/'original'/name).read_bytes(), original)
                expected = instrument_core(original) if name == 'line2Dup.cpp' else original
                self.assertEqual((destination/'captured'/name).read_bytes(), expected)
            manifest = json.loads((destination/'source_manifest.json').read_bytes())
            self.assertEqual(manifest['core_revision'], CORE_REVISION)
            self.assertEqual(set(manifest['files']), set(data))
            self.assertEqual(manifest['mipp_file_count'], 16)
            for name, original in data.items():
                record = manifest['files'][name]
                self.assertEqual(record['original_sha256'], hashlib.sha256(original).hexdigest())
                generated = (destination/'captured'/name).read_bytes()
                self.assertEqual(record['captured_sha256'], hashlib.sha256(generated).hexdigest())

    def test_snapshot_refuses_existing_directory_before_loading_git(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def forbidden(*arguments):
                raise AssertionError('Must refuse existing destination before Git access')

            with self.assertRaises(ValueError):
                make_snapshot(root, root, forbidden)

    def test_snapshot_rejects_incomplete_mipp_and_changed_git_payload(self):
        _, loader = self.fixture()
        for mutation in ('missing_mipp', 'changed_blob'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)

                def damaged(*arguments):
                    result = loader(*arguments)
                    if mutation == 'missing_mipp' and arguments[0] == 'ls-tree':
                        return b'\x00'.join(part for part in result.split(b'\x00')
                                            if b'MIPP/fixture0.h' not in part)
                    if mutation == 'changed_blob' and arguments[0] == 'show':
                        return result+b'changed'
                    return result

                with self.assertRaises(ValueError):
                    make_snapshot(root, root/'new', damaged)


if __name__ == '__main__':
    unittest.main()
