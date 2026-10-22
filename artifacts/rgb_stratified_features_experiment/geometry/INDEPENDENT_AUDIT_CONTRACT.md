# Independent exact geometry audit

`independent_geometry_audit.py` reconstructs every layer from all eighteen
C0/P/B banks and the six original pose CSVs. It imports only the strict YAML
grammar parser from the scanner's dependencies. It does not import `planner.py`,
`run_geometry.py`, or their calculation functions. Own feature coordinates,
pose canvases, layer requirements, the common padding plan, and every report
field are independently recomputed from the frozen padding specification.

The accepted result has schema
`rgb_stratified_independent_geometry_audit_v1`, `passed: true`,
`accepted_independent_audit: true`, `numeric_audit_passed: true`, and
`scope: "exact_geometry_only"`. Its complete `input_pins` map includes the exact
root `GEOMETRY_INPUT_FREEZE.json`, scanner `GEOMETRY_FREEZE.json`, training
numeric audit, original CSVs, eighteen banks and metadata files, scanner
sources/reservation, scanner report and standalone plan. Before/after pins and
auditor source pins must remain equal. No image decoding, matcher or native
execution occurs inside the worker.

The source training numeric audit is required to have all 20736 shared poses,
41472 pools, 41472 arm attempts, 82944 layer status rows, complete successful
bank counts, unchanged output pins and accepted public numeric status. All P/B
bank pins and original CSV pins must be linked to that audit. The worker checks
this closure; it does not independently repeat the training-selection numeric
audit. The root combines the separate training and geometry results, together
with source/runtime acceptance, into `scope: "training_and_exact_geometry"`.
This worker does not certify accuracy, performance, production readiness or
native training provenance.

## One reservation, one guarded execution

Root supplies the already frozen input pins. Reservation reads only the two
freeze JSONs and the training numeric audit JSON. It validates declarations
without reading banks, reports, metadata or CSV payloads.

```text
python -B geometry/run_independent_geometry_audit.py --reserve-only --inputs INPUT.json --inputs-bytes N --inputs-sha256 SHA --scanner-freeze SCANNER_FREEZE.json --scanner-freeze-bytes N --scanner-freeze-sha256 SHA --reservation FRESH_RESERVATION.json --evidence FRESH_EVIDENCE --execution FRESH_EXECUTION
python -B geometry/run_independent_geometry_audit.py --execute --reservation FRESH_RESERVATION.json
```

Equivalent Python API:

```python
reserve(input_pin, scanner_pin, reservation, evidence, execution)
execute(reservation)
```

`FRESH_EVIDENCE` and `FRESH_EXECUTION` must not exist, must have existing parent
directories and must be separate. The reservation stays outside both outputs.
Execution creates `FRESH_RESERVATION.json.consumed.json` before rechecking
sources/inputs or calling the guard. No failed or successful reservation can be
retried. A changed input or direct source is a retained failure. Failed worker
outputs, logs, guard telemetry and receipts remain in place. There is no
automatic retry, output deletion or failure cleanup.

The exact `execution_guard.run_guarded` ceilings are:

| Keyword | Value |
| --- | ---: |
| `maximum_seconds` | 1800.0 |
| `maximum_rss_bytes` | 1610612736 |
| `maximum_output_bytes` | 268435456 |
| `maximum_execution_bytes` | 33554432 |
| `minimum_free_bytes` | 536870912 |

The guard executes only the pinned interpreter with `-B` and the worker's
frozen input bytes/SHA arguments. Worker output is
`FRESH_EVIDENCE/audit_output/INDEPENDENT_GEOMETRY_AUDIT.json`; runner output is
`FRESH_EVIDENCE/RUNNER_RECEIPT.json`; guard logs are in `FRESH_EXECUTION`.
The watchdog polls RSS/wall/output; it is not an OS allocation sandbox. Worker
numeric reads are individually bounded: JSON64MiB, original CSV16MiB and each
compressed/decompressed bank512MiB. The RSS ceiling can reject an unusually
large bank without trimming any feature or pose.

The reservation pins the worker, wrapper, strict parser, protocol, frozen
padding helper, execution guard and interpreter executable. It records all
declared input pins without reading their payloads. Root owns acceptance of
transitive Python runtime/standard-library dependencies, scanner/runtime
provenance and the actual launch. Direct source pins are checked again after
execution. This source-only stage does not authorize or start a real audit.

## Source verification

```text
python -B geometry/run_independent_tests.py --output geometry/FRESH_SOURCE_EVIDENCE
```

Tests use synthetic in-memory compressed banks and CSVs, literal expected
geometry and a mocked guard. Every source test run has fresh source snapshots,
complete direct source pins and retained stdout/stderr/receipt. Real bank reads,
actual guard launches, image reads/decodes and native/matcher calls are zero.
Source tests and expected-failure mutation evidence do not establish real-bank
geometry correctness; that requires the separately authorized guarded audit.
