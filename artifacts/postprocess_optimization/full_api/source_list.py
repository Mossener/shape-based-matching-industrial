"""Explicit immutable-source closure for the whole-API experiment, not production."""
from generate_sources import CORE, MIPP

LOCAL_FILES=(
    "records.hpp","matcher.hpp","wrapper_methods.inc","exact_v11.cpp","index_reserve.cpp",
    "output_binary.hpp","evidence.hpp","correctness.cpp","benchmark.cpp","replay.cpp",
    "fixtures.hpp","fixture_banks.hpp","fixture_bank_methods.inc","prepare_fixture_sources.py",
    "test_fixture_sources.py","FIXTURE_SOURCE_NOTES.md","SOURCE_STATUS.md",
    "generate_sources.py","source_list.py","freeze_manifest.py","prepare_historical_catalog.py",
    "HISTORICAL_TRACE_PINS.json","build_policy.py","output_contract.py",
    "correctness_contract.py","run_full_api.py","FULL_API_RUNNER_DESIGN.md",
    "tests/output_binary_contract.cpp","tests/fixture_contract.cpp","tests/test_source_generation.py",
    "tests/test_build_policy.py","tests/test_output_contract.py","tests/test_correctness_contract.py",
    "tests/test_runner_contract.py",
    "generated/SOURCE_RECEIPT.json","generated_fixtures/FIXTURE_SOURCE_MANIFEST.json",
    "generated_fixtures/led.hpp","generated_fixtures/magnet.hpp")
SOURCE_FILES=LOCAL_FILES+tuple(variant+"/"+name for variant in ("generated/baseline","generated/candidate")
                              for name in CORE+MIPP)+("generated/candidate/hash_consolidation.hpp",)

# SHA-pinned earlier evidence is consumed without executing its old programs.
PREREQUISITES=(
    ("artifacts/postprocess_optimization/SOURCE_ORIGINS.json",
     "f43361feb0d350f2487044fa8c13e0aa04d1ed80b66111d05a97b8dedf3267eb"),
    ("artifacts/independent_reviews/postprocess_actual_match_v1/ROOT_V11_ORIGIN_20261022.json",
     "b34a31bbbb9d1923ced4dc63a46179bb9f6be6ab0b9e0c035294995505dc87ec"),
    ("artifacts/postprocess_optimization/build/red_20261022_100607_058998/stage_result.json",
     "6db3f48ea591433dec82c212706dd3b3c031466ecfa0a80e41ed5b0891ab4a5b"),
    ("artifacts/postprocess_optimization/build/green_20261022_100729_165374/stage_result.json",
     "60b129e7073cf154a016fd986bfd956cf9907b746c072ad6dcfc57be50cbfc4e"),
    ("artifacts/independent_reviews/postprocess_actual_match_v1/review_actual_red_green_20261022.json",
     "ba51ab5d5259ed20958bfe5e94ad6e451a21f32e880f9f6d14c2d6a2147cb696"),
    ("artifacts/postprocess_optimization/standalone_contract.py",
     "5d85b257183f893f98ef72fc2c1df5533b1938e93270220734583a858b5a2eff"))
