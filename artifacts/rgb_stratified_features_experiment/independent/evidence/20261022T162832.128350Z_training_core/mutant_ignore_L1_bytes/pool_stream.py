"""Strict bounded numeric gzip-member parser, independent of acquisition code.

Only consume numeric payloads. A generator must be fully exhausted before any
run acceptance is claimed; successfully reading one pool is not run acceptance.
"""
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numeric_oracle

HEADER = struct.Struct("<8sIIIiIIIIIIQQ")
HEADER_FIELDS = ("pool_id","obj","image","angle","scale_bits","level","width","height","K","N",
                 "mask_len","candidate_len")
MAX_PIXELS = 2_097_152
MAX_CANDIDATES = 2_097_152
MAX_SHARD = 64*1024*1024
MAX_PHYSICAL = 4*1024**3
MAX_LOGICAL = 32*1024**3
MAX_POOL = HEADER.size + MAX_PIXELS + 21*MAX_CANDIDATES
CHUNK = 65536


def _integer(value,low,high,name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid " + name)


def _digest(value,name):
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid SHA256 " + name)


def _hash_bytes(data,expected,name):
    _digest(expected,name)
    if hashlib.sha256(data).hexdigest()!=expected:
        raise ValueError(name + " SHA256 differs")


def _hash_file(stream):
    digest=hashlib.sha256()
    for chunk in iter(lambda:stream.read(CHUNK),b""):
        digest.update(chunk)
    return digest.hexdigest()


def _validate_header(header):
    if not isinstance(header,dict) or set(header)!=set(HEADER_FIELDS):
        raise ValueError("header fields differ from canonical schema")
    for key in HEADER_FIELDS:
        _integer(header[key],-(1<<31) if key=="angle" else 0,
                 (1<<64)-1 if key in ("mask_len","candidate_len") else (1<<32)-1,key)
    if header["obj"] not in (1,2,5,8,12,17) or header["angle"] not in range(0,360,30):
        raise ValueError("object/angle outside frozen experiment")
    if header["scale_bits"] not in (0x3F400000,0x3F800000,0x3FC00000,0x40000000):
        raise ValueError("scale outside frozen experiment")
    if header["level"] not in (0,1) or header["K"] != (32 if header["level"]==0 else 16):
        raise ValueError("level/budget differs from frozen experiment")
    width,height = header["width"],header["height"]
    if not (1<=width<=2048 and 1<=height<=2048 and width*height<=MAX_PIXELS):
        raise ValueError("mask dimensions exceed numeric geometry limits")
    if header["N"]>MAX_CANDIDATES or header["mask_len"]!=width*height or header["candidate_len"]!=21*header["N"]:
        raise ValueError("mask/candidate count or length differs")


def _read_member(stream,entry):
    """Consume exactly one member with bounded compressed and decoded buffers."""
    expected=entry["payload_bytes"]
    _integer(expected,HEADER.size,MAX_POOL,"pool logical bytes")
    remaining=entry["compressed_bytes"]
    _integer(remaining,1,MAX_SHARD,"member compressed bytes")
    decoder=zlib.decompressobj(31)
    compressed_digest=hashlib.sha256()
    payload=bytearray()
    try:
        while remaining:
            chunk=stream.read(min(CHUNK,remaining))
            if not chunk:
                raise ValueError("truncated compressed member")
            remaining-=len(chunk)
            compressed_digest.update(chunk)
            if decoder.eof:
                raise ValueError("trailing bytes after gzip member")
            pending=chunk
            while pending:
                output=decoder.decompress(pending,min(CHUNK,expected-len(payload)+1))
                payload.extend(output)
                if len(payload)>expected:
                    raise ValueError("decompressed member exceeds declared logical bytes")
                if decoder.unused_data:
                    raise ValueError("extra gzip member or trailing bytes inside member extent")
                pending=decoder.unconsumed_tail
        if not decoder.eof:
            raise ValueError("incomplete gzip member/footer")
    except zlib.error as error:
        raise ValueError("gzip decompression or CRC failure") from error
    if len(payload)!=expected:
        raise ValueError("member logical byte count differs")
    _digest(entry["compressed_sha256"],"member compressed")
    if compressed_digest.hexdigest()!=entry["compressed_sha256"]:
        raise ValueError("compressed member SHA256 differs")
    payload=bytes(payload)
    _hash_bytes(payload,entry["payload_sha256"],"member payload")
    unpacked=HEADER.unpack(payload[:HEADER.size])
    if unpacked[0]!=b"RGBPOOL1":
        raise ValueError("invalid pool magic")
    header=dict(zip(HEADER_FIELDS,unpacked[1:]))
    _validate_header(header)
    if header!=entry["header"] or header["pool_id"]!=entry["pool_id"]:
        raise ValueError("pool header differs from manifest")
    if expected!=HEADER.size+header["mask_len"]+header["candidate_len"]:
        raise ValueError("pool payload has trailing/missing bytes")
    mask_end=HEADER.size+header["mask_len"]
    mask,candidates=payload[HEADER.size:mask_end],payload[mask_end:]
    _hash_bytes(mask,entry["mask_sha256"],"mask")
    _hash_bytes(candidates,entry["candidate_sha256"],"candidates")
    return {"header":header,"mask":mask,"candidate_payload":candidates,
            "mask_sha256":entry["mask_sha256"],"candidate_sha256":entry["candidate_sha256"]}


def iter_verified_pools(directory,manifest,expected_pool_ids):
    """Yield one verified numeric pool at a time in externally frozen order.

    Manifest schema is documented in STREAM_SCHEMA.md. expected_pool_ids must
    come from the separately frozen training schedule, not the same manifest.
    This parser enforces byte/count bounds, not RSS/time/disk acquisition guards.
    """
    if manifest.get("schema")!="rgb_pool_shards_v1":
        raise ValueError("wrong shard manifest schema")
    for key,maximum in (("physical_bytes",MAX_PHYSICAL),("logical_bytes",MAX_LOGICAL),
                        ("pool_count",(1<<32)-1),("shard_count",(1<<32)-1)):
        _integer(manifest[key],0,maximum,key)
    shards=manifest["shards"]
    if not isinstance(shards,list) or len(shards)!=manifest["shard_count"]:
        raise ValueError("missing/extra shard count")
    if not isinstance(expected_pool_ids,list) or len(set(expected_pool_ids))!=len(expected_pool_ids):
        raise ValueError("expected pool IDs must be a complete unique ordered list")
    for pool_id in expected_pool_ids:
        _integer(pool_id,0,(1<<32)-1,"expected pool ID")
    declared_ids=[]
    declared_physical=declared_logical=0
    names=set()
    for shard in shards:
        name=shard["path"]
        if not isinstance(name,str) or not name or Path(name).name!=name or name in (".","..") or name in names:
            raise ValueError("shard path must be a unique local basename")
        names.add(name)
        _integer(shard["bytes"],1,MAX_SHARD,"shard physical bytes")
        _integer(shard["logical_bytes"],0,MAX_LOGICAL,"shard logical bytes")
        _digest(shard["sha256"],"shard")
        members=shard["members"]
        if not isinstance(members,list) or not members:
            raise ValueError("shard must contain complete pool members")
        offset=logical=0
        ids=[]
        for entry in members:
            _integer(entry["offset"],0,MAX_SHARD,"member offset")
            _integer(entry["compressed_bytes"],1,MAX_SHARD,"member compressed bytes")
            _integer(entry["payload_bytes"],HEADER.size,MAX_POOL,"member logical bytes")
            _integer(entry["pool_id"],0,(1<<32)-1,"pool ID")
            if entry["offset"]!=offset:
                raise ValueError("member offsets are not contiguous")
            _validate_header(entry["header"])
            if entry["header"]["pool_id"]!=entry["pool_id"]:
                raise ValueError("manifest/header pool ID differs")
            if entry["payload_bytes"]!=HEADER.size+entry["header"]["mask_len"]+entry["header"]["candidate_len"]:
                raise ValueError("manifest header logical lengths differ")
            offset+=entry["compressed_bytes"]
            logical+=entry["payload_bytes"]
            ids.append(entry["pool_id"])
        if offset!=shard["bytes"] or logical!=shard["logical_bytes"] or ids!=shard["pool_ids"]:
            raise ValueError("shard member counts/order/byte totals differ")
        declared_ids.extend(ids)
        declared_physical+=shard["bytes"]
        declared_logical+=logical
    if (declared_ids!=expected_pool_ids or len(declared_ids)!=manifest["pool_count"] or
        declared_physical!=manifest["physical_bytes"] or declared_logical!=manifest["logical_bytes"]):
        raise ValueError("run pool order/count/byte totals differ from frozen expectation")
    directory=Path(directory).resolve()
    for shard in shards:
        target=(directory/shard["path"]).resolve()
        if target.parent!=directory:
            raise ValueError("resolved shard is outside numeric pack directory")
        try:
            with target.open("rb") as stream:
                if target.stat().st_size!=shard["bytes"] or _hash_file(stream)!=shard["sha256"]:
                    raise ValueError("shard physical size/hash differs")
                stream.seek(0)
                for entry in shard["members"]:
                    if stream.tell()!=entry["offset"]:
                        raise ValueError("physical stream offset differs")
                    yield _read_member(stream,entry)
                if stream.read(1):
                    raise ValueError("unmanifested trailing shard bytes")
        except OSError as error:
            raise ValueError("missing/unreadable numeric shard") from error


def audit_pool(pool,claims=None,*,classifier=None):
    """Recompute mask strata and complete P/B results without hex duplication."""
    header=pool["header"]
    _validate_header(header)
    mask,payload=pool["mask"],pool["candidate_payload"]
    if len(mask)!=header["mask_len"] or len(payload)!=header["candidate_len"]:
        raise ValueError("pool buffers differ from canonical header lengths")
    _hash_bytes(mask,pool["mask_sha256"],"mask")
    _hash_bytes(payload,pool["candidate_sha256"],"candidates")
    candidates=numeric_oracle.decode_candidates(payload)
    numeric_oracle.validate_real_pool(candidates)
    classifier=numeric_oracle.classify if classifier is None else classifier
    strata=classifier(candidates,mask,header["width"],header["height"])
    result={"pool_id":header["pool_id"],"candidate_sha256":pool["candidate_sha256"],
            "mask_sha256":pool["mask_sha256"],"strata":strata}
    for arm in ("P","B"):
        result[arm]=numeric_oracle.sample(candidates,strata,header["K"],arm)
    if claims is not None:
        if not isinstance(claims,dict) or set(claims)!={"P","B"}:
            raise ValueError("claims require complete P/B result objects")
        for arm in ("P","B"):
            numeric_oracle.verify_claim(result[arm],claims[arm])
    return result


def _unique_json_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key]=value
    return result


def _read_jsonl(path,expected_sha256):
    try:
        if path.stat().st_size>128*1024*1024:
            raise ValueError("numeric manifest exceeds 128MiB")
        data=path.read_bytes()
    except OSError as error:
        raise ValueError("missing/unreadable numeric manifest") from error
    _hash_bytes(data,expected_sha256,path.name)
    rows=[]
    try:
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                raise ValueError("blank manifest row")
            row=json.loads(line,object_pairs_hook=_unique_json_object,
                           parse_constant=lambda value:(_ for _ in ()).throw(ValueError("nonfinite JSON")))
            if not isinstance(row,dict):
                raise ValueError("manifest row must be an object")
            rows.append(row)
    except UnicodeError as error:
        raise ValueError("manifest must be UTF8 JSONL") from error
    return rows


def manifest_from_jsonl(directory,pools_sha256,shards_sha256):
    """Normalize native writer JSONL names without importing its implementation.

    Expected file hashes must be independently pinned by the caller. External
    expected pool IDs are still mandatory for iter_verified_pools acceptance.
    """
    directory=Path(directory)
    pools=_read_jsonl(directory/"pools.jsonl",pools_sha256)
    shard_rows=_read_jsonl(directory/"shards.jsonl",shards_sha256)
    grouped=[[] for _ in shard_rows]
    pool_fields={"pool_id","object_id","image_id","angle_degrees","scale_float32_bits","level",
                 "width","height","K","N","shard","offset","compressed_bytes","logical_bytes",
                 "mask_sha256","candidate_sha256","payload_sha256","compressed_sha256"}
    shard_fields={"shard","path","compressed_bytes","logical_bytes","sha256","pool_ids"}
    for row in pools:
        if set(row)!=pool_fields:
            raise ValueError("native pool JSONL fields differ")
        _integer(row["shard"],0,len(shard_rows)-1,"native shard ID")
        for key in ("width","height","N"):
            _integer(row[key],0,(1<<32)-1,key)
        header={"pool_id":row["pool_id"],"obj":row["object_id"],"image":row["image_id"],
                "angle":row["angle_degrees"],"scale_bits":row["scale_float32_bits"],
                "level":row["level"],"width":row["width"],"height":row["height"],"K":row["K"],"N":row["N"],
                "mask_len":row["width"]*row["height"],"candidate_len":21*row["N"]}
        _validate_header(header)
        entry={"pool_id":row["pool_id"],"offset":row["offset"],"compressed_bytes":row["compressed_bytes"],
               "payload_bytes":row["logical_bytes"],"header":header}
        entry.update({key:row[key] for key in ("mask_sha256","candidate_sha256","payload_sha256","compressed_sha256")})
        grouped[row["shard"]].append(entry)
    shards=[]
    flattened=[]
    for index,row in enumerate(shard_rows):
        if set(row)!=shard_fields or type(row["shard"]) is not int or row["shard"]!=index:
            raise ValueError("native shard JSONL fields/order differ")
        ids=[entry["pool_id"] for entry in grouped[index]]
        if ids!=row["pool_ids"]:
            raise ValueError("native shard pool membership/order differs")
        flattened.extend(ids)
        shards.append({"path":row["path"],"bytes":row["compressed_bytes"],"logical_bytes":row["logical_bytes"],
                       "sha256":row["sha256"],"pool_ids":ids,"members":grouped[index]})
    if flattened!=[row["pool_id"] for row in pools]:
        raise ValueError("native pools JSONL is not in complete shard/member order")
    return {"schema":"rgb_pool_shards_v1","pool_count":len(pools),"shard_count":len(shards),
            "physical_bytes":sum(row["bytes"] for row in shards),
            "logical_bytes":sum(row["logical_bytes"] for row in shards),"shards":shards,
            "manifest_pins":{"pools.jsonl":pools_sha256,"shards.jsonl":shards_sha256}}
