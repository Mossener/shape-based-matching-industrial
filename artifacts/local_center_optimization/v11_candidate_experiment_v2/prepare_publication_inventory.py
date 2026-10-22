"""Inventory the completed V2 correctness/timing milestone, without Git writes.

Only explicit completed source/evidence groups are selected. Unexecuted
diagnostic files and mutable plans are intentionally outside the selection.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "PUBLICATION_INVENTORY_V2.json"

ROOT_FILES = (
    "auxiliary_dependencies.py", "benchmark.cpp", "benchmark_contract.py", "benchmark_statistics.py",
    "benchmark_validator_green_20261022_002825_145771.json", "benchmark_validator_red_20261022_002721_213845.json",
    "correctness_evidence.py", "CORRECTNESS_RESULT.md", "dependency_pins.py", "DESIGN.md", "fixtures.hpp",
    "literal_green_20261022_000824_614.json", "literal_red_20261022_000714_516.json", "prepare_sources.py",
    "prepare_publication_inventory.py", "PROTOCOL_DRAFT.json", "REGRESSION_MATRIX.json", "RESULT_V2.md",
    "run_benchmark.py", "run_benchmark_validator.py", "run_cache_contract.ps1", "run_correctness.ps1",
    "run_correctness.py", "run_summary_validator.py", "summarize_benchmark.py",
    "summary_validator_green_20261022_005905_053308.json", "v11_reference.cpp", "v11_reference.hpp",
    "v18_reference.cpp", "v18_reference.hpp")
TEST_FILES = ("benchmark_contract_test.py", "benchmark_statistics_test.py", "benchmark_summary_test.py",
              "direct_cache_contract.cpp", "matcher_contract.cpp", "test_evidence.py")
TREES = (
    ("baseline", "frozen_origin_sources"), ("linear", "frozen_linear_sources"),
    ("direct", "fixed_direct_candidate_sources"), ("origins", "frozen_derivation_receipts"),
    ("correctness_core_20261022_003538_097850", "successful_correctness_evidence"),
    ("correctness_flags_20261022_005324_876657", "successful_correctness_evidence"),
    ("correctness_lifetime_20261022_003453_156424", "successful_correctness_evidence"),
    ("benchmark_20261022_012041_421590", "successful_benchmark_evidence"),
    ("build/matcher_20261022_003331_222515", "correctness_build_dependencies_and_logs"),
    ("build/benchmark_20261022_010835_118746", "benchmark_build_dependencies_and_logs"))
REVIEWS = ("audit_benchmark.py", "test_benchmark_arithmetic.py", "root_review_all_stages_20261022.json",
           "root_review_core_lifetime_20261022.json", "root_benchmark_build_review_20261022.json",
           "root_benchmark_arithmetic_20261022.json")
EXCLUDED_DIAGNOSTIC = (
    "diagnostic", "diagnostic.cpp", "DIAGNOSTIC.md", "diagnostic_evidence.py", "diagnostic_reference.cpp",
    "diagnostic_reference.hpp", "diagnostic_shadow.hpp", "prepare_diagnostic.py", "run_diagnostic.py",
    "run_diagnostic_validator.py", "tests/diagnostic_evidence_test.py", "tests/diagnostic_shadow_contract.cpp")
EXCLUDED_PLANS = ("PLAN.md", "BENCHMARK_EXECUTION_PLAN.md", "SOURCE_CHANGES.md")
FORBIDDEN_SUFFIXES = {".exe", ".o", ".obj", ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".bmp",
                      ".tiff", ".tif", ".gif", ".webp", ".dll", ".a"}


def relative(path):
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(ROOT):
        raise ValueError("Publication path escaped repository: " + str(path))
    return resolved.relative_to(ROOT).as_posix()


def excluded(path):
    return "__pycache__" in path.parts or path.suffix.lower() in FORBIDDEN_SUFFIXES


def main():
    selected = {}

    def add(path, category):
        if not path.is_file() or excluded(path):
            raise ValueError("Explicit publication file is missing or excluded: " + str(path))
        name = relative(path)
        if "diagnostic" in path.name.lower() or "diagnostic" in path.parts:
            raise ValueError("Unexecuted diagnostic must stay excluded: " + name)
        if name in selected:
            raise ValueError("Duplicate explicit publication path: " + name)
        data = path.read_bytes()
        selected[name] = dict(path=name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                              category=category)

    for name in ROOT_FILES:
        add(HERE / name, "completed_sources_and_receipts")
    for name in TEST_FILES:
        add(HERE / "tests" / name, "completed_test_sources")
    omitted = []
    for name, category in TREES:
        directory = HERE / name
        if not directory.is_dir():
            raise ValueError("Missing completed evidence/source tree: " + name)
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                if excluded(path):
                    omitted.append(relative(path))
                else:
                    add(path, category)
    review_root = ROOT / "artifacts/independent_reviews/direct16_correctness_v2"
    for name in REVIEWS:
        add(review_root / name, "completed_independent_review")
    files = [selected[name] for name in sorted(selected)]
    result = dict(schema_version=1, inventory_root=str(ROOT),
        status="Publication candidate inventory only; no staging, commit or production adoption performed",
        decision="Fixed direct16 did not outperform frozen linear16 in this run; remain off by default",
        correctness=dict(matcher_calls=6609, complete_ordered_comparisons=5504, equal=True),
        benchmark=dict(matcher_calls=2250, formal_measured_rows=1875, fixed_images=25, equal=True,
            direct_on_over_linear_on_search_image_median=1.0101880403893826,
            direct_on_over_linear_on_total_image_median=1.037551478682672,
            search_regressions=15, total_regressions=19),
        file_count=len(files), total_bytes=sum(item["size_bytes"] for item in files), files=files,
        excluded_unexecuted_diagnostic=[str((HERE / name).relative_to(ROOT).as_posix())
                                       for name in EXCLUDED_DIAGNOSTIC],
        excluded_mutable_plans=[str((HERE / name).relative_to(ROOT).as_posix()) for name in EXCLUDED_PLANS],
        excluded_generated_or_media=omitted,
        exclusion_rules=["No executable/object, pycache, images or toolchain libraries",
                         "No unexecuted diagnostic source, plan or directory",
                         "This inventory does not include itself, avoiding a circular self-hash"],
        referenced_external_inputs="Existing source, image and toolchain paths inside evidence receipts remain references; not copied by this inventory",
        limitation="Single local timing run and exercised equality only; no universal speed or accuracy gain")
    if OUTPUT.exists():
        raise ValueError("Refusing to overwrite an existing publication inventory")
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    # Byte verification only. No matcher, decoder, compiler or Git mutation.
    for item in files:
        data = (ROOT / item["path"]).read_bytes()
        if len(data) != item["size_bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Publication inventory changed during construction: " + item["path"])
    print(str(OUTPUT))
    print("files=" + str(len(files)) + " bytes=" + str(result["total_bytes"]))
    print("inventory_sha256=" + hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
