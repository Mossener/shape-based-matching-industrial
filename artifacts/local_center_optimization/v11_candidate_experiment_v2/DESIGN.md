# V11 cache V2: bounded design for a fixed-cost lookup experiment

Status: static proposal only. No new matcher source, cache implementation,
compilation, image decoding, matcher run or benchmark has been performed here.
All new files stay in this sibling directory. V1 locked files and production
core remain unchanged. Parent reviews this design before implementation and
continues to coordinate every heavy CPU slot.

## Question and evidence

V1's exact sixteen-entry linear cache reduced search on all eight LED images,
but twelve of sixteen tiny development images regressed. Equal-weight image
median on/off search ratio was0.99775; the geometric mean was0.84391. The
different rollups and regressions must remain visible. The evidence supports
testing cache lookup cost and locality; it does not establish which caused a
particular regression or justify changing capacity or an object-specific rule.

The V2 question is whether a fixed-cost lookup can retain useful duplicate
center reuse while reducing negative overhead on the same broad fixed matrix.
Every accepted match vector must still agree in length, class/x/y/template ID,
float32 score bits and order with exact frozen V11.

## Alternatives

| Alternative | Storage | Lookup bound | Replacement | Tradeoff |
| --- | --- | --- | --- | --- |
| V1 linear reference | sixteen complete winners | sixteen key comparisons | first sixteen retained until reset | Existing measured baseline; misses after full scan can cost work without saving search. |
| Recommended V2 direct map | sixteen complete winners | one indexed slot plus full-key check | replace the indexed slot after a fully computed miss | Constant slot count; collisions can destroy useful reuse and hash work remains. |
| Considered but deferred hot-linear control | original sixteen winners plus one index, no extra winner | first check last-hit slot, then the other at most fifteen | original first-sixteen policy | Consecutive repeats may be cheaper without hash arithmetic, but nonlocal/full-cache misses still scan and incur reordering overhead. |

A one-winner cache is excluded because it changes capacity. A seventeenth
last-winner record is also excluded. The hot-linear alternative keeps an index
into the original sixteen slots. It should be a separately predeclared control
if parent chooses to include it, rather than a response to which images favor
direct mapping. Recommendation: direct-map is the primary V2 candidate; keep
hot-linear as a written alternative only. Parent selected direct-map as the
single V2 algorithm change and explicitly deferred the hot-linear variant.

## Exact direct-map behavior

The key is still the pair of signed C++ integer quotients `(x/T,y/T)` after
the existing coordinate clamps. A slot index can collide; a hit always checks
both full signed key components and a separate validity bit. No key or zero
score is a sentinel. Store and copy the complete `LocalMaximum`, including raw,
float32 score bits, row and column, with no reconstruction.

Predeclare the hash before reading any V2 runtime results. Convert signed
coordinates with `static_cast<std::uint32_t>`; conversion is modulo2^32,
including negative values. The supported build requires exactly32-bit `int`
and `uint32_t`, `CHAR_BIT==8`, and32-bit `unsigned int`, enforced by static
assertions so the `U` constants also participate in unsigned32 arithmetic.
Use this fixed generic pair
combination followed by the MurmurHash3 `fmix32` finalizer:

1. `h=ux+0x9e3779b9U`;
2. `h ^= uy+0x9e3779b9U+(h<<6)+(h>>2)`;
3. xor with right16; multiply modulo2^32 by `0x85ebca6bU`;
4. xor with right13; multiply modulo2^32 by `0xc2b2ae35U`;
5. xor with right16; use `h&15U` as slot0..15.

The hash contains only unsigned32 operations; no signed overflow or signed
shift is allowed. It is a fixed generic mixer, not a dataset-derived choice.
On a miss, leave the caller's output untouched and execute the unchanged
complete local-search dispatch. Only after that search finishes, write the
full key and full winner into the slot and mark it valid. A collision replaces
the old entry; it never means a match, early exit, failed candidate or reduced
search. Reset clears the sixteen validity bits at each template/level boundary.

The enable gate remains `reuse_local_centers && l==0 && candidates.size()>1`.
Each worker owns its cache in `SearchScratch`. Template/options/normalization
cannot cross the reset boundary. Candidate order/count, template banks,
thresholds, padding, feature count, windows and consolidation remain untouched.
The public experiment switch remains explicit off by default. Both off and on
paths execute in the same candidate binary; no object/image identity policy is
introduced.

## Isolation and comparison

Freeze exact V11's seven matcher and sixteen MIPP files again into V2. Verify
their byte identity against Git and the V1 frozen manifest; never modify V1 to
reuse its infrastructure. Copy existing fixtures/adapters/tests/runners into
V2 and pin their origins before editing. Input metadata is filtered to the same
sixteen tiny development frames before image-path construction or decoding.
No heldout image is decoded, viewed or matched, and no new template/data tuning
is performed in this speed-only experiment.

Avoid a runtime policy switch inside every candidate lookup. Compile exact V11
and each fixed candidate strategy in separate translation units/namespaces.
All candidate integration `.cpp` and `.h` bytes should be identical apart from
the explicit namespace mechanism applied during compilation; only the private
cache header differs between policies. Baseline/candidate include paths must
not resolve to production core. Export each fixture bank once, then load its
identical serialized bytes into all detector variants. Use separate retained
workspaces per variant and cache setting.

Parent fixed V18 linear16 as the prior-policy control and exact V11 as oracle.
The proposed concrete comparison set is exact V11, V18 linear16 off/on, and V2
direct16 off/on: five cases, two paired off/on comparisons and a linear-on vs
direct-on policy comparison. Both candidate off paths must agree with exact
V11, and their measured differences disclose namespace/code-layout overhead.
V18 supplies a frozen prior-policy control in the same fresh environment.
Do not choose a winning policy per image.
The different candidate namespaces/code layouts can influence timings; publish
off/exact-V11 differences and all per-image results rather than attributing
every change to cache lookup.

## TDD and output regression

Direct-map tests first compile a no-op stub and require a stored-key retrieval
failure, not a compile failure. Then implement the cache and retain RED/GREEN
source/binary/output hashes. Literal cases cover full winner bits including
signed zero, signed and swapped keys, reset/worker isolation, all sixteen slot
indices, deterministic collisions and replacement, and complete ordered
fallback on a long colliding stream. Unlike V1, the V2 test must explicitly
expect a displaced key to miss and the replacement key to hit.

Collision tests should generate a deterministic bounded set of signed key
pairs, independently group them by the predeclared slot formula, and use known
different keys in one slot. The test's slot calculation is separate from the
class under test. Include literal hash/slot vectors to catch a shared wrong
formula. A hit with a different full key must fail even when slots agree.

Reuse the existing direct tuple comparator and its one-bit/order/field/length
rejection checks. Preserve all previous flags, image routes, masks, synthetic
zero maxima, threads, defaults, workspace lifetime and concurrent-call coverage.
Run core, flags and lifetime once each for V18 linear16 and V2 direct16;
do not mechanically repeat the combined all route. The newly copied runner
will predeclare exact expected rows/calls after the parent fixes the policy
set, pin its build/executable/input/source/runtime closure and retain before/
after hashes. Every strategy and setting compares with independently compiled
exact V11, with no hash/set substitute for ordered record equality.

## Separate diagnostic build

If requested, make a separately named and hashed diagnostic variant. It always
executes the complete original V11 local computation for each candidate. It
maintains shadow linear16/direct16 caches on those same key/winner
events, verifies every hypothetical hit against the freshly computed complete
winner, and counts lookups, hits, misses, full misses, occupied-slot collisions,
consecutive repeats, comparisons and reset scopes. Counts live in worker-owned
storage and are merged only after search. No diagnostic timing is speed evidence.

The diagnostic explains how much work each cache could avoid on the observed
sequence. Track unique centers with a diagnostic-only per-scope set and
consecutive-run histograms; these extra structures never enter the
uninstrumented native binary. Comparison counts do not measure actual lookup nanoseconds, and
shadow hits must not be described as a measured speedup. Do not add per-object
or per-image thresholds from these counts. Any replay microbenchmark would be
separate evidence with its own predeclared protocol; native matcher timings
remain the application-level decision evidence.

## Controlled performance gate

Only after independent RED/GREEN and complete ordered regression pass may a
new uninstrumented binary run the frozen 25-image matrix. Keep all original
template banks/features/thresholds/padding, CV1/OMP4/passive settings, cold1,
warm2 and measured15 per case/image. Predeclare balanced rotating/reversed
order for the final number of cases; verify that order numerically. Compare
outputs outside internal and wall timers. Retain all five cold outputs until
that cold round has finished, then use its exact-V11 output as oracle and
compare all five; no extra uncounted oracle call is made. Keep all raw samples, regressions,
per-image medians and paired ratios, equal-weight image median/geometric mean,
and descriptive quantiles. Do not claim confidence intervals from these
quantiles, universal speed gain, accuracy gain or production adoption.

Check actual source/protected/runtime/compiler/protocol/build/receipt/exe/gate/
CSV pins before and after run and summary. Reuse the independently reviewed
V1 closure checks through V2 copies, with new semantic synthetic rejection
checks for changed variant identities and the chosen case-order matrix. Parent
will independently recheck arithmetic and complete hash closure before any
archival or adoption decision. Only parent stages, commits, tags or pushes.

## Parent decisions recorded

1. Direct-map16 is the sole new algorithm; hot-linear stays deferred. Use a
   fixed generic uint32 hash with explicit signed-to-unsigned conversion and
   no undefined arithmetic; the exact pair/fmix32 formula above is proposed
   for static review before implementation. No hash/capacity search is allowed.
2. V18 linear16 is the frozen policy control; exact V11 is the output oracle.
   This design proposes explicit off/on for each candidate in the same binary
   (five total cases) so code-layout effects are visible, with no runtime
   per-candidate policy dispatch.
3. The separate diagnostic may count hits/misses/collisions/unique/run-lengths
   on exactly the same25 images. It does not choose images or tune capacity,
   and none of its timings become speed evidence. Parent reviews native work
   and assigns CPU explicitly before compilation or execution.
