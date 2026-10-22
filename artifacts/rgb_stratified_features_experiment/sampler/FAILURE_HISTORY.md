# Sampler failure history

## V1: unsigned bound conflicts with frozen protocol

The first implementation used checked **uint64** squared Euclidean distances.
It accepted a full signed-int32 axial displacement of 4294967295 and distance
18446744065119617025. This exceeded the frozen protocol's required signed-int64
maximum of 9223372036854775807. The v1 tests explicitly expected that acceptance,
so their 16 cases / 153 assertions passing did not establish protocol compliance.

All original v1 sources, README, evidence manifest and three run directories
remain byte-for-byte intact. The missing-header RED and reversed-ordinal RED
remain useful historical checks but do not repair the numeric contract.

## Reproduced signed-contract RED before v2 implementation

`v2/sampler_literal_tests.cpp` was written with signed-bound expectations before
the v2 header existed. `v2/run_signed_limit_v1_red_20261022_a/` compiled those
tests against an unchanged snapshot of the original v1 header. The build
succeeded; execution failed after 0 complete cases / 3 assertions at:

```
full int32 axial distance above INT64_MAX accepted
```

`v1_source_seam.json` preserves the complete v1 distance function text, original
line numbers, function hash and header hash. This is a runtime RED exercising
the original function, with a text seam locating it; no native AST claim is made.
The runner captures all source/compiler/executable/output pins and confirms the
origin files were unchanged during execution.

## V2 repair and literal verification

`v2/stratified_sampler.hpp` checks each squared component and the sum against
INT64_MAX before multiplication/addition, then returns signed int64. The running
minimum vector and selection trace also use signed int64. Coordinate differences
remain signed int64; temporary nonnegative checked arithmetic uses uint64 solely
to avoid evaluating overflowing signed expressions. The permitted distance range
is [0, INT64_MAX], not the v1 uint64 range.

The v2 GREEN run passed 19 cases / 169 assertions. New boundary checks include
3037000499 squared (9223372030926249001), the immediately larger axial
displacement, a diagonal sum exactly INT64_MAX+1, full int32 diagonal overflow,
duplicate negative coordinates and overflow propagated through sampling. The
existing literal pooled/balanced sequences remain unchanged. API-only checks
also preserve an opaque nonfinite theta payload, finite negative magnitude and
UINT64_MAX ordinal; canonical uint32 serialization limits belong to the caller.

The separate v2 reversed-ordinal mutation compiled and failed after 10 cases /
89 assertions at `literal selected ordinal differs`, demonstrating the tie test
remains discriminating. Only the isolated snapshot was mutated.

## Limits

These are tiny standard-library C++14 literal executions: zero image bytes,
zero decodes, zero matcher calls, zero training, and no performance claims.
Compiler executable/version pins do not constitute a complete transitive
compiler/runtime dependency closure. Independent candidate geometry, sampler
oracle comparisons, real-pool training and accuracy/timing remain separate
acceptance steps owned by the parent experiment.
