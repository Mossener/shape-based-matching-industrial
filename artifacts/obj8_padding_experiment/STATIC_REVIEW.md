# Static protocol review

This design follows `artifacts/quality_coverage/PADDING_POLICY.md` while fixing
the experiment to the existing two-level V11 object-8 bank. The implementation
must inspect each actual loaded class/template/level, preserve left/top64,
check actual feature bounds and divisibility, and compute the full-bank maximum
before any frame is matched. Maxima from different template IDs are combined;
there is no pose dropping or per-frame parameter selection.

The independently derived final dimensions are848x800, not a symmetric256-pixel
margin. Minimality is conditional on preserving at least the original848x672
total dimensions and moving no source origin. One lower16-pixel height step
would be784, below the798 refinement bound. Reducing width would violate the
retained baseline-width requirement. Right64/bottom196 follows directly.

The arithmetic check exposed a useful historical boundary distinction:
declared-fit630 versus actual-feature-inclusive634 invalid template levels.
IDs566/951/999/1005 require coarse height337 because their actual feature y is336.
The old report stays intact; the corrected static protocol records both figures
and the prior design SHA. The correction used only numeric geometry, without
image evaluation, size/threshold tuning or a changed target bank.

The protocol freezes source/recipe inputs and exact frame selections, retains
all raw candidates and failures, separates old/new GT retention from aggregate
TP, and disallows cross-padding raw-cache reuse. The pilot can only validate
correctness and budget feasibility; an unhelpful pilot quality outcome is not
an excuse to retune or suppress the fixed full-development comparison.

The timing design includes the cost of extra padding and search extent and
keeps a separate match-only phase. Its maximum area increase is a predictable
cost, not evidence of a speed or recall benefit. The memory budget is an
explicit conservative estimate plus a measured RSS limit, not a proven native
allocation bound. Overflow/invalid inputs and budget aborts need explicit
failure records.

No image was opened or decoded, no native bank was loaded, and no compilation,
training or matching was run during this review. Runtime source provenance,
bank geometry, exact baseline recovery, fallback/fused equivalence, outputs
and physical-allocation limits still require implementation verification. The
proposal does not resolve the separate generic SIMD physical-tail-read caveat.
