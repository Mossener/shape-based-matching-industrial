# Auditor development failures

The first exploratory audit attempts used the output path
`run_20261022_development_audit`. Their failure files were overwritten while
the auditor was being developed, and no separate traceback logs were captured.
They are not retained raw failure evidence. This limitation is recorded here
instead of reconstructing traceback files.

The observed failures and corrections were:

- The selected-frame coverage check initially required a row for zero-detection
  frames. The corrected rule requires complete per-frame/equality schedules
  and accepts an empty selected list for a scheduled frame.
- The CSV parser initially rejected header-only zero-candidate raw archives.
  It now accepts a valid header with no data rows; schedule coverage is checked
  separately so a missing frame cannot masquerade as an empty result.
- Pooled output initially used the internal `eligible` key instead of the
  native `visibility_ge_0_5` key and omitted pooled negative/raw counts.
- An exact Python-dictionary comparison exposed ordinary floating-point
  accumulation-order differences near 1e-13. Summary comparison uses a numeric
  tolerance, while candidate score bits and serialized identities remain exact.

The synthetic runner captures all stdout/stderr and exact source bytes for
subsequent attempts in fresh directories. The v1 and v2 successful real numeric
receipts remain separate, with their own source hashes; neither starts native
matching nor reads dataset image bytes.
