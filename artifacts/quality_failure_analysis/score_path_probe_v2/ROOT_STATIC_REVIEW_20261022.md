# Root review before Phase2 native work

Reviewed the final single translation unit, builder, runner, source contract,
geometry helpers, synthetic tests and the fixed numeric input-plan receipt.
The source-check receipt is `source_check_v1/result.json`, SHA256
`bfb97fe7263e4d547526c184bd0089c852e4658351f953d7d8d20003b4c4f1b3`.
The fixed plan SHA256 is
`830a77d629ad766df998aa59fbd1b6cf6bc207c900263afd04b890560eb9215a`.
The reviewed `phase2.cpp` SHA256 is
`1390dc963675a1bc1d7e7e5da59c296f255bc85109d0cb8d2f9dc0f677745bbc`.

The earlier ambiguous job-number mapping is resolved by `jobs.csv.gz` and
unique planned/consumed job-key equality. The output connects all 430 jobs to
their object, frame, arm, serialized template, pose, feature counts and GT
anchor. The 430 target rows and 13,534 physical feature probes are explicit
summary gates, alongside all fixed cell/kernel/link/image budgets.

The scalar traversal preserves the native flattened coarse span, zero tail,
window-base feature skips, checked actual LM allocation bounds, binary32
normalization, strict coarse and inclusive fine thresholds, row-major first
maximum and all-zero sentinel. Parent enumeration uses the source clamp order
and C++ truncation. All reachable parents are retained; equal window bases
share kernel arrays while their parent identities remain distinct.

Native/scalar equality is conditional on the rebuilt native LM values. This
does not independently reconstruct gradients or response values from image
pixels. Same-pose paths are a subset of Phase1 full-class candidates. Complete
saved post records supply the NMS/assignment gate, and all 215 saved RGB TP
positions must be reproduced before binary absences are interpreted.

The build includes the frozen V11 core once and extracts the exact pinned
Phase1 preprocessing blocks into a generated namespace header. It avoids the
previous nested-main-macro approach. Dependency discovery and actual compiler
dependency records must agree. RED and GREEN project inputs differ only by
the location of an otherwise byte-identical generated header and the declared
RED compiler define. This is source provenance, not complete OS-loader
attestation.

The CPU flag is checked before creating build/run output. RED builds cannot
dispatch the dataset mode; each of the three injected faults must fail for
its exact intended reason. GREEN requires those frozen RED receipts. Dataset
mode requires its own bound GREEN selftest and a later, separate root CPU
grant. The runner reserves before native execution, bounds resources, retains
partial failures, rechecks source/input pins and inventories complete output.
It never automatically repeats a failed native stage.

Root independently reran all 13 pure synthetic geometry/source-contract tests:
passed. No compiler, native kernel, image read, match or production edit was
performed by this review. This accepts only the build plus three RED and one
GREEN synthetic stage. No accuracy or speed improvement follows, and no
dataset execution is granted by this document.
