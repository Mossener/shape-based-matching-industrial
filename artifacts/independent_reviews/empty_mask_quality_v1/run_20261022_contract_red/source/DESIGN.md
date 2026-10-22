# Independent three-arm numeric quality audit

This work reads no image and invokes no matcher, compiler or evaluator. Actual
archive audits require the parent's review and an explicit CPU slot. Small
literal tests are separate synthetic evidence. No accuracy or speed result is
claimed before the complete development output passes.

The three arms are retained V15 RGB (848x672), common-padding RGB (848x832),
and binary-source/empty-feature-mask (848x832). Compare padding, training
policy and overall change separately. The second comparison changes both
training source and selection-mask policy. Existing timing diagnostics cannot
establish a padding speed ratio.

Fixed scope is objects 1/2/5/8/12/17 on the same 400 development frames,
2400 object/frame combinations. Fallback and fused raw streams must agree in
complete canonical ordered fields and float32 bits within each arm. Empty
raw files are valid observations; absent frames/files fail the audit.

Implementation is independent Python standard library. It adapts the existing
independent obj8 audit's canonical ordering, class-aware NMS, greedy GT policy,
and source-origin reconstruction, with explicit source hashes in ORIGIN.json.
It imports no new quality evaluator, support, summary or provenance helper.

For each raw candidate check frame/class/rank, finite float32 score, template
metadata, training pose, and official box: match minus fixed64 padding plus
official warped-mask origin minus that arm's actual template tl_x/tl_y. The
same numeric template ID across different training arms implies no identity.
Cross-arm pose identity is object/training_image/angle/scale.

Recompute post-score>=85, NMS suppression only when same-class IoU>0.3,
GT acceptance IoU>=0.5, visibility eligibility>=0.5, and one-to-one ignores.
Eligible matching completes its TP pass before low-visibility ignore matching.
Check selected full identities/order, every label/GT ID, per-frame counts/IoU
sums, native ground-truth projection and retention rows before aggregation.

Report allGT and eligible TP/FP/FN/GT/IGNORE, precision/recall/F1, TP IoU
sum/mean, negative-frame FP and negative frames with FP. Keep object, scene,
micro and equal-object macro totals. Preserve retained/new/lost GT identities
for all three comparisons, including changes hidden by unchanged net TP.
Padding also retains exact original TP detection rows; full raw/selected
equality and first difference are reported without filtering or retuning.

Provenance first binds the new successful QUALITY_STAGE_FREEZE and complete
build/input/previous/selftest chain, then freezes all consulted numeric bytes.
The V15 baseline summary, per-object audit and preservation manifest anchor
old raw tar members, selected CSV/metrics/config, and bank metadata. Match RGB
bank/config/metadata against the inherited frozen closure. Validate gzip/tar
member inventory, SHA and byte counts before parsing. Recheck inputs and
auditor sources at completion. Failed/partial evidence remains immutable.

Required literal/mutation cases include changed frame ID, score bit, raw order,
bbox origin, selected row, GT retention identity and aggregate count. Further
tests cover NMS equality boundary, GT ties, eligible-priority ignores, negative
frames and explicit zero denominators in descriptive precision/recall.
