# Independent numeric audit of real consolidation traces

The reader/grouping implementation in `audit_trace.py` uses only Python's
standard library. It does not import the capture parser, hash prototype,
evaluator or matcher. It opens only contained JSON/binary trace evidence.

Four synthetic tests pass: complete fields and minimum-template representative,
negative numerical score order, explicit rejection of signed-zero/nonfinite
scores, and literal binary/class bytes with malformed/truncated-data rejection.
Signed-zero representative selection is outside this independent audit's scope;
the native hash contract handles it by falling back to exact V11 sort/unique.

`root_trace_audit_20261022.json` freshly verifies all 25 fixed actual-85 capture
cases in protocol order. Each trace passes byte/count checks and agrees with
its separately executed uninstrumented V11 reference. The independent numeric
implementation then groups the full pre-consolidation input by class/x/y/exact
nonzero score, chooses the minimum template ID, sorts by numerical descending
score/template/class bytes/y/x and compares the complete ordered records.
Every record is equal, including binary32 score bits and raw class bytes.

The traces contain 21–2,695 input candidates. They include small real inputs
and duplicate removal, but no empty, completely duplicate-free or historically
large 486k-candidate real input. Keep those limits when interpreting a replay
benchmark. These are 25 existing images, not 25 newly acquired images.

Root separately freshly checked the two actual build receipts, source pins,
executable hashes and ordered compiler dependency lists (405/437 occurrences
for capture, 402/434 for reference). All compile/link exits were zero; the
saved scope smoke receipt records 14 checks. Those checks use the capture
helpers and are distinct from the independent binary/grouping implementation.
The capture lane's full image/source/build/runtime provenance checks remain
separate evidence. No timing or accuracy conclusion follows from this audit.

From the repository root:

```powershell
python -m unittest discover -s artifacts/independent_reviews/consolidation_trace_v1 -p test_trace.py -v
python artifacts/independent_reviews/consolidation_trace_v1/audit_trace.py --capture-run artifacts/match_consolidation/hash_prototype/run_20261022_capture_actual85 --output artifacts/independent_reviews/consolidation_trace_v1/my_fresh_trace_audit.json
```

The output must be new. Evidence paths describe the original local workspace;
this command assumes the retained trace artifacts exist there.

The separate `audit_replay_statistics.py` also passed against the completed
4250-row replay CSV. It independently reconstructs routes, batch sizes,
diagnostics, paired per-trace ratios and scenario summaries; see
`root_replay_arithmetic_20261022.json`. It imports only this independent trace
reader, not the prototype statistics or matcher. The ten combined independent
reader/arithmetic synthetic tests passed in
`root_numeric_tests_green_20261022.json`.

The earlier saved-test wrapper receipt `root_numeric_tests_20261022.json`
reports failure because its `OK` marker parser assumed LF while Windows
unittest output used CRLF. All ten underlying test exits were zero. Its exact
source is retained as `run_saved_numeric_tests_before_crlf_fix.py`; the current
runner checks split lines while preserving the original stdout/stderr bytes.
This wrapper correction changes no audit arithmetic or matcher code.
