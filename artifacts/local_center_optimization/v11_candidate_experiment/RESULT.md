# V11 final-level duplicate-center cache: independent result

The private sixteen-entry cache preserved the complete ordered V11 output on
the declared correctness matrix. It reduced LED search time substantially in
this run, but regressed on twelve of sixteen tiny T-LESS development images.
It should remain an explicit experimental option rather than a universal
default. This experiment does not improve recognition accuracy.

## Change and baseline

Baseline is exact commit `b25df46f6ddf9c24fb43f5836f1414dc38c8caed`:
seven matcher files and sixteen vendored MIPP files. Candidate changes only
its private `.cpp`, `.h` and new local-cache header. The cache is worker owned,
resets for each template/level, uses signed quotients of already-clamped
centers, retains the complete `LocalMaximum`, and falls back to unchanged
computation when full or missing. Capacity remained sixteen. The switch
defaults false; no production matcher source was modified.

The literal cache RED compiled successfully and failed on its intended
missing-hit assertion before implementation. GREEN retained the same literal
tests and passed. All source, compiler, executable and original output evidence
is retained in the corresponding `cache_contract_red_*` and
`cache_contract_green_*` JSON files.

## Correctness

`core`, `flags` and `lifetime` ran independently once: 2880 direct ordered
vector comparisons from 3985 matcher calls. These include 2624 candidate
comparisons and 256 repeated-baseline comparisons. Length, class bytes, x/y,
template identity, float32 score bits and order all agreed. Coverage includes
all 128 computational flag combinations, repeated 1/4/2/4 thread passes,
grayscale/BGR and image-size changes, two classes, zero/full/partial masks,
empty candidates, zero maxima, legacy/default options, moved workspaces,
moved-from reuse and two concurrent callers with separate workspaces.
Root explicitly omitted a redundant combined `all` rerun.

Independent fresh audits checked 113 pinned files, CSV phase/thread/flag
counts, frozen Git bytes, source/input/build/executable identities and
literal RED/GREEN evidence without rerunning the matcher. Both worker and
root audits passed. Successful CSV rows record equality of the whole ordered
vector and its first-mismatch slot; they do not serialize every successful
match record. This fixed matrix is not a proof for every possible input.

## Controlled timing

There are 25 fixed images: eight LED, case1, and sixteen tiny development
frames. All original banks, features, thresholds and padding were retained:
LED900 at75, case1 361 at90, legacy tiny2212 at85. No heldout image was decoded,
viewed or matched. Each image ran exact V11, candidate off and candidate on
with cold1, warm2 and measured15 calls. Rotated/reversed call order was frozen
before execution. OpenCV used one thread; OpenMP used four and passive waiting.
The binary contains no cache counters or new timing instrumentation.

All 1350 outputs matched the exact V11 ordered oracle outside internal and
adapter wall timers. Source, protected, build-manifest, receipt and executable
hashes were unchanged. Compiler, OpenCV/libgomp/libstdc++/libgcc runtime bytes,
CPU identifier, logical processor count and OS version were recorded.

For each image, the summary takes the median of fifteen **paired on/off
ratios**. These are not ratios of independent medians. All regressions and
cold/warm/measured samples are retained.

| Metric: candidate on / off | Median over 25 images | Equal-weight geometric mean | Worst image ratio |
| --- | ---: | ---: | ---: |
| Search | 0.99775 | 0.84391 | 1.14644 |
| Internal total | 0.99907 | 0.91084 | 1.13020 |

Lower ratios are faster. Thus the median image showed essentially no gain,
despite the LED savings. Twelve images regressed in search and twelve in total.
Descriptive quantiles are not confidence intervals; this single run does not
remove thermal or scheduling variance. Candidate off / exact-V11 search had
an image-median ratio0.95357 and geometric mean0.95866, so candidate on/off is
the primary attribution rather than attributing every V11 difference to cache.
Exact-V11 adapter wall time includes an additional result copy; internal
search/total avoid that adapter difference.

| Image | Off search median ms | On search median ms | Median paired search ratio |
| --- | ---: | ---: | ---: |
| LED1 | 16.0288 | 9.6979 | 0.58685 |
| LED2 | 22.0589 | 13.0286 | 0.53349 |
| LED3 | 21.6216 | 10.8565 | 0.59234 |
| LED4 | 23.3083 | 11.8592 | 0.55348 |
| LED5 | 30.3662 | 15.4119 | 0.52540 |
| LED6 | 34.2779 | 17.6650 | 0.53287 |
| LED7 | 26.4506 | 15.1944 | 0.56745 |
| LED8 | 26.2135 | 13.9778 | 0.50846 |
| case1 | 2.9881 | 2.4044 | 0.88856 |
| tiny s5 i7 | 15.2757 | 15.4963 | 1.03746 |
| tiny s5 i70 | 15.8148 | 16.3508 | 1.09140 |
| tiny s5 i127 | 15.1610 | 16.4201 | 0.99369 |
| tiny s5 i215 | 15.1427 | 17.4881 | 1.07441 |
| tiny s5 i293 | 18.2566 | 20.2415 | 1.10872 |
| tiny s5 i353 | 15.2284 | 14.1175 | 0.96340 |
| tiny s5 i436 | 15.1135 | 15.1978 | 1.01765 |
| tiny s5 i493 | 13.8984 | 16.8251 | 1.14644 |
| tiny s2 i3 | 16.2919 | 14.7584 | 0.93516 |
| tiny s2 i92 | 13.6621 | 15.5694 | 1.10741 |
| tiny s2 i153 | 15.4679 | 16.7216 | 1.08350 |
| tiny s2 i214 | 13.4369 | 15.5726 | 1.08543 |
| tiny s2 i295 | 14.3061 | 16.1707 | 1.05736 |
| tiny s2 i374 | 16.2090 | 15.6811 | 0.99775 |
| tiny s2 i446 | 14.8104 | 15.1611 | 1.00639 |
| tiny s2 i494 | 15.4246 | 16.1014 | 1.00124 |

Next work should explain repeated-center frequency and lookup cost in a
separately labelled diagnostic build, without tuning capacity or enabling the
cache by object/image identity based on this result. Any adoption or adaptive
policy requires a new predeclared experiment. Accuracy work remains separate.

## Evidence and recheck

- Correctness acceptance: `correctness_acceptance_manifest_20261021_233133.json`
- Worker fresh audit: `fresh_correctness_audit_20261021_233133.json`
- Root fresh audit: `root_fresh_correctness_audit_20261021.json`
- Protocol: `BENCHMARK_PROTOCOL.json`
- Benchmark build: `benchmark_build_20261021_234030_440.json`
- Raw timing CSV: `benchmark_20261021_234119_051.csv`
- Run evidence: `benchmark_20261021_234119_051.json`
- Paired summary: `benchmark_summary_20261021_234119_051.json`
- Summary validator: `summary_validator_green_20261021_232935_467000.json`

Run evidence SHA256:
`358C0363E74C2761A8235F8E5669DBF3A9EA032E9316C733267AEF7CB2DB0E89`.
CSV SHA256:
`AB57905C39986F5E25DF092D083B239D31391C20F5F97CF3DA7C093C672726A3`.
Summary SHA256:
`44590038D04CF126C4CFE62569DA3C781297F0CE94A7A63740EDA1DD21681143`.
Benchmark executable SHA256:
`8006E14914F0DC09BE638D0BBBD997B4EB9B4F566A45384A681995C8335F50C9`.

`summarize.py` checks actual source/protected/runtime/protocol/build/receipt/
executable/gate/CSV pins before and after reading and validates case order,
phase/round pairs and bank/threshold/dimension invariants. Its fourteen-case
synthetic contract passed; it made zero matcher calls and decoded zero images.
Parent performs all staging, commit, tagging and publication decisions.
