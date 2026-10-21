# Independent benchmark audit

The recorded data support enabling all three optimizations for this LED workload.
OpenCV thread count 1 is the best measured full-call setting; increasing it to 2 or
4 does not show a stable end-to-end gain after the optimizations.

## Integrity and correctness

An independent raw-CSV check, separate from `summarize.py`, verified:

- Exactly 5,184 calls: 8 images × 3 OpenCV thread settings × 2 modes × 6 cases ×
  (1 cold + 2 warmups + 15 measured).
- Exactly 288 image/thread/mode/case groups, with the complete and nonduplicated
  cold round -1, warmup rounds 0–1, and measured rounds 0–14 in every group.
- Each round has all six case positions 0–5 once; all padded inputs are 896×704.
- All 5,184 calls have identical semantic sets, strict sets, and raw result counts
  to their corresponding immutable original reference. There are zero differences.
- Every full-search invocation returns candidates; every empty-template invocation
  returns none. Candidate counts for images 1–8 are respectively
  52, 43, 33, 15, 37, 35, 41, 15 across every case/thread/repetition. These are
  match candidates, not counts of physical LEDs. CSV alone does not establish
  ground-truth localization; the separate overlay review provides that check.
- All 19 recorded SHA-256 source/input hashes match current files, including the
  measured core, immutable baseline, reference adapter, harness, SMD and 8 bitmaps.
  Neither `benchmark.cpp` nor the reference adapter was edited after measurement.

The refreshed summary also reports 288/288 measured groups, 15 samples each, no
missing groups, no phase sample-count errors and no equivalence differences.

## CV1 ablations

All values below are milliseconds: compute the median of 15 measured calls for
each image, then take the arithmetic mean of those eight medians. Cold and warmup
calls are excluded. These are full-search calls, OpenMP 4, OpenCV 1, 900 templates,
three pyramid levels `{4,8,8}`, threshold 75.

| Case | Complete construction | Spread | LUT response | Linearize | Search | Full wall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Immutable original | 14.794 | — | — | — | 27.026 | 42.621 |
| All options false | 15.334 | 0.953 | 1.483 | 2.711 | 27.405 | 44.505 |
| Separable spread only | 14.903 | 0.370 | 1.571 | 2.763 | 26.985 | 43.721 |
| Fused LUT + linearize only | 13.151 | 0.973 | 2.026 | 0 (fused) | 27.061 | 41.800 |
| Buffer reuse only | 11.526 | 0.920 | 0.999 | 1.971 | 27.401 | 38.975 |
| All three | 9.677 | 0.311 | 1.738 | 0 (fused) | 27.219 | 36.983 |

Against the all-false control, the independent improvements are:

| Option | Relevant stage change | Complete construction reduction | Full wall reduction |
| --- | --- | ---: | ---: |
| Spread only | Spread 0.953 → 0.370 ms, 61.2% less | 2.8% | 1.8% |
| Fusion only | Response + linearize 4.194 → 2.026 ms, 51.7% less | 14.2% | 6.1% |
| Reuse only | Gradient interval 10.019 → 7.505 ms; allocation reuse also affects subsequent stages | 24.8% | 12.4% |
| All three | Combined pipeline | 36.9% | 16.9% |

Against the immutable original, all three reduce construction by **34.6%**
(14.794 → 9.677 ms) and full wall time by **13.2%** (42.621 → 36.983 ms).
Benefits are not additive; search is still about 27 ms and is not optimized here.
The construction interval includes the Gaussian/Sobel/orientation/quantization
pipeline and all pyramid levels, not only the small LUT operation.

For a scheduling-aware cross-check, the median within-round speedups against
all-false are 1.015×/1.028× for spread, 1.070×/1.175× for fusion,
1.148×/1.330× for reuse, and 1.200×/1.579× for all three (full/construction).
The small spread-only full-call benefit is within ordinary per-call variation;
its isolated kernel improvement is much clearer than its end-to-end effect.

## Combined setting and OpenCV threads

Same averaging method as above, full-search calls, OpenMP fixed at four threads:

| OpenCV threads | Original construction | All-three construction | Original full wall | All-three full wall | Full reduction vs original |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 14.794 | 9.677 | 42.621 | 36.983 | 13.2% |
| 2 | 13.288 | 9.542 | 40.700 | 37.451 | 8.0% |
| 4 | 13.039 | 9.588 | 40.750 | 37.299 | 8.5% |

All-three construction changes only about 1.4%/0.9% when using 2/4 rather than 1
OpenCV threads. Full wall time is instead 1.3%/0.9% higher. Across individual image
medians, 2 threads improve full time in only 1/8 images; 4 threads improve it in
4/8 images. The arithmetic mean of per-image full-call p95 values is
40.053/44.132/41.788 ms for 1/2/4 threads respectively. These are averages of
per-image descriptive p95 values, not a pooled p95 or a confidence interval.

Empty-template construction medians independently show only a small thread gain:
9.226/9.140/9.043 ms for all-three at 1/2/4 threads. This reinforces that more
OpenCV threads are not a material benefit for the optimized complete pipeline on
these inputs. The original unoptimized pipeline benefits more from OpenCV threads.

## Interpretation and limits

Enabling all three options is supported by byte-level kernel tests, unchanged
complete match sets and the positive CV1 combined timing result. Keep OpenCV 1 and
OpenMP 4 as the measured recommendation for this workload; do not advertise a
threading speedup after optimization. The setting remains configurable.

Each image/thread/mode/case owns an independent workspace; two warmup calls precede
all 15 measured calls. Reuse-disabled paths use call-local storage and release it
before returning. Measured case order rotates and reverses; cold calls are ordered
with original first and are not used for performance conclusions. “Cold” means a
fresh workspace for that configuration, not a fresh process or cache flush.

Immutable-original external wall includes log capture plus allocation/copy when
converting its Match vector into adapter Results. Original parsed construction
and search timings exclude that conversion. The all-false control does not have
adapter overhead and is therefore important for isolating the options. It also
has different workspace allocation lifetimes from immutable original, so it is
not interchangeable with the original cross-version baseline.

The thread groups ran sequentially in one process on an i5-13500HX, GCC 15.1,
OpenCV 4.12, SSE/SSSE3/SSE4.1 build. `OMP_WAIT_POLICY=PASSIVE`, dynamic teams off,
and maximum active levels 1 were fixed across cases. This is one controlled run
over eight supplied positive images; it does not establish cross-machine speed,
cross-process statistical stability, false-positive accuracy, or behavior on a
broader production image distribution.
