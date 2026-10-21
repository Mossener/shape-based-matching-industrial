# Independent review of numeric preservation

The original audit script SHA-256 was
`636a73ae8140fe04c941281b20d8bd0533f6f62aef1dba99cc8b78f8d57a8511`.
Static review and a fresh run confirmed the nine published packages and all
6,592 tar members, including copied-file byte counts/SHA, gzip restoration
to the original-file SHA, member names/lengths/SHA and duplicate/set checks.
The original two positive fixtures and 14 rejection fixtures passed.
`preservation_independent_review.json` preserves that review.

There was a real general-validator omission: two validly named manifest-only
members with `raw_archives=1` passed the original script. It counted total
members and required CSV -> manifest, but did not count actual CSVs or check
manifest -> CSV. The independent synthetic reproduction was accepted and is
preserved in the original review JSON. This did not invalidate the nine
published packages: a separate read-only check confirmed that those packages
already had exactly 3,296 CSVs and 3,296 bidirectionally paired manifests.

The parent agent subsequently added an independently failing regression
fixture, a CSV-count equality check and a reverse pairing check. I did not
edit `audit_preservation.py`. Its fixed SHA-256 is
`a16c648de1644712f3386a2f1cf36d30f895e29a4a69b05d4767ef06802edb81`.
I freshly reran its two positive fixtures, all 15 rejection fixtures and the
same nine packages. All passed; the new evidence is
`preservation_fixed_independent_review.json`. The initial accepted-malformed
fixture remains a recorded failure of the original revision.

The path defenses are suitable for this read-only archive audit. Copy paths
reject absolute/parent traversal, resolve to the expected package, and cannot
repeat a resolved target. Expected raw tar names use a flat, restrictive
regular expression. Actual entries must be regular files with names in that
set, cannot repeat, and must exhaust the expected set. The code reads members
using `extractfile`; it never extracts arbitrary paths to disk. The fixed
reverse/count checks close the observed orphan-manifest omission.

Gzip restoration handles both storage cases: an added `.gz` suffix is decoded
before comparison with `source_sha256`; a source that was already compressed
(for example a `.yml.gz` bank) is compared as its original compressed bytes.
This proves byte preservation, not CSV semantics or detector correctness.
Original `source` paths are names only in this audit and are not opened.

I also independently checked the separate source snapshot, which is outside
the nine numeric run manifests: its archive SHA/size, all 29 regular member
names/lengths/SHA and exact member set agree with the source manifest. All 23
members marked as committed V11 core/MIPP bytes are byte-for-byte equal to
`git show b25df46f6ddf9c24fb43f5836f1414dc38c8caed:<path>`: seven root core files
and sixteen MIPP files. These source-snapshot checks are recorded in
`preservation_independent_review.json`; no reconstruction was executed.

No original dataset image, derived preview, heldout RGB, matcher or coverage
executable was opened or invoked. Manifest/SHA consistency is preservation
evidence; it does not by itself authenticate a historical execution or replace
the separate raw numeric/metric audits.
