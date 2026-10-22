# V2 successor: shared frozen V30 closure role

The failed V1 real-development numeric audit is retained by root, including
its consumed reservation, guard logs and partial output. This successor does
not edit V1 sources/registry, the completed native quality stage or its frozen
quality-input declaration. It does not rebuild/retrain/re-match any input.

`quality/prepare_quality_inputs.py` builds `frozen_numeric_files` from explicit
acceptance/protocol/inherited pins and then appends `training_numeric`.
`inherited_closure_pin` in the first group and `inherited_control_closure` in
the accepted training dependency group refer to the same
`artifacts/rgb_dilated_mask_experiment/INPUT_CLOSURE.json`. There is no final
deduplication in that preparer. Native quality verification retains both roles
and accepts both pins. V1's independent `pin_map` rejected the identical pair.
Root identified exactly this duplicate; this source preparation does not open
the actual quality input, bank, archive, dataset index or image.

`contract.frozen_numeric_pin_map(inputs)` now permits this specific declared
inherited closure exactly once or twice. It requires the canonical path,
the exact V30 directory/file suffix, the already frozen V30 closure SHA256,
and complete equality with `inputs.inherited_input_closure`, including bytes.
A different duplicated path/role, conflicting size/hash, noncanonical shared
path, missing closure or third occurrence is rejected. Both frozen-list call
sites use the dedicated function. Every bank/raw/stage/receipt list continues
to use the unchanged strict `pin_map`; no duplicate exception applies there.
Every declared numeric pin is still read and checked by the existing Reader.

`numeric.py`, `evidence.py` and `quality_audit.py` are byte-identical to V1.
All score bits, NMS, GT, retention, primary quality gates, resource ceilings,
input hashes and failure policies remain inherited. `SOURCE_ORIGINS_V1.json`
is an exact copy of V1's origin record; the new origin record pins the complete
predecessor source set and documents the narrow successor.

The wrapper's new registry is `execution_reservations_v2`, with reservation
and runner schemas ending `_v2`. It records `successor_of` and reason. It
does not read, remove or reset V1's consumed registry. Root must explicitly
accept this successor's source evidence, issue a fresh reservation and grant
the exclusive CPU slot. Synthetic test success does not accept real quality
data or establish the primary accuracy hypothesis.

The source-only suite retains the original 23 test methods and 14 weakened
source mutants, plus eight shared-role regressions and four targeted mutants.
The genuine pre-fix RED and its source snapshot are in `source_role_red_v1`;
the narrow regression GREEN is in `source_role_green_v1`. `run_selftest.py`
creates a fresh, complete source snapshot and GREEN/RED receipt each time.
