# Exact local-center result cache: design review

Read-only review of the current local refinement path in `line2Dup.cpp`,
`line2Dup_local.hpp`, and `line2Dup_search.hpp`, plus the completed V9 center
census. No production code or snapshots were edited and no matching or CPU tests
were run for this review.

## Recommendation

Use the fixed 16-entry `std::array` in each `SearchScratch`, with an explicit
valid-entry count reset for every template/level. Enable lookups only when
`reuse_local_centers && l == 0 && candidates.size() > 1`. Keep cache-off behavior
as the existing selected compute path. Cache hits must return the full
`LocalMaximum` produced by that path; they must not remove or reorder candidates.

The count evidence supports a small cache specifically at L0:

| Workload / level | Calls | Unique scoped centers | Repeated calls | Repeated share | Unique centers per nonempty template/image: median / p95 / max |
| --- | ---: | ---: | ---: | ---: | --- |
| LED L0 | 104,937 | 20,316 | 84,621 | 80.64% | 3 / 5 / 8 |
| LED L1 | 106,231 | 101,791 | 4,440 | 4.18% | 14 / 22 / 30 |
| case1 L0 | 123 | 123 | 0 | 0.00% | 2.5 / 4 / 5 |

The p95 here is nearest-rank over nonempty template/image rows. All 7,200 LED L0
template/image scopes are nonempty. case1 has only 46 nonempty scopes out of
361. Because every observed LED L0 scope has at most eight unique centers, a
16-entry cache would retain all observed L0 centers irrespective of candidate
order, covering all 84,621 repeated calls. This is count coverage, not a runtime
speedup prediction. The capacity must never be treated as a search limit.

The `>1` candidate gate is a sufficient initial policy: one candidate cannot hit
its own cache, and the gate does not affect matching semantics. A higher gate
would be a performance policy to evaluate later, rather than a correctness
requirement. case1 gets no cache hits in this census, so paired results should
check that its small miss-only overhead stays acceptable.

## Key equivalence

Both current local kernels derive feature offsets only from:

```cpp
const int offset_x = (center.x / T - 8) * T;
const int offset_y = (center.y / T - 8) * T;
```

The candidate coordinate update also uses `x / T` and `y / T`. Within one fixed
image, class, template, pyramid level and option configuration, the full local
result is therefore a pure function of the post-clamp integer quotients
`(x / T, y / T)`. The image linear memories, template feature set, denominator,
step and selected implementation remain fixed throughout that scope.

- Compute the key **after both existing clamp operations**, in their current
  order: first `max(..., border)`, then `min(..., max_x/max_y)`. Do not replace
  them with a different clamp: for an undersized image, `max_x` can be below
  `border` or negative, and the current final center can be negative.
- Use C++ signed integer division by the existing positive `T`. Negative values
  truncate toward zero; `floor`, unsigned conversion, rounding, or division of
  the pre-clamp candidate coordinate would identify different windows.
- Distinct raw coordinates with the same quotient intentionally share a key.
  For example, when `T=4`, raw centers `-1` and `0` both have quotient zero and
  produce the same existing offsets and output-coordinate calculation.
- A fixed array may store negative quotient keys directly; it never derives a
  pointer or array index from them. It does not make an invalid local-memory
  access valid: misses must preserve the existing feature checks and dispatch.

The scope must reset between every template and level, every class, and every
match call, even when a template ID, center or image size happens to repeat.
Otherwise the same key can refer to different linear memories, features,
denominators or options. Resetting once per template/level is sufficient even
when the same scratch object persists across calls or detectors.

## Preserve the actual selected result

Store all fields of the selected path's `LocalMaximum`: `raw`, `score`, `row`,
and `col`. Return the stored value on a hit and keep the existing per-candidate
coordinate update outside the cache lookup.

- In integer mode, preserve the first row-major maximum and the existing score
  conversion. Cache the computed result rather than inventing a new conversion.
- In float-per-pixel mode, fused dispatch remains disabled as today. A miss must
  still run the old similarity-map plus `floatLocalMaximum` path, and a hit must
  reuse its actual float `score` and winner. Do not cache only `raw` and later
  recompute a score or switch argmax implementations.
- A zero result is a valid cache value. Preserve `raw=0`, `score=0`, and
  `row=col=-1`; explicit entry count or stamp validity is necessary. Testing
  `raw != 0` or `score != 0` as validity would fail to cache zero windows and can
  accidentally replace the current sentinel coordinates.
- Feature points discarded by bounds checks still remain in the score
  denominator. Cached values must come from the same existing kernel call;
  they must not renormalize to the valid feature count.
- Keep the fused-option, integer-option, byte/word-feature-count, and narrow-row
  fallback dispatch inside the miss computation. The cache option is independent
  of those switches. A cache hit skips the same complete computation that a miss
  would have run, without forcing fused mode or reading a stale similarity map.

The cached object contains scalar values only. It must not retain source/linear
memory pointers, references to a `Match`, or a mutable `Mat` view. It is safe for
scratch local streams or local similarity maps to retain old contents on a hit:
the hit must not read those contents, and the next miss already refreshes them.

## Candidate and cache control flow

The safe structure is:

```cpp
// At the beginning of this template's local level:
scratch.local_center_count = 0;
const bool use_cache = options.reuse_local_centers && l == 0
                    && candidates.size() > 1;

// For each candidate, after the existing clamping:
const int cell_x = x / T, cell_y = y / T;
LocalMaximum best;
bool hit = false;
if (use_cache) {
    for (size_t i = 0; i < scratch.local_center_count; ++i) {
        const auto& entry = scratch.local_centers[i];
        if (entry.cell_x == cell_x && entry.cell_y == cell_y) {
            best = entry.value;
            hit = true;
            break;
        }
    }
}
if (!hit) {
    best = compute_existing_selected_path();
    if (use_cache && scratch.local_center_count < scratch.local_centers.size()) {
        scratch.local_centers[scratch.local_center_count++] = {cell_x, cell_y, best};
    }
}
// Existing candidate score/coordinate update and later filtering stay here.
```

This is pseudocode for placement, not a new production API. The miss computation
should remain one shared block/lambda to avoid diverging cache-on/off dispatch.

When all 16 entries are occupied, **continue searching those entries**. A miss
must compute the full existing result and leave the valid count at 16. Do not
overwrite useful entries, increment beyond capacity, truncate the candidate
loop, remove duplicates, or prune candidates early. Any capacity is correct
with this fallback; larger unseen candidate/center populations merely reduce
cache efficiency.

The cache must not move the level's `remove_if`, threshold comparisons, candidate
append, final sort or final unique. Their order and behavior remain unchanged.

## Fixed array versus dense stamped grid

| Property | Fixed 16-entry array | Dense `W*H` values plus generation stamps |
| --- | --- | --- |
| Lookup | At most 16 key comparisons; observed L0 has at most eight keys | One range check and indexed stamp lookup |
| Per-worker footprint | About 384 bytes plus a count, assuming 24-byte entries | About `20*W*H` bytes, assuming a 16-byte result and 4-byte stamp |
| Allocation | None for the cache | Resize/allocation and initial stamp zeroing when capacity grows |
| State invalidation | Set valid count to zero for each template/level | Advance generation; handle wrap and new storage correctly |
| Negative centers | Valid signed keys; no index construction | Needs a safe uncached fallback for out-of-range indices |
| Unseen many unique centers | First 16 stay cached; later misses compute fully | Can cache all in-range centers |
| Present LED L0 hit coverage | All observed repeats | Same observed repeats, at greater footprint |

For the existing padded LED L0, `W=224`, `H=176`: a dense grid is about 788,480
bytes per worker, or 3.01 MiB for four workers. case1 L0 is `272*240`, about
1,305,600 bytes per worker or 4.98 MiB for four. These are approximate payloads
before allocator/capacity overhead, using the stated ordinary field sizes. A
four-worker fixed cache is about 1.5 KiB. A dense grid is feasible in absolute
size, but the current sparse L0 key population offers no additional hit benefit
on these fixtures.

Dense caching can become attractive for a demonstrated workload with many
unique, repeatedly used centers. It adds correctness and lifecycle details now
without evidence of a count advantage, and transient per-template scratch makes
its repeated allocation/zeroing particularly unattractive when search-buffer
reuse is disabled.

If the dense version is implemented later, require all of the following:

1. Check signed key bounds before calculating any element pointer or indexing:
   `0 <= xg && xg < W && 0 <= yg && yg < H`. Form the product/index with checked
   `size_t` arithmetic after valid positive dimensions; do not multiply signed
   ints first and cast after overflow.
2. If the stated policy also requires **raw negative centers** to bypass the
   cache, check `x < 0 || y < 0` separately. Quotient bounds alone do not detect
   small negative raw values because C++ truncates toward zero. Caching those
   quotient-zero windows would still be equivalent, but it differs from that
   stated policy.
3. Keep generation nonzero for active lookups. On unsigned wrap, clear every
   stamp and restart with generation one before lookup. Newly added stamp
   storage must be zero-initialized. A resize to another shape or another image
   must never make an old stamp valid in the new template/level scope.
4. Resize/rebind dimensions before any lookup, and advance generation for each
   eligible template/level even if previous candidates all disappeared. Equal
   `W*H` with changed W/H must still start a fresh logical scope.
5. A generation hit may reuse a zero-valued `LocalMaximum`; the stamp is the sole
   validity marker. Out-of-range or negative-policy fallback computes normally.

## Threads and workspace lifetime

The current loop selects `SearchScratch` by `omp_get_thread_num()` for the
worker's whole template iteration. A worker handles its templates serially, so
a fixed array/count or dense generation is private to that worker. Reset inside
the template-level loop; do not place one shared cache beside the matches
reduction or mutate another worker's scratch.

| Workspace switches | Existing scratch ownership | Cache requirement |
| --- | --- | --- |
| `reuse_buffers=true`, `reuse_search_buffers=true` | Persistent worker scratch across calls | Reset each template/level so no image, class, template, flag or size state leaks |
| `reuse_buffers=false`, `reuse_search_buffers=true` | Call-local worker scratch, reused across templates only during that call | Same template/level reset; no persistence is required for correctness or benefit |
| `reuse_search_buffers=false` | Transient scratch within one template iteration | Cache remains valid across that template's candidates; reset between local levels |

Worker-count growth/shrink, workspace move, detector/size switches and independent
concurrent callers are safe under the existing one-workspace-per-concurrent-call
contract if each new scope resets. Fixed keys require no image-size-dependent
storage or stale-width interpretation. The existing unsupported case of sharing
one explicit workspace simultaneously should not be broadened by this change.

## Checks to require before enabling by default

These are review recommendations; this review did not run them.

- A small cache helper test should compare cached/off results for repeated
  signed quotient keys, all-zero results, ties, more than 16 unique keys followed
  by repeats of both stored and unstored keys, and reset between scopes. Include
  a repeated stored key after the array becomes full.
- Matcher equivalence should cover cache on/off crossed with fused on/off,
  integer/float argmax, direct 8-bit on/off, and both scratch-lifetime switches.
  Keep source feature-boundary, undersized/narrow-row, empty-candidate and
  single-candidate cases. Test multi-class/template, detector/size changes,
  worker-count changes and separate concurrent callers.
- Preserve semantic sets and raw counts against immutable V4/V10; record strict
  template sets for equal-score review as in the existing harness. Test zero
  maps and zero/negative thresholds so the valid zero-result sentinel case is
  exercised beyond the positive fixture thresholds.
- Freeze newly added cache options explicitly off in historical benchmark
  configurations. An added default-true option must not silently change what
  the old three-search-option matrix or frozen V10 comparison means.
- Only an uninstrumented paired benchmark should decide default enablement and
  whether case1's miss-only overhead is acceptable. Run cache on/off with fused
  on/off independently; center counts alone do not measure net time saved.

The fixed-array design has no correctness blocker under these constraints. It
matches the measured scope and avoids the dense scheme's allocation, indexing,
shape and generation complexity. Broader workloads can motivate a different
cache later without changing the matching result or the option's semantics.
