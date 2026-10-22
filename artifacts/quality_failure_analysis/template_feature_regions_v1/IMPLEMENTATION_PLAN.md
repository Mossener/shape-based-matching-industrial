# Full-bank feature-region implementation plan

The frozen DESIGN/PROTOCOL are the specification. This source-only phase is
authorized by root; no image byte read, native build/run or Git mutation is
authorized in this phase. I am using the writing-plans and test-driven-
development workflows. All new files remain in this directory.

1. Write literal independent numeric tests; retain a failing stub run before
   implementing exact RLE maps, Chebyshev distances, restored coordinates,
   region/label/cell summaries and complete usage joins.
2. Implement a narrow numeric input expander that verifies frozen source and
   numeric pins, expands 18 banks and all attempt/metadata/quality members,
   writes a fresh input freeze and complete shared pose plan. It must never
   open image bytes. Tests reject unsafe image paths before opening anything.
3. Implement one C++ TU using OpenCV FileStorage rather than the matcher,
   recreating mask/support geometry, lossless complete map packs and every
   serialized feature observation. It reads only the explicit mask allowlist
   when a later run is authorized. No addTemplate/match/gradient extraction.
4. Implement explicit opt-in build/run scripts with fresh output directories,
   complete source/compiler/dependency/runtime closure, per-image before/after
   SHA checks, exact call counts and preserved failures. Root grants the CPU
   slot separately before either native action.
5. Implement independent standard-library replay of all map/feature rows,
   attempts, bank descriptors, selected TP/FP/IGNORE, negative frames and raw
   representative usage, with complete member/hash verification and separate
   native pixel-generation limitations.
6. Run only standard-library tests and static checks here. Report exact next
   commands and remaining native verification to root. Do not commit or claim
   successful pixel observation before an actual authorized run.

Files: `independent_numeric.py`, `test_numeric.py`, `input_contract.py`,
`prepare_inputs.py`, `observer.cpp`, `sha256.hpp`, `build_observer.py`,
`run_observer.py`, `audit_numeric.py`, `static_check.py`, `README.md`, copied
strict `bank_reader.py` and provenance helper with explicit origins.
