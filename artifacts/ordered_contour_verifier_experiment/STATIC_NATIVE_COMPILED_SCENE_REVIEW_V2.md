# Static compiled-scene v2 review

Status: static source and completed root receipt review. Actual RED, GREEN
and the paired synthetic benchmark passed their respective phase gates.
No builds, Python/native executions, Git operations, images or real data were
performed by this source author/reviewer.

## Source findings

No blocking defect was found in the reviewed v2 implementation. The factory
owns the complete frozen-v1 scene record and builds two maps from physical
pixel/chain ID to vector offset. Its only mutable shared owner is local during
construction; the exposed handle holds `shared_ptr<const SceneStorage>`.
Copy/move retain valid ownership without storing raw pointers into vectors.
Moved-from accessors and score calls explicitly reject absent storage.

The score body performs no whole-scene membership/chain iteration, constructs
no whole-scene lookup maps and does not call `candidate::score_candidate`.
It reads only incident physical memberships and complete incident chains via
the immutable indexes. Its candidate-local data structures and solver inputs
preserve original template chain order, owned sample order, edge sorting,
zero-owned chains, cycles, full physical scene membership and reuse semantics.
The frozen `detail::support`, checked frame arithmetic, exact threshold and
native solver remain the same code paths as v1.

The complete parity comparator covers all public scene, sample, candidate,
case/witness and seven solver-work fields. It includes a sensitivity check
that changes each work field. Factory counts and literal known cases supplement
6,144 full supplied-label comparisons; these tests are explicitly v1 parity,
not a second independent candidate oracle. Empty-stub RED container access is
guarded and actual RED ended with 8,437 ordinary failures and zero errors.

An independent peer also read the RED scaffolding, GREEN implementation and
latest paired benchmark source, and reported no blocking syntax, ownership,
whole-scene lookup or measurement-region problem. Root owns actual execution.

## Benchmark method review

The measured baseline invokes the exact frozen v1 score function. A generated
counted copy is bounded by a fixed source SHA and unique signature/map-block
anchors. Its two map loops increment counts and time those loops only in the
later untimed comparison phase. Every result is compared against both timed
paths with full solver work, so a counted-copy behavioral change fails.

Preparation, scoring and total timing are reported separately. Cached
preparation includes the new indexes; baseline preparation uses the same v1
factory. Alternating paired order reduces simple order bias. Timed scoring
includes returned evidence retention on both paths. No duration ratio is a
correctness or promotion gate, and a single process working-set peak cannot
be assigned to either path separately.

Membership-row and chain counts correspond to actual index-loop iterations.
Member counts refer to member records covered by indexed rows, obtained from
vector sizes; they are not individual-member traversal/allocation counts.
The workload is an isolated synthetic scene-index case with one small template,
not an end-to-end matcher or original-pixel benchmark. It provides no basis to
extrapolate the complete C0 real-input runtime or quality.

## Completed actual receipt findings

GREEN retained the same tests/runner/decisions bytes and reported 28 tests,
8,557 checks, zero failures/errors and compiler/native exits0. Its compiler
job peak was 355,893,248 bytes; native wall was approximately 0.172s with
observed peak working set 6,959,104 bytes. Actual RED retained 28 tests,
8,556 checks, 8,437 ordinary assertion failures, zero errors and native exit1.

The benchmark completed six alternating pairs x256 candidates and all 1,536
complete results/work comparisons. Each round's observed lookup counts were
256 pairs/512 maps in the untimed v1 copy versus one pair/two maps in v2.
Membership rows were 1,310,720 versus 5,120; member records covered were
1,572,864 versus 6,144; chains indexed were 524,288 versus 2,048. Measured
preparation and total times are separately retained for both timed paths.
The six paired total ratios had median 5.853320790117911, solely for this
artificial 256x256 workload. Untimed index time was not added to measured time.
Whole process wall was 2.125s and observed peak was 11,206,656 bytes; compiler
job peak was 384,303,104 bytes. All remained within their stated guards.

Completed result and benchmark reports list final source/receipt/stdout pins.
The benchmark receipt SHA is
`05365e9dc69596fa0b5841253cfda372b2e0aada13d53b11b746e293b33c353f`;
GREEN receipt SHA is
`7852219d0d55a5a9418e769d008bc6bc6c298cba4f429c20e18d86e70a355c3f`.

Frozen v1 source/test/driver/protocol/fixture/runner/report and all actual run
receipts were left unchanged. New v2 sources and report files are separate.
