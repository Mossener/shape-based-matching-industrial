# Binary source with an empty selection mask

This independent successor changes only the `addTemplate` selection-mask
argument relative to the frozen source-only experiment. Its source remains an
ownership-separated clone of the official binary warped mask. The official
mask still determines the source crop, affine, silhouette box and pose metadata.
The V11 extractor, feature counts, thresholds, border, view/angle/scale grid and
matching code remain fixed. The reviewed design and protocol are unchanged.

Current status: native RED/GREEN and all three native builds are complete.
The wrong-mask RED failed at the exact empty-mask assertion; GREEN passed the
ownership/selection spy and four invalid-mask checks. Both unchanged toys
extracted templates: rectangle 59/16 features and diagonal polygon 32/18.
All 20,736 real fixed training attempts are now complete and successful, and
root independently checked serialized banks, all poses and 41,472 layers.
The full twelve-bank union plans one 848×832 input (padding 64/64/64/228).
No development-image matching has run and no accuracy or speed improvement is
claimed. Root coordinates the CPU slot
and owns Git integration/publication. Evidence is summarized in
`NATIVE_PRETRAIN_RESULTS.md` and `NATIVE_PRETRAIN_SUMMARY.json`.

The private source freeze contains seven actual V11 Git core files and sixteen
MIPP files. Three unchanged frozen public helpers are copied after checking the
source-only freeze SHA. `INPUT_CLOSURE.json` expands the fixed predecessor
closure, checks all inherited numeric sources, owns private copies of 229 RGB
input/reference files and 26 source-only training evidence files, and retains
the expected download-manifest hashes for 864 training images/masks and 400
development images. Preparation and static verification never open those image
members. All source-only evidence remains unchanged.

The inheritance test failed before its implementation and now passes fourteen
literal rejecting cases. Dependency/PE-import/file-mutation literal oracles and
23-file Git-byte isolation checks also pass. These static checks are separate
from the actual native ownership/toy evidence.

A separate numeric/static regression caught an inherited adapter assertion
that incorrectly treated requested counts 32/16 as actual upper bounds. The
frozen RGB attempt tables already contain successful counts up to 44/23. Only
this successor adapter removes those incorrect upper bounds; it keeps actual
nonempty counts unchanged and records them in full. The RED and GREEN evidence
is retained under `actual_count_contract_*`; the frozen predecessor is intact.

`empty_mask_source_test.cpp` uses a literal detector spy to assert the exact
source pointer, class, empty selection mask and returned ID. It also checks
source/official-mask ownership in both mutation directions, rejects invalid
original masks, and records real `addTemplate` results for the unchanged
192×192 rectangle and diagonal polygon toys. The intentionally wrong RED
fixture passes the binary source as the selection mask; the RED executable
must fail specifically at the empty-mask assertion, before toy extraction.
The GREEN executable records either success or `insufficient_features` for
each toy. Toy geometry and thresholds never change to force a result.

The real adapter records every 3,456 attempted poses for each of all six
objects and checks pose geometry against both frozen RGB and source-only
attempt records. Successful layers additionally record actual crop offsets,
actual `cv::pyrDown` canvas size, local/absolute feature extents, and nearest
canvas-edge distance. A diagnostic never filters a pose or adjusts the border.
True coordinates outside the canvas are written first, then stop the stage as
incomplete. Every official silhouette is converted through its own actual L0
template origin; a feature box cannot replace the official box.

`build_adapter.py` checks the private source and input closures, declared
compiler tools and libraries, recursive non-system static PE imports, actual
GCC `-M`/`-MD` dependencies for both translation units, executable bytes and
before/after source bytes. Ordered dependency aliases are retained. Native
builds require the coordinated CPU slot. This is local provenance, not an
attestation of every OS resource or dynamic plugin.

Run these sequentially **only after the root CPU grant**:

```powershell
py -3.10 artifacts/silhouette_empty_mask_experiment/build_adapter.py --target source-test-red --output artifacts/silhouette_empty_mask_experiment/build_synthetic_red_v1 --cpu-slot-granted
py -3.10 artifacts/silhouette_empty_mask_experiment/run_synthetic.py --build-manifest artifacts/silhouette_empty_mask_experiment/build_synthetic_red_v1/build_manifest.json --output artifacts/silhouette_empty_mask_experiment/run_synthetic_red_v1 --cpu-slot-granted
py -3.10 artifacts/silhouette_empty_mask_experiment/build_adapter.py --target source-test-green --output artifacts/silhouette_empty_mask_experiment/build_synthetic_green_v1 --cpu-slot-granted
py -3.10 artifacts/silhouette_empty_mask_experiment/run_synthetic.py --build-manifest artifacts/silhouette_empty_mask_experiment/build_synthetic_green_v1/build_manifest.json --output artifacts/silhouette_empty_mask_experiment/run_synthetic_green_v1 --cpu-slot-granted
py -3.10 artifacts/silhouette_empty_mask_experiment/build_adapter.py --target adapter --output artifacts/silhouette_empty_mask_experiment/build_adapter_v1 --cpu-slot-granted
py -3.10 artifacts/silhouette_empty_mask_experiment/run_stage.py --mode train --build-manifest artifacts/silhouette_empty_mask_experiment/build_adapter_v1/build_manifest.json --output artifacts/silhouette_empty_mask_experiment/run_training_v1 --cpu-slot-granted
```

All output directories must be fresh. The training wrapper freezes all output
files even when the native comparison reports failure, verifies provenance
again after execution and preserves failure evidence. Any zero-success object,
extraction exception, missing pose or geometry/resource failure forbids the
quality stages. A bank unavailable for extraction is never a valid detector
that simply predicts no objects.

Only if all six banks are feasible, use the frozen twelve-bank union to plan
one common padding. Later freshly evaluated RGB and binary-empty-mask quality
arms share that padding. Relative to RGB, both source and selection-mask policy
differ, so a quality change cannot be attributed to the mask parameter alone.
Full quality/timing adapters are a later stage and are not implemented here
yet. Heldout images and reserved objects 25/29 remain sealed.
