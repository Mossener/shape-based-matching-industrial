"""Small real subprocess fault tests; no dataset, native training or matcher."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import execution_guard as g

class GuardTest(unittest.TestCase):
    def run_case(self,code,**limits):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);native=root/'native';execution=root/'execution'
        command=[sys.executable,'-c',code,str(native)]
        result=g.run_guarded(command,dict(os.environ),root,native,execution,**limits)
        return root,result
    def test_complete_and_zero_failure(self):
        root,r=self.run_case("import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.mkdir();(p/'ok.txt').write_text('ok');print('done')")
        self.assertTrue(r['passed']);self.assertEqual(r['exit_code'],0)
        self.assertEqual((root/'native/ok.txt').read_text(),'ok')
        self.assertTrue((root/'execution/guard_receipt.json').exists())
    def test_wall_guard_retains_partial(self):
        root,r=self.run_case("import pathlib,sys,time;p=pathlib.Path(sys.argv[1]);p.mkdir();(p/'partial').write_text('keep');time.sleep(10)",maximum_seconds=.3)
        self.assertFalse(r['passed']);self.assertEqual(r['reason'],'wall_time_ceiling')
        self.assertEqual((root/'native/partial').read_text(),'keep')
    def test_peak_memory_guard(self):
        _,r=self.run_case("import time;time.sleep(10)",maximum_rss_bytes=1)
        self.assertFalse(r['passed']);self.assertEqual(r['reason'],'peak_working_set_ceiling')
    def test_native_output_guard(self):
        root,r=self.run_case("import pathlib,sys,time;p=pathlib.Path(sys.argv[1]);p.mkdir();(p/'large').write_bytes(b'x'*20000);time.sleep(10)",maximum_output_bytes=12000)
        self.assertEqual(r['reason'],'native_output_ceiling');self.assertEqual((root/'native/large').stat().st_size,20000)
    def test_total_output_guard_includes_logs(self):
        root,r=self.run_case("import pathlib,sys,time;p=pathlib.Path(sys.argv[1]);p.mkdir();(p/'data').write_bytes(b'x'*7000);print('z'*7000,flush=True);time.sleep(10)",maximum_output_bytes=12000)
        self.assertEqual(r['reason'],'combined_output_ceiling');self.assertTrue((root/'native/data').exists())
    def test_disk_preflight_no_process(self):
        root,r=self.run_case("raise RuntimeError('must never launch')",minimum_free_bytes=1<<100)
        self.assertFalse(r['started']);self.assertEqual(r['reason'],'insufficient_free_disk')
        self.assertFalse((root/'execution/stdout.txt').exists())
    def test_nonzero_exit_is_incomplete(self):
        _,r=self.run_case("raise SystemExit(7)")
        self.assertFalse(r['passed']);self.assertEqual(r['reason'],'process_exit_nonzero');self.assertEqual(r['exit_code'],7)
    def test_existing_output_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);native=root/'native';native.mkdir()
            with self.assertRaises(ValueError):g.run_guarded([sys.executable,'-c','pass'],dict(os.environ),root,native,root/'exec')

if __name__=='__main__':unittest.main(verbosity=2)
