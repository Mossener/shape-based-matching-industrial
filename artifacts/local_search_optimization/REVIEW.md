# Independent review of the local accumulator

Reviewed `line2Dup_local.hpp`, `similarityLocalMaximum`, the `matchClass` dispatch, final default/caller settings, the immutable V4 adapter, and the independent paired harness. No blocking output-equivalence issue was found for the existing response domain (values 0..4), legal nonempty feature counts below 8192, and readable legacy local patches. Production code was not changed by this reviewer.

## Integer and selection proof

For fewer than 64 total features, at most 63 valid streams contribute to each byte accumulator, so the maximum is 252 and `_mm_add_epi8` cannot wrap. For 64..8191 features, zero-extension before word addition gives a maximum of 32764. Source order changes from feature-major to row-major, but every pixel receives exactly the same integer terms without overflow. The source reads cover exactly 16 bytes per row; the old SSE word path loaded overlapping ranges at columns 0 and 8, with the latter's upper bytes unused.

The prepared streams retain the original adjusted-coordinate expressions, original exclusion checks, original `accessLinearMemory` indexing, and original stream order. Skipped features remain in the denominator because the kernel receives the original total feature count. Empty streams return the default `(raw=0, score=0.f, row=-1, col=-1)`.

Completed rows are reduced in increasing row/column order and update only on a strictly larger raw value. Thus positive ties retain the first row-major position, while all-zero patches retain the original -1 coordinates. The final nonzero raw winner uses the unchanged `(int(raw)*100.f)/(4*total_features)` normalization. The existing independent normalization tests establish equivalence to the old float-per-pixel scan over this legal raw range.

## Dispatch and ownership

The final default is `fused_local_search=true`. Production uses the new path only with `MIPP_SSE`, `integer_local_max=true` and decimated width at least 16. Float requests, narrower images and other ISA builds retain their original path. Historical search fixtures now set `fused_local_search=false` explicitly; this harness overrides the flag explicitly for each current case, so changing the default did not change the tested fallback/fused pair.

The per-worker stream vector follows the existing scratch ownership. It is cleared and repopulated for every local call, and does not retain caller response pointers beyond the call's use. Reused and transient scratch use the same kernel. Bounds checks were not removed: an undersized image can clamp the center back below the nominal border, and loaded templates can have negative feature coordinates. The previous top-left feature check alone does not prove a whole 16x16 patch readable for arbitrary malformed templates; the new path does not broaden the reads made by the old SSE kernel.

The intrinsics used here are available in the measured SSE4.1 build. This review and these runs establish no AVX2, AVX512, NEON or GPU result. A direct MIPP `interleavehi<uint8_t>` call would have lacked a specialization in this vendored MIPP; the implementation correctly avoids it by using explicit SSE unpack intrinsics.

## Independent evidence

The benchmark obtains expected matches exclusively from the separately compiled frozen V4 implementation, with the exact fixture template bank exported through the existing loader. It does not invoke the new helper to construct expected output. Full C++ key sets compare class, x/y and the float score bit pattern; strict sets add template ID. Hashes are audit fingerprints only and never decide equality. Raw counts are checked independently of set equality.

Both complete runs contain 486 timed calls and nine untimed float-dispatch sanity calls, each checked against its image's V4 cold output. Each run has zero semantic, strict-template, count or hash differences; all 81 phase groups and sample counts are present. Compiled-source hashes are checked before measurement, after compilation and after measurement, with input/template hashes recorded separately. Internal total/search timers exclude result-key construction and V4 adapter conversion.

The separately authored kernel tests were inspected: expected sums use literal scalar stream accesses and the original float scan, with literal expected winners for all 256 cells. The preparation tests independently calculate adjusted coordinates and LM indexes, including odd T, negative source features and empty streams. These tests do not use the tested helper to construct expectations. Their execution belongs to the root agent's test runner and is recorded separately in `test_results_v10.json`.

One nonblocking invalid-input difference remains: an illegal fine-level template with at least 8192 features reaches the helper's assertion on the fused path, whereas the old branch raises `StsBadArg`. Legal template scores and selection are unaffected.

See `RESULTS.md` for both runs and their performance limits. The large LED direction repeats, while case1's complete-call paired result does not establish a stable improvement.
