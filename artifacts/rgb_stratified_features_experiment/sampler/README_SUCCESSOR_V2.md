# Current sampler: explicit signed-int64 successor

Use `v2/stratified_sampler.hpp` for the frozen V31 protocol. Its literal source,
runner and evidence are documented in `v2/README.md` and
`v2/SOURCE_AND_LITERAL_EVIDENCE.json`.

The files directly in this directory, including `README.md` and
`SOURCE_AND_LITERAL_EVIDENCE.json`, are immutable **v1 historical evidence**.
Their uint64 distance contract does not conform to the frozen protocol's
signed-int64 upper bound. The v1 green receipt proves only its original tests;
it cannot establish V31 protocol conformance. Its original README is preserved
because the historical source manifest pins its exact bytes.

`FAILURE_HISTORY.md` records the mismatch, its reproduced failure, and the v2
repair without replacing or relabeling any old receipt. No sampler evidence
here establishes image recognition accuracy, production readiness, or speed.
