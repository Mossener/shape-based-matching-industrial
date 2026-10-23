# Source provenance

This project derives from [meiqua/shape_based_matching](https://github.com/meiqua/shape_based_matching), a gradient-orientation template matcher following the LINEMOD approach. The imported source was a local snapshot; its exact upstream commit has not been verified.

The local Git history starts at `2a914712a0bea312f2af2e94d56ea69e7609a990`. That commit includes inherited sources and local LED experiments, so it must not be described as an unmodified upstream release. The imported README remains available in the history before the source-distribution cleanup.

The C++ core in releases 0.1.0 and 0.1.1 is the verified production version from `b25df46f6ddf9c24fb43f5836f1414dc38c8caed` (V11). Local additions include separable orientation spreading, fused response/rearrangement, reusable preprocessing and search workspaces, fused local accumulation/maximum selection, stage timings and deterministic candidate consolidation. Later research versions are not automatically part of the production core.

Earlier `optimization-v*` tags preserve experimental sources and validation records. They are research checkpoints, not semantic releases or general industrial performance guarantees. The 0.1.0 cleanup changes distribution and build tooling without changing the seven production `line2Dup*` files.

Release 0.1.1 adds the supplied real LED and magnetic-part examples, their C++ reproduction program, and bilingual architecture/algorithm articles. These images are development examples with documented source-image overlap, not a held-out accuracy benchmark. The production core remains unchanged; local contour-verifier and evidence-codec experiments are not part of the release.

The bundled MIPP snapshot includes inherited modifications for byte operations. Its exact upstream revision is unverified. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and the notices inside each source file.

This project is independent of the upstream authors, OpenCV and commercial vision vendors. References to those projects or products do not imply endorsement, certification, format compatibility or feature equivalence.
