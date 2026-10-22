"""Synthetic standard-library gzip/manifest corruption tests, written first."""
import copy
import gzip
import hashlib
import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.find_spec("pool_stream")
if SPEC is not None:
    import pool_stream


class Availability(unittest.TestCase):
    def test_independent_stream_parser_exists(self):
        self.assertIsNotNone(SPEC, "independent pool_stream is missing")


@unittest.skipIf(SPEC is None, "missing parser; availability is the RED")
class StreamLiterals(unittest.TestCase):
    def fixture(self, directory):
        masks = [bytes([255]*169), bytes([1]*81)]
        candidates = [b"".join(struct.pack("<IiiBII",i,2+i,2,i,0x3F800000,0x7FC01234+i)
                               for i in range(5)), b""]
        payloads, members, entries = [], [], []
        for i in range(2):
            header = {"pool_id":i,"obj":1,"image":0,"angle":0,"scale_bits":0x3F800000,
                      "level":i,"width":13 if i==0 else 9,"height":13 if i==0 else 9,
                      "K":32 if i==0 else 16,"N":5 if i==0 else 0,
                      "mask_len":len(masks[i]),"candidate_len":len(candidates[i])}
            packed = struct.pack("<8sIIIiIIIIIIQQ", b"RGBPOOL1", *header.values())
            payload = packed+masks[i]+candidates[i]
            compressed = gzip.compress(payload,mtime=0)
            entries.append({"pool_id":i,"offset":sum(map(len,members)),"compressed_bytes":len(compressed),
                            "compressed_sha256":hashlib.sha256(compressed).hexdigest(),
                            "payload_bytes":len(payload),"payload_sha256":hashlib.sha256(payload).hexdigest(),
                            "mask_sha256":hashlib.sha256(masks[i]).hexdigest(),
                            "candidate_sha256":hashlib.sha256(candidates[i]).hexdigest(),"header":header})
            payloads.append(payload)
            members.append(compressed)
        joined = b"".join(members)
        (directory/"shard_00000.pools.gz").write_bytes(joined)
        shard = {"path":"shard_00000.pools.gz","bytes":len(joined),
                 "sha256":hashlib.sha256(joined).hexdigest(),"logical_bytes":sum(map(len,payloads)),
                 "pool_ids":[0,1],"members":entries}
        manifest = {"schema":"rgb_pool_shards_v1","pool_count":2,"shard_count":1,
                    "physical_bytes":len(joined),"logical_bytes":shard["logical_bytes"],"shards":[shard]}
        return manifest,members,payloads

    def verify(self, directory, manifest, expected=(0,1)):
        return list(pool_stream.iter_verified_pools(directory,manifest,list(expected)))

    def rewrite(self,directory,manifest,members,payloads=None):
        # Repin physical bytes so tests reach member boundaries/inner hash checks.
        joined = b"".join(members)
        (directory/manifest["shards"][0]["path"]).write_bytes(joined)
        shard = manifest["shards"][0]
        shard.update(bytes=len(joined),sha256=hashlib.sha256(joined).hexdigest())
        manifest["physical_bytes"] = len(joined)
        offset = 0
        for i,member in enumerate(members):
            entry = shard["members"][i]
            entry.update(offset=offset,compressed_bytes=len(member),compressed_sha256=hashlib.sha256(member).hexdigest())
            offset += len(member)
            if payloads is not None:
                entry.update(payload_bytes=len(payloads[i]),payload_sha256=hashlib.sha256(payloads[i]).hexdigest())
        if payloads is not None:
            shard["logical_bytes"] = sum(map(len,payloads))
            manifest["logical_bytes"] = shard["logical_bytes"]

    def test_complete_concatenated_members_and_numeric_audit(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            directory = pathlib.Path(temp)
            manifest,_,_ = self.fixture(directory)
            pools = self.verify(directory,manifest)
            self.assertEqual([p["header"]["pool_id"] for p in pools],[0,1])
            self.assertEqual(len(pools[0]["candidate_payload"]),105)
            self.assertEqual(pools[1]["mask"],bytes([1]*81))
            first = pool_stream.audit_pool(pools[0])
            self.assertEqual(first["P"]["status"],"ok")
            self.assertEqual([c["ordinal"] for c in first["B"]["selected"]],[0,4,2,1,3])
            second = pool_stream.audit_pool(pools[1])
            self.assertEqual(second["P"]["status"],"insufficient_features")
            self.assertEqual(second["B"]["selected"],[])
            claims = {arm:first[arm] for arm in ["P","B"]}
            pool_stream.audit_pool(pools[0],claims)
            claims["B"]["selected"][0]["label"] = 7
            with self.assertRaises(ValueError):
                pool_stream.audit_pool(pools[0],claims)

    def test_missing_shard_omitted_pool_and_incomplete_exhaustion(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            directory=pathlib.Path(temp)
            manifest,_,_=self.fixture(directory)
            missing=copy.deepcopy(manifest)
            missing["shards"][0]["path"]="missing.gz"
            with self.assertRaises(ValueError): self.verify(directory,missing)
            missing=copy.deepcopy(manifest)
            missing["shards"][0]["members"].pop()
            missing["shards"][0]["pool_ids"].pop()
            missing["pool_count"]=1
            with self.assertRaises(ValueError): self.verify(directory,missing)
            with self.assertRaises(ValueError): self.verify(directory,manifest,(0,))
            # Consumers must exhaust before acceptance: successful next() is not a final receipt.
            broken=copy.deepcopy(manifest)
            broken["shards"][0]["members"][1]["mask_sha256"]="0"*64
            iterator=pool_stream.iter_verified_pools(directory,broken,[0,1])
            self.assertEqual(next(iterator)["header"]["pool_id"],0)
            with self.assertRaises(ValueError): list(iterator)

    def test_manifest_order_offsets_counts_and_resource_guards(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            directory=pathlib.Path(temp)
            manifest,_,_=self.fixture(directory)
            changes=[("offset",1),("compressed_bytes",0),("payload_bytes",2**30)]
            for key,value in changes:
                wrong=copy.deepcopy(manifest)
                wrong["shards"][0]["members"][1][key]=value
                with self.subTest(key=key),self.assertRaises(ValueError): self.verify(directory,wrong)
            for key,value in [("pool_count",1),("shard_count",2),("physical_bytes",2**32+1),
                              ("logical_bytes",2**35+1)]:
                wrong=copy.deepcopy(manifest); wrong[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError): self.verify(directory,wrong)
            wrong=copy.deepcopy(manifest); wrong["shards"][0]["bytes"]=64*1024*1024+1
            with self.assertRaisesRegex(ValueError,"shard physical bytes"): self.verify(directory,wrong)
            wrong=copy.deepcopy(manifest); wrong["physical_bytes"]=2**32+1
            with self.assertRaisesRegex(ValueError,"physical_bytes"): self.verify(directory,wrong)
            wrong=copy.deepcopy(manifest); wrong["shards"][0]["pool_ids"]=[1,0]
            with self.assertRaises(ValueError): self.verify(directory,wrong)
            wrong=copy.deepcopy(manifest); wrong["shards"][0]["path"]="../other.gz"
            with self.assertRaises(ValueError): self.verify(directory,wrong)

    def test_truncation_trailing_data_extra_member_and_crc(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            directory=pathlib.Path(temp)
            original,members,_=self.fixture(directory)
            for replacement in [members[0][:-1],members[0]+b"garbage",members[0]+gzip.compress(b"extra",mtime=0),
                                members[0][:-8]+bytes([members[0][-8]^1])+members[0][-7:]]:
                wrong=copy.deepcopy(original)
                self.rewrite(directory,wrong,[replacement,members[1]])
                with self.assertRaises(ValueError): self.verify(directory,wrong)

    def test_payload_header_mask_candidate_and_compressed_hash_tamper(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            directory=pathlib.Path(temp)
            original,members,payloads=self.fixture(directory)
            for key in ["compressed_sha256","payload_sha256","mask_sha256","candidate_sha256"]:
                wrong=copy.deepcopy(original); wrong["shards"][0]["members"][0][key]="0"*64
                with self.subTest(key=key),self.assertRaises(ValueError): self.verify(directory,wrong)
            for offset in [0,8,64,64+169+20]:
                payload=bytearray(payloads[0]); payload[offset]^=1
                changed=[bytes(payload),payloads[1]]
                wrong=copy.deepcopy(original)
                self.rewrite(directory,wrong,[gzip.compress(changed[0],mtime=0),members[1]],changed)
                with self.subTest(offset=offset),self.assertRaises(ValueError): self.verify(directory,wrong)

    def test_reject_invalid_header_lengths_dimensions_and_level_budget(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            directory=pathlib.Path(temp)
            original,members,payloads=self.fixture(directory)
            for key,value in [("mask_len",168),("candidate_len",104),("width",2049),("height",0),
                              ("level",2),("K",16),("N",2097153),("angle",15),("scale_bits",0x7FC00000)]:
                wrong=copy.deepcopy(original)
                header=wrong["shards"][0]["members"][0]["header"]
                header[key]=value
                data=struct.pack("<8sIIIiIIIIIIQQ",b"RGBPOOL1",*header.values())+payloads[0][64:]
                self.rewrite(directory,wrong,[gzip.compress(data,mtime=0),members[1]],[data,payloads[1]])
                with self.subTest(key=key),self.assertRaises(ValueError): self.verify(directory,wrong)

    def test_native_jsonl_schema_adapter_binds_pins_and_preserves_order(self):
        self.assertTrue(hasattr(pool_stream,"manifest_from_jsonl"),"native JSONL adapter is missing")
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            directory=pathlib.Path(temp)
            manifest,_,_=self.fixture(directory)
            shard=manifest["shards"][0]
            pool_rows=[]
            for entry in shard["members"]:
                h=entry["header"]
                row={"pool_id":h["pool_id"],"object_id":h["obj"],"image_id":h["image"],
                     "angle_degrees":h["angle"],"scale_float32_bits":h["scale_bits"],
                     "level":h["level"],"width":h["width"],"height":h["height"],"K":h["K"],"N":h["N"],
                     "shard":0,"offset":entry["offset"],"compressed_bytes":entry["compressed_bytes"],
                     "logical_bytes":entry["payload_bytes"]}
                row.update({k:entry[k] for k in ["mask_sha256","candidate_sha256","payload_sha256","compressed_sha256"]})
                pool_rows.append(row)
            shard_row={"shard":0,"path":shard["path"],"compressed_bytes":shard["bytes"],
                       "logical_bytes":shard["logical_bytes"],"sha256":shard["sha256"],"pool_ids":[0,1]}
            pool_bytes=("\n".join(json.dumps(row) for row in pool_rows)+"\n").encode()
            shard_bytes=(json.dumps(shard_row)+"\n").encode()
            (directory/"pools.jsonl").write_bytes(pool_bytes)
            (directory/"shards.jsonl").write_bytes(shard_bytes)
            pool_pin=hashlib.sha256(pool_bytes).hexdigest()
            shard_pin=hashlib.sha256(shard_bytes).hexdigest()
            converted=pool_stream.manifest_from_jsonl(directory,pool_pin,shard_pin)
            self.assertEqual(len(self.verify(directory,converted)),2)
            with self.assertRaises(ValueError): pool_stream.manifest_from_jsonl(directory,"0"*64,shard_pin)
            reversed_bytes=("\n".join(json.dumps(row) for row in reversed(pool_rows))+"\n").encode()
            (directory/"pools.jsonl").write_bytes(reversed_bytes)
            with self.assertRaises(ValueError):
                pool_stream.manifest_from_jsonl(directory,hashlib.sha256(reversed_bytes).hexdigest(),shard_pin)


if __name__=="__main__":
    unittest.main(verbosity=2)
