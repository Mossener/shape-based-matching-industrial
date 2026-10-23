# Static candidate compatibility review V1

Date: 2026-10-23. Scope: `candidate_compatibility.py` and
`test_candidate_compatibility.py`, against the module docstring and sections
3–5 of `docs/superpowers/plans/2026-10-23-ordered-contour-verifier-contract.md`.
The relevant `edge_chains.py` factory and `weighted_ordered_match.py` interfaces
were also read to check their composition. **No material finding was found
within the stated factory-evidence API contract.**

This is a static review of a mathematical prototype on supplied tiny legal
label grids. It does not certify source-image labels, C0/bank connections,
native implementation, image accuracy, or runtime performance. The independent
candidate oracle was pending at review time and is not covered by this report.

## Source and evidence binding

| Current file | Bytes | SHA-256 |
| --- | ---: | --- |
| `candidate_compatibility.py` | 12,559 | `96b01bb5ecf74640f1c4b2bd52604e2afb4b9f64088dcbabe5875490a2611f85` |
| `test_candidate_compatibility.py` | 21,716 | `a4c17d9b3ee76d5ed1b82edb9a21d3deb76f987472856e9ba6a0bfeafc565625` |
| `run_synthetic_checks_v2.py` | 5,130 | `64ef98e9083e0f410cbc5cf657d3c8dd01bf923c7da2512204fe784f357c6f3b` |

The current candidate implementation and test hashes were independently read
and agree with the GREEN receipt's source pins. The actual GREEN implementation
and test snapshots have those same hashes; the actual RED test snapshot also has
the same test hash. Thus the recorded RED/GREEN comparison uses an unchanged
test suite. The old implementation remains in `candidate_red_v1/source` with a
different recorded pin; no failed reservation was overwritten by this review.

The small RED/GREEN receipts, invocations, guard receipts, and saved stderr tails
were inspected. The invocation pins record `edge_chains.py` at
`5f7e9890a57014653363cd73d4af304ee2f228f55e7f0c12777a50a3e62b8f3d` and
`weighted_ordered_match.py` at
`190204b69ea3646b836ac216bc4254c2f2c7c7f11a4517b434659ddd1ea18a64`.
Those dependency hashes are quoted from the receipts, rather than claimed as a
new independent hash audit in this review.

## Contract checks

| Area | Static result and relevant tests |
| --- | --- |
| Coordinate stages and int64 | `_pair` validates builtin integers in signed-int64 range and rejects bool/float. `_support` first completes checked `p_canvas - tl`, then checked `match + relative`, then checked `q_padded - (left, top)`, before bounds checks. Python's unbounded intermediate arithmetic is followed immediately by the relevant range check, so later cancellation cannot excuse an overflowing stage. Tests cover both axes, int64 boundaries, cancellation after the first stage, addition overflow, and original-coordinate subtraction even for an outside padded center. |
| Canvas and padding semantics | Samples use their factory canvas `(x,y)` directly. There is no rotation, scale, crop-origin addition, or second padding operation. Padding is left/top/right/bottom, nonnegative builtin integers; opposite-side sums are checked int64 and must leave strictly positive original dimensions. Nonzero origins, negative relative coordinates, asymmetric padding, odd scene width, and padding-area support have explicit examples. Original bounds affect diagnostics only. |
| Outside centers | The radius scan is inside `if padded_in_bounds`. An outside center cannot obtain support from a nearby valid border pixel. Its weight remains in the full template denominator. Four border directions and sorted outside-ID diagnostics are tested. No early bounds return bypasses coordinate overflow checks. |
| Labels and radius | `prepare_scene` delegates legal-label validation and snapshotting to `edge.thin_labels`, then extracts chains from the surviving grid. Compatibility scans exactly the clipped Chebyshev-radius-two neighborhood of an in-bounds center. It excludes 255 and applies `min(abs(a-b), 8-abs(a-b)) <= 1` to legal unsigned8 labels. Tests distinguish radius two from three, wraparound 0/7, incompatible labels, and eligible pixels removed by thinning. |
| Full scene topology and memberships | Every pixel of every extracted scene chain contributes its `(chain_id, chain_index)` membership. Membership rows are sorted by physical pixel ID and members by chain ID. Isolated pixels, shared junctions, unsampled scene vertices, and an empty scene are represented. When constructing a core scene chain, the adapter passes its complete original `pixel_ids` and closed flag; compatible edges do not shorten or re-sort its topology. Only chains with at least one compatibility edge for this template chain are passed. |
| Owned sample order and zero chains | Template samples arrive in physical-ID order for diagnostics. Before each core call they are regrouped by the original owner and sorted by original `chain_index`, preserving the owner's open/cyclic order despite removed unowned samples. The closed flag comes from the original full template chain. Every original chain gets a core result, including a chain with no owned samples and zero contribution. The closed-diamond spy test detects confusing physical ID order with chain order; a separate fixture verifies the full zero result. |
| A physical support and witness | Neighborhood positions are visited once in row-major physical-ID order. A adds a sample's exact weight once when that physical compatibility set is nonempty, regardless of how many scene chains contain a supporting junction. Its witness is the first, hence smallest, compatible physical pixel. Tests cover disconnected chains, the shared-junction duplicate hazard, and the smallest-pixel witness. |
| B chain choice and reuse | A separate `core.solve` call is made for each template chain; a solve selects at most one full scene chain. No path is assembled across disconnected chains or branches. Unique sample/physical pixel IDs and strict ordering are delegated to the validated core. Different template chains do not reserve pixels against each other, as required. The reuse statistic collects distinct selected template-chain IDs per physical pixel, so multiple scene memberships do not themselves report cross-template reuse. The suite covers single-chain pixel reuse rejection, disconnected support, order conflict, and allowed reuse by different template chains. |
| Exact scores and threshold | All weights, sums, bounds, and threshold arithmetic remain Python integers. D is the original factory denominator. The adapter checks `0 <= B <= A <= D` and checks that per-chain independent numerators sum to A. Both acceptance flags call the same exact inclusive `20*N >= 13*D` helper. Tests cover 13/20 versus 12/20, scaled boundaries, a 220-bit scale, invalid score domains, and denominator retention for unsupported samples. |
| Stable immutable output | Factory samples and original template chains already have canonical physical-ID and chain-ID order. The adapter preserves those orders, explicitly sorts selected scene IDs and reused pixel IDs, and returns frozen dataclasses containing tuples. Nested scene membership and candidate-result immutability, list-input snapshotting, and empty-scene evidence have tests. |

The composition is sufficient to avoid the two relevant shared-junction errors:
the physical support set cannot multiply A, while B receives each membership on
its own complete scene chain and may choose only one such chain for a given
template chain. Ownership similarly ensures a shared template scoring point is
counted once before the adapter projects samples back into chain order.

## Factory-evidence boundary

The public scoring contract requires unmodified results of
`edge.prepare_template` and `prepare_scene`. Container type checks deliberately
do not prove that a caller has not forged or replaced dataclass fields. Treating
the scorer as a validator for arbitrary hand-built `TemplateEvidence` or
`SceneEvidence` would be a broader contract and was not used as a review
criterion. No externally reachable correctness hole was found for ordinary
legal supplied grids and pose/padding inputs within the documented factory
contract. Empty scenes are legal; a whole template without owned samples fails
at the template factory.

Section 3's source/decode/crop/warp/matrix-bit/bank identity and noncontinuous
native ROI requirements are intentionally outside these supplied-grid APIs.
The coordinate examples establish the arithmetic connection only after a caller
has supplied the correct already-warped canvas and own origin. They cannot
establish that those inputs originated from the required real C0 stage.

## Retained execution evidence and limits

| Reservation | Existing saved result | Observed guard data |
| --- | --- | --- |
| `candidate_red_v1` | 33 unittest methods, 110 assertion failures, no errors item in the saved `FAILED (failures=110)` summary; exit 1. `expected_phase_observed=true` means the expected RED was observed. | wall 0.828 s; peak working set 26,800,128 bytes; 16 samples; reason `process_exit_nonzero`. |
| `candidate_green_v1` | 33 unittest methods, saved tail `OK`; zero assertion failures; exit 0; guard passed. | wall 0.938 s; peak working set 26,685,440 bytes; 18 samples; reason null. |

Both invocations use the snapshot as child cwd and run
`python -B -m unittest -v test_candidate_compatibility` with configured limits
of 60 seconds, 512 MiB RSS, and 64 MiB output. The coordinator checks source pins
before/after execution and equality of executed snapshots with current suite
sources. GREEN requires guard pass and `OK`; RED requires a nonresource exit 1
and a failure-only unittest summary. The reviewed saved results satisfy those
checks. No new test execution was performed for this static review.

The invocation explicitly describes approximately 50 ms observed process peak
working-set and directory-size monitoring, rather than OS allocation isolation.
These tiny observed values are not native-speed measurements or a stronger
resource-enforcement claim. `native_output_bytes=0` does not mean the reservation
created no logs or source snapshots. The passing 33 methods are focused examples,
not an independent reconstruction or exhaustive proof of all candidate graphs.

Only this report was written. No implementation/test/old evidence was modified,
and no Git command, Python/test/native execution, image decode, real image/bank
read, or production V11/V31/V32 change was made. Further acceptance still needs
the independent candidate oracle and the separate provenance, full-data,
NMS/GT, quality, and performance gates in the contract.
