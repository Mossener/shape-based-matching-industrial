# Independent candidate oracle: static review V1

Date: 2026-10-23. **No material finding was found within the declared tiny supplied-label domain.** The implementation independently rebuilds candidate evidence and uses a partial-injection oracle for ordered scores and canonical witnesses. The saved GREEN output agrees with its frozen loop counts and source pins.

Scope: `independent_candidate_oracle.py`, `test_independent_candidate_oracle.py`, their composition with `independent_edge_oracle.py` and `independent_tiny_oracle.py`, and the saved `candidate_oracle_green_v1` receipt, invocation, stdout/stderr and guard receipt. The tested implementation's public carriers and assembly were read for the comparison boundary. This review performed static source/log reads and hashing only; it did not rerun tests, execute Python/native code, compile, use Git, read real images/banks/candidates, or change V11/V31/V32 evidence. Only this review document was written during this review.

Paths below are relative to `D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment`. All hashes are SHA-256.

## Source and execution binding

All seven current suite sources were independently hashed. Their sizes and hashes agree with the actual executed `candidate_oracle_green_v1/source/` snapshots, the receipt's `snapshot_pins`, and the invocation's `source_pins`; there were no mismatches.

| Current source | Bytes | SHA-256 |
| --- | ---: | --- |
| `edge_chains.py` | 15,259 | `5f7e9890a57014653363cd73d4af304ee2f228f55e7f0c12777a50a3e62b8f3d` |
| `weighted_ordered_match.py` | 13,015 | `190204b69ea3646b836ac216bc4254c2f2c7c7f11a4517b434659ddd1ea18a64` |
| `candidate_compatibility.py` | 12,559 | `96b01bb5ecf74640f1c4b2bd52604e2afb4b9f64088dcbabe5875490a2611f85` |
| `independent_edge_oracle.py` | 13,628 | `bca66cf17ab0036aecd3c7f6f141e925d50055385cd95d53fa9659299bab5315` |
| `independent_tiny_oracle.py` | 21,472 | `47fd4bb9545d64e72de03d78aa917c479e6909d316eb6a40a01f2db372b16e68` |
| `independent_candidate_oracle.py` | 11,862 | `09600a1c5e6a6b65986cbcf1163d1549c6e32716477d442cafd956d31e96e55f` |
| `test_independent_candidate_oracle.py` | 24,913 | `c44240615caf7e94011efd3c11014a11743e2b40589b7c51ef0035e58199dd4d` |

The following saved evidence and coordinator source were also read and hashed. Invocation/stdout/stderr pins match the enclosing GREEN receipt.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `candidate_oracle_green_v1/receipt.json` | 3,952 | `a0a9c55fa9feb2fde3dd51d17ca84bdcfd369da7221f160607e213c2379ad047` |
| `candidate_oracle_green_v1/invocation.json` | 3,142 | `44e4a974d107249ad5392df7e339da4c69cb21cf2b4430ae5e35671e4dc64078` |
| `candidate_oracle_green_v1/execution/stdout.txt` | 279 | `d5f8452e58b27b466db1c7d8b164b9776fa7b5a4bd1ce7308557f226387d6261` |
| `candidate_oracle_green_v1/execution/stderr.txt` | 7,030 | `243143d7f34681167daac5ae2890783339aa52e1a7061f839664b65d821d87d6` |
| `candidate_oracle_green_v1/execution/guard_receipt.json` | 687 | `80c05b0d94311c4ed19b25a5dfa657b4fa1c8e68233528cc826d14cfab59e1da` |
| `run_candidate_oracle_checks_v3.py` | 5,110 | `6bb3b32da1aad46905c0330f5212115830d4d14645f8f848aa7602adb31a7360` |

The coordinator copies the seven sources into a fresh snapshot directory and uses that directory as child cwd. It checks original-source pins and snapshot equality again after execution. GREEN requires a passing guard, exit zero, a parsed unittest count and a saved stderr ending in `OK`. The reviewed receipt records `sources_unchanged=true`, `executed_snapshots_equal=true`, and `expected_phase_observed=true`. No new execution was performed to reproduce those historical observations. This review does not independently re-attest the Python/runtime dependency closure.

## Independence and mathematical checks

| Area | Static result |
| --- | --- |
| Imports and reference boundary | `independent_candidate_oracle.py` imports standard-library `Counter`, dataclasses and `Fraction`, plus only `independent_edge_oracle` and `independent_tiny_oracle.brute_force`. Neither reference dependency imports the tested candidate, edge or optimized solver modules. The test module imports both sides to compare them; the reference algorithm does not call the tested implementations. |
| Independent topology and weights | `reference_scene` uses the independent edge reference's thinning and chains, then enumerates each surviving pixel's complete chain memberships. `reference_template` independently derives chains, sampling, ownership, 4×4 cells and exact weights from rational cell mass. The edge reference uses degree-two induced components and boundary attachments, cumulative lengths/binary search, and `Fraction`, rather than the tested traversal/LCM helpers. This review checked composition and the relevant dependency code; it does not replace their separate reviews. |
| All-pair compatibility | `_all_pairs_supports` enumerates every surviving physical scene pixel in row-major physical-ID order for each owned template sample. It tests Chebyshev distance ≤2 and `(scene_label-template_label)%8 in (0,1,7)`. This differs from the tested radius-window/membership lookup. Only in-bounds predicted centers can obtain support. Thinned-away and invalid255 pixels do not enter the physical list. The smallest compatible physical ID is the A witness. |
| Coordinate stages | `_bounded` accepts only builtin integers in signed-int64 range; bool/float are rejected. Canvas subtraction, match addition and original-coordinate subtraction are individually bounded before bounds shortcuts. `tl`, match and LTRB have fixed sequence shapes; padding is nonnegative, opposite sides have checked sums, and a nonempty original rectangle must remain. No rotation, crop-origin addition or second padding operation appears. Original bounds remain diagnostics; an outside padded center cannot be rescued and never shrinks the denominator. |
| Problem construction | `_candidate_inputs` orders owned samples by the independent original `chain_index`, preserves every scene chain's complete original physical sequence and closed flag, and omits only scene chains with no incident edge. Every template chain gets a problem, including a zero-owned chain. Shared scene junctions retain membership on each complete chain, without duplicating A's physical support. |
| Ordered objective and ties | Each chain is solved by `independent_tiny_oracle.brute_force`: enumerate unmatched/matched choices as partial injections, reject reused scene pixels, and test original open/circular order without Fenwick or optimized cut helpers. Only after obtaining the optimum does the reference walk declared cases to choose the canonical scene/direction/cuts and reversed-original-edge witness tie. The original-order objective does not depend on those linearizations. |
| Exact aggregation | A is the sum of each physically supported owned sample's integer weight once; B is the sum of per-template-chain optima. The code verifies `0<=B<=A<=D` and that per-chain A numerators sum to candidate A. D stays the independent template's original denominator. Cross-template reuse is counted by distinct `(pixel,template_chain_id)` pairs, so repeated scene memberships alone cannot create a reuse report. |
| Inclusive threshold | `reference_threshold` validates integer `0<=N<=D`, `D>0`, then compares `Fraction(N,D)>=Fraction(13,20)`. It does not call the candidate's cross-product helper or convert to float. Tests include equality/below-boundary and a 220-bit scale with a one-integer deficit. |
| Finite domain | Candidate/problem APIs explicitly reject any scene chain longer than8, even an unused one, and any template chain with more than8 owned scoring samples. They do not truncate chains or skip them. `reference_scene` alone intentionally has no such solver-size limit. These are finite reference APIs, not unrestricted full-image solvers. |

## Compared observables and focused cases

`test_independent_candidate_oracle.py:31` normalizes nested dataclasses by field name and value and sequences recursively, excluding **only the field named `work`**. For the reviewed carriers this excludes the optimized solver's `WorkCounters`; it does not exclude score or witness fields. Dataclass implementation types themselves are intentionally not compared between the independent carriers and the tested carriers.

`assertEquivalent` compares every `CandidateScore` field: D, A/B numerators, both acceptance flags, all per-sample canvas/relative/padded/original coordinates, both bounds flags, full compatible physical-ID tuples and A witnesses, per-chain results, outside-ID diagnostics, aggregate A witnesses and cross-chain reuse IDs. Every per-chain template ID, numerator, A numerator, total weight, selected scene/direction/cuts and ordered witness participates in the recursive comparison.

It then calls `reference_problems` afresh and invokes `tiny.brute_force` again for each actual chain result, separately comparing the selected case and full witness, checking unique template and scene physical IDs, and reconstructing cross-chain reuse. This second invocation uses the **same independent brute-force algorithm**, rather than a third independent solver. It isolates candidate aggregation and confirms full chain observables; it is not additional algorithmic independence. Work-counter values are outside this comparison.

The 34 named test methods include literal singleton evidence, erased and empty scenes, unsampled scene nodes, shared/returning junction memberships, asymmetric padding and negative relative coordinates, padding-area support, all four outside borders, radius2 versus3, all64 direction-label pairs, invalid255, smallest A witness, within-chain reuse rejection, disconnected-chain separation, cross-template reuse, a closed-template index-order fixture, full scene topology, zero-owned chains, denominator retention, int64 stage/overflow cases, malformed grids/poses/padding/scores, immutable snapshots and explicit reference-size rejection. Some focused tests validate the independent reference against hand literals; those are not all separate comparisons against the tested candidate. The exhaustive loop below does invoke `assertEquivalent` on every counted candidate.

## Exhaustive counts and retained GREEN result

The exhaustive method at test line395 contains nested loops over:

- `range(512)`: every occupancy bitmap of a3×3 scene, including empty/full and every disconnected pattern;
- two fixed direction-label profiles: all zero and `(0,7,2,6,4,1,5,3,0)`;
- three fixed templates: a singleton, a five-node open line and a closed diamond;
- two fixed `(tl,match,LTRB)` transforms, including a nonzero origin and asymmetric padding.

The product is **512×2×3×2=6,144 candidate comparisons**. Each of the three templates has one canonical chain; hence **6,144 separately repeated chain brute-force comparisons** in the exhaustive method. Its maximum owned sample count is asserted to be3. Scene-chain size is checked against the8-point reference limit before each candidate loop; no `skip`, truncation, recovery or selective `continue` is present. The final `comparisons==6144` assertion would also reject a shortened successful run. `skipped_cases=0` is a printed declaration supported by that control flow and the passing total-count assertion, not a separate measured skip counter.

Saved stdout records exactly:

```text
candidate_comparisons=6144
chain_brute_force_comparisons=6144
scene_occupancies=512, direction_profiles=2, templates=3, transforms=2
maximum_owned_template_samples=3
maximum_scene_chain_points=5
skipped_cases=0
```

Saved stderr lists all34 methods as `ok`, followed by `Ran 34 tests in 6.446s` and `OK`; the source has exactly34 `test_` definitions. The receipt records zero assertion failures and guard exit0/passed. The guard's whole-child wall observation is **6.594s**, peak working set **22,269,952 bytes**,126 samples, no stop reason. These two time values have different scopes and are not interchangeable.

The configured limits were60s,512MiB RSS and64MiB output/execution evidence. The invocation describes approximately50ms observed process working-set/directory monitoring, not OS allocation isolation. `native_output_bytes=0` describes the designated payload directory; it does not mean no logs or snapshots were produced. These historical unittest observations establish no native runtime, full-image cost or matcher-speed conclusion.

This is an exhaustive **occupancy** exercise for the listed two label profiles, three small templates and two transforms; it is not all8-valued label grids, all templates, all poses, all8-point graphs or arbitrary image sizes. The explicit limit8 is an API boundary, while the reported exhaustive maxima are3 owned template samples and5 scene-chain pixels. Additional hand cases cover multi-template-chain reuse and zero-owned chains; the6,144 product itself has one chain per template.

The result supports the supplied-label candidate evidence contract in this finite domain. Source-image gradient generation, own-C0 provenance/replay, native implementation, complete development candidate/NMS/GT behavior, quality and performance still require their separate gates. It does not authorize real pixel execution or production promotion.
