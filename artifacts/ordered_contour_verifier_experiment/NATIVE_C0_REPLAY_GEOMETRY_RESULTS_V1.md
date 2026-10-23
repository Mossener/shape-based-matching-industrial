# Native C0 replay geometry synthetic results V1

The coordinator compiled and executed the same frozen seven-test suite against the two zero stubs and their implementation. Actual RED recorded **35 checks, 24 assertion failures, zero errors**, exit 1. Actual GREEN recorded **4,660 checks, zero failures/errors**, exit 0. Successful matrix shape/type checks enable the additional complete pixel comparisons in GREEN; the test source bytes did not change.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| RED `native_c0_replay_geometry.hpp` | 808 | `da0f5a5adfa9667fc786de5e83877740e25c7cb041b416ce9e9ca1dea91cde26` |
| GREEN `native_c0_replay_geometry.hpp` | 2,724 | `ac227f1b89d83dd95931e42f00ce1caa06a05f112edaa974d48631f969c32897` |
| Frozen `native_c0_replay_geometry_test.cpp` | 5,843 | `838a150452e14d357437b43652875c844dafcfc7e51002752c917a34fa35a9d7` |
| Coordinator `run_native_c0_replay_geometry_checks_v1.py` | 10,720 | `776abea672db6208d62ed1a833805008c84589a5589a94b5f1a4976ca4a1ce60` |
| Frozen `NATIVE_C0_REPLAY_GEOMETRY_DECISIONS_V1.json` | 1,438 | `d406e64744be0623b6642754e515432d1b1345c0f0bec38d9e5c4804da910b28` |

`rebuild_warp` accepts matching nonempty two-dimensional grayscale `CV_8UC1` image/full official mask, fixed scales 0.75/1/1.5/2 and angles 0..330 step30. The full nonzero mask defines the source crop. The helper reproduces the public C0 training geometry: ceil(hypot(crop width,height) × scale), border16 on both sides, align16 canvas, float crop center passed to `getRotationMatrix2D`, double translation adjustment, linear image and nearest mask interpolation with constant-zero border. It rejects empty masks, malformed inputs, unsupported poses and overflowing extent.

The asymmetric literal fixture checks crop `[2,1,9,7]`, canvases48 at scales0.75/1 and64 at1.5/2, the angle0 affine `[1,0,19.5,0,1,20.5]`, and angle90 affine approximately `[0,1,20.5,-1,0,28.5]`. Literal bilinear boundary pixels and nearest-mask pixels exercise half-pixel positioning and constant-zero border. Complete ROI-versus-owned-clone row comparisons check parent context independence. These are finite synthetic checks using the inherited OpenCV implementation, not an independent interpolation oracle for every image or pose.

`same_saved_layer` compares width, height, tl_x, tl_y, pyramid_level, feature count and every ordered x/y/label triple. Tests mutate each matching field and feature order. The unsaved `Feature.theta` is never read by the comparator; fixtures initialize it before copying their owned features.

| Recorded phase | Wall | Peak process working set | Other observation |
| --- | ---: | ---: | --- |
| RED build helper | 6.344 s | 23,552,000 B | Compiler Job peak committed 546,734,080 B |
| RED test | 0.063 s | 12,247,040 B | Expected exit1 |
| GREEN build helper | 6.984 s | 23,744,512 B | Compiler Job peak committed 545,996,800 B |
| GREEN test | 0.062 s | 12,619,776 B | Exit0 |

Build limits were180s, helper working-set threshold1GiB and output threshold128MiB. The separate compiler Job committed-memory limit was1GiB and included GCC children. Test limits were60s, process working-set threshold512MiB and output threshold64MiB. Job committed memory differs from process working set; polling limits are observed-excess watchdogs, not allocation barriers or aggregate coordinator RSS bounds. The inherited resource/provenance limitations in `NATIVE_RESOURCE_SCOPE_SUPPLEMENT_V1.md` apply, including unguarded metadata preflight and OS/dynamic-import limits. These short synthetic timings are not replay speed benchmarks.

Retained RED receipt: `native_c0_replay_geometry_red_v1/receipt.json`,113,197B, SHA-256 `e5ce7232a4beb0d8fdd97fe4c48775cddfba52dea84e1b5e7810d8e5e1c894a1`. Retained GREEN receipt: `native_c0_replay_geometry_green_v1/receipt.json`,113,240B, SHA-256 `113959d4a404bd9ac76dc86ece8b8342b3c373b72a7e123d57ac47ab96593ea6`. Each pins the archived sources, exact frozen V11 source, compiler dependencies and runtime; the coordinator executes its compiled archive. RED top-level `passed=true` means the expected assertion-failing gate passed; its test guard records exit1.

No image file was decoded, real payload read, matcher called, bank reconstructed, attempt replayed, scene prepared, score produced, or real quality/speed measured. The helper author only edited sources/report and statically inspected metadata; compilation and execution belong to the coordinator's retained receipts. Production and V31 remain unchanged. The decisions file preserves its original RED-only preparation state; the later receipts establish the actual results. The separate full-attempt replay source and schedule preparer remain pending review/execution and are excluded from the V35 selection.
