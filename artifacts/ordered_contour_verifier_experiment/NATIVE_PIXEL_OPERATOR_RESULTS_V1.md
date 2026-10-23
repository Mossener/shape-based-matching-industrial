# Native pixel operator synthetic results V1

The coordinator compiled and executed the same frozen 22-test suite against the zero stubs and implementation. Actual RED recorded **970 checks, 338 assertion failures, zero errors**, exit 1. Actual GREEN recorded **8,452 checks, zero failures/errors**, exit 0. Additional GREEN checks are complete pixel comparisons guarded by successful matrix shape/type checks; the test bytes did not change.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `native_pixel_operator.hpp` | 2,069 | `2098d4b3ac83b0825fff9be2a06615a27fa14865d66ff30e7e3574b571700956` |
| RED `native_pixel_operator.cpp` | 675 | `d8a371813b7193a9bbd8b1943a8c9b0f6b512fc87b875e0c054ba53ae0a8a71c` |
| GREEN `native_pixel_operator.cpp` | 4,405 | `cefc9b9e8632d4b2b9738d658a5ce8cdd5e9cdbd3cffcb293c9ede039e8601e9` |
| Frozen `native_pixel_operator_test.cpp` | 17,821 | `3ff954d831293b9478a78535bfe036b1e93ae76954b3aeeadcf4943b6571cc1d` |

The adapter validates nonempty two-dimensional `CV_8UC1` input/mask and matching sizes. It owns logical ROI rows before calling the unchanged frozen V11 public `ColorGradientPyramid(20,32,40)` and `quantize`, then returns independent full-size unspread/magnitude-squared/phase matrices. No hook, core fork or gradient reimplementation was needed. It decodes all bytes before selection, rejects every multibit byte, uses invalid label 255, retains full official nonzero mask with finite magnitude-squared strictly above 1600 for templates, and keeps weak20 scene labels without a strong threshold. It performs no erosion or historical 2x2 strongest-point sampling.

Literal synthetic tests cover all single/multibit values, typed/shape rejection, independently strided fields, noncontinuous odd-width ROIs and parent poison, full-mask singleton retention, finite/NaN/Inf selection, exact weak400/strong1600 equality, tiny images, caller immutability, and complete constant/axis-ramp magnitude/phase/bits/label grids. A vertical-ramp fixture includes the four inner corners where five forced-zero raw border votes select bin0 despite a 90-degree center phase. This checks exported histogram behavior rather than recomputing the center angle bin.

| Recorded phase | Wall | Peak process working set | Other observation |
| --- | ---: | ---: | --- |
| RED build helper | 6.390 s | 23,760,896 B | Compiler Job peak committed 553,201,664 B |
| RED test | 0.063 s | 12,271,616 B | Expected exit 1 |
| GREEN build helper | 7.344 s | 23,891,968 B | Compiler Job peak committed 554,975,232 B |
| GREEN test | 0.078 s | 13,611,008 B | Exit 0 |

Build limits were 180 s, helper working-set threshold 1 GiB and output threshold 128 MiB; the separate compiler Job committed-memory limit was 1 GiB and included GCC children. Test limits were 60 s, process working-set threshold 512 MiB and output threshold 64 MiB. Committed memory differs from working set; polling watchdogs stop after observed excess and do not provide an allocation barrier or aggregate coordinator RSS bound. The inherited resource/provenance limitations in `NATIVE_RESOURCE_SCOPE_SUPPLEMENT_V1.md` still apply, including unguarded metadata queries and OS/dynamic-import limits. The short synthetic wall measurements include startup/assertions and are not native speed benchmarks.

Retained RED receipt: `native_pixel_operator_red_v1/receipt.json`, 113,931 B, SHA-256 `4129831ce7485a66915ff17c841dae187210514c7f2ee1a6c91495244b0821ab`. Retained GREEN receipt: `native_pixel_operator_green_v1/receipt.json`, 113,953 B, SHA-256 `223cb910b49d27ae634b49c392b8ad8b2dc4fd11feda1be749422601689eb829`. Each includes exact source/compiler dependency/runtime pins and executes archived source. Top-level RED `passed=true` means its expected assertion-failing gate passed; the test guard correctly records failure/exit 1.

This result is finite synthetic characterization of the adapter and inherited OpenCV axis behavior, **not an independent original-pixel gradient oracle** or exhaustive phase/histogram characterization. No image files were decoded, real payloads read, matcher called, bank reconstructed, full attempts replayed, or real quality/speed measured. The operator author performed only source/report edits and static inspection; compilation/execution belongs to the coordinator's receipts. Production and V31 sources remain unchanged. `NATIVE_PIXEL_OPERATOR_DECISIONS_V1.json` preserves its original RED-only preparation state; these later receipts establish actual implementation results.
