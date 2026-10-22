"""Byte-only source freezing for the two private V11 translation units.

Running main reads source/JSON evidence only. It never invokes a compiler,
native test, detector, image decoder or Git. Failure preserves partial output;
there is no retry, overwrite or deletion. Imports have no filesystem effects.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / "artifacts/local_center_optimization/v11_candidate_experiment_v2/baseline"
BASELINE = "b25df46f6ddf9c24fb43f5836f1414dc38c8caed"
ORIGINS = HERE.parent / "SOURCE_ORIGINS.json"
ORIGINS_SHA = "f43361feb0d350f2487044fa8c13e0aa04d1ed80b66111d05a97b8dedf3267eb"
ROOT_ATTESTATION = ROOT / "artifacts/independent_reviews/postprocess_actual_match_v1/ROOT_V11_ORIGIN_20261022.json"
ROOT_ATTESTATION_SHA = "b34a31bbbb9d1923ced4dc63a46179bb9f6be6ab0b9e0c035294995505dc87ec"
HELPER = HERE.parent / "candidate/hash_consolidation.hpp"
HELPER_SHA = "c45e21978fb142d697e139bc2aa3c83e78247052c717e52d188e13da909cbbda"
CORE = ("line2Dup.cpp", "line2Dup.h", "line2Dup_local.hpp", "line2Dup_search.hpp",
        "line2Dup_response.hpp", "line2Dup_spread.hpp", "line2Dup_matches.hpp")
MIPP = ("MIPP/math/avx512_mathfun.h", "MIPP/math/avx512_mathfun.hxx",
        "MIPP/math/avx_mathfun.h", "MIPP/math/avx_mathfun.hxx", "MIPP/math/neon_mathfun.h",
        "MIPP/math/neon_mathfun.hxx", "MIPP/math/sse_mathfun.h", "MIPP/math/sse_mathfun.hxx",
        "MIPP/mipp.h", "MIPP/mipp_impl_AVX.hxx", "MIPP/mipp_impl_AVX512.hxx",
        "MIPP/mipp_impl_NEON.hxx", "MIPP/mipp_impl_SSE.hxx", "MIPP/mipp_object.hxx",
        "MIPP/mipp_scalar_op.h", "MIPP/mipp_scalar_op.hxx")
INCLUDE = b'#include "line2Dup_matches.hpp"\n'
EXTRA_INCLUDE = b'#include "hash_consolidation.hpp"\n'
OLD_CALL = b'detail::consolidateMatches(matches);'
NEW_CALL = b'postprocess_hash::consolidateMatches(matches);'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(name):
    require(type(name) is str and bool(name) and "\\" not in name and ":" not in name and
            "\0" not in name and not name.startswith("/"), "Unsafe relative path")
    path = PurePosixPath(name)
    require(bool(path.parts) and str(path) == name and all(part not in ("", ".", "..") for part in path.parts),
            "Noncanonical relative path")
    return Path(*path.parts)


def candidate_bytes(original):
    require(type(original) is bytes, "Literal source bytes required")
    require(original.count(INCLUDE) == 1 and original.count(OLD_CALL) == 1 and
            EXTRA_INCLUDE not in original and NEW_CALL not in original, "Unique untouched V11 seams required")
    changed = original.replace(INCLUDE, INCLUDE + EXTRA_INCLUDE, 1).replace(OLD_CALL, NEW_CALL, 1)
    # Reverse proof prevents accidental additional transformations.
    require(changed.replace(INCLUDE + EXTRA_INCLUDE, INCLUDE, 1).replace(NEW_CALL, OLD_CALL, 1) == original,
            "Two-seam reverse proof failed")
    return changed


def fresh_destination(here, destination):
    here = Path(here).resolve(strict=True)
    destination = Path(destination).resolve()
    require(destination == here / "generated", "Fresh direct generated/ child required")
    require(not destination.exists(), "Source output already exists; preserve it and stop")
    return destination


def read_pinned(path, expected_hash=None, expected_bytes=None):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), "Regular source/evidence file required")
    data = path.read_bytes()
    require(expected_hash is None or digest(data) == expected_hash, "Source SHA differs: " + str(path))
    require(expected_bytes is None or len(data) == expected_bytes, "Source size differs: " + str(path))
    return data, dict(path=str(path), bytes=len(data), sha256=digest(data))


def prepare():
    destination = fresh_destination(HERE, HERE / "generated")
    inputs = []
    origins_bytes, item = read_pinned(ORIGINS, ORIGINS_SHA)
    inputs.append(item)
    origins = json.loads(origins_bytes)
    attestation_bytes, item = read_pinned(ROOT_ATTESTATION, ROOT_ATTESTATION_SHA)
    inputs.append(item)
    attestation = json.loads(attestation_bytes)
    require(origins["baseline_commit"] == attestation["revision"] == BASELINE and
            attestation["passed"] is True and attestation["checked_source_files"] == 23,
            "Fixed accepted V11 source attestation required")
    manifest_bytes, item = read_pinned(FROZEN / "manifest.json",
        attestation["frozen_manifest"]["sha256"], attestation["frozen_manifest"]["bytes"])
    inputs.append(item)
    manifest = json.loads(manifest_bytes)
    require(manifest["commit"] == BASELINE and set(manifest["files"]) == set(CORE + MIPP),
            "Exact seven-core/sixteen-MIPP source allowlist required")
    frozen_pins = {}
    for pin in origins["frozen_baseline_files"]:
        relative = Path(pin["path"]).resolve(strict=True).relative_to(FROZEN.resolve(strict=True)).as_posix()
        require(relative not in frozen_pins, "Duplicate frozen pin")
        frozen_pins[relative] = pin
    require(set(frozen_pins) == set(CORE + MIPP) | {"manifest.json"}, "Exact twenty-four frozen pins required")
    require(frozen_pins["manifest.json"]["sha256"] == item["sha256"] and
            frozen_pins["manifest.json"]["bytes"] == item["bytes"], "Frozen manifest pin differs")
    roots = {record["relative_path"]: record for record in attestation["records"]}
    require(len(roots) == len(attestation["records"]) == 23 and set(roots) == set(CORE + MIPP),
            "Exact root Git attestation records required")
    sources = {}
    for relative in CORE + MIPP:
        approved = manifest["files"][relative]
        root_record = roots[relative]
        require(root_record["frozen_equals_git_blob"] is True and
                root_record["production_equals_git_blob"] is True and
                approved["sha256"] == frozen_pins[relative]["sha256"] == root_record["sha256"] and
                approved["bytes"] == frozen_pins[relative]["bytes"] == root_record["bytes"] and
                approved["git_blob"] == root_record["git_blob"], "Source provenance disagreement: " + relative)
        data, pin = read_pinned(FROZEN / safe_relative(relative), approved["sha256"], approved["bytes"])
        sources[relative] = data
        inputs.append(pin)
    helper, pin = read_pinned(HELPER, HELPER_SHA)
    inputs.append(pin)
    for path in (Path(__file__), HERE / "tests/test_source_generation.py"):
        _, pin = read_pinned(path)
        inputs.append(pin)
    planned = {}
    for variant in ("baseline", "candidate"):
        for relative, data in sources.items():
            planned[variant + "/" + relative] = (candidate_bytes(data)
                if variant == "candidate" and relative == "line2Dup.cpp" else data)
    planned["candidate/hash_consolidation.hpp"] = helper
    require(len(planned) == 47, "Source copy budget differs")
    # No output is created until every declared input and transform is checked.
    destination.mkdir()
    files = []
    for relative, data in planned.items():
        path = destination / safe_relative(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(data)
        require(path.read_bytes() == data, "Written source bytes differ")
        files.append(dict(relative=relative, bytes=len(data), sha256=digest(data)))
    for pin in inputs:
        read_pinned(pin["path"], pin["sha256"], pin["bytes"])
    receipt = dict(schema="whole_api_literal_sources_v1", prepared_utc=datetime.now(timezone.utc).isoformat(),
        baseline_commit=BASELINE, input_pins=inputs, files=files,
        candidate_transforms=[dict(old=INCLUDE.decode(), new=(INCLUDE + EXTRA_INCLUDE).decode(), occurrences=1),
                              dict(old=OLD_CALL.decode(), new=NEW_CALL.decode(), occurrences=1)],
        baseline_source_files=23, candidate_source_files=24, native_compilations=0,
        native_executions=0, detector_calls=0, image_or_smd_reads=0, git_commands=0,
        limitations=["Source-only byte freezing, no native build or run",
                     "Root Git-byte attestation is pinned, not rerun by this script",
                     "Wrappers and future dependencies/build/harness require separate review"])
    path = destination / "SOURCE_RECEIPT.json"
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(receipt, output, indent=2)
        output.write("\n")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        path = prepare()
        print(json.dumps(dict(source_receipt=str(path), sha256=digest(path.read_bytes())), indent=2))
        return 0
    except Exception as error:
        print("SOURCE PREPARATION FAILED; evidence preserved: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
