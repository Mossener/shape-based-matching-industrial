"""Coordinator-only synthetic phases: a late pin failure must fail the exit.

Mocked payloads deliberately do not run any compiler, graph solver or oracle.
These tests establish control-flow handling, never numerical correctness.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


class CoordinatorExitTests(unittest.TestCase):
    def exercise(self, fail_final):
        source = HERE / 'run_native_oracle_checks_v1.py'
        spec = importlib.util.spec_from_file_location('_exit_coordinator', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='native_coordinator_exit_') as name:
            root = Path(name)
            here, inherited = root / 'here', root / 'inherited'
            here.mkdir()
            inherited.mkdir()
            for filename in ['native_ordered_match.hpp', 'native_ordered_match_batch_v1.cpp',
                    'native_oracle_fixtures_v1.py', 'independent_tiny_oracle.py',
                    'weighted_ordered_match.py', 'NATIVE_BATCH_PROTOCOL_V1.json', 'native_compile_child_v1.py']:
                (here / filename).write_text('synthetic coordinator placeholder\n')
            for filename in ('native_provenance.py', 'execution_guard.py'):
                (inherited / filename).write_text('synthetic coordinator placeholder\n')
            compiler = root / 'tool/bin/g++.exe'
            compiler.parent.mkdir(parents=True)
            (root / 'tool/lib').mkdir()
            for filename in ('libgmpxx.dll.a', 'libgmp.dll.a'):
                (root / 'tool/lib' / filename).write_bytes(b'placeholder')
            def file_pin(path):
                path = Path(path)
                data = path.read_bytes()
                return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            failed = []
            def check_pin(row):
                if fail_final and row['path'] == str(here / 'native_ordered_match.hpp'):
                    failed.append(row['path'])
                    raise ValueError('injected final source stability failure')
                self.assertEqual(file_pin(Path(row['path'])), row)
            provenance = SimpleNamespace(file_pin=file_pin, check_pin=check_pin,
                compiler_tools=lambda *_: ([], []), import_closure=lambda *_: dict(files=[]))
            def run_guarded(command, env, cwd, payload, execution, **limits):
                payload, execution = Path(payload), Path(execution)
                execution.mkdir()
                (execution / 'stdout.txt').write_text('')
                payload.mkdir()
                if 'generate' in command:
                    (payload / 'requests.txt').write_text('placeholder')
                    (payload / 'expected.jsonl').write_text('placeholder')
                    (payload / 'generation.json').write_text(json.dumps(dict(comparisons=25024)))
                elif payload.name == 'payload':
                    (payload / 'native_batch.exe').write_bytes(b'placeholder')
                    (payload / 'compiler_child_result.json').write_text(json.dumps(dict(
                        passed=True, peak_job_committed_memory_bytes=1, compiler_dependency_pins=[])))
                elif 'audit' in command:
                    (payload / 'audit.json').write_text(json.dumps(dict(passed=True, comparisons=25024)))
                return dict(passed=True, exit_code=0)
            guard = SimpleNamespace(run_guarded=run_guarded)
            module.HERE, module.ROOT, module.INHERITED, module.COMPILER = here, root, inherited, compiler
            module.load = lambda name, _: provenance if 'provenance' in name else guard
            with patch.object(sys, 'argv', ['coordinator', 'case']), redirect_stdout(io.StringIO()):
                exit_code = module.main()
            receipt = json.loads((here / 'case/receipt.json').read_bytes())
            if fail_final:
                self.assertEqual(len(failed), 1)
            return exit_code, receipt

    def test_successful_mocked_phases_keep_zero_exit(self):
        code, receipt = self.exercise(False)
        self.assertEqual(code, 0)
        self.assertTrue(receipt['passed'])
        self.assertTrue(receipt['sources_stable'])

    def test_final_pin_failure_cannot_return_zero(self):
        code, receipt = self.exercise(True)
        self.assertFalse(receipt['passed'])
        self.assertFalse(receipt['sources_stable'])
        self.assertNotEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
