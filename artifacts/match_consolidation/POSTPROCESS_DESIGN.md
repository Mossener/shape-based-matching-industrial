# Postprocess consolidation design: hash alternatives

Status: design only. This document does not modify `line2Dup_matches.hpp`, run
the unverified `postprocess_optimization/instrument.py` sandbox, or claim a
speed result. It compares two isolated C++14 designs against the committed V11
contract and defines the smallest correctness/performance experiment needed
before any core change.

## Problem and non-negotiable V11 behavior

`Detector::match` merges worker/template results and calls
`detail::consolidateMatches` once after the search. V11 currently performs:

1. A first sort by exact `similarity` descending, `class_id` ascending, `y`,
   `x`, then `template_id`.
2. `std::unique` using `Match::operator==`, whose duplicate key is exactly
   `(class_id, x, y, similarity)` and intentionally excludes the template ID.
3. A second sort by exact `similarity` descending, `template_id` ascending,
   `class_id` ascending, `y`, then `x`.

The first order makes every equal key adjacent and puts the smallest template
ID first. Thus the retained record is the complete `Match` with the minimum
template ID. The second order is the deterministic output order. No score,
coordinate, class string, template bank, or bounding box is recomputed.

The alternative must be a drop-in implementation of this semantic and ordered
contract. A semantic-set match with a different order is insufficient: adapter
NMS and a template-ID-derived silhouette can observe order or representative
identity. Existing V11 tests and image evidence remain the oracle; the hash
experiment must preserve them byte-for-byte for every finite input.

## Candidate A: owning-string key

The direct hash design stores one key per unique group:

```cpp
struct Key {
    std::string class_id;
    int x, y;
    float similarity;
};
std::unordered_map<Key, std::size_t, KeyHash, KeyEqual> groups;
```

The mapped value should be an input index (or template ID plus a complete
representative), not a partially rebuilt `Match`. For each input record, find
the key; on a duplicate, replace the mapped representative only if its
`template_id` is smaller. Copy the selected complete `Match` to an output
vector, then apply the V11 final comparator. Never emit unordered-map iteration
order.

`KeyEqual` must match `Match::operator==`: class, x, y, and floating-point
`similarity ==`. `KeyHash` must canonicalize both signed zeros to the same hash,
then hash the exact bits of every other finite float. Hash collisions are
resolved by `KeyEqual`, not by trusting the hash value.

Advantages:

- Straightforward ownership and no lifetime dependency on the input vector.
- A key remains valid if an implementation later compacts the input vector.
- Long class IDs make the cost visible and easy to inspect in a memory profile.

Costs and risks:

- Each unique key owns another `std::string`; classes beyond the small-string
  buffer allocate and copy their bytes. The input vector already owns the same
  class string, so this can duplicate the largest field.
- Each hash node carries a string object, integer/float fields, mapped value and
  allocator/link overhead, plus the bucket array. The implementation may also
  allocate a temporary output vector of complete `Match` values.
- Hashing still scans every class string. Heavy duplicates avoid the second
  `N log N` sort but do not avoid this string scan.
- A malformed or adversarial class hash can turn the expected linear pass into
  a long collision chain. Collision handling is correct but may be slower than
  sorting.
- Moving a complete `Match` into a map value can make representative updates
  more expensive than changing a small index. Any optimization that stores only
  `template_id` must still emit all original fields from the minimum-ID record.

This is the easiest reference hash oracle, but it should not be selected merely
because it is simpler than the index design.

## Candidate B: immutable input-index key/equality

Keep the caller's `std::vector<Match>` immutable while the map is alive and use
indices as keys. The map key is the index of the first record seen for that
duplicate group; the mapped value is the index of the current minimum-ID
representative:

```cpp
struct IndexHash {
    const std::vector<Match>* input;
    std::size_t operator()(std::size_t i) const noexcept {
        return hashFields((*input)[i]);
    }
};
struct IndexEqual {
    const std::vector<Match>* input;
    bool operator()(std::size_t a, std::size_t b) const noexcept {
        return equalFields((*input)[a], (*input)[b]);
    }
};
std::unordered_map<std::size_t, std::size_t, IndexHash, IndexEqual> groups;
```

For input index `i`, call `find(i)` and `emplace(i,i)` on a miss. On a hit,
replace only `mapped_value` when `input[i].template_id` is lower. Do not write
to, append to, move from, sort, or resize the input vector until `groups` is
destroyed; its key and equality functors dereference it. After extraction,
compact the original vector in place from the representative indices or build a
temporary output vector, destroy the map, and apply the unchanged V11 final
sort. Reserve the map before insertion.

The hash function hashes the same fields as Candidate A. It may optionally
read a precomputed `std::vector<std::size_t>` of per-input field hashes, but
that is a separate memory/time tradeoff and must not change equality.

Advantages:

- No class-string copies or per-key string allocations; long IDs cost only the
  hash/equality scan while the input strings remain owned by the caller.
- A map node can contain two indices instead of a key object and a complete
  `Match`; the output can retain the original complete representative.
- For duplicate-heavy vectors, the map stores only U groups while all N input
  records stay in the existing contiguous vector. Compaction can avoid a
  second N-sized `Match` vector.

Costs and risks:

- The map is valid only while the input vector and all its `std::string` values
  stay immutable and allocated. Any reallocation, move, append or in-map
  compaction invalidates the functor's interpretation of existing indices.
- A callback, allocator hook or future parallel code must not mutate the
  vector while a lookup is active. Document this as an internal precondition.
- `unordered_map` still stores one node and bucket entry per unique key and
  still hashes every class string unless a hash cache is added.
- An index key is less familiar to reviewers; a test must prove that updating
  the mapped representative cannot alter the key/equality group.
- If the implementation compacts in place, it needs a U-sized index vector or
  an equivalent two-phase extraction before destroying the map. Writing output
  slots while lookups continue is forbidden.

For this matcher, Candidate B is the preferred prototype because the large
T-LESS vectors have long candidate lists and complete `Match` records already
exist. It is a hypothesis about reduced postprocess cost, not a measured gain.

## Exact floating-point policy

The core produces finite response-derived scores. Both hash candidates should
enforce that internal precondition before inserting any record:

```text
finite score only; NaN and ±infinity are rejected as invalid input
```

For finite values, equality and duplicate membership use the C++ float `==`
semantics already used by `Match::operator==`:

- Adjacent representable finite values remain distinct.
- `+0.0f` and `-0.0f` are equal duplicate-key values and must hash identically.
  Canonicalize zero bits to zero before hashing.
- Nonzero finite values are hashed from their exact IEEE-754 `uint32_t` bits;
  do not round, promote to a decimal string, or use an epsilon.

This signed-zero rule preserves V11. Treating signed zero as distinct would be
a behavior change, even if it appears unlikely in a normal response map.
Allowing NaNs without a policy is unsafe: `std::sort`'s comparator is not a
strict weak ordering for NaN and V11's output is not defined for it. A prototype
may return a clear invalid-input status; it must not silently invent a NaN
ordering. The production detector has no public path that injects mutable
matches, so this guard is a defensive internal contract rather than a quality
claim.

## Memory and small-vector behavior

Let N be the input count and U the number of unique duplicate keys.

| Design | Extra asymptotic storage | Main per-unique payload | Small N behavior |
| --- | --- | --- | --- |
| V11 sort/unique | O(1) beyond vector and sort stack | none | contiguous comparisons, usually best below a crossover |
| Owning-string hash | O(U) nodes + buckets + output | key string/fields and mapped index/record | allocator/hash overhead dominates |
| Input-index hash | O(U) nodes + buckets + representative indices | two indices; original strings reused | map setup and string hashing dominate |

The owning design can exceed input storage for long class IDs. The index design
still has a bucket/node allocation for every U group and may need U indices, so
it is not automatically cheaper when N is tiny or U≈N. It also retains the full
N input vector until extraction, whereas a direct in-place sort needs no map.

Use an explicit small-vector fallback to the committed V11 sort path only if a
benchmark demonstrates a stable crossover on the supported compiler/allocator.
Do not choose the threshold from a single timing run, and do not silently use
different duplicate semantics in the fallback. A threshold around 32/64/128
is a benchmark candidate, not a default or a result.

Do not reserve based on a guessed unique ratio. `reserve(N)` avoids repeated
rehashing but can allocate heavily for a no-duplicate vector. A two-pass exact
U count would reintroduce sorting or hashing and defeat the point. Measure
`reserve(N)`, a bounded load-factor reserve, and no reserve under the target
allocator; record bucket count and peak allocation.

## Correctness hazards to reject before timing

1. **Wrong key fields.** Omitting class, x, y, or exact score merges valid
   records. Including template ID retains duplicates that V11 removes.
2. **Wrong representative.** Updating only a template ID while another field
   differs is safe only after exact key equality is established. Emit the full
   record at the minimum template-ID input index.
3. **Unordered final output.** Hash iteration order is never the API order.
   Apply the exact V11 final comparator after reduction.
4. **Mutable index source.** Do not compact/sort/reallocate the input vector
   while an index-key map is active. Keep functors' vector pointers valid.
5. **String lifetime.** An owning key may move/copy safely, but an index hash
   must not store `c_str()` pointers or `string_view`-like references.
6. **Signed zero and NaN.** Preserve `+0/-0` equality; reject nonfinite input
   before sorting or hashing.
7. **Integer overflow.** Use `size_t` for input indices and map reserves;
   do not cast a candidate count to `int` for storage or allocation.
8. **Concurrent use.** Each call owns its map. Sharing a mutable input vector or
   a map/functor between detector calls is outside the workspace contract.
9. **Exception safety.** If allocation or hashing throws, leave the caller's
   input vector unchanged until the map has been reduced successfully. In-place
   compaction should happen only after all map operations succeed.
10. **Adapter assumptions.** Equal class/x/y/score records may have different
    template metadata boxes. V11 intentionally retains the smallest template
    ID; an adapter must use that same representative contract when deriving a
    silhouette. Hash reduction must not choose a first-seen ID.

## Minimum isolated prototype and test matrix

The prototype should live outside core source and expose three functions:

```text
v11_sort_unique(input)       // independent copy of the committed behavior
owning_hash(input, hash)     // candidate A; optional forced hash functor
index_hash(input, hash)      // candidate B; input immutable while map lives
```

Each returns an ordered vector of complete `Match` fields and a diagnostic
record containing N, U, bucket count, map allocations if available, and whether
all scores passed the finite guard. A deterministic tuple/bit oracle should
group by `(class,x,y,float-==)` and choose the smallest template ID, then use
the V11 final order. Do not use either candidate as its own oracle.

Required correctness cases:

- empty and singleton vectors;
- no duplicates and all records one duplicate key;
- 300+ shuffled input orders with equal scores and shuffled template IDs;
- same x/y/score in two classes, same class in two positions, and adjacent
  representable scores;
- exact `+0.0f`/`-0.0f` duplicates and distinct nonzero finite bit patterns;
- maximum finite score and `std::nextafter` neighbors;
- NaN, `+infinity`, and `-infinity` rejected with no partial output;
- forced constant-hash collisions for both designs, including all-duplicate and
  no-duplicate vectors;
- class IDs of lengths 0, 1, SSO boundary, 64, 256 and 4096 bytes, including
  equal long IDs and near-equal IDs;
- template IDs where the minimum appears first, last and in the middle;
- final ordering ties across class, template ID, y and x; idempotence after a
  second consolidation; and exact field/float-bit preservation;
- N around 0, 1, 16, 32, 64, 128, 1,024, 8,192, 32,768 and 131,072;
- duplicate ratios near 0%, 50%, 90% and 99.9%, with stable and shuffled input;
- vectors containing the observed LED/T-LESS candidate counts and the four
  recorded T-LESS vectors (230,077–486,045) as replay-only data.

The real candidate traces must be treated as immutable evidence. The old V10
and current V11 traces have different duplicate counts by design; compare each
candidate against the exact trace/provenance that produced it, not a relabeled
count.

## Benchmark plan and expected decision rule

Benchmark cold allocation plus warm repeated calls separately. Pin the same
CV/OpenMP environment used by V11, but run consolidation in isolation from
gradient/search work. Alternate implementation order, include enough warmups,
report median and tail (p95/p99), and record allocator/compiler/CPU details.
Measure:

- V11 sort/unique;
- owning-string hash with normal hash;
- immutable-index hash with normal hash;
- each with candidate map reserve/load-factor variants;
- forced-collision hash as a correctness stress, not a production speed claim.

For each vector record N, U, duplicate ratio, class byte length, bucket count,
peak/allocated bytes if the allocator can measure them, reduction time, final
sort time, total postprocess time, and exact oracle status. Include no-duplicate
cases where hashing is expected to lose and heavy-duplicate cases where it may
win. A single large T-LESS sample is not sufficient; the V11 stage evidence
shows LED vectors of 187–486 records and T-LESS vectors of 230,077–486,045.

The candidate is eligible for a later isolated core patch only if:

1. all correctness cases and independent oracle comparisons pass, including
   finite/signed-zero and forced-collision cases;
2. final ordered output and minimum-ID complete records are byte-for-byte equal
   to V11 on the real replay traces;
3. the benchmark shows a repeatable win on the large target vectors without a
   material regression on LED/case1 and small/no-duplicate vectors, or the
   fallback threshold demonstrably contains that regression;
4. peak memory and worst-case collision behavior are within an explicit budget;
5. a fresh uninstrumented matcher run rechecks the exact V11 image/equivalence
   matrix before any user-facing speed statement.

Otherwise retain V11. Correctness alone does not make hashing an optimization,
and an expected-O(N) algorithm can be slower than contiguous sorting for the
small vectors that dominate ordinary calls.

## Recommendation

Implement the immutable input-index prototype first, with a V11 sort fallback
for an experimentally justified small-N range. Keep the owning-string variant
as a correctness/memory comparison rather than the likely production choice.
Use one final V11 comparator, explicit finite-score validation, canonical signed
zero hashing and an independent oracle. Test forced collisions, long class
strings, empty/no-duplicate/heavy-duplicate vectors, and the recorded real
candidate counts before considering any core integration. Until that evidence
exists, report this as a design hypothesis and preserve the measured V11
overhead (about 0.004–0.011 ms on LED and 20.8–56.7 ms on the four large
T-LESS vectors), not as a claimed speed improvement.
