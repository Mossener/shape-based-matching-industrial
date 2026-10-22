"""Separately gated full-API build/synthetic, numeric replay, correctness and timing.

Imports perform no image, bank, native-program or Git operation. Every phase
requires an explicit root CPU grant before output validation/creation. Dataset
bytes additionally require the dataset-stage flag; build never reads them.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

from build_policy import (require,checked_output,checked_manifest,fixture_catalog,parse_dependencies,
                          parse_calls,parse_comparisons,enrich_calls,table,integer,boolean)
from generate_sources import BASELINE,CORE,MIPP,HELPER_SHA,candidate_bytes,safe_relative
from output_contract import FIXTURES,decode_output,audit_timing
from source_list import SOURCE_FILES,PREREQUISITES

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BUILD_ROOT=HERE/"build"
MANIFEST=HERE/"FULL_API_SOURCE_MANIFEST.json"
FIXTURE_MANIFEST=HERE/"generated_fixtures/FIXTURE_SOURCE_MANIFEST.json"
FROZEN=ROOT/"artifacts/local_center_optimization/v11_candidate_experiment_v2/baseline"
CAPTURE=ROOT/"artifacts/match_consolidation/hash_prototype/run_20261022_capture_actual85"
BASE_FLAGS=["-std=c++14","-O3","-mssse3","-msse4.1","-Wall","-Wextra","-Wno-sign-compare"]
UNITS=(("exact_v11","exact_v11.cpp",True),("index_reserve","index_reserve.cpp",True),
       ("correctness","correctness.cpp",True),("benchmark","benchmark.cpp",True),
       ("output_binary_contract","tests/output_binary_contract.cpp",False),
       ("fixture_contract","tests/fixture_contract.cpp",False),("replay","replay.cpp",False))
EXES={"correctness":(["exact_v11","index_reserve","correctness"],True,True),
      "benchmark":(["exact_v11","index_reserve","benchmark"],True,True),
      "output_binary_contract":(["output_binary_contract"],False,False),
      "fixture_contract":(["fixture_contract"],False,True),"replay":(["replay"],False,False)}
OMP_ENV={"OMP_NUM_THREADS":"4","OMP_DYNAMIC":"FALSE","OMP_MAX_ACTIVE_LEVELS":"1","OMP_WAIT_POLICY":"PASSIVE"}
RUNTIMES=("libstdc++-6.dll","libgcc_s_seh-1.dll","libwinpthread-1.dll","libgomp-1.dll")
LIMITATION=("Local byte/dependency/import-file provenance; not all compiler helper, startup, linker, OS or "
            "loader reads. Returned U-vector destruction is outside symmetric direct API clocks; old N-vector "
            "destruction is inside the helper. Exact-output performance experiment, no accuracy improvement, "
            "peak-memory or production-adoption claim. Earlier26 allocation fault interceptions do not establish "
            "failure injection inside dynamically linked libstdc++ non-SSO string copies.")


def utc():return datetime.now(timezone.utc).isoformat()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read_json(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def pin(path):
    path=Path(path).resolve(strict=True);require(path.is_file(),"Regular file required: "+str(path))
    raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=sha(raw))
def add(tracked,path):
    item=pin(path);old=tracked.setdefault(item["path"],item);require(old==item,"Repeated pin changed")
    return item
def check(item):require(pin(item["path"])==item,"Pinned file changed: "+item["path"])
def recheck(tracked):
    for item in tracked.values():check(item)
def write_json(path,value):
    with path.open("x",encoding="utf-8",newline="\n") as out:json.dump(value,out,indent=2);out.write("\n")


def verify_sources(expected_sha,tracked,manifest_path=MANIFEST):
    require(re.fullmatch(r"[0-9a-f]{64}",expected_sha or "") is not None,"Root-reviewed source manifest SHA required")
    manifest_path=checked_manifest(HERE,manifest_path)
    manifest_pin=add(tracked,manifest_path);require(manifest_pin["sha256"]==expected_sha,"Source manifest SHA differs")
    value=read_json(manifest_path)
    require(set(value)=={"schema","baseline_commit","sources","prerequisites"} and
            value["schema"]=="whole_api_sources_v1" and value["baseline_commit"]==BASELINE,"Fixed source manifest schema required")
    require([x["relative"] for x in value["sources"]]==list(SOURCE_FILES),"Explicit complete source closure differs")
    for item in value["sources"]:
        path=HERE/safe_relative(item["relative"]);actual=add(tracked,path)
        require(actual["bytes"]==item["bytes"] and actual["sha256"]==item["sha256"],"Prepared source changed: "+item["relative"])
    require([(x["relative"],x["sha256"]) for x in value["prerequisites"]]==list(PREREQUISITES),"Earlier evidence binding differs")
    for item in value["prerequisites"]:
        actual=add(tracked,ROOT/safe_relative(item["relative"]))
        require(actual["sha256"]==item["sha256"] and actual["bytes"]==item["bytes"],"Earlier evidence changed")
    root_origin=read_json(ROOT/PREREQUISITES[1][0]);original_pin=add(tracked,FROZEN/"manifest.json")
    require(root_origin["passed"] is True and root_origin["revision"]==BASELINE and
            root_origin["frozen_manifest"]==original_pin,"Root Git-byte origin binding differs")
    original=read_json(FROZEN/"manifest.json")
    require(original["commit"]==BASELINE and set(original["files"])==set(CORE+MIPP),"Original source allowlist differs")
    for name in CORE+MIPP:
        approved=original["files"][name];actual=add(tracked,FROZEN/safe_relative(name))
        require(actual["sha256"]==approved["sha256"] and actual["bytes"]==approved["bytes"],"Original frozen source changed")
        raw=(FROZEN/name).read_bytes()
        require((HERE/"generated/baseline"/name).read_bytes()==raw,"Baseline copy differs")
        expected=candidate_bytes(raw) if name=="line2Dup.cpp" else raw
        require((HERE/"generated/candidate"/name).read_bytes()==expected,"Candidate exceeds literal two-seam transform")
    require(sha((HERE/"generated/candidate/hash_consolidation.hpp").read_bytes())==HELPER_SHA,"Actual-Match helper changed")
    return manifest_pin


def command(argv,directory,env,name,result,timeout=600):
    outpath,errpath=directory/(name+".stdout.txt"),directory/(name+".stderr.txt")
    record=dict(argv=list(map(str,argv)),cwd=str(directory),started_utc=utc(),exit_code=None)
    result["commands"].append(record)
    try:
        with outpath.open("xb") as out,errpath.open("xb") as err:
            process=subprocess.run(list(map(str,argv)),cwd=directory,env=env,stdin=subprocess.DEVNULL,
                stdout=out,stderr=err,timeout=timeout,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        record["exit_code"]=process.returncode
    except subprocess.TimeoutExpired:
        record["timeout_seconds"]=timeout
        raise
    finally:
        record.update(completed_utc=utc(),stdout=pin(outpath),stderr=pin(errpath))
    print(name+" exit="+str(record["exit_code"]),flush=True)
    require(record["exit_code"]==0,"Native command failed: "+name)
    return record


def environment(compiler,opencv):
    env=dict(os.environ);removed=[]
    for name in ("CPATH","C_INCLUDE_PATH","CPLUS_INCLUDE_PATH","OBJC_INCLUDE_PATH","LIBRARY_PATH",
                 "COMPILER_PATH","GCC_EXEC_PREFIX","COLLECT_GCC_OPTIONS"):
        if name in env:removed.append(name);env.pop(name)
    env["PATH"]=str(compiler.parent)+os.pathsep+str(opencv/"build/bin")+os.pathsep+env.get("PATH","")
    env.update(OMP_ENV)
    return env,dict(stripped_override_names=removed,openmp=OMP_ENV,normal_priority=True,
                    cpu_affinity_changed=False,power_settings_changed=False)


def dependency_scope(paths,allowed,compiler_root,opencv):
    # Scope every discovered path before hashing any discovered dependency.
    for path in paths:
        require((path.is_relative_to(ROOT) and path in allowed) or
                (not path.is_relative_to(ROOT) and (path.is_relative_to(compiler_root) or path.is_relative_to(opencv))),
                "Dependency outside approved source/toolchain scope: "+str(path))


def runtime_closure(exes,compiler,opencv,output,env,tracked,result):
    from standalone_contract import classify_dll
    system_extra={"dwmapi.dll","uxtheme.dll","gdiplus.dll","winspool.drv","avicap32.dll","msvfw32.dll",
                  "vfw32.dll","setupapi.dll","d3d11.dll","dxgi.dll","dxva2.dll","d3d9.dll","wsock32.dll",
                  "mfplat.dll","mfreadwrite.dll","evr.dll","quartz.dll","oleacc.dll"}
    objdump=compiler.parent/"objdump.exe";queue=list(exes);seen=set();copies={};records=[]
    while queue:
        binary=queue.pop(0).resolve()
        if binary in seen:continue
        seen.add(binary);scan=command([objdump,"-p",binary],output,env,"pe_imports_%03d"%len(records),result)
        names=re.findall(r"^\s*DLL Name:\s*(\S+)\s*$",Path(scan["stdout"]["path"]).read_text(encoding="utf-8"),re.MULTILINE)
        require(names,"PE import names missing");entries=[]
        for name in names:
            require(re.fullmatch(r"[A-Za-z0-9_+.-]+\.(?:dll|drv)",name,re.IGNORECASE) is not None and ".." not in name,
                    "Invalid PE import basename")
            lower=name.lower()
            if lower=="libopencv_world4120.dll":source=opencv/"build/bin"/name
            elif lower in RUNTIMES:source=compiler.parent/name
            elif lower in system_extra:
                entries.append(dict(name=name,classification="system_name_only"));continue
            else:
                require(classify_dll(name)=="system_name_only","Unexpected runtime classification")
                entries.append(dict(name=name,classification="system_name_only"));continue
            original=add(tracked,source)
            if lower not in copies:
                target=output/name
                with target.open("xb") as copied:copied.write(source.read_bytes())
                actual=add(tracked,target);require(actual["sha256"]==original["sha256"],"Runtime copy differs")
                copies[lower]=actual;queue.append(source)
            entries.append(dict(name=name,classification="pinned_explicit_runtime",source=original,copy=copies[lower]))
        records.append(dict(binary=add(tracked,binary),imports=entries))
    return dict(import_records=records,copied_runtimes=list(copies.values()),system_dlls="Names only; no loader identity attestation")


def build(args,output,env,tracked,result):
    compiler=args.compiler.resolve(strict=True);opencv=args.opencv.resolve(strict=True)
    compiler_root=compiler.parent.parent
    require(not compiler_root.is_relative_to(ROOT) and not opencv.is_relative_to(ROOT),"External toolchain roots required")
    import_library=opencv/"build/lib/libopencv_world4120.dll.a"
    result["toolchain"]=dict(compiler=add(tracked,compiler),objdump=add(tracked,compiler.parent/"objdump.exe"),
        python=add(tracked,sys.executable),opencv_root=str(opencv),compiler_root=str(compiler_root),
        import_library=add(tracked,import_library),base_flags=BASE_FLAGS)
    for path in [opencv/"build/bin/libopencv_world4120.dll"]+[compiler.parent/name for name in RUNTIMES]:add(tracked,path)
    snapshot=output/"source";allowed=set()
    for name in SOURCE_FILES:
        source=HERE/safe_relative(name);target=snapshot/safe_relative(name);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("xb") as out:out.write(source.read_bytes())
        require(add(tracked,target)["sha256"]==pin(source)["sha256"],"Snapshot differs");allowed.add(target.resolve())
    includes=[snapshot,snapshot/"generated/baseline",snapshot/"generated/baseline/MIPP",
              snapshot/"generated/candidate",snapshot/"generated/candidate/MIPP",opencv/"build"]
    includes += [opencv/"modules"/name/"include" for name in ("core","imgproc","highgui","imgcodecs","videoio")]
    command([compiler,"--version"],output,env,"compiler_version",result)
    command([compiler.parent/"objdump.exe","--version"],output,env,"objdump_version",result)
    result["dependency_units"]=[];objects={}
    for unit,name,omp in UNITS:
        flags=BASE_FLAGS+(["-fopenmp"] if omp else [])+["-I"+str(path) for path in includes]
        source=snapshot/name;target=unit+".o";discovery=output/(unit+".discovered.d");actual=output/(unit+".actual.d")
        prefix=[compiler]+flags
        recheck(tracked)
        command(prefix+["-M","-MF",discovery,"-MT",target,source],output,env,unit+"_dependency_scan",result)
        add(tracked,discovery);discovered=parse_dependencies(discovery.read_bytes(),output,target)
        dependency_scope(discovered,allowed,compiler_root,opencv)
        require(source.resolve() in discovered,"Compiled source absent from discovered dependencies")
        deps=[add(tracked,path) for path in discovered]
        recheck(tracked);obj=output/target
        command(prefix+["-MD","-MF",actual,"-MT",target,"-c",source,"-o",obj],output,env,unit+"_compile",result)
        add(tracked,actual);observed=parse_dependencies(actual.read_bytes(),output,target)
        dependency_scope(observed,allowed,compiler_root,opencv)
        require(observed==discovered,"Ordered discovered/actual dependency closure differs: "+unit)
        for item in deps:check(item)
        objects[unit]=obj
        result["dependency_units"].append(dict(unit=unit,source=str(source),flags=flags,dependencies=deps,
            discovered=pin(discovery),actual=pin(actual),object=add(tracked,obj)))
    result["executables"]={}
    for name,(units,omp,cv) in EXES.items():
        exe=output/(name+".exe");argv=[compiler]+[objects[unit] for unit in units]
        if omp:argv.append("-fopenmp")
        if cv:argv.append(import_library)
        recheck(tracked);command(argv+["-o",exe],output,env,name+"_link",result)
        result["executables"][name]=add(tracked,exe)
    result["runtime_provenance"]=runtime_closure([Path(item["path"]) for item in result["executables"].values()],
                                               compiler,opencv,output,env,tracked,result)
    expected={"output_binary_contract":"PASS output_binary literal contract; matcher_calls=0 image_decodes=0\n",
              "fixture_contract":"PASS fixture ownership, historical alias reproduction, matrix and masks; matcher_calls=0 image_decodes=0\n"}
    for name,text in expected.items():
        recheck(tracked);tested=command([result["executables"][name]["path"]],output,env,name+"_synthetic_test",result)
        require(Path(tested["stdout"]["path"]).read_text(encoding="utf-8")==text and
                Path(tested["stderr"]["path"]).read_bytes()==b"","Synthetic contract output differs")
    result.update(native_compilations=7,native_links=5,native_contract_executions=2,matcher_calls=0,
                  image_decodes=0,image_smd_bank_content_reads=0,output_archives=0)


def verify_previous(path,phase,manifest_sha,tracked):
    path=path.resolve(strict=True);require(path.is_relative_to(BUILD_ROOT.resolve()),"Prior receipt must be inside fixed build root")
    receipt_pin=add(tracked,path);value=read_json(path)
    require(value.get("accepted") is True and value.get("phase")==phase and
            value.get("binding",{}).get("source_manifest_sha256")==manifest_sha and
            value.get("final_recheck_errors")==[],"Accepted same-source prior stage required")
    directory=path.parent
    bound_manifest=checked_manifest(HERE,value["binding"]["source_manifest_path"])
    allowed=set((HERE/safe_relative(name)).resolve() for name in SOURCE_FILES)|{bound_manifest}
    allowed.update((ROOT/safe_relative(name)).resolve() for name,_ in PREREQUISITES)
    allowed.update((FROZEN/name).resolve() for name in CORE+MIPP+("manifest.json",))
    directories=[directory]
    for field in ("build_evidence","replay_evidence","correctness_evidence"):
        if field in value:
            linked=Path(value[field]["path"]).resolve(strict=True)
            require(linked.is_relative_to(BUILD_ROOT.resolve()) and linked.name=="stage_result.json",
                    "Linked prior receipt outside fixed build scope")
            directories.append(linked.parent)
    if phase!="build":
        for fixture in FIXTURES:
            allowed.update((CAPTURE/fixture/name).resolve() for name in
                           ("manifest.json","protocol.json","reference.bin","capture.bin"))
    if phase in ("correctness","benchmark"):
        allowed.update((ROOT/safe_relative(item["path"])).resolve() for item in
                       fixture_catalog(read_json(FIXTURE_MANIFEST),True))
    compiler_root=Path(value["toolchain"]["compiler_root"]).resolve()
    opencv=Path(value["toolchain"]["opencv_root"]).resolve()
    python=Path(value["toolchain"]["python"]["path"]).resolve()
    require(python==Path(sys.executable).resolve(),"Current Python executable differs from prior stage")
    allowed.add(python)
    # Validate every prior pin's scope before rehashing any of those files.
    for item in value["input_pins"]+value["artifact_pins"]:
        candidate=Path(item["path"]).resolve()
        require(candidate in allowed or any(candidate.is_relative_to(parent) for parent in directories) or
                (not candidate.is_relative_to(ROOT) and (candidate.is_relative_to(compiler_root) or candidate.is_relative_to(opencv))),
                "Prior evidence pin escaped fixed build/source/toolchain scope")
    for item in value["input_pins"]+value["artifact_pins"]:
        check(item);require(add(tracked,item["path"])==item,"Prior pinned bytes changed")
    result=dict(receipt=receipt_pin,value=value)
    return result


def historical(tracked,read_traces):
    # Scope all25 numeric trace/reference manifests before reading trace bytes.
    catalog=[];prepared=read_json(HERE/"HISTORICAL_TRACE_PINS.json")
    require(prepared["schema"]=="whole_api_historical_numeric_pins_v1" and prepared["baseline_commit"]==BASELINE and
            [row["fixture"] for row in prepared["fixtures"]]==list(FIXTURES),"Fixed historical numeric catalog required")
    for fixture,prepared_row in zip(FIXTURES,prepared["fixtures"]):
        directory=CAPTURE/fixture;manifest=directory/"manifest.json";protocol=directory/"protocol.json"
        manifest_pin=add(tracked,manifest);protocol_pin=add(tracked,protocol);value=read_json(manifest)
        require(manifest_pin==prepared_row["manifest"] and protocol_pin==prepared_row["protocol"] and
                value["trace"]==prepared_row["trace"] and value["reference"]==prepared_row["reference"],
                "Historical numeric provenance differs from frozen catalog")
        require(value["core_revision"]==BASELINE and value["case"]["case_id"]==fixture and
                value["protocol_sha256"]==protocol_pin["sha256"],"Historical reference identity differs")
        require(value["reference"]["path"]=="reference.bin" and value["reference"]["input_count"]==0 and
                value["trace"]["path"]=="capture.bin","Fixed historical trace basenames required")
        for key in ("trace","reference"):
            item=value[key]
            require(type(item["size_bytes"]) is int and item["size_bytes"]>=32 and
                    re.fullmatch(r"[0-9a-f]{64}",item["sha256"]) is not None,"Historical numeric byte pin differs")
        catalog.append((fixture,directory,value))
    from correctness_contract import decode_v21_reference,decode_v21_trace
    refs={};traces={}
    for fixture,directory,value in catalog:
        for key in (("reference","trace") if read_traces else ("reference",)):
            item=value[key];path=directory/item["path"];actual=add(tracked,path)
            require(actual["bytes"]==item["size_bytes"] and actual["sha256"]==item["sha256"],"Historical archive changed")
            if key=="reference":
                refs[fixture]=decode_v21_reference(path.read_bytes())
                require(len(refs[fixture])==item["output_count"],"Historical reference count differs")
            else:
                traces[fixture]=decode_v21_trace(path.read_bytes())
                require(len(traces[fixture][0])==item["input_count"] and len(traces[fixture][1])==item["output_count"],
                        "Historical capture count differs")
    return refs,traces


def archive_reader(output):
    def read(name):
        require(type(name) is str and re.fullmatch(r"outputs/call_[0-9]{6}\.bin",name) is not None,"Noncanonical native output name")
        path=(output/name).resolve(strict=True)
        require(path.is_relative_to((output/"outputs").resolve()) and path.is_file(),"Archive escaped fresh output directory")
        return path.read_bytes()
    return read


def run_native(args,output,env,tracked,result,manifest_sha):
    require(args.build_evidence is not None,"Explicit accepted build evidence required")
    previous=verify_previous(args.build_evidence,"build",manifest_sha,tracked);build_result=previous["value"]
    result["build_evidence"]=previous["receipt"];result["toolchain"]=build_result["toolchain"]
    require(build_result["toolchain"]["compiler"]["path"]==str(args.compiler.resolve(strict=True)) and
            build_result["toolchain"]["opencv_root"]==str(args.opencv.resolve(strict=True)),"Current toolchain differs from build")
    phase=args.phase
    if phase in ("correctness","benchmark"):
        require(args.dataset_stage_granted is True,"Explicit root dataset-stage grant required before input hashing")
        prerequisite=args.replay_evidence if phase=="correctness" else args.correctness_evidence
        require(prerequisite is not None,"Explicit preceding accepted stage required")
        wanted="replay" if phase=="correctness" else "correctness"
        predecessor=verify_previous(prerequisite,wanted,manifest_sha,tracked)
        prior_pin,prior=predecessor["receipt"],predecessor["value"]
        require(prior.get("build_evidence")==previous["receipt"],
                "Accepted same-build prerequisite stage required")
        result[wanted+"_evidence"]=prior_pin
    references,traces=historical(tracked,phase=="replay")
    if phase in ("correctness","benchmark"):
        catalog=fixture_catalog(read_json(FIXTURE_MANIFEST),phase=="correctness")
        result["fixture_inputs"]=[]
        # fixture_catalog fully validates the entire fixed input scope first.
        for item in catalog:
            path=(ROOT/safe_relative(item["path"])).resolve(strict=True)
            require(path.is_relative_to(ROOT),"Fixture input resolved outside repository")
        for item in catalog:
            actual=add(tracked,ROOT/safe_relative(item["path"]))
            require(actual["bytes"]==item["bytes"] and actual["sha256"]==item["sha256"],"Fixture source bytes changed")
            result["fixture_inputs"].append(dict(actual,role=item["role"]))
    executable=build_result["executables"]["replay" if phase=="replay" else phase]
    check(executable);(output/"outputs").mkdir();recheck(tracked)
    # No automatic retry. Full correct/timing runs get a fixed2-hour timeout;
    # the caller's exec session remains yieldable so root can report progress.
    ran=command([executable["path"],"--root",ROOT,"--output-directory",output],output,env,"native_"+phase,result,
                timeout=7200 if phase in ("correctness","benchmark") else 600)
    require(Path(ran["stderr"]["path"]).read_bytes()==b"","Native stage wrote unexpected stderr")
    read=archive_reader(output)
    if phase=="replay":
        rows=table((output/"replay.csv").read_bytes(),("fixture","trace_input_count","trace_output_count",
                   "v11_output_count","candidate_output_count","full_ordered_equal"))
        require(len(rows)==25,"Replay row budget differs")
        for i,(fixture,row) in enumerate(zip(FIXTURES,rows)):
            require(row["fixture"]==fixture and boolean(row["full_ordered_equal"]),"Replay route/equality differs")
            n,u=map(len,traces[fixture]);require((integer(row["trace_input_count"],True),integer(row["trace_output_count"],True))==(n,u),
                                             "Replay capture counts differ")
            require(integer(row["v11_output_count"],True)==integer(row["candidate_output_count"],True)==u,"Replay output counts differ")
            for variant in (0,1):
                call_id=2*i+variant;records=decode_output(read("outputs/call_%06d.bin"%call_id),call_id).records
                require(records==traces[fixture][1]==references[fixture],"Independent complete replay/reference equality differs")
        result.update(audit_summary=dict(traces=25,complete_archives=50,ordered_equalities=100),
                      native_contract_executions=1,matcher_calls=0,image_decodes=0,image_smd_bank_content_reads=0,output_archives=50)
    else:
        rows=enrich_calls(parse_calls((output/"calls.csv").read_bytes(),phase=="benchmark"),read)
        write_json(output/"calls.json",rows)
        if phase=="correctness":
            from correctness_contract import audit_correctness
            comparisons=parse_comparisons((output/"comparisons.csv").read_bytes())
            write_json(output/"comparisons.json",comparisons)
            result["audit_summary"]=audit_correctness(rows,comparisons,read,references)
            preflight=table((output/"magnet_preflight.csv").read_bytes(),("template_id","level","width","height","border",
                "required_width","required_height","max_x","max_y"))
            require(len(preflight)==6120,"Missing magnet refinement rows")
            for index,row in enumerate(preflight):
                p={key:integer(value,True) for key,value in row.items()};level=index%2;border=8*(4 if level==0 else 8)
                require(p["template_id"]==index//2 and p["level"]==level and p["border"]==border and
                    p["required_width"]==(p["width"]+2*border)*(1<<level) and
                    p["required_height"]==(p["height"]+2*border)*(1<<level) and
                    p["max_x"]==(896>>level)-p["width"]-border and p["max_y"]==(832>>level)-p["height"]-border and
                    p["max_x"]>=border and p["max_y"]>=border,"Magnet preflight interval differs")
            result["audit_summary"]["magnet_preflight_rows"]=6120
            result.update(matcher_calls=2722,output_archives=2722,image_decodes=32,
                          dataset_bytes_accessed=True,input_read_count_instrumented=False)
        else:
            result["audit_summary"]=audit_timing(rows,read)
            for fixture in FIXTURES:
                cold=next(row for row in rows if row["fixture"]==fixture and row["phase"]=="cold" and row["variant"]=="exact_v11")
                require(decode_output(read(cold["output_file"]),cold["call_id"]).records==references[fixture],
                        "Timed cold baseline differs from historical independent reference")
            result["audit_summary"]["historical_truth_gate_fixtures"]=25
            result.update(matcher_calls=950,output_archives=950,image_decodes=25,
                          dataset_bytes_accessed=True,input_read_count_instrumented=False)
        result["native_contract_executions"]=1
    result.update(native_compilations=0,native_links=0)


def run(args):
    # Must precede validation/creation and any declared image/bank/trace read.
    require(args.cpu_slot_granted is True,"Explicit root CPU slot required")
    if args.phase in ("correctness","benchmark"):
        require(args.dataset_stage_granted is True,"Explicit root dataset stage grant required")
    requested=args.output_directory or BUILD_ROOT/(args.phase+"_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    output=checked_output(BUILD_ROOT,requested,args.cpu_slot_granted);output.mkdir(parents=True)
    result=dict(schema="whole_api_stage_v1",phase=args.phase,accepted=False,started_utc=utc(),commands=[],
        cpu_slot_granted=True,dataset_stage_granted=args.dataset_stage_granted,limitation=LIMITATION,
        host=dict(platform=platform.platform(),machine=platform.machine(),logical_processors=os.cpu_count()),
        git_commands=0,production_modified=False)
    tracked={}
    try:
        require(os.name=="nt","Fixed Windows MinGW runner required")
        manifest_pin=verify_sources(args.source_manifest_sha256,tracked,args.source_manifest)
        result["binding"]=dict(source_manifest_sha256=manifest_pin["sha256"],source_manifest_path=manifest_pin["path"],baseline_commit=BASELINE)
        env,description=environment(args.compiler.resolve(strict=True),args.opencv.resolve(strict=True));result["environment"]=description
        if args.phase=="build":build(args,output,env,tracked,result)
        else:run_native(args,output,env,tracked,result,manifest_pin["sha256"])
        recheck(tracked);result["accepted"]=True
    except Exception as error:
        result["error"]=dict(type=type(error).__name__,message=str(error))
    finally:
        changes=[]
        for item in tracked.values():
            try:check(item)
            except Exception as error:changes.append(dict(path=item["path"],message=str(error)))
        if changes:result["accepted"]=False
        result.update(completed_utc=utc(),input_pins=list(tracked.values()),final_recheck_errors=changes,
                      artifact_pins=[pin(path) for path in sorted(output.rglob("*")) if path.is_file()])
        write_json(output/"stage_result.json",result)
    print(json.dumps(dict(accepted=result["accepted"],phase=args.phase,result=str(output/"stage_result.json"))))
    return 0 if result["accepted"] else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",required=True,choices=("build","replay","correctness","benchmark"))
    parser.add_argument("--cpu-slot-granted",action="store_true")
    parser.add_argument("--dataset-stage-granted",action="store_true")
    parser.add_argument("--source-manifest-sha256",required=True)
    parser.add_argument("--source-manifest",type=Path,default=MANIFEST)
    parser.add_argument("--build-evidence",type=Path)
    parser.add_argument("--replay-evidence",type=Path)
    parser.add_argument("--correctness-evidence",type=Path)
    parser.add_argument("--output-directory",type=Path)
    parser.add_argument("--compiler",type=Path,default=Path("F:/mysys2/ucrt64/bin/g++.exe"))
    parser.add_argument("--opencv",type=Path,default=Path("D:/opencv-4.12.0"))
    try:return run(parser.parse_args())
    except Exception as error:print(str(error),file=sys.stderr);return 1


if __name__=="__main__":raise SystemExit(main())
