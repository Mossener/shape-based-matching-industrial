# Source-only silhouette training result

The fixed six-object training stage completed all 20,736 planned poses. Every pose returned `insufficient_features`; no new template bank was created. The comparison is marked **incomplete** and the native executable exits 1. Padding planning, development-image decoding, matching, quality evaluation and timing stages were not run.

| Object | Attempted poses | Successful templates | insufficient_features | OpenCV exceptions |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3,456 | 0 | 3,456 | 0 |
| 2 | 3,456 | 0 | 3,456 | 0 |
| 5 | 3,456 | 0 | 3,456 | 0 |
| 8 | 3,456 | 0 | 3,456 | 0 |
| 12 | 3,456 | 0 | 3,456 | 0 |
| 17 | 3,456 | 0 | 3,456 | 0 |
| Total | 20,736 | 0 | 20,736 | 0 |

The sole algorithmic factor was the training source: `warped_mask.clone()` replaced the grayscale RGB warp, while the same official warped object mask remained the feature-selection mask. The V11 core, erosion/blur/gradient/NMS/scattered-selection code, requested 32/16 features, weak/strong 20/40, T 4/8, 72 official views, four scales, twelve angles, canvas and border stayed fixed. Each attempt's source ROI, canvas and warped mask box was checked against the corresponding original RGB attempt. Failed poses were retained rather than filtered or assigned artificial feature counts.

This establishes that this particular source-only change cannot produce usable banks under the frozen recipe. It does not identify a unique internal cause, prove that contour templates are inherently unsuitable, or measure detection accuracy. The supplied selection mask restricts the candidates after erosion; whether allowing both sides of a binary contour improves extraction is a separately proposed factor. That proposal is not implemented or included in these results. Accuracy, recall and speed for the absent mask bank are **unavailable**, not zero-valued evaluation results.

`run_source_only_training_v1/` preserves per-object attempts, empty metadata, configurations, error files, full native stdout/stderr, native and wrapper failures, execution provenance, before/after verification and `BANK_FREEZE.json`. The summary records all attempts complete, six zero-success objects, comparison infeasible and matcher calls 0. Peak process RSS was 56,287,232 bytes; it is a resource diagnostic, not a performance comparison. No development or heldout image was opened, and reserved objects 25/29 were not trained.

The required wrapper checked all 864 training RGB/mask members against the frozen download-manifest SHA/size both before and after the stage. It also rechecked private inputs, actual compiler dependencies, explicit import libraries, compiler/helper tools, executable and recursively resolved non-system static PE imports. Post-verification passed despite the expected incomplete native exit. OS/API-set DLLs are named but not hashed; dynamic plugins and every OS resource are outside this local provenance claim.

The actual native build uses the experiment's 23 exact private V11 Git files and three fixed helper copies. Its five compiler commands all exit 0. Core GCC dependencies contain 402 ordered occurrences resolving to 399 files; adapter dependencies contain 513 occurrences resolving to 506 files. Real header aliases are retained in order and pinned. Both actual `-MD` files equal their precompile `-M` bytes. The first build's incorrect duplicate-path assumption is preserved in `build_adapter_v1/`, and literal plus real-GCC RED/GREEN evidence accompanies its correction. Inherited MIPP/core compiler warnings remain preserved.

| Frozen evidence | SHA-256 |
| --- | --- |
| PROTOCOL.json | 88a7476c6b947917978034545cd670a90b8fcc074adf4e4690429e2ebbf3c8c5 |
| INPUT_CLOSURE.json | 1ca5d92184f970f159bcd6e0879c1bbd757a21408ec7a5844cab35e02669a33e |
| build_adapter_v2/build_manifest.json | 78de8f0bff775ffdcb6853698058903fd0d2bc5d3f49bea31b376c455a040fd1 |
| Native executable | 9c8089004a6dd5a755f44c0859e9f53dad69074b7ed529ef86bbc476c847a72d |
| native/training_summary.json | 37ea7aebfc29daef3f15167224b8960bc3be54be6cf2536022aac368aa214575 |
| BANK_FREEZE.json | 5576e1c8113d7256a0bc7f7fd7f50ade6feb2004e06297360991f5889fc9dde1 |

Independent numeric verification is performed by the root agent in `artifacts/independent_reviews/silhouette_training_v1/`, without importing experiment helpers or opening images. The initial implementation, synthetic prerequisites and unchanged protocol are documented in `DESIGN.md` and `SYNTHETIC_RESULTS.md`; the latter's earlier “no real training” statement describes the prerequisite stage before this run.
