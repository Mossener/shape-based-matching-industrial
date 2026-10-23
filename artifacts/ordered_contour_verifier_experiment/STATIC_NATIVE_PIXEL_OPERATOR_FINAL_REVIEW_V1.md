# Static native pixel operator final review V1

No blocking source defect was found in the reviewed adapter and its stated
synthetic scope. This reviewer did not compile, run native code, decode images
or reopen any real input payload. Root execution remains the runtime evidence.

Reviewed exact source pins:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `native_pixel_operator.hpp` | 2,069 | `2098d4b3ac83b0825fff9be2a06615a27fa14865d66ff30e7e3574b571700956` |
| `native_pixel_operator.cpp` | 4,405 | `cefc9b9e8632d4b2b9738d658a5ce8cdd5e9cdbd3cffcb293c9ede039e8601e9` |
| `native_pixel_operator_test.cpp` | 17,821 | `3ff954d831293b9478a78535bfe036b1e93ae76954b3aeeadcf4943b6571cc1d` |
| `NATIVE_PIXEL_OPERATOR_DECISIONS_V1.json` | 4,049 | `b061ab3b11befedafd88c6a27bb80f1e2f7ba743ddb28a6dccff0e191fa86ae2` |

The implementation validates two-dimensional, nonempty, single-channel input
types and size agreement before calling V11. Cloning the logical image and
optional mask prevents parent ROI data from affecting OpenCV filtering borders.
It calls the exact frozen `ColorGradientPyramid(...,20,32,40)` and `quantize`,
then owns full-size unspread, squared-magnitude and phase matrices. V11's
7x7 blur, Sobel, separate float products/addition, phase and histogram code were
read directly; no spread or sparse/strongest-feature selector is called here.

Byte decoding handles all eight single bits and rejects every multibit value
before the later mask/strong gate can hide it. Template selection uses the full
nonzero official mask and finite squared magnitude strictly greater than 1600;
scene selection uses weak20 unspread labels. No erosion or additional border
removal is present. Returned matrices and grids own their storage; caller image
and mask are not mutated.

The frozen test bytes in the actual RED/GREEN archives equal the current test
hash above. Root receipts report RED 22 tests/970 checks/338 failures/0 errors,
and GREEN 22 tests/8,452 checks/0 failures/0 errors. Tests compare full literal
constant/ramp fields and label grids, including 400/1600 strict-threshold
boundaries, vertical inner-corner histogram behavior, unsigned opposite
directions, independently strided views, poisoned ROI parents, tiny dimensions,
mask singleton and caller immutability. The many per-pixel checks are not
8,452 independent image cases. They do not exhaust arbitrary images, phase
angles or every OpenCV optimization path and do not form an independent
general original-pixel gradient oracle.

The runner pins the exact frozen V11 manifest and source member set, builds one
translation unit from its source snapshots, records GCC's complete ordered
dependency pins and rechecks sources, dependencies, executable and selected
non-system static PE imports. Static import resolution is not observation of
every loaded module, dynamic plugin or OS/API-set resource. Compiler/tool and
objdump metadata queries occur outside the child wall/working-set watchdog and
use the inherited unbounded capture/timeout behavior. Ambient environment and
the whole Python/OS runtime are not fully attested. The compiler's inherited
1 GiB Windows Job limit measures committed memory including children; the
foreground guards observe process working set and wall/output at 50 ms. These
distinct limits must not be described as an aggregate RSS proof for the whole
coordinator. The source's existing scope/limitation statements preserve this.

The decision JSON remains the frozen RED-preparation artifact; its initial
stub/unexecuted status is historical. Later GREEN evidence belongs in a
separate acceptance/report, without rewriting that frozen decision file.
No real pixel provenance, all-attempt C0 bank replay, chain/candidate scoring,
industrial generalization, speed benefit or production promotion is established
by this component review.
