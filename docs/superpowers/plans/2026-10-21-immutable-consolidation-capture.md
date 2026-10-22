# Immutable consolidation capture plan

**Goal:** Capture complete, ordered pre-consolidation V11 inputs without editing
production sources; verify exact output against a separate uninstrumented build
before any replay timing. Parent authorization and scope are recorded in
`artifacts/match_consolidation/hash_prototype/TRACE_CAPTURE_PLAN.md`.

**Files:** New capture support lives only in
`artifacts/match_consolidation/hash_prototype/`. Existing run directories remain
immutable. Parent owns staging/commits and coordinates exclusive heavy CPU.

- [x] Pass isolated hash/trace RED/GREEN and targeted mutation checks.
- [x] Write and freeze literal manifest/SHA/metadata/output-identity and source
  anchor tests; run API stubs for semantic RED before implementing them.
- [x] Implement an independent Python little-endian parser preserving raw score
  bits, original input ordering and raw class bytes. Validate schema/count/size/
  source/config pins before and after read, compare complete captured output to
  uninstrumented reference output, reject path escapes and mixed scopes.
- [x] Implement exact one-call source redirection plus one include addition.
  Leave the committed V11 helper completely unchanged. Generation must start
  from `git show` at the fixed V11 revision and copy every tracked MIPP file,
  refusing existing destinations; preserve original/generated source hashes.
- [x] Pass 21 unchanged generic manifest/source tests and obtain parent static
  review. Freeze failures rather than overwrite them. Parent noted that generic
  declared pins are not full real-build closure; next item is required.
- [x] Add negative RED fixtures and enforce required 23 core/MIPP source files,
  source-manifest Git identities/seam, adapter/hook/trace sources, both compiled
  build manifests, compiler/runtime/executables and exact command binding.
  Nine synthetic tests passed; this is saved-manifest closure, not proof that
  the compiler consumed every declared dependency.
- [x] Require pinned OpenCV compile headers/import library and per-TU compiler
  dependency-file binding. Seven synthetic dependency tests and nine integrated
  source/build tests passed after semantic RED. This checks saved artifacts;
  no native compiler dependency file has yet been collected.
- [x] Test capture hook complete-record copying, one-shot arming, unarmed
  pass-through and output-serialization safety before real matching. Semantic
  RED then 44 checks across two translation units passed. The real-closure and
  hook GREEN runs may overlap another native compile; no timing is eligible.
- [ ] Build two isolated adapters from the same frozen core and dependencies:
  capture adds only the approved call seam; reference uses original sources.
  Freeze build/runtime/compiler/config/source/input identities. Compile TUs
  separately with `-MD -MF` (not `-MMD` or a shared multi-TU depfile), then link
  with a pinned explicit import library. Scope is actual local compiler
  dependencies plus project/toolchain/runtime provenance, not all OS resources.
- [ ] With parent CPU grant, capture LED8/case1 and fixed tiny actual85
  development; run an uninstrumented same-core/config reference. Tiny coarse50
  is a separate explicitly named stress workload, never relabeled actual85 or
  a historical exact trace. Never open heldout images or objects 25/29.
- [ ] Independently audit SHA, counts and exact ordered fields/score bits; only
  passing immutable traces are eligible for uninstrumented replay. Instrumented
  API times and capture overhead cannot support speed claims.
- [ ] Freeze replay benchmark protocol before measurement, including common
  input-copy accounting, warmup/repeats/order and all small/no-duplicate cases.
  Include owning/index reserve/no-reserve paths, retain regressions and avoid a
  guessed small-N switch. Report memory-measurement limits explicitly.

Encoded byte bounds do not constitute a hard process-memory cap. Synthetic
format/manifest tests do not establish detection accuracy, image count or speed.
