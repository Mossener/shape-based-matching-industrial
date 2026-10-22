"""Copy/verify immutable V11 and V18 origins; no native compile or image decode."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V1 = HERE.parent / "v11_candidate_experiment"
COMMIT = "b25df46f6ddf9c24fb43f5836f1414dc38c8caed"
BASELINE_SHA = "505c0ccd0ebad8b2db6b51b0e341433f6fb44849dd8dd3adbe42899692491aa2"
CORE = ("line2Dup.cpp", "line2Dup.h", "line2Dup_local.hpp", "line2Dup_search.hpp",
        "line2Dup_response.hpp", "line2Dup_spread.hpp", "line2Dup_matches.hpp")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def exact(path, data, create):
    if path.exists():
        require(path.is_file() and path.read_bytes() == data, "Refusing differing bytes: " + str(path))
    else:
        require(create, "Missing frozen file: " + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("freeze", "verify"), required=True)
    args = parser.parse_args()
    create = args.mode == "freeze"
    origin_bytes = (V1 / "baseline/manifest.json").read_bytes()
    require(sha(origin_bytes) == BASELINE_SHA, "V1 frozen baseline manifest differs")
    baseline = json.loads(origin_bytes)
    require(baseline["commit"] == COMMIT and len(baseline["files"]) == 23, "V11 source inventory differs")
    names = sorted(baseline["files"])
    process = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT,
                             input="".join(COMMIT + ":" + name + "\n" for name in names).encode(),
                             capture_output=True, check=True)
    stream = io.BytesIO(process.stdout)
    files, protected = {}, {}

    def record(destination, source, data):
        exact(HERE / destination, data, create)
        source = str(source.resolve())
        protected[source] = sha(data)
        files[destination] = {"source": source, "sha256": sha(data), "bytes": len(data)}

    for name in names:
        blob, kind, size = stream.readline().strip().split()
        require(kind == b"blob", "Non-blob frozen source")
        data = stream.read(int(size))
        require(stream.read(1) == b"\n", "Invalid batch blob separator")
        expected = baseline["files"][name]
        require(blob.decode() == expected["git_blob"] and sha(data) == expected["sha256"] and
                len(data) == expected["bytes"], "Exact Git baseline identity differs: " + name)
        source = V1 / "baseline" / name
        require(source.read_bytes() == data, "V1 source differs from Git: " + name)
        record("baseline/" + name, source, data)
        protected[str((ROOT / name).resolve())] = sha((ROOT / name).read_bytes())
    require(not stream.read(), "Unexpected extra batch source bytes")
    record("baseline/manifest.json", V1 / "baseline/manifest.json", origin_bytes)
    change_path = V1 / "candidate_change_manifest.json"
    change_bytes = change_path.read_bytes()
    change = json.loads(change_bytes)
    require(change["baseline_commit"] == COMMIT and change["baseline_manifest_sha256"] == BASELINE_SHA,
            "V18 control baseline differs")
    expected_core = {item["path"]: item["candidate_sha256"] for item in change["core"]}
    for name in CORE + ("line2Dup_local_cache.hpp",):
        source = V1 / "candidate" / name
        data = source.read_bytes()
        expected = change["cache_header_sha256"] if name == "line2Dup_local_cache.hpp" else expected_core[name]
        require(sha(data) == expected, "Frozen V18 control differs: " + name)
        record("linear/" + name, source, data)
        if name in CORE:
            record("direct/" + name, source, data)
    record("origins/v18_candidate_change_manifest.json", change_path, change_bytes)
    green_path = V1 / change["literal_green_evidence"]
    green_bytes = green_path.read_bytes()
    require(sha(green_bytes) == change["literal_green_evidence_sha256"], "V18 cache GREEN evidence differs")
    record("origins/v18_cache_green.json", green_path, green_bytes)
    helpers = {
        "v11_reference.hpp": "v11_reference.hpp",
        "v11_reference.cpp": "v11_reference.cpp",
        "benchmark_fixtures.hpp": "origins/v1_fixtures.hpp",
        "tests/matcher_contract_test.cpp": "origins/v1_matcher_contract.cpp",
        "run_cache_contract.ps1": "origins/v1_run_cache_contract.ps1",
        "run_correctness.ps1": "origins/v1_run_correctness.ps1",
        "run_benchmark.ps1": "origins/v1_run_benchmark.ps1",
        "summarize.py": "origins/v1_summarize.py",
    }
    for origin, destination in helpers.items():
        source = V1 / origin
        record(destination, source, source.read_bytes())
    # Protect the earlier production and failed-experiment paths already pinned
    # by V18 correctness, without opening or decoding any heldout RGB.
    previous_build = json.loads((V1 / "matcher_build_20261021_230741_506.json").read_text(encoding="utf-8-sig"))
    for path, expected in previous_build["protected_source_sha256"].items():
        actual = sha((ROOT / path).read_bytes())
        require(actual.upper() == expected, "Earlier protected source changed: " + path)
        protected[str((ROOT / path).resolve())] = actual
    manifest = {"baseline_commit": COMMIT, "baseline_manifest_sha256": BASELINE_SHA,
                "method": "batched exact Git blob verification; byte copies only, never newline conversion",
                "files": files, "protected_source_sha256": protected,
                "direct_cache_header": "not copied from V18; literal no-op stub and RED precede direct algorithm",
                "limitation": "Provenance preparation only; zero native compilation/matcher calls/image decodes"}
    encoded = (json.dumps(manifest, indent=2) + "\n").encode()
    exact(HERE / "origins/manifest.json", encoded, create)
    for directory, expected in (("baseline", set("baseline/" + name for name in names) | {"baseline/manifest.json"}),
                                ("linear", set("linear/" + name for name in CORE + ("line2Dup_local_cache.hpp",)))):
        actual = {path.relative_to(HERE).as_posix() for path in (HERE / directory).rglob("*") if path.is_file()}
        require(actual == expected, "Frozen inventory differs: " + directory)
    print(json.dumps({"passed": True, "mode": args.mode, "frozen_files": len(files),
                      "protected_files": len(protected), "manifest_sha256": sha(encoded),
                      "native_calls": 0, "image_decodes": 0}))


if __name__ == "__main__":
    main()
