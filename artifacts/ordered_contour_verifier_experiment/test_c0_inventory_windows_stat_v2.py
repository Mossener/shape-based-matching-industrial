"""Windows file-stamp regression using only self-created temporary files.

Delivered unexecuted against the V2 copy of V1's faulty cross-API ctime stamp.
The coordinator must retain actual RED before changing the implementation.
No dataset, real input payload, image, bank, raw candidate or native call.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

import prepare_c0_payload_inventory_v2 as inventory

HERE = Path(__file__).absolute().parent


@unittest.skipUnless(os.name == 'nt', 'Windows stat/fstat regression')
class WindowsFileStampTests(unittest.TestCase):
    def temporary_directory(self):
        return tempfile.TemporaryDirectory(prefix='inventory_stamp_v2_', dir=HERE)

    def test_regular_file_with_mtime_different_from_birth_is_hashed(self):
        with self.temporary_directory() as directory:
            path = Path(directory) / 'literal.txt'
            payload = b'Only this literal temporary fixture is hashed.\n'
            path.write_bytes(payload)
            original = os.stat(path)
            self.assertTrue(hasattr(original, 'st_birthtime_ns'),
                            'Runtime must expose explicit Windows birth time')
            # Reproduce the actual estimate failure's precondition without
            # sleeps, images or external data. Birth time remains unchanged.
            os.utime(path, ns=(original.st_atime_ns,
                               original.st_birthtime_ns - 30000000000))
            changed = os.lstat(path)
            self.assertNotEqual(changed.st_mtime_ns, changed.st_birthtime_ns)
            expected_stamp = inventory.stamp(changed)
            # A normal unchanged regular file must succeed through the public
            # inspector, not merely through a reimplemented stamp comparison.
            try:
                actual, captured = inventory.inspect_file(
                    path, capture=True, expected_stamp=expected_stamp)
            except ValueError as error:
                self.fail('Unchanged literal regular file was rejected: ' + str(error))
            self.assertEqual(captured, payload)
            self.assertEqual(actual, dict(path=str(path), bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest()))

    def test_replacement_after_preflight_is_rejected(self):
        with self.temporary_directory() as directory:
            path, replacement = Path(directory) / 'literal.txt', Path(directory) / 'replacement.txt'
            path.write_bytes(b'AAAA')
            expected_stamp = inventory.stamp(os.lstat(path))
            replacement.write_bytes(b'BBBB')
            os.replace(replacement, path)
            self.assertNotEqual(inventory.stamp(os.lstat(path)), expected_stamp)
            with self.assertRaisesRegex(ValueError, 'Input changed since preflight'):
                inventory.inspect_file(path, expected_stamp=expected_stamp)

    def test_size_change_after_preflight_is_rejected(self):
        with self.temporary_directory() as directory:
            path = Path(directory) / 'literal.txt'
            path.write_bytes(b'AAAA')
            expected_stamp = inventory.stamp(os.lstat(path))
            path.write_bytes(b'AAAA plus additional bytes')
            self.assertNotEqual(os.lstat(path).st_size, expected_stamp[2])
            with self.assertRaisesRegex(ValueError, 'Input changed since preflight'):
                inventory.inspect_file(path, expected_stamp=expected_stamp)


if __name__ == '__main__':
    unittest.main()
