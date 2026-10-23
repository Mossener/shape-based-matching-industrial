# Changelog

## 0.1.1 — 2026-10-23

- Add real LED and magnetic-part matching examples, losslessly converted input images, supplied SMD models and a C++ reproduction command. Show observed results and identify template-source images and evaluation limits.
- Add English and Chinese architecture/algorithm articles with module and data-flow diagrams, scoring and memory-layout explanations, integration limits, comparison with OpenCV methods and future optimization questions.
- Update the CMake package version to 0.1.1. The seven production matcher files remain identical to verified V11; this release makes no new accuracy or speedup claim and does not promote local research verifiers or codecs.
- Verify the 15 real-image examples against the published baseline: all 1,470 returned candidate rows agree. SIMD/OpenMP, scalar/OpenMP and serial integration checks pass on Windows/GCC/OpenCV 4.12, as does an installed external CMake consumer requesting exactly version 0.1.1.

## 0.1.0 — 2026-10-23

First source release with a distribution focused on the C++ matcher.

- Provide a CMake static-library target, installable package and a command-line example with a generated-image self-check.
- Provide an English homepage and Chinese documentation.
- Retain the previously verified V11 matching core, including reusable workspaces, response/search optimizations, timing and deterministic duplicate consolidation. This release introduces no new accuracy claim or algorithm change.
- Remove research scripts, snapshots, datasets and experimental results from the current distribution. Earlier `optimization-v*` tags retain their history.
- Preserve upstream attribution, the original BSD-2-Clause license and bundled MIPP notices.

This release contains no image datasets or experimental contour verifiers. Application-specific accuracy, speed and measurement precision require validation on the application's own data. The API is pre-1.0 and may change.
