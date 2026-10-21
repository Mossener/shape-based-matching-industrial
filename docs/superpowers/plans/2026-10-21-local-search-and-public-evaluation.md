# Local search and public evaluation iteration

**Goal:** Identify the dominant remaining search cost, reduce it without changing matching decisions, and establish a small reproducible real-image evaluation slice.

**Architecture:** Keep the current matcher as a selectable comparison path. Profile an isolated instrumented copy, then implement a local 16×16 accumulator that can retain one row in SIMD registers and return the first row-major maximum. Normalize using the original feature count and float operation order. Public data and annotations stay separate from equivalence fixtures; cached external assets are ignored by Git.

**Tech stack:** C++14, OpenCV 4.12, bundled MIPP/SSE4.1, OpenMP, Python 3.10, PowerShell. Other instruction sets are not newly claimed as validated.

**Spec:** No change to template bank, threshold, feature count, spatial search, input preprocessing, tie selection, all-zero result, or per-candidate out-of-bounds feature skipping. An optimization is retained only after independent correctness comparison and paired timing. A real-image evaluation must state its source, license, train/test split, localization definition, negative images, and limitations; similarity scores are not probabilities.

- [x] Profile coarse accumulation, candidate collection, per-level local accumulation/maximum/filtering and final sorting using identical existing fixtures. Verify the instrumented copy agrees with the current matcher before timing.
- [x] Add failing behavioral tests for local row accumulation and maximum selection: byte/word transition, highest legal feature count, first ties, zero and skipped features, non-contiguous source rows, and exact scores.
- [x] Implement a selectable local register accumulator, preserving the existing path for isolation. Dispatch only to validated instruction-set code and keep the existing implementation elsewhere.
- [x] Compare the new path and fallback with frozen V4 integration results, masks, changing workspaces/thread counts, and concurrent calls.
- [x] Run one CPU performance experiment at a time, alternating fallback/new paths; preserve raw timings, configuration, source hashes and failed/no-gain results.
- [ ] Obtain a small clearly licensed public dataset slice, commit acquisition/annotation metadata and keep images out of Git. Add a fixed train/test evaluation entry point and report detection/localization failures honestly.
- [ ] Request independent review, record measured changes and limits in the version log, commit/tag/push verified changes, and continue the next iteration under the user's ongoing authorization.

The user explicitly authorized autonomous ongoing iteration until they stop it; this plan does not require a new approval checkpoint.
