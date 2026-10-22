"""Build/run the isolated four-TU V2 matrix with local byte/dependency receipts.

Native actions require the parent's separately coordinated CPU assignment.
Nothing here stages Git files, decodes heldout images, or runs a timing benchmark.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from correctness_evidence import validate_csv
from dependency_pins import parse_depfile, require

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENVIRONMENT = {"OMP_NUM_THREADS": "4", "OMP_DYNAMIC": "FALSE",
               "OMP_MAX_ACTIVE_LEVELS": "1", "OMP_WAIT_POLICY": "PASSIVE"}
LIMITATION = ("Local source, discovered/actual compiler dependencies, explicit OpenCV import library, "
              "compiler, four runtime DLLs and generated objects/executable are pinned. This is not "
              "an attestation of all compiler/linker/OS/loader reads. Correctness regression only; "
              "no speed, accuracy-improvement, universal equality or production-adoption claim.")


def now():
    return datetime.now(timezone.utc).isoformat()


def stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def pin(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), "Regular file required: " + str(path))
    data = path.read_bytes()
    return dict(path=str(path), size_bytes=len(data), sha256=sha(data))


def check(item):
    actual = pin(item["path"])
    require(actual == item, "Pinned file changed: " + item["path"])


def checks(items):
    for item in items:
        check(item)


def inside(path, parent):
    return Path(path).resolve().is_relative_to(Path(parent).resolve())


def toolchain(compiler, opencv):
    compiler, opencv = compiler.resolve(strict=True), opencv.resolve(strict=True)
    runtime = [opencv / "build/bin/libopencv_world4120.dll"] + [
        compiler.parent / name for name in ("libgomp-1.dll", "libstdc++-6.dll", "libgcc_s_seh-1.dll")]
    library = opencv / "build/lib/libopencv_world4120.dll.a"
    return dict(compiler=pin(compiler), python=pin(sys.executable), opencv_root=str(opencv),
                import_library=pin(library), runtimes=[pin(path) for path in runtime])


def tool_pins(tool):
    return [tool["compiler"], tool["python"], tool["import_library"]] + tool["runtimes"]


def environment(tool):
    env = dict(os.environ)
    env.update(ENVIRONMENT)
    env["PATH"] = str(Path(tool["opencv_root"]) / "build/bin") + os.pathsep + str(
        Path(tool["compiler"]["path"]).parent) + os.pathsep + env.get("PATH", "")
    return env


def command(argv, cwd, env, directory, name):
    stdout, stderr = directory / (name + ".stdout.txt"), directory / (name + ".stderr.txt")
    require(not stdout.exists() and not stderr.exists(), "Fresh command evidence required")
    with stdout.open("xb") as out, stderr.open("xb") as err:
        process = subprocess.run(list(map(str, argv)), cwd=cwd, env=env, stdout=out, stderr=err)
    result = dict(argv=list(map(str, argv)), cwd=str(cwd), exit_code=process.returncode,
                  stdout=pin(stdout), stderr=pin(stderr))
    print(name + " exit=" + str(process.returncode), flush=True)
    return result


def verify_origins(green_path):
    # This performs byte/Git-blob checks only, never native compilation or image decoding.
    process = subprocess.run([sys.executable, str(HERE / "prepare_sources.py"), "--mode", "verify"],
                             cwd=ROOT, capture_output=True)
    require(process.returncode == 0, "Frozen origins differ: " + process.stderr.decode("utf-8", "replace"))
    green = read_json(green_path)
    require(green["phase"] == "Green" and green["accepted"] is True and
            green["compile_exit"] == 0 and green["test_exit"] == 0, "Accepted literal GREEN required")
    require(base64.b64decode(green["cache_header_base64"], validate=True) ==
            (HERE / "direct/line2Dup_local_cache.hpp").read_bytes(), "Direct header changed since GREEN")
    require(sha((HERE / "tests/direct_cache_contract.cpp").read_bytes()).upper() ==
            green["test_source_sha256"].upper(), "Literal test changed since GREEN")
    require(sha((HERE / "origins/manifest.json").read_bytes()).upper() ==
            green["origins_manifest_sha256"].upper(), "Origins manifest changed since GREEN")
    return dict(argv=[sys.executable, str(HERE / "prepare_sources.py"), "--mode", "verify"],
                exit_code=process.returncode, stdout=process.stdout.decode("utf-8", "replace"),
                stderr=process.stderr.decode("utf-8", "replace"))


def fixture_inputs():
    tiny = ROOT / "datasets/tless_tiny"
    index = read_json(tiny / "index.json")
    # Filter split metadata first. Never construct or read a heldout image path.
    development = [frame for frame in index["test"] if frame["split"] == "development"]
    require(len(development) == 16, "Fixed sixteen development frames required")
    paths = [ROOT / "LED/ku.smd", ROOT / "test/case1/test_templ.yaml", ROOT / "test/case1/test.png",
             ROOT / "datasets/tless_train_f32/templates_tless_object_1.yml.gz", tiny / "index.json"]
    paths += [ROOT / "LED" / (str(index) + ".bmp") for index in range(1, 9)]
    names = []
    for frame in development:
        relative = Path(frame["rgb"])
        require(not relative.is_absolute() and ".." not in relative.parts and relative.suffix.lower() == ".png",
                "Development RGB must be a contained relative PNG")
        path = tiny / relative
        require(inside(path, tiny), "Development image escaped tiny dataset")
        paths.append(path)
        names.append("tiny_s" + str(int(frame["scene_id"])) + "_i" + str(int(frame["image_id"])))
    require(len(set(names)) == 16, "Development names must be distinct")
    return [pin(path) for path in paths], names


def source_scope(green_path):
    origins = read_json(HERE / "origins/manifest.json")
    local = [HERE / path for path in origins["files"]]
    local += [HERE / path for path in (
        "origins/manifest.json", "direct/line2Dup_local_cache.hpp", "tests/direct_cache_contract.cpp",
        "prepare_sources.py", "run_cache_contract.ps1", "v11_reference.hpp", "v11_reference.cpp",
        "v18_reference.hpp", "v18_reference.cpp", "fixtures.hpp", "tests/matcher_contract.cpp",
        "REGRESSION_MATRIX.json", "DESIGN.md", "PROTOCOL_DRAFT.json",
        "run_correctness.py", "correctness_evidence.py", "dependency_pins.py",
        "tests/test_evidence.py", "run_correctness.ps1")]
    local += [green_path, ROOT / "artifacts/led_match/led_demo.cpp"]
    protected = []
    for path, expected in origins["protected_source_sha256"].items():
        item = pin(path)
        require(item["sha256"].upper() == expected.upper(), "Protected source differs: " + path)
        protected.append(item)
    return [pin(path) for path in dict.fromkeys(local)], protected


def scoped_dependencies(paths, source_items, tool):
    allowed = {Path(item["path"]).resolve() for item in source_items}
    compiler_tree = Path(tool["compiler"]["path"]).parent.parent
    opencv_tree = Path(tool["opencv_root"])
    # Validate the whole scope before hashing anything named by a depfile.
    for path in paths:
        require((inside(path, ROOT) and path in allowed) or
                (not inside(path, ROOT) and (inside(path, compiler_tree) or inside(path, opencv_tree))),
                "Compiler dependency outside approved source/toolchain scope: " + str(path))
    return [pin(path) for path in paths]


def unit_specs(build, tool):
    compiler = tool["compiler"]["path"]
    opencv = Path(tool["opencv_root"])
    flags = ["-std=c++14", "-O3", "-mssse3", "-msse4.1", "-fopenmp", "-Wall", "-Wextra",
             "-Wno-sign-compare", "-I" + str(opencv / "build")]
    flags += ["-I" + str(opencv / "modules" / module / "include") for module in
              ("core", "imgproc", "highgui", "imgcodecs", "videoio")]
    result = []
    for name, source, include in (
            ("v11_reference", HERE / "v11_reference.cpp", HERE / "baseline"),
            ("v18_reference", HERE / "v18_reference.cpp", HERE / "linear"),
            ("direct_core", HERE / "direct/line2Dup.cpp", HERE / "direct"),
            ("matcher_contract", HERE / "tests/matcher_contract.cpp", HERE / "direct")):
        prefix = [compiler] + flags + ["-I" + str(include), "-I" + str(HERE / "baseline/MIPP")]
        target = name + ".o"
        result.append(dict(name=name, source=str(source), target=target, object=str(build / target),
                           scan=str(build / (name + "_scan.d")), depfile=str(build / (name + ".d")),
                           prefix=prefix))
    return result


def build(args):
    build_path = (args.build_directory or HERE / "build" / ("matcher_" + stamp())).resolve()
    require(inside(build_path, HERE / "build") and build_path != HERE / "build", "Build must stay in V2/build")
    build_path.mkdir(parents=True, exist_ok=False)
    manifest_path = build_path / "build_manifest.json"
    result = dict(passed=False, started_at=now(), limitation=LIMITATION, working_directory=str(build_path),
                  commands=[], dependency_units=[])
    try:
        result["origin_verification"] = verify_origins(args.green_evidence)
        sources, protected = source_scope(args.green_evidence)
        inputs, names = fixture_inputs()
        tool = toolchain(args.compiler, args.opencv)
        result.update(source_pins=sources, protected_pins=protected, input_pins=inputs,
                      development_names=names, toolchain=tool, environment=ENVIRONMENT,
                      green_evidence=str(args.green_evidence.resolve()))
        env = environment(tool)
        all_pins = sources + protected + inputs + tool_pins(tool)
        units = unit_specs(build_path, tool)
        # All four dependency discoveries and their initial hashes precede compilation.
        for unit in units:
            argv = unit["prefix"] + ["-M", "-MF", unit["scan"], "-MT", unit["target"], unit["source"]]
            ran = command(argv, build_path, env, build_path, unit["name"] + "_scan")
            result["commands"].append(ran)
            require(ran["exit_code"] == 0, "Dependency discovery failed: " + unit["name"])
            paths = parse_depfile(Path(unit["scan"]).read_bytes(), unit["target"], build_path)
            require(Path(unit["source"]).resolve() in paths, "Discovery omitted its source")
            unit["dependencies"] = scoped_dependencies(paths, sources, tool)
            unit["discovery_command"] = ran
            unit["discovery_depfile_pin"] = pin(unit["scan"])
            result["dependency_units"].append(unit)
        checks(all_pins)
        for unit in units:
            checks(unit["dependencies"])
            check(unit["discovery_depfile_pin"])
        for unit in units:
            argv = unit["prefix"] + ["-c", "-MD", "-MF", unit["depfile"], "-MT", unit["target"],
                                      unit["source"], "-o", unit["object"]]
            ran = command(argv, build_path, env, build_path, unit["name"] + "_compile")
            result["commands"].append(ran)
            unit["compile_command"] = ran
            require(ran["exit_code"] == 0, "Compile failed: " + unit["name"])
            actual = parse_depfile(Path(unit["depfile"]).read_bytes(), unit["target"], build_path)
            require(actual == [Path(item["path"]) for item in unit["dependencies"]],
                    "Discovered/actual ordered dependencies differ: " + unit["name"])
            checks(unit["dependencies"])
            check(unit["discovery_depfile_pin"])
            unit["artifacts"] = [pin(unit[key]) for key in ("object", "scan", "depfile")]
        exe = build_path / "matcher_contract.exe"
        argv = [tool["compiler"]["path"], "-fopenmp"] + [unit["object"] for unit in units] + [
            tool["import_library"]["path"], "-o", str(exe)]
        ran = command(argv, build_path, env, build_path, "link")
        result["commands"].append(ran)
        require(ran["exit_code"] == 0, "Four-TU link failed")
        checks(all_pins)
        for unit in units:
            checks(unit["dependencies"] + unit["artifacts"])
        for ran in result["commands"]:
            checks([ran["stdout"], ran["stderr"]])
        result.update(executable=pin(exe), passed=True)
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    result["finished_at"] = now()
    write_json(manifest_path, result)
    (build_path / "build_manifest.sha256").write_text(sha(manifest_path.read_bytes()) + "\n", encoding="ascii")
    print("Build evidence: " + str(manifest_path), flush=True)
    require(result["passed"], result.get("error", "Build failed"))


def verify_build(build_path):
    manifest_path = build_path / "build_manifest.json"
    receipt_path = build_path / "build_manifest.sha256"
    receipt = receipt_path.read_text(encoding="ascii").strip()
    require(len(receipt) == 64 and sha(manifest_path.read_bytes()) == receipt, "Build manifest receipt differs")
    built = read_json(manifest_path)
    require(built["passed"] is True and Path(built["working_directory"]).resolve() == build_path,
            "Successful fixed build required")
    require(built["environment"] == ENVIRONMENT, "Build runtime environment differs")
    require([unit["target"] for unit in built["dependency_units"]] ==
            ["v11_reference.o", "v18_reference.o", "direct_core.o", "matcher_contract.o"],
            "Four independent translation units required")
    items = built["source_pins"] + built["protected_pins"] + built["input_pins"] + tool_pins(built["toolchain"])
    items += [built["executable"], pin(manifest_path), pin(receipt_path)]
    for unit in built["dependency_units"]:
        items += unit["dependencies"] + unit["artifacts"] + [unit["discovery_depfile_pin"]]
        scanned = parse_depfile(Path(unit["scan"]).read_bytes(), unit["target"], build_path)
        actual = parse_depfile(Path(unit["depfile"]).read_bytes(), unit["target"], build_path)
        require(scanned == actual == [Path(item["path"]) for item in unit["dependencies"]],
                "Pinned dependency occurrence/order differs")
        scoped_dependencies(actual, built["source_pins"], built["toolchain"])
    for ran in built["commands"]:
        items += [ran["stdout"], ran["stderr"]]
        require(type(ran["exit_code"]) is int and ran["exit_code"] == 0, "Build command did not succeed")
    checks(items)
    return built, items


def run(args):
    require(args.build_directory is not None, "Run requires successful --build-directory")
    build_path = args.build_directory.resolve(strict=True)
    require(inside(build_path, HERE / "build"), "Run build must stay in V2/build")
    evidence = HERE / ("correctness_" + args.stage + "_" + stamp())
    evidence.mkdir(exist_ok=False)
    result = dict(passed=False, stage=args.stage, started_at=now(), limitation=LIMITATION,
                  cv_threads=1, environment=ENVIRONMENT, build_directory=str(build_path))
    try:
        result["origin_verification"] = verify_origins(args.green_evidence)
        built, pins_before = verify_build(build_path)
        require(str(args.green_evidence.resolve()) == built["green_evidence"], "GREEN evidence differs from build")
        fresh_inputs, names = fixture_inputs()
        require(fresh_inputs == built["input_pins"] and names == built["development_names"],
                "Current development fixture inventory differs")
        result.update(build_manifest=pin(build_path / "build_manifest.json"),
                      build_receipt=pin(build_path / "build_manifest.sha256"),
                      executable_before=built["executable"], verified_pins_before=pins_before)
        csv_path = evidence / "ordered_comparisons.csv"
        argv = [built["executable"]["path"], "--stage", args.stage, "--output", str(csv_path)]
        ran = command(argv, ROOT, environment(built["toolchain"]), evidence, "matcher")
        result["matcher_command"] = ran
        # Check closure even when native execution fails; failed artifacts remain readable.
        checks(pins_before)
        result["pins_unchanged_after"] = True
        result["executable_after"] = pin(built["executable"]["path"])
        if csv_path.exists():
            result["csv"] = pin(csv_path)
        require(ran["exit_code"] == 0, "Native matcher stage failed")
        output = Path(ran["stdout"]["path"]).read_text(encoding="utf-8", errors="replace")
        output += "\n" + Path(ran["stderr"]["path"]).read_text(encoding="utf-8", errors="replace")
        result["csv_validation"] = validate_csv(csv_path, args.stage, names,
                                                read_json(HERE / "REGRESSION_MATRIX.json"), output)
        checks(pins_before)
        result["passed"] = True
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    result["finished_at"] = now()
    path = evidence / "result.json"
    write_json(path, result)
    print("Correctness evidence: " + str(path), flush=True)
    require(result["passed"], result.get("error", "Correctness stage failed"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("build", "run"))
    parser.add_argument("--green-evidence", type=Path, required=True)
    parser.add_argument("--stage", choices=("core", "flags", "lifetime"), default="core")
    parser.add_argument("--build-directory", type=Path)
    parser.add_argument("--compiler", type=Path, default=Path("F:/mysys2/ucrt64/bin/g++.exe"))
    parser.add_argument("--opencv", type=Path, default=Path("D:/opencv-4.12.0"))
    args = parser.parse_args()
    args.green_evidence = args.green_evidence.resolve(strict=True)
    (build if args.mode == "build" else run)(args)


if __name__ == "__main__":
    main()
