# Supported next optimization targets

The nine fixed workloads passed exact semantic, strict-template, and raw-count
equivalence before profiling and on all 90 collected calls. The independent
post-processing audit passed. These findings describe this fixture set and build.

1. **Prioritize the exact 16-bit local accumulation kernel for LED.** Local
   accumulation is 92.48% of timed worker stages, versus coarse 1.57%, candidate
   collect 0.61%, and argmax 5.24%. Both LED local levels use the 16-bit path:
   111 features at L1 and 236 at L0. L0 accounts for 80.966 ms and L1 for
   37.067 ms of summed worker accumulation per image, using equal means of image
   medians. The existing SSE path repeatedly loads/stores the destination for
   every feature and loads overlapping 16-byte source registers for its two
   8-lane widening operations. An exact row-oriented kernel can load each
   16-byte source row once, widen both halves, accumulate the 16 result cells in
   registers, and store once after the feature loop. Precomputing valid feature
   pointers can keep coordinate/bounds work outside the row loop. Preserve
   byte-for-byte raw maps, out-of-bounds feature skipping, and existing argmax
   tie behavior; verify with kernel tests and the uninstrumented matcher suite.

2. **Measure unique local centers before implementing a center cache.** LED
   makes 20,782–35,501 local calls per image. Repeated refinement can converge to
   identical centers, but this profiler did not record unique centers. L1 Y
   clamping affects 7.65–26.35% of candidates and X clamping at most 0.78%; L0
   has no clamping in these fixtures. These counts do not establish cache hit
   rate. A separate count-only census of `(template_id, level, x/T, y/T)` after
   clamping can quantify exact duplicate windows. If repeats are material, a
   cache within one template and level could reuse the raw maximum and winner
   coordinates without changing candidate multiplicity or pruning semantics.

3. **Treat coarse-tail collection as a case1-specific follow-up.** case1 uses
   only 123 local calls; coarse similarity and candidate collection occupy
   68.49% and 20.12% of timed worker stages. Candidate collection scans a zero
   tail covering 33.40% of map positions (LED: 10.84%). For nonnegative
   thresholds, those zeros cannot pass the strict `score > threshold` condition,
   so a bound derived from the existing accumulated prefix could avoid scanning
   them while preserving behavior. Negative thresholds require the existing
   full scan. The prefix's row-wrapped positions are separate; removing those
   would need an explicit semantic decision even though they produced no
   candidates on this fixture set. This target is negligible for LED because
   its whole collection stage is only 0.61% of worker intervals.

Final sort is already small: 0.020 ms for LED and 0.003 ms for case1, as equal
means of per-image medians. Argmax is secondary to LED accumulation. L1 retains
98.71% of coarse candidates on average, and L0 retains only 2.92%; changing pose
banks or thresholds to lower these counts would change the task and is not
supported by this profile.

All percentages above use only summed worker stages. Those are elapsed worker
intervals including descheduling, not process CPU time or serial wall time.
Instrumented calls include extra timer/counter/census work, and per-candidate
timers affect short argmax intervals proportionally more. Similarity intervals
include map zeroing/allocation and any conversion. None of these figures is an
uninstrumented speedup prediction; use the established benchmark for that.
