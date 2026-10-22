# Fixture source preparation

The prepared common bank/image order is LED1..8, case1 and the fixed sixteen
tiny development frames from scenes5 and2. `fixtures()` returns these25 plus
two-class LED and the legal zero-maxima fixture. `inputs()` appends four LED
mask/threshold routes and one larger-image route, yielding32 inputs and28
fixture objects. `magnetFixtures()` is separate and returns exactly7 local
regressions; it is never part of the25-fixture timing set.

`fixture_bank_methods.inc` is included by the existing exact-wrapper TU while
its private core namespace macro is active. It adds no third core definition.
It exports one LED/zero/magnet YAML string and both wrappers receive the same
complete string, class order and template IDs. Existing case1 and tiny banks
are loaded from the same pinned file by both wrappers. No training image,
heldout frame, response image or derived private preview is read or written
by source preparation.

The LED and magnet SMD import classes are exact marker-delimited blocks from
historical frozen adapter sources. `prepare_fixture_sources.py` adds only
namespace wrappers. It checks their fixed source SHA values and creates
`generated_fixtures/led.hpp` and `magnet.hpp`. The generated manifest pins both
original sources, transformed headers,25 capture protocols, tiny index and
historical magnet provenance. Four pure tests pass; the initial missing-module
RED and a test-fixture path typo failure are retained in separate logs.

The manifest contains29 common and16 private input pins. Their SHA values
come from historical receipts. This preparation does not open image/SMD/bank
bytes or freshly prove those input hashes; private sizes use file stat only.
The later native runner must check the actual allowed bytes before and after
execution. The private group pins both the original magnet files and the
existing ASCII copies, whose expected SHA values agree. Those bytes must stay
local. Reading a template-bank file at runtime is distinct from decoding a
training image; no template-image path is constructed here.

The magnet adapter retains the exact scale expression `.60f+.05f*s`, scale
major insertion and2-degree angle steps, with3060 poses. It independently
checks the historical816x816 maximum requirement and all6120 refinement
intervals at896x832 padding. Optional preflight rows can be archived by the
correctness harness; no matcher call occurs during bank construction.

During this source review, the older multi-fixture helper was found to reuse
one mutable padded Mat across its tiny-frame loop. OpenCV Mat push-back is a
shallow copy, so destination reuse can overwrite earlier stored frames. The
new helper creates a fresh padded Mat for every frame and checks that all25
common inputs have distinct destination allocations. `tests/fixture_contract.cpp`
is prepared to reproduce the old alias using synthetic Mats and verify the
new ownership,32-input order, masks and larger geometry; it has not yet been
compiled or run. Do not retroactively label the old numeric benchmark as
sixteen independent input images until its actual source path is reviewed.
The frozen V21 capture adapter uses one selected image and local destination
per process, so this particular multi-fixture reuse path is absent there.

All files in this slice remain source preparation. No compiler, native
contract, image decode, bank construction, Detector call, speed result or
default algorithm change is asserted by these notes. Full source/dependency
review and separately coordinated native stages remain required.
