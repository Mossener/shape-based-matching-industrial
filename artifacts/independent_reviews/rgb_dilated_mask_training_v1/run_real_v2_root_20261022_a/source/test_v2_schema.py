"""Synthetic training member-schema regression; no real banks or images.

SCHEMA_AUDIT_MODULE=audit reproduces the frozen v1 code in isolation by
compiling its literal membership statements. The default audit_v2 calls the
successor's real helper. Fixtures live only in a TemporaryDirectory.
"""
import ast
import copy
import importlib
import os
from pathlib import Path
import tempfile
import unittest


module = importlib.import_module(os.environ.get('SCHEMA_AUDIT_MODULE', 'audit_v2'))


def membership_checker():
    if hasattr(module, 'validate_training_members'):
        return module.validate_training_members
    # Execute the unchanged v1 membership block, not a rewritten approximation.
    tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8-sig'))
    body = next(n.body for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'audit')
    start = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id == 'training_paths' for t in n.targets))
    stop = next(i for i in range(start + 1, len(body)) if isinstance(body[i], ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == 'banks' for t in body[i].targets))
    wrapper = ast.parse('def validate_training_members(read, train, freeze):\n    pass\n')
    wrapper.body[0].body = copy.deepcopy(body[start:stop])
    ast.fix_missing_locations(wrapper)
    namespace = dict(Path=Path, require=module.require)
    exec(compile(wrapper, str(module.__file__) + ':membership-only', 'exec'), namespace)
    return namespace['validate_training_members']


validate = membership_checker()


class TrainingMemberSchema(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.train = self.root/'run_training_v1'
        self.train.mkdir()
        for name, data in [('training_summary.json', b'{"literal_summary":true}\n'),
                           ('training_audit.json', b'{"literal_runner_validation":true}\n'),
                           ('obj1/template_attempts.csv', b'fixture\n1\n'),
                           ('.gitignore', b'*\n'), ('BANK_FREEZE.json', b'{}\n')]:
            p = self.train/name
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(data)
        self.members = ['training_summary.json', 'training_audit.json', 'obj1/template_attempts.csv']
        self.freeze = {'files': [self.record(self.train/name) for name in self.members]}

    def record(self, p):
        return dict(path=str(p.resolve()), **module.pin(p.read_bytes()))

    def check(self, freeze=None):
        reader = module.Reader(self.root)
        validate(reader, self.train, self.freeze if freeze is None else freeze)
        reader.final_check()
        return reader

    def test_actual_runner_schema_includes_and_binds_training_audit(self):
        try:
            reader = self.check()
        except ValueError as error:
            self.fail('Actual runner member schema was rejected: ' + str(error))
        self.assertIn(str((self.train/'training_audit.json').resolve()), reader.pins)
        self.assertEqual(reader.pins, reader.after_pins)

    def test_existing_audit_must_not_be_omitted_from_frozen_members(self):
        self.freeze['files'] = [r for r in self.freeze['files'] if Path(r['path']).name != 'training_audit.json']
        with self.assertRaises(ValueError):
            self.check()

    def test_audit_file_is_required_even_if_entirely_absent(self):
        (self.train/'training_audit.json').unlink()
        self.freeze['files'] = [r for r in self.freeze['files'] if Path(r['path']).name != 'training_audit.json']
        with self.assertRaises(ValueError):
            self.check()

    def test_bound_audit_corruption_is_rejected(self):
        (self.train/'training_audit.json').write_bytes(b'{"corrupt":true}\n')
        with self.assertRaisesRegex(ValueError, 'SHA/size'):
            self.check()

    def test_post_validation_audit_corruption_is_rejected(self):
        reader = module.Reader(self.root)
        validate(reader, self.train, self.freeze)
        (self.train/'training_audit.json').write_bytes(b'{"later_corrupt":true}\n')
        with self.assertRaisesRegex(ValueError, 'SHA/size'):
            reader.final_check()

    def test_unlisted_nested_training_file_is_rejected(self):
        (self.train/'obj1'/'extra.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_member_is_rejected(self):
        self.freeze['files'].append(dict(self.freeze['files'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.check()

    def test_member_outside_training_directory_is_rejected(self):
        p = self.root/'outside.json'
        p.write_bytes(b'{}')
        self.freeze['files'].append(self.record(p))
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            self.check()

    def test_summary_cannot_be_omitted_either(self):
        self.freeze['files'] = [r for r in self.freeze['files'] if Path(r['path']).name != 'training_summary.json']
        with self.assertRaises(ValueError):
            self.check()


if __name__ == '__main__':
    unittest.main()
