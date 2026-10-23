# Static C0 geometry RED preparation review V1

No blocking source or literal-fixture defect was found. This review read only
the small declared source/helper/decision files, did not compile or execute any
code, and did not open raw, bank, image, annotation or dataset-index payloads.

| Reviewed source | Bytes | SHA-256 |
| --- | ---: | --- |
| `native_c0_replay_geometry.hpp` | 808 | `da0f5a5adfa9667fc786de5e83877740e25c7cb041b416ce9e9ca1dea91cde26` |
| `native_c0_replay_geometry_test.cpp` | 5,843 | `838a150452e14d357437b43652875c844dafcfc7e51002752c917a34fa35a9d7` |
| `run_native_c0_replay_geometry_checks_v1.py` | 10,720 | `776abea672db6208d62ed1a833805008c84589a5589a94b5f1a4976ca4a1ce60` |
| `NATIVE_C0_REPLAY_GEOMETRY_DECISIONS_V1.json` | 1,438 | `d406e64744be0623b6642754e515432d1b1345c0f0bec38d9e5c4804da910b28` |

The referenced C0 `train()` code was read in
`artifacts/rgb_empty_mask_experiment/frozen_helpers/tless_eval.cpp`
(SHA-256 `c9e4016d1cd7ad6ce37d49bc04f49f1f3d496573a0047a9d1b8da951eb7204ef`)
and compared with the same V31 frozen-helper geometry. C0's actual defaults are
border16, angle step30 and scales .75/1/1.5/2. Its image/mask decode is grayscale;
the full nonzero mask determines the crop. Geometry uses
`ceil(hypot(w,h)*scale)+32`, align16, float crop center, double affine translation,
linear image/nearest mask interpolation and constant-zero borders. The new
interface's declared recipe matches these operations. The empty-mask treatment
code was used only to confirm identical geometry; its changed feature mask is
not substituted for original C0 training.

Literal values were hand-checked. A 9 by 7 crop at (2,1) has diagonal about
11.4017, giving aligned sides 48/48/64/64 for the four scales. For angle0/scale1,
the double affine is `[1,0,19.5;0,1,20.5]`. Destination (19,21) maps to crop
(-.5,.5): constant-zero bilinear support gives (12+22)/4=8.5, rounded to 9 by
the 8-bit linear warp. Destination (21,22) maps to (1.5,1.5), giving 28.5 and
rounded 29. The nearest-mask sample at (20,21) is 1. At angle90 the ideal affine
is `[0,1,20.5;-1,0,28.5]`; the test allows trig roundoff.

All seven RED test bodies safely handle the header's empty `Warp` return.
Matrix element accesses are guarded by full expected shapes; default Rect/Mat
metadata accesses and saved-layer boolean checks do not dereference empty
storage. Missing validations cause ordinary assertion failures. No obvious
compile syntax problem was found. Actual compiler success, normal RED exit1,
positive assertion failures and zero errors still require root execution.
The saved-layer mutation checks cover width, height, both origins, level,
feature count and ordered feature x/y/label; theta is excluded because V11's
serialized matching representation does not save it.

The literal geometry domain is intentionally small. It does not exhaust all
48 poses or large dimensions, and the 90-degree tolerance is not evidence of
six exact double bit patterns. Future all-attempt provenance must retain the
actual affine bits, logical warped image/mask bytes, crop/canvas and every
successful/failed training attempt, then compare all serialized layer fields.
The coordinator retains inherited GCC dependency and static import provenance,
compiler Job committed-memory and foreground observed working-set limits;
tool/metadata preflight and dynamic/OS/runtime limitations remain separate.
No real bank replay, pixel freeze, quality or performance gain is proven here.
