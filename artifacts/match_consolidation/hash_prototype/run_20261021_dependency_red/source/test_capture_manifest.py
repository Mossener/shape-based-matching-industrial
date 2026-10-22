"""Synthetic byte/manifest contracts; no dataset image or matcher access."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from capture_manifest import CORE_REVISION, audit_capture, read_trace


def sha(data):
    return hashlib.sha256(data).hexdigest()


def trace_bytes(inputs, outputs):
    # Independent explicit fixture, not the candidate writer/parser.
    result = b'SBMHASH1'+struct.pack('<IIQQ', 1, 0x01020304,
                                      len(inputs), len(outputs))
    for x, y, score_bits, name, template_id in inputs+outputs:
        result += struct.pack('<iiiIQ', x, y, template_id, score_bits,
                              len(name))+name
    return result


class CaptureManifestContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root/'capture'
        self.out.mkdir()
        self.records = [(-2, 7, 0x42ad0000, b'LED', 19),
                        (-2, 7, 0x42ad0000, b'LED', -4),
                        (2147483647, -2147483648, 0x3f800001,
                         b'near\x00\xffname', 3)]
        self.expected = [self.records[1], self.records[2]]
        self.trace = trace_bytes(self.records, self.expected)
        self.reference = trace_bytes([], self.expected)
        (self.out/'capture.bin').write_bytes(self.trace)
        (self.out/'reference.bin').write_bytes(self.reference)
        pins = []
        for role in ('source', 'image', 'bank', 'config',
                     'capture_build', 'reference_build'):
            name = {'image': 'LED/1.bmp', 'bank': 'LED/ku.smd'}.get(
                role, 'pinned/'+role+'.fixture')
            (self.root/name).parent.mkdir(exist_ok=True)
            data = ('synthetic '+role).encode('ascii')
            (self.root/name).write_bytes(data)
            pins.append(dict(path=name, sha256=sha(data), size_bytes=len(data),
                             role=role))
        self.case = dict(case_id='LED_1', dataset='LED', split='legacy',
                         scenario='legacy', matcher_threshold=75)
        self.protocol = dict(schema_version=1, core_revision=CORE_REVISION,
                             capture_kind='exact_pre_consolidation_v11',
                             reference_kind='uninstrumented_same_core',
                             case=self.case, pins=pins)
        self.protocol_path = self.out/'protocol.json'
        self.write_protocol()
        self.manifest = dict(schema_version=1, core_revision=CORE_REVISION,
                             protocol_sha256=sha(self.protocol_path.read_bytes()),
                             case=self.case,
                             trace=self.metadata('capture.bin', self.trace, 3, 2),
                             reference=self.metadata('reference.bin', self.reference, 0, 2))
        self.manifest_path = self.out/'manifest.json'
        self.write_manifest()

    @staticmethod
    def metadata(name, data, inputs, outputs):
        return dict(path=name, sha256=sha(data), size_bytes=len(data),
                    input_count=inputs, output_count=outputs)

    def write_protocol(self):
        self.protocol_path.write_text(json.dumps(self.protocol)+'\n', encoding='utf-8')

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest)+'\n', encoding='utf-8')

    def audit(self):
        return audit_capture(self.manifest_path, self.protocol_path, self.root)

    def repin_protocol(self):
        self.write_protocol()
        self.manifest['protocol_sha256'] = sha(self.protocol_path.read_bytes())
        self.write_manifest()

    def test_a_corrupted_trace_sha_is_rejected(self):
        # First semantic RED: API stub must not accept changed trace bytes.
        (self.out/'capture.bin').write_bytes(self.trace+b'changed')
        with self.assertRaisesRegex(ValueError, 'trace|SHA|size|byte'):
            self.audit()

    def test_complete_bitwise_input_order_and_output_identity(self):
        parsed = read_trace(self.trace)
        self.assertEqual(parsed['input'], self.records)
        self.assertEqual(parsed['output'], self.expected)
        result = self.audit()
        self.assertTrue(result['verified'])
        self.assertEqual((result['input_count'], result['output_count']), (3, 2))
        self.assertEqual((result['image_decodes'], result['matcher_calls']), (0, 0))
        self.assertFalse(result['performance_measurement'])

    def test_pin_sha_size_and_missing_file_rejected(self):
        for mutation in ('data', 'size', 'missing'):
            with self.subTest(mutation=mutation):
                pin = self.protocol['pins'][0]
                path = self.root/pin['path']
                original = path.read_bytes()
                original_size = pin['size_bytes']
                if mutation == 'data':
                    path.write_bytes(b'x'*len(original))
                elif mutation == 'size':
                    pin['size_bytes'] += 1
                    self.repin_protocol()
                else:
                    path.unlink()
                with self.assertRaises(ValueError):
                    self.audit()
                path.write_bytes(original)
                pin['size_bytes'] = original_size
                self.repin_protocol()

    def test_protocol_hash_case_core_and_kind_mismatch_rejected(self):
        pristine = copy.deepcopy(self.manifest)
        for key, value in (('protocol_sha256', '0'*64), ('core_revision', 'a'*40),
                           ('case', dict(self.case, case_id='LED_2'))):
            self.manifest[key] = value
            self.write_manifest()
            with self.assertRaises(ValueError):
                self.audit()
            self.manifest = copy.deepcopy(pristine)
        self.write_manifest()
        self.protocol['reference_kind'] = 'instrumented_api'
        self.repin_protocol()
        with self.assertRaises(ValueError):
            self.audit()

    def test_metadata_counts_and_reference_input_rejected(self):
        for record, key in (('trace', 'input_count'), ('trace', 'output_count'),
                            ('reference', 'input_count'), ('reference', 'output_count')):
            self.manifest[record][key] += 1
            self.write_manifest()
            with self.assertRaises(ValueError):
                self.audit()
            self.manifest[record][key] -= 1
        different = trace_bytes([self.records[0]], self.expected)
        (self.out/'reference.bin').write_bytes(different)
        self.manifest['reference'] = self.metadata('reference.bin', different, 1, 2)
        self.write_manifest()
        with self.assertRaises(ValueError):
            self.audit()

    def test_score_bits_class_bytes_template_id_and_output_order_rejected(self):
        for changed in (
                [(self.expected[0][0], self.expected[0][1], 0x42ad0001,
                  self.expected[0][3], self.expected[0][4]), self.expected[1]],
                [(*self.expected[0][:3], b'LED\x00', self.expected[0][4]), self.expected[1]],
                [(*self.expected[0][:4], 19), self.expected[1]],
                list(reversed(self.expected))):
            different = trace_bytes([], changed)
            (self.out/'reference.bin').write_bytes(different)
            self.manifest['reference'] = self.metadata('reference.bin', different, 0, 2)
            self.write_manifest()
            with self.assertRaisesRegex(ValueError, 'output|identity|equal'):
                self.audit()

    def test_path_escape_absolute_duplicate_pin_and_missing_role_rejected(self):
        original = copy.deepcopy(self.protocol['pins'])
        for path in ('../outside', str(self.root/'absolute.fixture'),
                     'pinned/../source.fixture', 'pinned\\source.fixture'):
            self.protocol['pins'][0]['path'] = path
            self.repin_protocol()
            with self.assertRaises(ValueError):
                self.audit()
        self.protocol['pins'] = copy.deepcopy(original)+[copy.deepcopy(original[0])]
        self.repin_protocol()
        with self.assertRaises(ValueError):
            self.audit()
        self.protocol['pins'] = original[:-1]
        self.repin_protocol()
        with self.assertRaises(ValueError):
            self.audit()

    def test_trace_path_must_be_a_direct_child_with_distinct_identity(self):
        for path in ('../capture.bin', '/absolute.bin', 'folder/capture.bin',
                     'folder\\capture.bin', 'reference.bin'):
            self.manifest['trace']['path'] = path
            self.write_manifest()
            with self.assertRaises(ValueError):
                self.audit()

    def test_reserved_or_mixed_scenarios_rejected_before_pin_access(self):
        for case in (
                dict(self.case, dataset='tless_expanded'),
                dict(self.case, dataset='tless_tiny', split='heldout',
                     scenario='quality_actual85', matcher_threshold=85, object_id=1),
                dict(self.case, dataset='tless_tiny', split='development',
                     scenario='quality_actual85', matcher_threshold=50, object_id=1),
                dict(self.case, dataset='tless_tiny', split='development',
                     scenario='stress_coarse50', matcher_threshold=50, object_id=25)):
            self.protocol['case'] = case
            self.manifest['case'] = case
            self.repin_protocol()
            with self.assertRaises(ValueError):
                self.audit()

    def tiny_protocol(self):
        image_path = 'datasets/tless_tiny/scene5/development.fixture'
        bank_path = 'datasets/tless_train_f32/templates_tless_object_1.yml.gz'
        for role, relative in (('image', image_path), ('bank', bank_path)):
            pin = next(p for p in self.protocol['pins'] if p['role'] == role)
            data = (self.root/pin['path']).read_bytes()
            (self.root/relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root/relative).write_bytes(data)
            pin['path'] = relative
        metadata = dict(test=[
            dict(scene_id=5, image_id=70, split='development',
                 rgb='scene5/development.fixture'),
            dict(scene_id=5, image_id=71, split='heldout',
                 rgb='scene5/heldout_never_opened.fixture')])
        path = 'datasets/tless_tiny/index.json'
        encoded = json.dumps(metadata).encode()
        (self.root/path).write_bytes(encoded)
        self.protocol['pins'].append(dict(path=path, role='index', sha256=sha(encoded),
                                         size_bytes=len(encoded)))
        case = dict(case_id='tiny_s5_i70', dataset='tless_tiny', split='development',
                    scenario='quality_actual85', matcher_threshold=85, object_id=1)
        self.protocol['case'] = case
        self.manifest['case'] = case
        self.repin_protocol()

    def test_tiny_actual85_and_separate_coarse50_accept_development_only(self):
        self.tiny_protocol()
        self.assertTrue(self.audit()['verified'])
        case = self.protocol['case']
        case['scenario'] = 'stress_coarse50'
        case['matcher_threshold'] = 50
        self.repin_protocol()
        self.assertTrue(self.audit()['verified'])

    def test_tiny_scope_cannot_pin_heldout_path_even_if_label_says_development(self):
        self.tiny_protocol()
        image = next(p for p in self.protocol['pins'] if p['role'] == 'image')
        # This path does not exist. Scope validation must reject the pin before
        # any attempt to open a heldout image, even to hash it.
        image['path'] = 'datasets/tless_tiny/scene5/heldout_never_opened.fixture'
        self.repin_protocol()
        with self.assertRaisesRegex(ValueError, 'scope|development|image identity'):
            self.audit()

    def test_duplicate_json_keys_and_boolean_integer_fields_rejected(self):
        self.manifest_path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(ValueError):
            self.audit()
        self.write_manifest()
        self.manifest['trace']['input_count'] = True
        self.write_manifest()
        with self.assertRaises(ValueError):
            self.audit()

    def test_pinned_bytes_rechecked_after_trace_loading(self):
        import capture_manifest
        original_parser = capture_manifest.read_trace
        calls = []

        def load_then_change(data, *args, **kwargs):
            parsed = original_parser(data, *args, **kwargs)
            if not calls:
                (self.root/self.protocol['pins'][0]['path']).write_bytes(b'changed during read')
            calls.append(1)
            return parsed

        with patch('capture_manifest.read_trace', side_effect=load_then_change):
            with self.assertRaisesRegex(ValueError, 'pin|SHA|size|changed'):
                self.audit()

    def test_trace_malformed_prefix_trailing_nonfinite_and_bounds(self):
        for data in [self.trace[:i] for i in range(len(self.trace))]+[
                self.trace+b'x', b'WRONGMAG'+self.trace[8:],
                self.trace[:8]+struct.pack('<I', 2)+self.trace[12:],
                trace_bytes([(0, 0, 0x7f800000, b'', 0)], []),
                trace_bytes([], [(0, 0, 0xff800000, b'', 0)]),
                trace_bytes([(0, 0, 0x7fc00001, b'', 0)], [])]:
            with self.assertRaises(ValueError):
                read_trace(data)
        for options in (dict(max_records=2), dict(max_class_bytes=2),
                        dict(max_total_bytes=len(self.trace)-1)):
            with self.assertRaises(ValueError):
                read_trace(self.trace, **options)

    def test_empty_zero_and_extreme_finite_records_are_lossless(self):
        self.assertEqual(read_trace(trace_bytes([], [])), {'input': [], 'output': []})
        records = [(0, 0, v, b'', 0) for v in
                   (0, 0x80000000, 1, 0x80000001, 0x7f7fffff, 0xff7fffff)]
        self.assertEqual(read_trace(trace_bytes(records, records)),
                         {'input': records, 'output': records})


if __name__ == '__main__':
    unittest.main()
