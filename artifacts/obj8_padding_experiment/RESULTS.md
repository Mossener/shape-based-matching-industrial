# Object-8 fixed full-bank padding result

Increasing the padding from848x672 to848x800 made all6,912 template layers
geometrically feasible, but did not improve recognition on the frozen400-frame
development split. Every auto-padding raw candidate, including float32 score
bits and order, equals its original baseline counterpart on all400 frames.
Both paths retain the same93 raw candidates and69 NMS detections. The larger
padding increased paired external-call time. This experiment does not justify
changing the default padding.

The protocol SHA-256 remains
`ab9207f2dd492622aed8f563997b00ca6d137d5c93fa0f2c99b67f7ec756573d`.
The existing3,456-template bank, all scales/angles, matcher/post threshold85,
NMS0.3, GT IoU0.5 and visibility0.5 were unchanged. The production core and
public evaluator were not edited. No coverage gate was enabled. No heldout
image or reserved object25/29 was matched.

## Quality

| Metric | Baseline848x672 | Auto848x800 |
|---|---:|---:|
| Frames |400|400|
| AllGT TP / FP / FN / GT |1 /68 /49 /50|1 /68 /49 /50|
| Eligible TP / FP / FN / GT |1 /68 /49 /50|1 /68 /49 /50|
| Precision |1.4493%|1.4493%|
| Recall |2.0000%|2.0000%|
| F1 |1.6807%|1.6807%|
| Mean TP IoU |0.6585365854|0.6585365854|
| Raw candidates |93|93|
| Negative frames |350|350|
| Negative frames with FP |51|51|
| FP on negative frames |63|63|
| Baseline GT retained |1 /1|1 /1|
| Exact original TP detection retained |1 /1|1 /1|
| New / lost baseline GT |0 /0|0 /0|

AllGT and eligible totals are equal because these50 object-8 instances satisfy
the visibility threshold. Both arms have the following identical per-scene
results. All scenes contain50 evaluated frames.

| Scene | TP | FP | FN | GT | Raw | Negative frames with FP |
|---|---:|---:|---:|---:|---:|---:|
|1|0|4|0|0|4|2|
|4|1|5|49|50|8|0|
|6|0|4|0|0|7|3|
|7|0|6|0|0|7|5|
|8|0|3|0|0|4|3|
|10|0|13|0|0|16|10|
|12|0|22|0|0|30|20|
|13|0|11|0|0|17|8|

The fixed eight-frame pilot completed32 calls and verified all fresh baseline
candidates against their original same-padding cache. Both pilot arms had
TP0/FP2/FN1. This was a correctness/resource gate, not a parameter-selection
or accuracy-acceptance gate. Full development then completed800 calls.

## Timing

The separate fixed timing stage completed2,048 calls on64 predetermined
frames, eight per scene, with one warmup and seven measured rounds. Each
variant has448 measured samples. Variant order rotates each round. Decoding
and bank loading are excluded from external-call times. That external call
includes border allocation/copy, matching, coordinate conversion and NMS.

| Padding / path | Match median ms | Match p95 ms | External median ms | External p95 ms |
|---|---:|---:|---:|---:|
| Baseline / fallback |18.6666|52.4325|18.7240|52.5134|
| Baseline / fused |18.1487|51.9880|18.2310|52.0595|
| Auto / fallback |20.7766|59.5655|20.8422|59.6694|
| Auto / fused |20.2487|57.7792|20.3156|57.8674|

The median of the paired auto/baseline external-call ratios is1.12094065 for
fallback and1.11498612 for fused: approximately12.09% and11.50% slower. These
are medians of paired ratios, not ratios of the distribution medians. Their
p95 ratios are1.51401170 and1.51109112. Timing-stage image decoding totaled
667.9291ms and bank loading took78.5073ms, reported separately.

Native code compares every timed call with its own arm/path reference,
including all fields and float32 score bits. The independent numeric audit
checks every timing row's raw/selected counts against that reference and
reconstructs all percentiles and paired ratios. Per-call candidate contents
are not archived again during timing, so the CSV alone cannot independently
reconstruct each timed call's full output.

## Geometry, resources and independent validation

The historical declared-size report remains630 infeasible layers. The new
actual-feature-inclusive scan finds634:412 L0 refined layers and222 L1 coarse
layers. Four extra L1 cases (IDs566/951/999/1005) need337 rows because a feature
has y336. The auto plan has zero infeasible layers. Pixel area grows19.05%.
Geometric feasibility alone does not prove recognition or physical SIMD
tail-read safety.

Peak process RSS was140,791,808 bytes in the pilot,86,794,240 in development
and141,443,072 in timing. Full-development new raw gzip output totals91,098
bytes. All run resource checks passed. Resource/time limits are soft checks
between native calls/frames; a single matcher call cannot be interrupted.

The independent Python audit rehashed2,625 distinct numeric/source files and
reconstructed raw-to-box conversion, canonical NMS, one-to-one GT assignment,
eligible/ignore handling, all per-frame/per-scene totals, retention, all6,912
geometry rows and all timing samples. It imports no evaluator/adapter code,
reads no dataset image and calls no matcher. Its first complete run passed:
`independent_audit_attempt1.json`.

The geometry audit independently recomputes constraints from the exported CSV.
The native `loadedLayers` scan generates that CSV from the loaded bank; the
bank and native source are bound by provenance SHA values. The Python audit
does not parse the YAML bank a second time to independently recover maximum
feature coordinates.

The auditor's literal self-test covers IoU, NMS ordering, allGT, low-visibility
ignore handling and nearest-rank percentiles, with two rejected numeric
corruptions. Eleven additional persisted fixtures reject corrupted allGT,
eligible FP, retention, selected boxes, raw source-origin boxes, geometry fit,
timing percentiles, paired ratios, own-reference counts, rotating order and
output SHA. Fixture inputs/results remain in `audit_mutation_fixtures/`.

## Reproducibility and retained evidence

The final executable SHA-256 is
`2f2226ab2267f574f6c7a48ec684144878fe92896890ec19d9f92b4d39fed050`;
the final build-manifest SHA-256 is
`173c98cd4a1e849309400359ba6181adf3df2333febff90c1f9c9dcfe0b2b339`.
All three runs verify sources/inputs before and after execution, and check
that the executable and build manifest remain unchanged. Development also
requires the exact completed pilot/build; timing requires the exact completed
full-development/build. All stages ended with exit0.

| Evidence | Location |
|---|---|
| Fixed design and schedule |`PROTOCOL.json`, `frame_schedule.json`, `preflight_plan.json`|
| Static geometry/overflow validation |`static_validation.json`, `STATIC_REVIEW.md`|
| Planner compiled semantic RED |`build/planner_red_final/`|
| Planner GREEN + seven RED mutations |`build/planner_green_and_mutations_recheck/validation.json`|
| Final adapter build diagnostics |`build/adapter_compiler_stdout_parent_review.txt`, `build/adapter_compiler_stderr_parent_review.txt`|
| Final synthetic native integration |`run_native_selftest_parent_review/`|
| Pilot full raw/provenance/metrics |`run_obj8_pilot/`|
| Full400 full raw/provenance/metrics |`run_obj8_full400/`|
| Timing samples/provenance/metrics |`run_obj8_timing64/`|
| Independent numeric audit |`audit_results.py`, `independent_audit_attempt1.json`|
| Audit literal and corruption checks |`audit_selftest.json`, `test_audit_mutations.py`, `audit_mutation_fixtures/validation.json`|

Initial environment compile failure, the earlier GCC diagnostic and superseded
synthetic integration attempts are preserved. The final adapter build retains
warnings inherited from the frozen MIPP/core sources; the whole build is not
claimed warning-free. No industrial accuracy or generalization claim follows
from this development-only experiment.
