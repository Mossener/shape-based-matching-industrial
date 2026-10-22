"""Pure policy for the separately authorized whole-API runner.

No compiler/native calls and no filesystem reads on import. Scope complete
catalogs before a caller hashes any image, SMD, template-bank or trace bytes.
"""
import csv
import hashlib
import io
import math
from pathlib import Path
import re
import sys

from generate_sources import safe_relative
from output_contract import FIXTURES, SCHEDULE_FIELDS

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from standalone_contract import parse_depfile

TIMING_FIELDS=("call_id","fixture","phase","round","position","variant","output_file","output_bytes",
               "record_count","api_wall_ms","has_internal_timing","internal_search_ms","internal_total_ms")
CORRECTNESS_FIELDS=("call_id","stage","route","variant","input","threads","flags","pass","repeat","worker","step",
                    "output_file","output_bytes","record_count","api_wall_ms","has_internal_timing",
                    "internal_search_ms","internal_total_ms")
COMPARISON_FIELDS=("comparison_id","actual_call_id","expected_call_id","full_ordered_equal","first_mismatch")
INTEGER_FIELDS={"call_id","round","position","threads","flags","pass","repeat","worker","step",
                "output_bytes","record_count"}
CLOCK_FIELDS={"api_wall_ms","internal_search_ms","internal_total_ms"}


def require(ok,message):
    if not ok:raise ValueError(message)


def checked_output(build_root,requested,cpu_granted):
    require(cpu_granted is True,"Explicit root CPU slot is required before output validation/creation")
    root=Path(build_root).resolve();output=Path(requested).resolve()
    require(output!=root and output.is_relative_to(root),"Output must be a contained build child")
    require(not output.exists(),"Fresh output required; preserve prior evidence")
    return output


def checked_manifest(here,requested):
    root=Path(here).resolve();path=Path(requested).resolve()
    require(path.parent==root and re.fullmatch(r"FULL_API_SOURCE_MANIFEST(?:_v[1-9][0-9]*)?\.json",path.name) is not None,
            "Direct versioned full-API source manifest required")
    return path


def fixture_catalog(manifest,include_private):
    require(manifest["common_names"]==list(FIXTURES),"Fixed common25 membership/order differs")
    common={"LED/%d.bmp"%i:"image" for i in range(1,9)}
    common.update({"LED/ku.smd":"bank","test/case1/test.png":"image","test/case1/test_templ.yaml":"bank",
                   "datasets/tless_train_f32/templates_tless_object_1.yml.gz":"bank",
                   "datasets/tless_tiny/index.json":"metadata"})
    for name in FIXTURES[9:]:
        scene,image=name[len("tiny_s"):].split("_i")
        common["datasets/tless_tiny/test_primesense/%06d/rgb/%06d.png"%(int(scene),int(image))]="image"
    private={prefix+"/"+name:"private_smd" if name.endswith(".smd") else "private_image"
             for prefix in ("artifacts/magnet_match/build/input","磁片")
             for name in ["M%02d.bmp"%i for i in range(1,8)]+["moban.smd"]}
    # Validate both full declared scopes even when this stage selects common.
    selected=[]
    for field,wanted in (("common_input_pins",common),("private_input_pins",private)):
        rows=manifest[field]
        require(type(rows) is list and len(rows)==len(wanted),"Fixed fixture catalog budget differs")
        seen=set()
        for item in rows:
            require(type(item) is dict and set(item)=={"path","bytes","sha256","role"},"Fixture pin schema differs")
            name=item["path"];safe_relative(name)
            require(name in wanted and name not in seen and item["role"]==wanted[name],"Unexpected/duplicate fixture path or role")
            require(type(item["bytes"]) is int and item["bytes"]>=0,"Fixture byte count must be nonnegative int")
            require(type(item["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}",item["sha256"]) is not None,
                    "Canonical fixture SHA256 required")
            seen.add(name)
        if field=="common_input_pins" or include_private:selected.extend(rows)
    return selected


def parse_dependencies(data,directory,target):
    prefix=(target+":").encode("ascii")
    require(type(data) is bytes and data.startswith(prefix),"Dependency target differs")
    return parse_depfile(b"actual_match_contract.o:"+data[len(prefix):],directory)


def integer(value,nonnegative=False):
    require(type(value) is str and re.fullmatch(r"(?:0|-?[1-9][0-9]*)",value) is not None,"Canonical decimal integer required")
    result=int(value)
    require(not nonnegative or result>=0,"Nonnegative integer required")
    return result


def boolean(value):
    require(value in ("0","1"),"Native boolean must be0/1")
    return value=="1"


def table(raw,fields):
    require(type(raw) is bytes and b"\0" not in raw,"CSV bytes required")
    reader=csv.reader(io.StringIO(raw.decode("utf-8"),newline=""),strict=True)
    require(next(reader,None)==list(fields),"Native CSV fields differ")
    output=[]
    for row in reader:
        require(len(row)==len(fields),"Native CSV row width differs")
        output.append(dict(zip(fields,row)))
    return output


def parse_calls(raw,timing):
    fields=TIMING_FIELDS if timing else CORRECTNESS_FIELDS
    rows=table(raw,fields)
    for row in rows:
        for name in fields:
            if name in INTEGER_FIELDS:row[name]=integer(row[name])
            elif name in CLOCK_FIELDS:
                require(row[name] and row[name].strip()==row[name],"Canonical clock value required")
                value=float(row[name]);require(math.isfinite(value) and value>=0,"Nonfinite/negative timing rejected")
                row[name]=value
            elif name=="has_internal_timing":row[name]=boolean(row[name])
    return rows


def parse_comparisons(raw):
    rows=table(raw,COMPARISON_FIELDS)
    for row in rows:
        for field in COMPARISON_FIELDS[:3]:row[field]=integer(row[field],True)
        row["full_ordered_equal"]=boolean(row["full_ordered_equal"])
        row["first_mismatch"]=None if row["first_mismatch"]=="" else integer(row["first_mismatch"],True)
        require(row["full_ordered_equal"]==(row["first_mismatch"] is None),"Native equality/mismatch fields disagree")
    return rows


def enrich_calls(rows,read_output):
    for row in rows:
        require(type(row["call_id"]) is int and row["call_id"]>=0 and
                row["output_file"]=="outputs/call_%06d.bin"%row["call_id"],"Canonical output call identity required")
    result=[]
    for row in rows:
        raw=read_output(row["output_file"])
        require(type(raw) is bytes and type(row["output_bytes"]) is int and len(raw)==row["output_bytes"],"Output byte size differs")
        result.append(dict(row,output_sha256=hashlib.sha256(raw).hexdigest()))
    return result
