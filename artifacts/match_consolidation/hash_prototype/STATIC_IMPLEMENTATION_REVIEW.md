# Static implementation review

Reviewed only; no compilation, test execution, image access, trace capture or
benchmark was performed for this review. No correctness or speed measurement
is inferred from inspection.

Reviewed SHA-256 values:

| File | SHA-256 |
|---|---|
|`hash_consolidation.hpp`|`8a338ef8f7ea92dc8420fc1c7607f096d54a59dd1bcd32be7a2c7802979e4589`|
|`trace_io.hpp`|`4e15a9027b39bc22e26d73ed1f248ee0276db090934faddbc007a78bf56303f7`|
|`record.hpp`|`9f07a9f977fa3624274c3b38bd086a4957ce76bb054e67f9cfa37ccedc34ab21`|

No blocking contract deviation was found against the V11 helper and the
independent test design.

The owning and index maps use all equality-key fields: class, x, y and score.
For finite nonzero binary32 values, numeric equality also preserves score
bits. Representatives use the minimum template ID and copy its complete
record. Final ordering matches V11. Index keys reference only the immutable
input; updating the mapped representative does not mutate the key, and the
map is destroyed before the separate result is sorted. Invalid scores are
rejected before any hash call. Any zero score sends the whole copied input
through the unchanged V11 path, preserving signed-zero representative bits.
Hasher/allocation exceptions leave the const input untouched.

The trace format uses explicit little-endian fields and a checked two's
complement signed conversion. It bounds record-count sums, minimum encoded
bytes, class lengths and streamsize conversions before allocation/read;
it does not reserve attacker-declared record counts. Reads reject truncation,
unknown format/version/marker, trailing bytes and nonfinite scores. Writer
validation checks both vectors before emitting the header on invalid scores.
Tests contain an independently built literal byte fixture, complete field/bit
comparisons, truncation at every byte and malformed boundary cases.

`TraceLimits.max_total_bytes` bounds encoded stream bytes. It is not a hard
bound on actual heap allocation or process RSS, which additionally depends on
vector capacity, strings and object overhead. Keep that distinction in the
capture/replay resource documentation. Runtime limits and actual correctness
evidence remain the implementation owner's responsibility.
