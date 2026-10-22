# Independent review of full API v2

Reviewer: `/root/remote_review`, 2026-10-22. This directory is separate from
the frozen 85-source experiment and the frozen V25 quality classifier.

No blocking issue was found in the inspected source pipeline. Independent
numeric review of `correctness_v2` passed. This review does not authorize
production adoption or establish an accuracy improvement or a speed result.

## Exact evidence

| Item | SHA-256 |
| --- | --- |
| Full API v1 manifest | `e44bc645b73087c280992a87a7e7f25056346a7818daa177888410a77eb2bb3e` |
| Full API v2 manifest | `a97e54bd4159a247a8d5f08b4189f246b39da5ae687ce7552365491dcbd10595` |
| Independent review result | `7dca9bbcdec0e83b2f8186ca2c0f1cb85752d72fe39ea29d6d8eb3d57abb110a` |

`review_correctness.py` uses only Python's standard library. It does not
import `correctness_contract`, `output_contract`, the runner, or a native
package. Its exact source pin is recorded in
`review_correctness_20261022_v1.json`. The single review execution passed in
approximately 5.7 seconds; that duration is review overhead, not matching
performance.

The independent review rehashed all 85 source files and six prior evidence
files, compared v1/v2 member order and declarations, and rehashed all 2,729
correctness artifact pins. It verified exact directory membership including
all 2,722 `HMOUT001` output archives, totaling 6,846,226 archive bytes.

It reconstructed the complete 2,722-call and 1,602-pair schedules from the
native harness design, checked raw CSV against enriched JSON, decoded every
ordered record and finite score bit pattern, repeated all 1,602 complete
comparisons, and checked 25 historical V21 reference bindings. It separately
checked baseline output stability across thread counts and routes, full/zero
masks, empty-candidate controls, nonempty positive-zero fallback outputs,
renamed two-class banks and class filters, and all 6,120 magnetic-part local
refinement preflight rows. It bound the accepted build and replay receipt
identities to the same manifest and build.

Observed call counts were 1,376 baseline and 1,346 candidate calls. Their
stage counts were core 1,024; flags 1,562; lifetime 106; class filters 16; and
magnetic parts 14. These are API regression calls, not object detection recall
measurements.

## Source inspection

V2 changes only `run_full_api.py` and `tests/test_runner_contract.py` relative
to v1. The runner adds three lines that permit precisely the current Python
executable in prior evidence pins. It rejects a different Python identity
before reading prior file pins. The new tests exercise the valid exact
executable, an unapproved neighboring file, and a forged Python role pointing
to an image. Source membership and prerequisite declarations are unchanged.

`generate_sources.py` and runner checks bind the baseline to exact V11 commit
`b25df46f6ddf9c24fb43f5836f1414dc38c8caed`. They require every baseline core
and MIPP copy to match its frozen origin. The candidate changes exactly one
include seam and one consolidation call seam and pins the actual-Match hash
helper. No other core or MIPP change is admitted by this source manifest.

Build, numeric replay, correctness and benchmark are separate fresh phases.
The CPU grant precedes output creation, and dataset stages additionally
require their dataset grant. Failed outputs remain in their original fresh
directories. A successor requires an accepted, unchanged, same-manifest
predecessor and an identical build receipt. The prior-pin allowlist is fully
scoped before any prior pin is rehashed. Build discovers and pins dependency
lists before compilation and compares them with the actual ordered compiler
dependency lists. It recursively inspects PE import declarations and pins
explicit copied runtimes. This is local byte provenance, with the documented
limits on compiler helpers and actual OS loader identities.

The baseline and candidate use the same wrapper methods in private core
namespaces. Their API wall clocks enclose the actual `Detector::match` call
and returned native vector construction. Neutral record copying, archive
serialization, and destruction of the returned U-vector are outside both
clocks. The original N-vector destruction inside the helper remains inside
the call. The workspace move routes invoke real core moves and reuse the
moved-from core objects, rather than transferring only wrapper pointers.

Correctness covers all 128 flag combinations on six prescribed inputs, plus
the broader repeated core matrix, masks, moves, default overloads,
concurrency, class filters, and seven private magnetic-part fixtures. This
does not mean every possible flag/input/state combination was tested.

The timing harness makes 950 actual API calls over common25: one cold, two
warm and sixteen formal rounds per variant/fixture. Its formal positions are
balanced 8/8. Both variant results are buffered before serializing a round.
The first baseline output from a fresh fixture workspace supplies its cold
oracle without an extra matcher call. “Cold” is the first call with that
fresh workspace, not a claim of a freshly started process or cleared CPU/OS
caches. Only the sixteen formal rounds enter reported speed ratios.

`audit_timing` rechecks complete outputs against both cold and same-round
baselines. The runner then independently requires every cold baseline to
equal its pinned historical V21 reference. Thus the whole timing pipeline
does not rely solely on agreement between two newly produced variants.
The fixed auditor uses all sixteen positive finite clock values, retains
regressions, and reports candidate/baseline paired medians and equal-fixture
aggregate summaries without selecting another run from its ratios.

## Limits and remaining evidence

This reviewer executed no compiler, matcher, target auditor, or target unit
test suite. It opened no image, SMD, template bank, training image, new
heldout scene, or private source data. Dataset input pins were deliberately
not independently rehashed. Build/runtime/executable/header input pins were
not independently rehashed in this review; their accepted receipt identities
were checked. These limits are also recorded in the machine-readable result.

The complete benchmark receipt and 950 output archives remain a separate
review step after root authorizes their use. No matching latency figure is
inferred from source inspection or correctness runtime. All equality results
support preservation of the tested V11 behavior; the separate quality
investigation must support any future claim about accuracy.

## Independent benchmark review

After the benchmark stage was accepted, `review_benchmark.py` independently
rehashed its receipt and 954 artifact pins, decoded all 950 output archives
(4,552,210 archive bytes), reconstructed the fixed 950-call schedule and
1,900 cold/same-round output equalities, and verified 8/8 formal positions for
both variants on every common25 fixture. It also checked every cold baseline
against the 25 pinned historical references. The review result is
`review_benchmark_20261022_v1.json` (SHA
`3c8425c981ca0fe955fde644d3c8f2bf65e24a34496eff8f801561cb4cb0e737`), and the
benchmark receipt SHA is
`da6810afcc7280f141d3e88b970f06ef75830b456d8faa974c31d43fc1285125`.

Across all 400 formal pairs for each clock, the independently recomputed
candidate/baseline ratios were: API wall median `1.00356622`, geometric mean
`1.00504555`; internal search median `1.00594941`, geometric mean
`1.00466700`; internal total median `1.00356636`, geometric mean `1.00505002`.
The equal-fixture median of per-fixture paired medians was API wall
`1.00623184`, internal search `1.00127096`, and internal total `1.00622800`.
Ratios below one are faster, so these data show no aggregate speedup for the
candidate on this run. Regression fixtures were retained: 13/25 for API wall
and internal total, and 13/25 for internal search. These timing summaries are
descriptive; they do not justify selecting a favorable rerun.
