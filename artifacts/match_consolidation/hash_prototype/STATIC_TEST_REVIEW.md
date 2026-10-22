# Independent static review of hash correctness tests

This review reads the plan, record contract, current test source and runner.
It neither implements nor compiles/runs the prototype. No correctness result
or performance claim follows from this review.

No blocking test-design issue was found. The independent ordered-map oracle
groups `(class,x,y,float score)` without calling candidate hash/equality/sort,
and expresses final order as its own tuple. The committed V11 helper is a
second oracle; the runner verifies its Git blob before snapshotting it.
Complete output fields include template ID and float32 score bits.

The signed-zero design handles the otherwise unspecified representative:
unique minimum IDs can be checked by both oracles, while identical minimum IDs
with both score signs are compared bit-for-bit with the actual V11 path.
The whole-input zero fallback is explicit, its bucket count must be zero and
a throwing hash proves that no map is used. Zero at the first position followed
by nonfinite input still requires full finite rejection before the fallback.

The tests cover all duplicate-key fields, adjacent float values, finite extrema
and subnormals, true duplicate-key shuffles, long/nearly equal/embedded-NUL
classes, forced collisions, empty/singleton/idempotent calls and reserve modes.
Synthetic stress at old stage counts is correctly labeled synthetic, rather
than represented as captured pre-consolidation vectors.

Exception tests compare the complete original input after nonfinite/option
rejection, injected hash failures and every actual allocation ordinal until a
successful call. Allocation injection is disabled before checking the input.
These tests support the const-input contract; actual implementation still
needs review for input-key lifetime, equality/hash compatibility and complete
representative copying.

Useful optional additions before freezing tests are positive nondefault
`max_load_factor` values (for example0.25 and2.0), a small `reserve=false`
allocation-failure sweep, and exact `ThrowHash` call-count checks of
`throw_at+1`. The current default-path sweep and success tests already cover
the principal contract; these additions would make the exposed option and
injection evidence more explicit.

The runner preserves source/compiler/output hashes and checks source stability.
Initial RED must compile and fail semantically. Later mutations and GREEN,
real trace acquisition, timing and any threshold/default selection remain
separate steps. The old sandbox instrumentation must remain unexecuted.
