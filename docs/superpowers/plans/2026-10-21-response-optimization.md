# Response construction optimization plan

**Goal:** Implement and independently verify separable bit spreading, fused response/linear-memory construction, reusable buffers, and thread tuning without changing matching semantics.

**Authorized scope:** User requested all proposed optimizations together, with independent validation, and subsequently requested local Git versions recording changes and effects. A local repository was initialized from the original project. Existing two/three-level LED experiments remain available; immutable baseline source copies and SHA-256 manifest live under `artifacts/response_optimization/baseline`.

**Design:** Keep the existing `Detector::match` signature. Add an explicit per-worker workspace/options overload so callers can reuse memory and select independently measurable stages. Existing calls use an independent thread-local workspace. OpenCV thread count stays application-controlled; benchmark 1/2/4 without a hidden global library setting.

## Tasks

- [x] Write and run independent kernel tests against scalar OR and the original similarity LUT/linearize semantics before implementing optimized kernels.
- [x] Implement `line2Dup_spread.hpp`: `line2Dup::detail::spreadSeparable(src,dst,scratch,T)`, forward bitwise OR, zero outside the image, preserve strides, safe for narrow images.
- [x] Implement `line2Dup_response.hpp`: `line2Dup::detail::ResponseLUT(lut)` and `.linearize(src,memories,T)` producing eight final linear memories with no full-size response/nibble intermediates. Byte-for-byte validation against the original LUT.
- [x] Add `MatchOptions`, `MatchWorkspace`, and phase timings; retain the original path under options, keep workspace data per worker, and refresh source/mask/thresholds every call.
- [x] Validate all independent configurations and their combination against the immutable original implementation, including masks, gray/color inputs, size changes, multiple workers, two/three pyramid levels, and all 8 LED images.
- [x] Benchmark baseline, spread only, fusion only, reuse only, all optimizations, and OpenCV thread counts 1/2/4 using alternating order and no simultaneous benchmark jobs. Preserve raw phase/total times and correctness results.
- [x] Request independent code review, address findings, rerun affected checks, and publish concise per-optimization results with a reproducible runner.

## Verification contract

No change to blur kernel, gradient quantization, direction count, thresholds, templates, angle/scale bank, or search area. Compare intermediate matrices byte-for-byte. Compare match sets after canonical sorting because equal-score OpenMP order is unspecified. Performance improvements must be measured rather than inferred from loop counts. Any unsuccessful tuning is reported instead of silently promoted.
