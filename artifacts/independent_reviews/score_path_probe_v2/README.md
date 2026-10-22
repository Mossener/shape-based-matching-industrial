# Independent Phase2 numeric auditor

This standard-library-only auditor verifies the fixed same-pose diagnostic for
215 RGB TP identities in both RGB and binary-template arms. It rebuilds score
sums/binary32 bits, thresholds, local maxima/ties, complete parent links,
occurrence multiplicities, representative geometry, full-class NMS, and both GT
assignment modes from frozen numeric tables.

It imports only its own `numeric2`, `traces`, and `evidence2` modules. It does not
execute a native binary, import a probe/evaluator/matcher, decode an image, or
read serialized template-bank bytes. Historical bank pins are declarations from
the pinned passed Phase1 audit; `safe()` keeps bank-byte reads forbidden.

Run the synthetic tests from this directory:

```powershell
& 'F:\mysys2\ucrt64\bin\python.exe' -B -m unittest -v test_numeric2 test_traces test_evidence2 test_driver
```

The completed-dataset audit is separately authorized by the root and requires a
new output directory. Reproduction writes a new independent receipt; it never
reruns the native dataset stage:

```powershell
& 'F:\mysys2\ucrt64\bin\python.exe' -B -u audit_main.py `
  --freeze 'D:\h\shape_based_matching-master\artifacts\quality_failure_analysis\score_path_probe_v2\probe_phase2_v1\PHASE2_STAGE_FREEZE.json' `
  --output 'D:\h\shape_based_matching-master\artifacts\independent_reviews\score_path_probe_v2\NEW_AUTHORIZED_OUTPUT'
```

`run_numeric_audit_20261022_v1` preserves a provenance preflight failure: the
historical field `numeric_pins` included 12 serialized banks, correctly blocked
by this auditor. No Phase2 numeric CSV was processed in that attempt. The root
authorized a fresh v2 attempt after adding exact declaration-path coverage and a
test that uses deliberately nonexistent bank paths to prove no bank read.

`numeric_red.txt`, `trace_red.txt`, `map_stream_red.txt`, `fullframe_red.txt`,
`evidence_red.txt`, and `bank_declarations_red.txt` retain genuine failed
synthetic executions. `all_green_v4.txt` contains the 39-test GREEN run before
the fresh v2 audit, including a full eight-gzip synthetic path and independent
corruption rejection for every output table.

The fresh audit completed successfully in 102.71 seconds:

| Evidence | Independently checked |
| --- | ---: |
| Feature response digits | 73,337,912 |
| Coarse + local cells | 3,024,440 |
| Distinct local windows | 7,185 |
| Point-parent links | 12,016 |
| Complete Phase1 pre / post records | 1,312,006 / 227,816 |
| Full-class frame arms, including both GT assignment modes | 426 |
| Original RGB positive controls | 215 / 215 |
| Unique traced emissions / parent multiplicity | 292 / 1,462 |
| Inert source, build, numeric and receipt pins | 3,210 |

Receipt: `run_numeric_audit_20261022_v2/result.json`, 7,545 bytes, SHA256
`1710a1b3fe934ad73b8484b24527a99c2dddcdc6c20cca82aa2c3860ba724ea8`.
Its 430-row `diagnostics.csv` is 35,965 bytes, SHA256
`a953830bd1db680ebae834b1075b1100b60ce3c280e2d1a342bcafce6e4793c7`.

All 215 RGB controls recover the preserved TP path. In the binary same-pose
probe, 39 physical anchors and 46 neighboring-grid targets reach a fine score
of 85. Seventy-two targets have a reachable parent emission. These counts
describe only the selected same-pose paths: the original complete binary arm
retains 148 of the 215 RGB TP identities, including matches at other poses.
The one same-pose traced TP retained after full-class NMS must never be reported
as the overall binary TP count.

Response digits and feature coordinates remain frozen native observations, not
independent pixel/template reconstructions. A passing audit establishes numeric
trace consistency, not improved accuracy, recall, precision, or runtime.
