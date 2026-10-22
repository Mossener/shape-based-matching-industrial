# Independent Phase1 numeric audit

This directory owns a standard-library-only auditor of the fixed
`score_path_probe_v1` Phase1 numeric evidence. It imports neither the probe nor
the matcher/evaluator implementations and performs no native execution.

The fixed input plan SHA256 is
`353615a753a0be27a2665997488301259fe99989858068895870d16fe32de91c`.
The authorized Phase1 completion freeze SHA256 is
`f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed`.
Its preserved V22 independent development-audit parent has SHA256
`38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68`.

`numeric.py` independently parses finite binary32 scores, exact pose and
metadata boxes; reconstructs the V11 class/x/y/float-equality consolidation
key; chooses the complete minimum-template-ID representative; applies the
V11 final order and then the archive adapter order; and recomputes collision
multiplicities and occurrence-based GT IoU support. Signed zero uses float
equality in generic fixtures; ambiguous same-ID mixed-sign-zero ties fail.
Actual Phase1 archives require scores in `[85,100]`, so zero is excluded.

`evidence.py` validates the fixed plan and the complete Phase1 → GREEN
selftest → deliberate RED selftest → build/reservation receipt chain. It
hashes build members as inert bytes, checks the actual single-TU command
sequence and macro difference, and checks exact native/runner output member
sets. Successful stages may not carry failure files. The earlier failed
include-order build remains in its separate original directory.

`audit_main.py` independently reconstructs the 215 RGB TP identities from
preserved selected-detection and GT CSV files, checks all 426 pre/post
archive pairs against their own V22 saved raw references, and compares every
per-frame, GT-support, representative and summary value. Native numeric-byte
accounting excludes `.gitignore` and `stage_summary.json`; physical native
and runner-measured output sizes are reported separately.

The auditor never opens a dataset image or private SMD. It compares the
before/after image hash declarations to the pinned allowlist. It does **not**
independently recompute LM feature scores: it validates the pinned native
scalar-score exactness receipt and coverage for every pre candidate. This
diagnostic establishes candidate-support provenance, not a recovered TP,
accuracy improvement or throughput improvement.

The retained real audit passed in
`run_phase1_audit_20261022_v1/result.json`, SHA256
`67ff1b3967e762984bf9a35e358fa2a1a9d039124de88b7fc53c98eb18eacc06`.
It independently checked all **1,312,006 pre candidates**, **227,816 post
candidates**, **78,372 representative/discarded-template mapping rows** and
**430 GT-arm support rows**. There are 41,581 cross-template collision groups
and 1,005,818 repeated occurrences within the same template. Candidate-support
losses at consolidation are **0**. Every post record exactly matches its own
preserved V22 raw reference, including complete fields and binary32 bits.

The evidence check cache contains 1,461 unique pinned files spanning preserved
numeric inputs, receipts and build members. The 560 unique declared build
closure members are included in that total, rather than an additional 560.
Native output files are separately checked against the exact 1,709-member
set before and after reconstruction. Build member bytes are SHA256-checked
without execution. The native fine-score gate covers all 1,312,006 pre rows;
the independent numeric auditor validates its receipt and coverage and does
not recompute native LM feature scores. Image-byte reads, image decodes and
matcher calls by the independent auditor are all **0**.

Native schema-counted numeric output is 23,046,003 bytes. Physical native
output is 23,046,658 bytes; runner-measured output is 23,060,201 bytes and
excludes the later stage-freeze file. These are distinct accounting scopes.

Synthetic verification was genuine RED then GREEN: the independent numeric
skeleton failed all 9 numeric fixtures; the evidence skeleton then failed
all 8 evidence fixtures; the completed implementation passed all 17.
Receipts are `synthetic_red.txt`, `evidence_red.txt`, `synthetic_green.txt`.
Run the complete current 17-test suite from the repository root:

```powershell
& 'F:\mysys2\ucrt64\bin\python.exe' -B -m unittest discover -v -s artifacts/independent_reviews/score_path_probe_v1 -p 'test_*.py'
```

The root task owns Git and publication. Raw evidence and audit run outputs
are retained locally; no image is included in this directory's intended
publication scope.
