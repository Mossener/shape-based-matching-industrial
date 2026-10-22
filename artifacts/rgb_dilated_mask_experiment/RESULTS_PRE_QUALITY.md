# Source, synthetic and training results before quality

This checkpoint does not report accuracy or speed. No development image has
been decoded and no matcher has been called by this experiment.

The core candidate differs from pinned V11 in exactly one line:
`erode(mask,local_mask,...)` becomes same-argument `dilate(...)` inside actual
per-layer extraction. The treatment still receives grayscale RGB and the
official warped mask. Production source remains unchanged.

Four sequential native toy tests completed: original erosion sanity passed;
original erosion with a dilation expectation produced the exact preregistered
native RED; the changed dilation implementation passed; the official-mask spy
passed. All four builds completed actual two-translation-unit dependency scans,
compilation and linking. The raw RED stderr, stdout and failure receipt remain
in `run_literal_control_red_v1`. `toy_verification_20261022_b.json` verifies
the fixed oracle, real source pins and complete recorded C++ dependency closure.
The four historical toy builders did not explicitly pin transitive Python
`source_contract.py`; the fresh training v2 builder corrects that source-pin
omission without rewriting any toy evidence.

One authorized training build and one full training run completed. Every
original pose geometry was compared with frozen RGB control. Every serialized
successful layer was checked against retained actual-count/geometry diagnostics.

| Object | Attempts | Successful | Insufficient features | Exceptions | Actual feature range, both layers | Minimum canvas-edge distance |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 3456 | 3432 | 24 | 0 | 5–41 | 11 |
| 2 | 3456 | 3456 | 0 | 0 | 6–40 | 10 |
| 5 | 3456 | 3456 | 0 | 0 | 14–40 | 9 |
| 8 | 3456 | 3456 | 0 | 0 | 16–37 | 11 |
| 12 | 3456 | 3456 | 0 | 0 | 14–43 | 10 |
| 17 | 3456 | 3456 | 0 | 0 | 9–39 | 10 |

Totals: 20,736 attempts, 20,712 successful templates, 24 retained failures,
41,424 serialized treatment layers, zero extraction exceptions. Actual feature
counts were retained even when they differed from requested 32/16 targets.
The completed fixed loop implies 864 training decodes: 432 RGB and 432 mask
`imread` calls. These are derived counts, not a decode-hook measurement. The
native training summary reports peak working set 64,069,632 bytes.

The separately granted complete-union plan scanned all 12 control+treatment
banks and 77,822 actual layers. It passed exactly 848×832, alignment 16 and
padding `[64,64,64,228]`, estimated dynamic memory 361,234,432 bytes. It did not
enlarge padding, drop any template or decode a development image.

`BANK_FREEZE.json` and `COMMON_PADDING_FREEZE.json` preserve native outputs,
runner numeric checks and execution evidence. Those runner checks are not the
independent audit. A separate independent audit and `AUDIT_ACCEPTANCE.json`
must bind the unchanged original freezes before the quality input may be built.
The acceptance implementation has two passing standard-library synthetic tests,
with its genuine initial RED preserved. It has not created a real acceptance
marker at this checkpoint.

The final source suite at this checkpoint is
`tests_all_20261022_f`: 16/16 pass. Prior failures and incomplete exploratory
checks remain recorded in `FAILURE_HISTORY.md`. Quality source is prepared and
frozen for review, including actual bank/metadata/plan byte closure and
stage-specific index/RGB pre/post verification. Quality native execution,
independent quality audit and timing remain pending.
