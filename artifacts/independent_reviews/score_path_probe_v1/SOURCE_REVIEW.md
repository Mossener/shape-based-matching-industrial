# Source-only review before the first real numeric replay

The independent implementation was read against the actual frozen V11
consolidation semantics, probe output schemas, archive adapter sorting and
runner/build receipts. No target implementation was imported or executed.

Checks performed:

- The consolidation key excludes template ID and uses float equality;
  finite validation precedes grouping. The representative is copied as a
  complete record. Adapter ordering is distinct from V11 final ordering.
- GT hit counts count pre occurrences. A support loss requires a pre hit
  and no post hit at IoU ≥ 0.5. Every cross-template group is reported,
  including groups whose official boxes happen to be equal.
- Archive rank, manifest frame/class/path/size/count, binary32 score bits,
  pose metadata, official box conversion and canonical ordering are checked.
- Phase1 reads only the fixed 213 object/frame and 175 image declarations.
  Every target identity is reconstructed from the preserved development
  numeric CSV closure. Reserved objects and held-out scenes are rejected.
- Full native and runner member sets are checked; unexpected failure files
  remain failures even if repinned. GREEN binds deliberate RED and identical
  project/tool closures, with only the explicit RED macro enabled there.
- Numeric byte counts follow the native schema. Native physical bytes and
  runner-measured bytes are separate quantities; runner counting excludes
  the later freeze file.
- The independent auditor does not claim independent LM feature-score
  recomputation. Native score-gate flags and full pre-row coverage are the
  exact boundary verified here.

The 17 synthetic tests passed before the one retained real replay started.
