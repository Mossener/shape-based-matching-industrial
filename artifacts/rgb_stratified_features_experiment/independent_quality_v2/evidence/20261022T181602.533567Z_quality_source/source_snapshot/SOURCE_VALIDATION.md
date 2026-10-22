# V31 independent quality source iterations

This log records audit correctness and execution controls. It contains no real
quality, speed, industrial-readiness or candidate-promotion result.

The first source milestone retained the V30 numeric core byte-identically and
added separate C0/P/B raw, NMS, selected-row, GT, negative-frame and retention
replay. It passed 17 synthetic tests and rejected 11 deliberate source mutants
in `evidence/20261022T171856.927969Z_quality_source/RECEIPT.json`. This early
snapshot predates the final canonical input-version join and guarded wrapper.

The current source milestone uses the single input version
`rgb_stratified_quality_inputs_v1`, checks the passing combined independent
training/exact-geometry report and exact freeze pins, binds all 18 banks to
their own filenames/directories/counts, hashes complete declared numeric
allowlists, and compares full old-padding C0, common-padding C0 and pilot
overlap archives. Native integral byte counters accept FileStorage's integer
doubles while refusing booleans, fractions and nonfinite numbers. Gzip output
is bounded while decoding; duplicate/misclassified/invalid GT is rejected.

The guarded wrapper adds stage-hash reservation exclusivity, an explicit CPU
grant, persistent consumption before the child, source/interpreter pin checks,
RSS/wall/output/log observations, exact result-stage binding and preserved
failure evidence. Peer source review found reservation/output/native-stage
path overlap; a RED test reproduced it and the fixed preflight rejects it
before any write. Composite reports that contradict numeric success or claim
production promotion are also rejected.

Current coverage is 23 synthetic tests and 14 deliberate source mutants. Each
`run_selftest.py` invocation preserves its exact source snapshot, interpreter,
GREEN/RED outputs and receipt under a fresh timestamped `evidence/` directory.
RED/source-development receipts remain preserved. The last passing receipt
must be selected by its actual recorded source hashes, not by this prose log.

All this preparation used zero real archive/bank/metadata/index/image reads,
zero native matcher calls and zero image decodes. Native RGB gradient/NMS
candidate acquisition, runtime closure and heldout/industrial generalization
remain separate evidence. No real audit reservation was issued by this work.
