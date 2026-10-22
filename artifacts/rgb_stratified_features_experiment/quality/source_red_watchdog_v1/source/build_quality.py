"""Build the isolated V31 quality adapter with an explicit two-TU closure.

The command is intentionally gated by ``--cpu-slot-granted``.  Source and
input declarations are verified before invoking the compiler; all diagnostics
and partial outputs remain in the fresh build directory on failure.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
ROOT = EXPERIMENT.parents[1]


def _load_local(name):
    sys.dont_write_bytecode = True
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    if str(EXPERIMENT) not in sys.path:
        sys.path.insert(0, str(EXPERIMENT))
    return __import__(name)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _require(value, message):
    if not value:
        raise ValueError(message)


def _source_manifest():
    path = EXPERIMENT / "TRAINING_SOURCE_FREEZE.json"
    manifest = _load(path)
    _require(manifest.get("schema") == "rgb_stratified_exact_v11_training_source_v1",
             "V31 exact source freeze schema changed")
    _require(len(manifest.get("files", {})) == 23 and len(manifest.get("helpers", {})) == 3,
             "V31 exact source scope changed")
    _require(manifest.get("git_revision") == "b25df46f6ddf9c24fb43f5836f1414dc38c8caed" and
             manifest.get("sole_core_delta") is None, "Exact original V11 required")
    _require(Path(manifest.get("core_translation_unit", "")).resolve() ==
             (EXPERIMENT / "control_v11" / "line2Dup.cpp").resolve(),
             "V31 core translation unit changed")
    for directory, names in ((EXPERIMENT / "control_v11", manifest["files"]),
                             (EXPERIMENT / "frozen_helpers", manifest["helpers"])):
        actual = {member.relative_to(directory).as_posix() for member in directory.rglob("*")
                  if member.is_file()}
        _require(actual == set(names), "Frozen source snapshot member set changed")
        for name, expected in names.items():
            member_path = directory / name
            p = _load_local("native_provenance")
            p.check_pin(dict(path=str(member_path), **expected))
    return manifest, path


def _new_output(args):
    _require(args.cpu_slot_granted, "Await coordinated actual-build CPU slot")
    out = args.output.resolve()
    _require(out.is_relative_to(HERE) and not out.exists(),
             "Build directory must be fresh inside V31 quality")
    out.mkdir(parents=True)
    return out


def _build_gate(args, inputs, contract):
    compiler = args.compiler.resolve(strict=True)
    opencv = args.opencv.resolve(strict=True)
    _require((HERE / "quality_eval.cpp").is_file() and (HERE / "quality_support.hpp").is_file(),
             "V31 quality adapter sources are missing")
    inputs.verify()
    contract.validate_native_sources(HERE)
    return compiler, opencv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-slot-granted", action="store_true")
    parser.add_argument("--compiler", type=Path, default=Path("F:/mysys2/ucrt64/bin/g++.exe"))
    parser.add_argument("--opencv", type=Path, default=Path("D:/opencv-4.12.0"))
    args = parser.parse_args()
    p = _load_local("native_provenance")
    inputs = _load_local("prepare_quality_inputs")
    contract = _load_local("quality_contract")
    attempts = []
    out = None
    try:
        out = _new_output(args)
        compiler, opencv = _build_gate(args, inputs, contract)
        manifest, _ = _source_manifest()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + ";" + str(opencv / "build/bin") + ";" + env.get("PATH", "")
        tools, queries = p.compiler_tools(compiler, env)
        runtime_before = p.import_closure(
            tools + [opencv / "build/bin/libopencv_world4120.dll", compiler.parent / "zlib1.dll"],
            compiler, opencv, env)
        libraries = [opencv / "build/lib/libopencv_world4120.dll.a",
                     compiler.parent.parent / "lib/libz.dll.a",
                     compiler.parent.parent / "lib/libpsapi.a"]
        tool_pins = [p.file_pin(path) for path in tools + libraries]
        sources = [EXPERIMENT / "control_v11" / "line2Dup.cpp",
                   HERE / "quality_eval.cpp"]
        frozen_source_paths = [EXPERIMENT / "control_v11" / name
                               for name in manifest["files"]]
        frozen_source_paths += [EXPERIMENT / "frozen_helpers" / name
                                for name in manifest["helpers"]]
        supporting = [HERE / name for name in
                      ("build_quality.py", "quality_contract.py", "prepare_quality_inputs.py",
                       "quality_execution_inputs.py", "run_quality.py", "quality_eval.cpp",
                       "quality_support.hpp")]
        supporting += [EXPERIMENT / "TRAINING_SOURCE_FREEZE.json",
                       EXPERIMENT / "PROTOCOL.json", HERE / "QUALITY_INPUT_FREEZE.json",
                       EXPERIMENT / "native_provenance.py", EXPERIMENT / "execution_guard.py",
                       HERE / "EXECUTION_RESOURCES.md"]
        project_pins = [p.file_pin(path) for path in frozen_source_paths + sources + supporting]
        control = EXPERIMENT / "control_v11"
        flags = ["-std=c++17", "-O3", "-mssse3", "-msse4.1", "-fopenmp",
                 "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-unused-function",
                 "-I" + str(control), "-I" + str(control / "MIPP")]
        flags += ["-I" + str(opencv / "build"),
                  "-I" + str(opencv / "modules/core/include"),
                  "-I" + str(opencv / "modules/imgproc/include"),
                  "-I" + str(opencv / "modules/highgui/include"),
                  "-I" + str(opencv / "modules/imgcodecs/include"),
                  "-I" + str(opencv / "modules/videoio/include")]
        units = []

        def run(label, command):
            record = {"label": label, "command": [str(x) for x in command],
                      "working_directory": str(out)}
            attempts.append(record)
            (out / "attempts.json").write_text(json.dumps(attempts, indent=2) + "\n", encoding="utf-8")
            try:
                process = subprocess.run(record["command"], cwd=out, env=env,
                                         capture_output=True, timeout=300)
            except subprocess.TimeoutExpired as error:
                (out / (label + ".stdout")).write_bytes(error.stdout or b"")
                (out / (label + ".stderr")).write_bytes(error.stderr or b"")
                record.update(timed_out=True, timeout_seconds=300, exit_code=None)
                (out / "attempts.json").write_text(json.dumps(attempts, indent=2) + "\n", encoding="utf-8")
                raise
            (out / (label + ".stdout")).write_bytes(process.stdout)
            (out / (label + ".stderr")).write_bytes(process.stderr)
            record["exit_code"] = process.returncode
            (out / "attempts.json").write_text(json.dumps(attempts, indent=2) + "\n", encoding="utf-8")
            _require(process.returncode == 0, label + " failed; diagnostics were preserved")
            return process.stdout

        for name, source in (("core", sources[0]), ("adapter", sources[1])):
            target = name + ".o"
            before_data = run(name + "_dependency_before",
                              [compiler, *flags, "-M", "-MT", target, source])
            (out / (name + "_before.d")).write_bytes(before_data)
            before = p.dependency_pins(before_data, target, out, ROOT,
                                       frozen_source_paths + sources + supporting)
            _require(source.resolve() in [Path(item["path"]) for item in before],
                     "Precompile dependency list omits translation unit")
            run(name + "_compile", [compiler, *flags, "-c", source, "-o", out / target,
                                     "-MD", "-MF", out / (name + ".d"), "-MT", target])
            actual_data = (out / (name + ".d")).read_bytes()
            actual = p.dependency_pins(actual_data, target, out, ROOT,
                                       frozen_source_paths + sources + supporting)
            _require(actual == before, "Actual compiler dependencies differ from precompile")
            units.append({"source": str(source), "target": target,
                          "object": p.file_pin(out / target),
                          "dependency_file": p.file_pin(out / (name + ".d")),
                          "dependencies": actual})
        executable = out / "quality_eval.exe"
        run("link", [compiler, "-fopenmp", out / "core.o", out / "adapter.o",
                      *libraries, "-o", executable])
        actual_runtime = p.import_closure([executable], compiler, opencv, env)
        for pin in tool_pins + project_pins + runtime_before["files"] + actual_runtime["files"]:
            p.check_pin(pin)
        for unit in units:
            p.check_pin(unit["object"])
            p.check_pin(unit["dependency_file"])
            for pin in unit["dependencies"]:
                p.check_pin(pin)
        _source_manifest()
        inputs.verify()
        result = {
            "passed": True, "target": "rgb_stratified_quality",
            "core_revision": manifest["git_revision"],
            "actual_core": str(sources[0]), "executable": p.file_pin(executable),
            "compiler": str(compiler), "opencv": str(opencv),
            "compiler_tools_and_link_libraries": tool_pins,
            "compiler_tool_queries": queries,
            "compiler_runtime_closure": runtime_before,
            "executable_runtime_closure": actual_runtime,
            "project_sources": project_pins, "dependency_units": units,
            "compile_flags": flags,
            "commands": attempts, "image_decodes": 0, "matcher_calls": 0,
            "scope": "Separate fixed V31 quality/selftest/timing adapter; no production promotion",
        }
        (out / "build_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"passed": True, "compiler_commands": len(attempts),
                          "image_decodes": 0, "matcher_calls": 0}))
    except Exception as error:
        if out is not None:
            (out / "failure.json").write_text(json.dumps({
                "incomplete": True, "reason": str(error), "attempts": attempts,
                "image_decodes": 0, "matcher_calls": 0,
            }, indent=2) + "\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
