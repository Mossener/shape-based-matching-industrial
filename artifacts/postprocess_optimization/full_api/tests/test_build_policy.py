"""Build/run boundary and fixed input-catalog policy; written before implementation."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_policy import (checked_output, checked_manifest, fixture_catalog, parse_calls,
                          parse_comparisons, parse_dependencies, enrich_calls)
from output_contract import FIXTURES


class BuildPolicy(unittest.TestCase):
    def test_versioned_manifest_paths_are_direct_and_preserve_old_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            for name in ("FULL_API_SOURCE_MANIFEST.json","FULL_API_SOURCE_MANIFEST_v2.json"):
                self.assertEqual(checked_manifest(root,root/name),root/name)
            for wrong in (root.parent/"FULL_API_SOURCE_MANIFEST.json",root/"nested/FULL_API_SOURCE_MANIFEST.json",
                          root/"FULL_API_SOURCE_MANIFEST_v0.json",root/"other.json"):
                with self.assertRaises(ValueError):checked_manifest(root,wrong)

    def test_cpu_gate_precedes_output_validation_or_creation(self):
        with self.assertRaisesRegex(ValueError,"CPU"):
            checked_output(None,None,False)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            self.assertEqual(checked_output(root,root/"stage",True),root/"stage")
            self.assertFalse((root/"stage").exists())
            for name in (root,root.parent/"outside"):
                with self.assertRaises(ValueError):checked_output(root,name,True)
            (root/"old").mkdir()
            with self.assertRaises(ValueError):checked_output(root,root/"old",True)

    def test_catalog_entire_scope_validated_before_any_input_reader(self):
        common=[("LED/%d.bmp"%i,"image") for i in range(1,9)]
        common += [("LED/ku.smd","bank"),("test/case1/test.png","image"),
                   ("test/case1/test_templ.yaml","bank"),
                   ("datasets/tless_train_f32/templates_tless_object_1.yml.gz","bank"),
                   ("datasets/tless_tiny/index.json","metadata")]
        for fixture in FIXTURES[9:]:
            scene,image=fixture[len("tiny_s"):].split("_i")
            common.append(("datasets/tless_tiny/test_primesense/%06d/rgb/%06d.png"%(int(scene),int(image)),"image"))
        private=[(prefix+"/"+name,"private_smd" if name.endswith(".smd") else "private_image")
                 for prefix in ("artifacts/magnet_match/build/input","磁片")
                 for name in ["M%02d.bmp"%i for i in range(1,8)]+["moban.smd"]]
        def records(items):return [dict(path=p,role=r,bytes=1,sha256="a"*64) for p,r in items]
        value=dict(common_names=list(FIXTURES),common_input_pins=records(common),private_input_pins=records(private))
        self.assertEqual(len(fixture_catalog(value,False)),29)
        self.assertEqual(len(fixture_catalog(value,True)),45)
        for field,bad in (("path","../secret.bmp"),("path","LED/heldout.bmp"),
                          ("role","private_image"),("bytes",True),("bytes",-1),
                          ("sha256","a")):
            changed={**value,"common_input_pins":[dict(x) for x in value["common_input_pins"]]}
            changed["common_input_pins"][0][field]=bad
            with self.assertRaises(ValueError):fixture_catalog(changed,False)
        changed={**value,"private_input_pins":value["private_input_pins"][:-1]}
        with self.assertRaises(ValueError):fixture_catalog(changed,False)

    def test_dependency_target_and_order_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            value=b"unit.o: one.h two\\ file.h one.h\n"
            self.assertEqual(parse_dependencies(value,root,"unit.o"),
                             [root/"one.h",root/"two file.h",root/"one.h"])
            with self.assertRaises(ValueError):parse_dependencies(value,root,"other.o")

    def test_csv_requires_exact_fields_and_strict_numeric_forms(self):
        header="call_id,fixture,phase,round,position,variant,output_file,output_bytes,record_count,api_wall_ms,has_internal_timing,internal_search_ms,internal_total_ms\n"
        row="0,LED_1,cold,0,0,exact_v11,outputs/call_000000.bin,24,0,1.5,1,1,1.2\n"
        parsed=parse_calls((header+row).encode(),True)
        self.assertEqual(parsed[0]["call_id"],0)
        self.assertIs(parsed[0]["has_internal_timing"],True)
        for bad in (row.replace(",1.5,",",nan,"),row.replace(",1.5,",",-1,"),
                    row.replace("0,LED_1","00,LED_1"),row.replace(",1,1,1.2",",true,1,1.2"),
                    row.rstrip()+",extra\n"):
            with self.assertRaises(ValueError):parse_calls((header+bad).encode(),True)
        with self.assertRaises(ValueError):parse_calls((header.replace("call_id","unexpected")+row).encode(),True)

    def test_comparison_csv_rejects_fabricated_booleans(self):
        header="comparison_id,actual_call_id,expected_call_id,full_ordered_equal,first_mismatch\n"
        self.assertEqual(parse_comparisons((header+"0,1,0,1,\n").encode()),
                         [dict(comparison_id=0,actual_call_id=1,expected_call_id=0,full_ordered_equal=True,first_mismatch=None)])
        for row in ("0,1,0,true,\n","0,1,0,1,-1\n","0,1,0,1,0\n","0,1,0,0,\n"):
            with self.assertRaises(ValueError):parse_comparisons((header+row).encode())

    def test_archive_pin_enrichment_binds_canonical_identity_before_read(self):
        raw=b"HMOUT001"+bytes(16)
        row=dict(call_id=0,output_file="outputs/call_000000.bin",output_bytes=24)
        readers=[]
        def read(name):readers.append(name);return raw
        result=enrich_calls([row],read)
        self.assertEqual(result[0]["output_sha256"],hashlib.sha256(raw).hexdigest())
        self.assertNotIn("output_sha256",row)
        with self.assertRaises(ValueError):enrich_calls([dict(row,output_file="../private.bmp")],read)
        self.assertEqual(readers,[row["output_file"]])


if __name__=="__main__":unittest.main()
