"""Root-owned two-contract native check; no detector, bank or image input.

The executable only allocates synthetic Mats or serializes literal records.
This is a limited compilation/contract receipt, not the full-API build gate.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from standalone_contract import parse_depfile


def pin(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    output = HERE / "build" / ("root_synthetic_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f"))
    output.mkdir(parents=True, exist_ok=False)
    compiler = Path("F:/mysys2/ucrt64/bin/g++.exe")
    opencv = Path("D:/opencv-4.12.0")
    env = os.environ.copy()
    env["PATH"] = str(compiler.parent) + os.pathsep + str(opencv / "build/bin") + os.pathsep + env.get("PATH", "")
    for key in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH", "LIBRARY_PATH", "COMPILER_PATH", "GCC_EXEC_PREFIX"):
        env.pop(key, None)
    receipt = dict(schema="root_synthetic_contracts_v1", commands=[], matcher_calls=0,
                   image_decodes=0, bank_reads=0, status="failed", limitations=
                   "Synthetic contracts only; dependency bytes pinned before/after; no complete toolchain or loaded DLL attestation.")
    tracked = {}

    def track(path):
        item = pin(path)
        if item["path"] in tracked and tracked[item["path"]] != item:
            raise ValueError("Dependency changed: " + item["path"])
        tracked[item["path"]] = item

    def call(name, argv):
        result = subprocess.run([str(x) for x in argv], cwd=HERE, env=env, capture_output=True, timeout=600)
        for suffix, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
            (output / (name + "." + suffix + ".txt")).write_bytes(raw)
        receipt["commands"].append(dict(name=name, argv=[str(x) for x in argv], exit_code=result.returncode))
        if result.returncode:
            raise ValueError("Native stage failed: " + name)

    try:
        track(__file__)
        track(compiler)
        track(opencv / "build/lib/libopencv_world4120.dll.a")
        track(opencv / "build/bin/libopencv_world4120.dll")
        includes = [opencv / "build"] + [opencv / "modules" / name / "include" for name in ("core", "imgproc", "imgcodecs")]
        prefix = [compiler, "-std=c++14", "-O2", "-Wall", "-Wextra"] + ["-I" + str(p) for p in includes]
        for name in ("output_binary_contract", "fixture_contract"):
            source = HERE / "tests" / (name + ".cpp")
            discovered = output / (name + ".discovered.d")
            actual = output / (name + ".actual.d")
            obj, exe = output / (name + ".o"), output / (name + ".exe")
            call(name + "_scan", prefix + ["-M", "-MF", discovered, "-MT", "actual_match_contract.o", source])
            dependencies = parse_depfile(discovered.read_bytes(), HERE)
            for dependency in dependencies:
                track(dependency)
            call(name + "_compile", prefix + ["-MD", "-MF", actual, "-MT", "actual_match_contract.o", "-c", source, "-o", obj])
            if parse_depfile(actual.read_bytes(), HERE) != dependencies:
                raise ValueError("Discovered/actual dependencies differ")
            call(name + "_link", [compiler, obj, "-L" + str(opencv / "build/lib"), "-lopencv_world4120", "-o", exe])
            call(name + "_test", [exe])
        for item in tracked.values():
            if pin(item["path"]) != item:
                raise ValueError("Input changed during synthetic stage")
        receipt["status"] = "passed"
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        receipt["inputs"] = list(tracked.values())
        receipt["artifacts"] = [pin(path) for path in sorted(output.iterdir()) if path.is_file()]
        with (output / "result.json").open("x", encoding="utf-8", newline="\n") as file:
            json.dump(receipt, file, indent=2)
            file.write("\n")
        print(str(output), receipt["status"])


if __name__ == "__main__":
    main()
