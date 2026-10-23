# Changelog

## 0.1.0 — 2026-10-23

First source release with a distribution focused on the C++ matcher.

- Provide a CMake static-library target, installable package and a command-line example with a generated-image self-check.
- Provide an English homepage and Chinese documentation.
- Retain the previously verified V11 matching core, including reusable workspaces, response/search optimizations, timing and deterministic duplicate consolidation. This release introduces no new accuracy claim or algorithm change.
- Remove research scripts, snapshots, datasets and experimental results from the current distribution. Earlier `optimization-v*` tags retain their history.
- Preserve upstream attribution, the original BSD-2-Clause license and bundled MIPP notices.

This release contains no image datasets or experimental contour verifiers. Application-specific accuracy, speed and measurement precision require validation on the application's own data. The API is pre-1.0 and may change.
