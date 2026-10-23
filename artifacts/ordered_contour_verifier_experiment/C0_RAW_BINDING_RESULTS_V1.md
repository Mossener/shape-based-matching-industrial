# C0 raw/NMS/GT projection binding V1

The complete saved C0 positive control was reproduced exactly. The root ran
`run_c0_raw_binding_v1.py c0_raw_binding_green_v1` with Python `-E -B`; the child
exited 0 and its guard accepted the run. This is numeric replay, not a new
matcher run or evidence of a speed/accuracy improvement.

| Evidence | Observed result |
| --- | --- |
| Fixed projection tests, actual RED | 28 methods, 35 assertion failures, 0 errors; exit 1 |
| Same test bytes, actual GREEN | 28 methods, 0 failures/errors; exit 0 |
| Complete object/frame scope | Objects 1, 2, 5, 8, 12, 17; 400 frames; 2,400 combinations |
| Complete raw scope | 457,279 rows; all 390 zero-raw combinations retained |
| NMS output | 42,327 selected candidates, full tuples and order exact |
| All-GT result | TP 215, FP 42,112, FN 185, GT 400 |
| Visibility >= 0.5 | TP 209, FP 42,112, FN 165, GT 374, ignored 6 |
| Original GT identities | All 215 all-GT and 209 eligible identities exact and unique |
| Numeric files read and end-rehashed | Exactly 4,809 unique registered files |
| Unique encoded payload bytes / decoded raw bytes | 25,422,544 / 40,922,149 |
| Guard wall / observed peak working set | 57.485 seconds / 222,965,760 bytes |

The reader admits only 2,400 C0 fallback raw gzip CSVs, their 2,400 manifests,
six own template metadata JSONs, and `ground_truth.csv`, `per_frame_metrics.csv`
and `selected_detections.csv` from the actual V31 development stage. The plan
and inventory are separately fixed bootstrap metadata. All dataset paths,
including `index.json`, images, bank payloads and arbitrary paths are refused.
It imports only the existing pure `numeric.py` and parsing helpers from
`evidence.py`; it does not import or call the old quality audit, dataset reader,
`bindings()`, `gt_schedule()` or `stage_gate()`.

Each raw row checks every canonical candidate field: class, template, match
coordinates, score float32 bits, own training-pose bits, official box and order.
The own metadata origin conversion uses padding `[64,64,64,244]` on 848 by 848.
NMS at IoU 0.3 and assignment at IoU 0.5 are recomputed; full selected tuples,
labels/GT IDs and every per-frame metric must equal the frozen projection.
Missing zero combinations are failures, never inferred negatives. The original
all-GT 215 identities are stored explicitly for later retention checks.

The recorded source and bootstrap hashes are checked before/after. Stable
single-handle hashing reuses the tested V2 Windows `birthtime_ns` stamp. The
source archive is a before-execution copy; code executes from the workspace.
Single payloads are bounded at 64 MiB, manifests at 1 MiB, combined admitted
payloads at 512 MiB, combined decoded raw bytes at 256 MiB and output at 16 MiB.
The root's 50 ms watchdog observes one child's wall time, working set and output
with limits 900 seconds, 512 MiB and 16 MiB. These are observation limits, not
OS allocation isolation or a complete Python/DLL/runtime attestation. The wall
time includes validation and hashing and is not a matching performance result.

A separate metadata/output-only review parsed all 2,400 `per_combination.json`
records and all identity records after execution. It confirmed the complete
plan schedule, totals above, unique identities, exact agreement between the
per-combination and identity files, 4,809 distinct payload declarations, and
current size/SHA agreement for all six result source pins. It did not reopen
raw, image, bank or GT payloads and is not a second numeric algorithm.

The GT CSV is an inherited frozen projection; official annotation payloads
were not independently reconstructed. Raw matcher outputs were not regenerated
from pixels. Pixel operators, all 20,736 training attempts/36,398 template
layers, new ordered-contour scores and real quality/performance evaluation
remain separate gates. No production promotion is implied.

Retained result: `c0_raw_binding_green_v1_payload/result.json`, 1,467,279 bytes,
SHA-256 `019fdde451612aa0b31e8d3e330cd11194979aa66e5284088e134e51e39387eb`.
The acceptance record pins the per-combination, identity and guard evidence.
