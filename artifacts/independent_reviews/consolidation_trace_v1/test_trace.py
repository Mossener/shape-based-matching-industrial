import struct
import unittest

from audit_trace import numeric_v11, parse


class TraceAudit(unittest.TestCase):
    def test_minimum_representative_and_all_fields(self):
        records = [(1, 2, 8, 0x3f800000, b'B'), (1, 2, 3, 0x3f800000, b'B'),
                   (1, 2, 4, 0x3f800001, b'B'), (1, 2, 3, 0x3f800000, b'A\0'),
                   (-1, 2, 3, 0x3f800000, b'A\0')]
        self.assertEqual(numeric_v11(records), [records[2], records[4], records[3], records[1]])

    def test_negative_numeric_order(self):
        rows = [(0, 0, 0, 0xbf800000, b'a'), (0, 0, 1, 0x3f800000, b'a')]
        self.assertEqual(numeric_v11(rows), rows[::-1])

    def test_zero_is_explicitly_unsupported(self):
        for bits in (0, 0x80000000, 0x7f800000, 0x7fc00001):
            with self.assertRaises(ValueError):
                numeric_v11([(0, 0, 0, bits, b'a')])

    def test_binary_literal(self):
        data = b'SBMHASH1'+struct.pack('<IIQQ', 1, 0x01020304, 1, 0)
        data += struct.pack('<iiiIQ', -2, 7, -3, 0x3f800001, 3)+b'A\0B'
        self.assertEqual(parse(data), [[(-2, 7, -3, 0x3f800001, b'A\0B')], []])
        for bad in [data[:-1], data+b'x', data[:8]+b'\0'*24, b'x'+data[1:]]:
            with self.assertRaises(ValueError):
                parse(bad)


if __name__ == '__main__':
    unittest.main()
