"""Fresh synthetic stream/corruption tests plus pinned native-writer byte check."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SOURCES=["numeric_oracle.py","pool_stream.py","test_numeric_oracle.py","test_pool_stream.py",
         "run_selftest.py","run_pack_selftest.py","README.md","STREAM_SCHEMA.md"]
WRITER_PINS={"pools.jsonl":"d7d435f3434bda03be0bd8dcfac79d2b5e7ff70a8d1d255bf9acac4e68790463",
             "shards.jsonl":"d9358674f039595a333879a917a7f13b5822b873d833c8d7854e3367fa88fec9"}
MUTANTS=[
    ("ignore_frozen_pool_order","declared_ids!=expected_pool_ids or ","",
     "StreamLiterals.test_missing_shard_omitted_pool_and_incomplete_exhaustion"),
    ("ignore_mask_hash",'_hash_bytes(mask,entry["mask_sha256"],"mask")','pass',
     "StreamLiterals.test_payload_header_mask_candidate_and_compressed_hash_tamper"),
    ("ignore_embedded_member","if decoder.unused_data:","if False:",
     "StreamLiterals.test_truncation_trailing_data_extra_member_and_crc"),
    ("ignore_physical_resource_limit","MAX_PHYSICAL = 4*1024**3","MAX_PHYSICAL = (1<<64)-1",
     "StreamLiterals.test_manifest_order_offsets_counts_and_resource_guards"),
]


def pin(path):
    data=path.read_bytes()
    return {"path":str(path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}


def invoke(directory,label,modules):
    command=[sys.executable,"-B","-m","unittest","-v"]+modules
    run=subprocess.run(command,cwd=directory,capture_output=True,text=True,
                       env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1"))
    out,err=directory/(label+".stdout.txt"),directory/(label+".stderr.txt")
    out.write_text(run.stdout,encoding="utf-8"); err.write_text(run.stderr,encoding="utf-8")
    return {"command":command,"cwd":str(directory),"exit_code":run.returncode,"stdout":pin(out),"stderr":pin(err)},run


def main():
    if len(sys.argv)!=2:
        print("usage: python run_pack_selftest.py path/to/packing/run_green_20261022_a/data/ok",file=sys.stderr)
        return 2
    writer=Path(sys.argv[1]).resolve()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence=HERE/"evidence"/(stamp+"_stream")
    snapshot=evidence/"source_snapshot"
    snapshot.mkdir(parents=True,exist_ok=False)
    before={name:pin(HERE/name) for name in SOURCES}
    for name in SOURCES: shutil.copyfile(HERE/name,snapshot/name)
    green,run=invoke(snapshot,"green",["test_numeric_oracle","test_pool_stream"])
    source=(snapshot/"pool_stream.py").read_text(encoding="utf-8")
    reds=[]
    for name,needle,replacement,test in MUTANTS:
        if source.count(needle)!=1: raise RuntimeError("mutation anchor not unique: "+name)
        target=evidence/("mutant_"+name); target.mkdir()
        for filename in ("numeric_oracle.py","test_pool_stream.py"): shutil.copyfile(snapshot/filename,target/filename)
        (target/"pool_stream.py").write_text(source.replace(needle,replacement,1),encoding="utf-8")
        record,mutant_run=invoke(target,"red",["test_pool_stream."+test])
        record.update(name=name,source=pin(target/"pool_stream.py"),
                      detected=mutant_run.returncode==1 and "FAIL:" in mutant_run.stderr and "ERROR:" not in mutant_run.stderr)
        reds.append(record)
    sys.path.insert(0,str(snapshot))
    import pool_stream
    import numeric_oracle
    writer_before={name:pin(writer/name) for name in WRITER_PINS}
    manifest=pool_stream.manifest_from_jsonl(writer,WRITER_PINS["pools.jsonl"],WRITER_PINS["shards.jsonl"])
    observations=[]
    for pool in pool_stream.iter_verified_pools(writer,manifest,[0,1]):
        expected={"pool_id":len(observations),"obj":1,"image":7,"angle":30,"scale_bits":0x3F800000,
                  "level":0,"width":7,"height":5,"K":32,"N":1,"mask_len":35,"candidate_len":21}
        if pool["header"]!=expected: raise ValueError("writer literal header changed")
        observed={"header":pool["header"],"mask_hex":pool["mask"].hex(),
                  "candidates":[c.__dict__ for c in numeric_oracle.decode_candidates(pool["candidate_payload"])],
                  "domain_or_selection_audited":False}
        observations.append(observed)
    writer_files=writer_before.copy()
    for shard in manifest["shards"]: writer_files[shard["path"]]=pin(writer/shard["path"])
    writer_after={name:pin(writer/name) for name in WRITER_PINS}
    after={name:pin(HERE/name) for name in SOURCES}
    passed=run.returncode==0 and all(r["detected"] for r in reds) and before==after and writer_before==writer_after
    receipt={"schema":"independent_pool_stream_selftest_v1","utc":stamp,"all_checks_passed":passed,
             "native_calls":0,"image_reads":0,"bank_reads":0,"synthetic_only":True,
             "interpreter":{"path":sys.executable,"version":sys.version,"pin":pin(Path(sys.executable))},
             "sources_before":before,"sources_after":after,"source_snapshots":[pin(snapshot/n) for n in SOURCES],
             "green":green,"mutant_red":reds,"writer_synthetic_files":writer_files,"writer_observations":observations,
             "writer_manifest_pins_unchanged":writer_before==writer_after,"source_pins_unchanged":before==after,
             "limits":["No real training/audit execution","No pixel candidate completeness proof",
                       "No cross-layer mask/crop/bank/full schedule acceptance",
                       "Original native literal pins were observed and fixed before this cross-check; not a historical acquisition proof"]}
    path=evidence/"RECEIPT.json"; path.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":passed,"receipt":str(path),"mutants_detected":sum(r["detected"] for r in reds),
                      "native_writer_pools_independently_parsed":len(observations)}))
    return 0 if passed else 1


if __name__=="__main__": raise SystemExit(main())
