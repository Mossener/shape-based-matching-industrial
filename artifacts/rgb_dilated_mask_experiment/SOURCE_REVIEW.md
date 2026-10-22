# Independent source review — 2026-10-22

The minimum source slice is consistent with the declared per-layer mask
experiment. No substantive algorithm-seam or literal-fixture issue was found
in this read-only review. Native toy results and actual training/quality remain
separate evidence; this source review does not establish an accuracy benefit.

## Source delta and real layer semantics

The reviewer independently compared all 23 control and treatment source members
with the pinned V27 private V11 source. The control bytes are exact copies.
Only line2Dup.cpp differs in the treatment, at the local-mask operation inside
ColorGradientPyramid::extractTemplate:

    erode(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);
    dilate(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);

That is one byte of added length, 63,388 to 63,389 bytes. The other 22 source
members are identical. The treatment core SHA256 is:

    0cc2f52aa92786c80e3dc90d09e6979e01874435dacbd73b562dc9b90d27dab6

The default empty kernel is the existing 3x3 rectangular morphology operation.
The original BORDER_REPLICATE, anchor and iteration count are preserved. Each
actual layer first uses the existing mask state. The unchanged pyrDown
floor-halves src dimensions, resizes a nonempty mask with INTER_NEAREST, and
updates gradients. extractTemplate computes a separate local_mask and never
assigns it back to mask. Thus the treatment is per-layer dilation of each
layer's official mask, rather than repeatedly propagating a dilated mask down
the pyramid. Empty-mask behavior remains the existing unrestricted branch.

The policy forwards the same grayscale source and nonempty official warped
mask by reference. The spy checks source/mask object addresses, the returned
template ID, one detector call, and rejection of mismatched size, empty mask,
and color source before the detector is reached. It verifies that interface,
not actual detector training. The training adapter restores the original
official-mask argument and snapshots that mask before the call so its mutation
check is meaningful.

## Literal fixture semantics, beyond static string checks

The literal test constructs the real ColorGradientPyramid, calls the real
extractTemplate, and uses the real feature NMS and scattered selector. It
injects deterministic magnitude/orientation arrays to isolate mask behavior:
five same-column positions with y in {20,26,32,38,44}, squared magnitude 2500
above the unchanged strong threshold 40 squared, angle bit 1, and theta 0.

The fine mask is the inclusive rectangle x/y 16..47. The coarse fixture starts
with the 128-pixel source and mask x/y 32..95, calls the actual pyrDown, and
asserts size 64x64, requested features 10 -> 5, level 1, and the exact nearest
mask x/y 16..47. At that actual layer:

- Erosion admits x 17..46; dilation admits x 15..48.
- x=15 is one layer pixel outside the official boundary and distinguishes the
  new operator from the original.
- x=14 is two outside and both masked versions reject it.
- x=20 is safely interior and both retain it.
- x=14 with an empty mask exercises the original unrestricted branch.

Successful extraction must return exactly the five literal coordinates as a
set, exactly five features, label/theta 0, and the correct pyramid level. Both
masked fine and coarse branches check that the current official mask is not
mutated. The one-pixel full-mask border operation is a separate literal OpenCV
operator check; it does not prove extractor behavior at the image edge, which
the unchanged scan excludes by two pixels.

The reviewer also executed temporary pure-Python arithmetic of this fixture's
mask morphology, the original 5x5 magnitude_valid NMS, and the unchanged
scattered selector. All 12 operator/fixture combinations agreed with the
intended acceptance and five-coordinate set. This script was not saved and
its process output was not captured as a persistent file; the tool output is
only conversational evidence. It is not presented as a reproducible native
test or an executed-source receipt.

The first self-written arithmetic checker incorrectly compared feature list
order even though the C++ fixture compares a set. It therefore raised an
AssertionError on a valid reordered five-point result. After correcting that
checker to compare sets and count, the 12 arithmetic cases passed. The first
checker stderr was not persistently captured. This was a reviewer-checker
mistake, not a product, literal-fixture, compilation, or native failure.

Injecting gradient arrays deliberately bypasses the actual gradient generator,
and the literal fixture does not invoke Detector::addTemplate or image-based
training. The spy and literal tests together isolate forwarding and extraction
semantics; they cannot establish successful training or industrial accuracy.

## Predeclared native oracle and build closure

The initial review found that run_native_test accepts exit zero only, so its
preserved failure alone could not classify an arbitrary failure as a valid RED.
The root added the separate TOY_TEST_EXPECTATIONS.json successor oracle before
the expected RED run, without editing already pinned build protocol bytes.
Its fixed combinations are:

| Case | Actual core | Literal expectation | Native exit |
| --- | --- | --- | ---: |
| Original sanity | control | erode / EXPECT_DILATION=0 | 0 |
| Expected RED | control | dilate / EXPECT_DILATION=1 | 1 |
| GREEN | treatment | dilate / EXPECT_DILATION=1 | 0 |
| Pointer spy | treatment | official-mask policy | 0 |

RED must have exactly the literal acceptance failure stderr, not a load,
compiler, crash, missing-resource, or unrelated assertion failure. Success
cases require their fixed PASS suffix and empty stderr. The RED execution
keeps its real runner failure receipt; a separate read-only verifier can
recognize the narrow expected outcome without relabeling that failure.

The expectation file explicitly states that it is a successor oracle and was
not part of the already started first build's source pins. Source review of
this declaration does not itself provide independent timestamp attestation.

The build driver selects control or treatment actual core translation units
and corresponding include roots. Literal builds set EXPECT_DILATION explicitly.
For each of the two translation units it obtains a precompile dependency list,
compiles with -MD/-MF, requires equality of dependency pins, then links the
actual two objects. Its five recorded compiler invocations are two dependency
scans, two compilations, and one link; they are not five compilations.

The first original-sanity build manifest, when reviewed, records the control
core, EXPECT_DILATION=0 on both translation units, two actual units, and all five
commands with exit zero. The associated run records exit zero. Full four-case
outcome verification is still delegated to the separate receipt verifier and
root; it is not claimed from those initial files here.

Compiler tools/link libraries, actual dependency files and objects, executable,
and recursively resolved non-system static PE imports are pinned and rechecked.
OS/API-set imports are named but not hashed; dynamic plugins and all OS
resources are explicitly outside that local closure's attestation. The runner
checks the declared pins before/after execution. These are local provenance
records, not cryptographic proof of process execution.

The completed four toy build manifests were later inspected for their Python
supporting-source list. All four contain 36 project-source pins and omit
source_contract.py, although prepare_input_closure.py imports it. Thus these
historical build manifests do not provide a complete executed-Python project
closure. This does not alter the actual two C++ translation units' -MD
dependencies. The historical manifests must remain intact; a future training
build can pin the added Python dependency before execution. Its current bytes
were observed only at review time (2,409 bytes, SHA256
b65b5972a914cd1f0b657390fd3ab1f140e5b127bb6cfd7fb04e25d9309db6c5), which
must not be represented as proof of those bytes during the four prior builds.
The interpreter and complete standard-library execution closure are also not
attested by these project-source lists.

## Reviewed source pins

| Source | SHA256 |
| --- | --- |
| freeze_private_sources.py | 10d839330886f4d80e5db66b3b57a3dc67383b1fdce13886827d2e8c2708b567 |
| PRIVATE_SOURCE_FREEZE.json | 6187aac5c1ca1b49b0398770ef37740014c0c734bc7102771662a1f2761143d7 |
| literal_mask_test.cpp | 916d5129105fefabbe5033776fc244ce09acfd6e934005eb8260f32992f05afe |
| rgb_dilated_mask_source_test.cpp | f480119bc49450ec1b966b856e6cc47c57127e6c6f15a1bff61eeb6212cf755c |
| rgb_dilated_mask_policy.hpp | c9c6e5fc9bd4d7c604549d795676501d27374e70779cbce6759184532dd1daed |
| build_training.py | 1240a95c10d15877db474d312e419a3986be416a07e1f007232034e4c6023cc7 |
| run_native_test.py | c59f0d51d04417a944fd77818ef6d065f9a88a587a00e02ac2faa171ac28b69c |
| TOY_TEST_EXPECTATIONS.json | 45ae7790bbe7b31dafaf4f53c5eb542c8fbda73e825de5ba412061f5e4d7facb |

The reviewer did not compile or run native code, open image/bank/raw archives,
read held-out/private SMD data, commit, or spawn another agent. Only this source
review document was added at the root's request.
