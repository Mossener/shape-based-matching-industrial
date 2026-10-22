# Immutable V11 trace capture and replay protocol

Status: capture design only, before any capture/matcher/benchmark run. Existing
stage timing CSVs preserve counts and timings, not the complete ordered input
records; their vectors cannot be reconstructed from counts. Public raw archives
contain post-consolidation results and must not be relabeled as pre-consolidation
input traces. No old sandbox instrumentation is executed.

## Frozen scope

First finish prototype RED/GREEN correctness. Capture then uses a newly created
private copy of exact V11 sources at `b25df46`, including the consolidation
header and all MIPP dependencies. Record original/generated SHA, compiler flags,
OpenCV/runtime versions and every image/template/config SHA. Never edit the
production core or frozen public evaluation source. The parent coordinates
exclusive CPU before compilation and matching.

Capture cases may include the existing eight LED frames, case1 and the fixed
tiny development set at actual matcher threshold 85. Heldout scenes and reserved
objects are excluded. An additional coarse-50 replay that recreates large
historical consolidation pressure is a separately labeled stress workload,
with its own config/bank/source provenance. Coarse-50 data must not be mixed
with actual85 quality results or used to claim the historical vector was
reproduced exactly.

## One narrow capture seam

Only the single `consolidateMatches` call in the new private core snapshot is
redirected to a capture wrapper, with one capture-header include added. Preserve
the committed helper byte for byte under its original name. The wrapper first
copies complete ordered input records, invokes the original
helper on the original vector, then copies complete ordered output records.
Serialization occurs outside timed consolidation and instrumented full API
timings are never used as speed evidence. The source generator checks exactly
one include and one call replacement anchor, rejects an already instrumented
source and aborts on any mismatch.

The trace writer emits a binary format with an explicit version and little
endian integers. Every input/output record stores x/y and template ID as exact
32-bit signed integers, similarity as exact uint32 score bits, uint64 class byte
length and complete class bytes. Preserve embedded NUL, non-ASCII bytes and
original input order; do not round scores to CSV decimal or normalize class
strings. Use uint64 counts and bounded length/count validation when reading.
SHA256 covers exact trace bytes; a manifest contains core/source/build/config/
image/bank identities, count, byte length and trace hash.

Run an uninstrumented matching implementation at the same frozen core/config
and compare complete final field/score-bit output with captured output. OMP
merge order can permute original input records; canonical nonzero output must
still agree. Preserve actual capture input order, rather than regenerating one
from a canonical output. If repeated run source/image/bank checks or final
equality fails, keep the failed evidence and do not benchmark that capture.

## Reader/writer integrity tests before images

Use synthetic records to fail and then pass the reader/writer implementation:

- round-trip all complete fields, negative/extreme integers, adjacent finite
  floats, signed zeros, long classes, embedded NUL and original record order;
- empty input/output arrays and one record;
- wrong magic/version, truncated header/count/record/string and trailing bytes;
- excessive declared record count/class length and integer overflow rejection;
- SHA mismatch, mismatched metadata count and input/output identity;
- nonfinite score records rejected before consolidation;
- full exact V11 replay output equals captured output, including the zero-score
  fallback's bitwise representative behavior.

No fixture accesses a dataset image or matcher. Input files remain immutable;
writers refuse existing outputs. A separate read-only manifest audit rehashes
all sources/input files and trace bytes before and after loading. A successful
round-trip is format evidence, not an image or speed result.

## Separate replay-only performance phase

Only verified immutable traces are timed, using the uninstrumented V11 helper
and the prototype functions. File reads, parsing, SHA, oracle computation and
trace generation remain outside timed regions. Report common input-copy cost
separately and use identical ownership/accounting for all five methods. Freeze
warmup/repeat/order/statistics/compiler/allocator/CPU policy before measurement.
Report small/no-duplicate cases and regressions, reserve/no-reserve behavior,
large real trace identity, N/U, bucket counts and memory-measurement limits.
Forced collisions are correctness stress, not production performance samples.

No small-N threshold is selected here. No instrumented API or isolated
consolidation speedup becomes a whole-matcher latency claim. Production
integration requires a later independent review and fresh uninstrumented image
equivalence/performance run under the authorized workflow.
