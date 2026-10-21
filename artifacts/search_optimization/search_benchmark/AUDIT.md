# Independent search-optimization audit

Correctness and data integrity pass. This run shows a small LED improvement,
primarily from integer argmax, rather than a substantial or consistently general
speedup from all three changes. Case1 does not show a search-time improvement.

## Integrity and correctness

Independent raw-data and hash checks, without rerunning performance, verified:

- Exactly 972 rows and 162 dataset/image/case/phase groups: nine images × six cases
  × (one cold + two warmups + fifteen measured calls).
- All groups contain precisely the intended round numbers, without duplication;
  every round contains case positions 0–5 once.
- Every recorded semantic/strict/count comparison passes. Best score, candidate
  count and template ID are unchanged across configurations for each image.
  The harness computes exact sets in memory; the audit checks its recorded flags
  and the additional raw result metadata, without a new matcher run.
- All nine fixtures return candidates. LED counts are 52/43/33/15/37/35/41/15;
  case1 returns seven. LED best scores span 86.017–98.411; case1 is 98.664.
  Candidate counts are not counts of physical objects or a broad accuracy metric.
- Recorded dimensions, channels, thresholds, template counts, levels and thread
  settings are correct: LED gray 896×704/900/L3/75; case1 BGR
  1088×960/361/L2/90; CV1/OMP4 throughout.
- All 25 measured source/input SHA-256 entries match current files, and the
  immutable V4 baseline matches both hashes in its manifest.
- Internal total/construction/search intervals are finite, nonnegative and do not
  overlap beyond the existing floating-point tolerance.

Machine-readable results are in `independent_audit.json`. The source, fixtures,
core and reference adapter were not edited after measurement. The runner's later
test-reporting enhancement does not alter the measured executable's source.

## LED timing

Units are milliseconds. For each image, take the median of its fifteen measured
calls, then average those eight medians. Cold and warmup rows are excluded.
All configurations retain the previous three preprocessing optimizations.

| Configuration | Search | Core total (`api_total_ms`) | Search reduction vs V4 | Core-total reduction vs V4 |
| --- | ---: | ---: | ---: | ---: |
| Immutable V4 | 28.781 | 38.763 | — | — |
| Search options all false | 28.766 | 39.038 | 0.05% | -0.71% |
| Integer argmax only | 27.559 | 37.611 | 4.25% | 2.97% |
| Direct 8-bit only | 28.845 | 38.717 | -0.22% | 0.12% |
| Search scratch reuse only | 28.580 | 38.708 | 0.70% | 0.14% |
| All three | 27.666 | 37.873 | 3.87% | 2.30% |

Against the current all-false control, integer argmax reduces search/core total by
4.20%/3.66%; direct 8-bit by -0.28%/0.82%; scratch reuse by 0.65%/0.85%; all three
by 3.82%/2.99%. Negative reductions mean slower.

Integer-only search medians improve in 7/8 LED images. All-three improves in 6/8;
image 6 contributes approximately 52% of its summed search saving and 63% of its
summed core-total saving. Consequently the aggregate improvement is sensitive to
this particular image set. The combined result does not outperform integer-only
in the aggregate and does not establish additive gains from direct 8-bit or reuse.

Within-round V4/all-three speedup has a median of 1.042× for search and 1.026× for
core total; descriptive 5th–95th percentiles are 0.807–1.312× and 0.853–1.253×.
These use the formal summary's linear interpolation at sorted index `(n−1)p`.
The independent variants also have paired ranges crossing 1. These are noisy
per-call descriptive ranges, not confidence intervals or proof of no benefit.

## Case1 timing

This is one different workload, so its single-image medians are not averaged with
LED. It uses the supplied 361 templates and the actual original test input path,
not the README's historical unspecified machine/configuration.

| Configuration | Search | Core total (`api_total_ms`) | Search reduction vs V4 | Core-total reduction vs V4 |
| --- | ---: | ---: | ---: | ---: |
| Immutable V4 | 1.713 | 17.592 | — | — |
| Search options all false | 1.793 | 17.517 | -4.66% | 0.43% |
| Integer argmax only | 1.800 | 17.219 | -5.08% | 2.12% |
| Direct 8-bit only | 1.820 | 17.326 | -6.21% | 1.51% |
| Search scratch reuse only | 1.806 | 17.022 | -5.43% | 3.24% |
| All three | 1.783 | 17.140 | -4.07% | 2.57% |

Against the all-false control, all-three changes search/core total by 0.56%/2.15%.
Its construction interval also changes from V4's 15.890 ms to 15.342 ms even though
the preprocessing settings are fixed. Thus a smaller full-call time is not
evidence of successful search optimization on case1. Its all-three paired search
speedup median is 0.997×, with a descriptive 5th–95th range of 0.765–1.317×.

Case1's coarse/fine templates exceed 64 features, so it does not exercise the
direct-8-bit branch. Its small measured changes help illustrate noise and control
path differences; they must not be presented as an 8-bit kernel benefit.

## Reproducibility and interpretation

Primary search conclusions use `search_ms`; comparable core-call totals use
`api_total_ms`. V4's external wall also includes adapter result-vector allocation
and conversion, while these internal intervals exclude it. Using internal times
avoids counting that adapter overhead as an optimization benefit.

Cases were interleaved in the same process with rotating/reversed measured order,
independent current workspaces and a V4 workspace reset per image. CV1/OMP4 and
passive waiting were fixed. This remains one run on one machine over nine supplied
positive fixtures. It does not establish cross-process stability, universal
speedup, or general detection accuracy. The much larger LED/case1 search-time
difference is consistent with their different workloads; without internal search
profiling, this experiment does not attribute the difference to individual search
operations. These three changes do not make the LED search approach case1 time.

The implementation is semantically supported; integer argmax is the most promising
LED timing change. Preserve the independent switches and report the observed
small gains honestly. This evidence is insufficient to claim direct 8-bit or
scratch reuse brings a stable individual end-to-end gain, or that the combination
is universally better than integer-only.

## Test runner verification

After performance completed, the enhanced `-Test` path compiled and passed:

- Search kernels: 1,876 maps, 34,855 bit-exact scores, 278,840 threshold pairs and
  nine invalid-argument rejections.
- Workspace integration: 480 V4-equivalent calls across all eight switch
  combinations, nine positive fixtures, masks, empty candidates, worker-count
  resize, Detector/size/channel changes; plus moves and two concurrent workers.
  Strict-set differences are zero.
- Configuration smoke, Python statistics self-test and the 33-column CSV layout
  check also pass.

`../search_test_results.json` retains both outputs, exit codes, executable hashes
and tested source hashes. No new performance measurement was run during audit.
