# Deterministic match consolidation (V11)

The first public development run exposed an existing output bug. The matcher
sorted by score and template ID, then removed adjacent records using equality
on class/x/y/score. Equal positions need not become adjacent in that ordering.
At four OpenMP threads, even repeating the same frozen V10 implementation on
scene 5/image 70 changed the raw count from 75,044 to 74,668. One-thread runs
were stable at 74,934. The semantic set was unchanged, but template identity,
multiplicity and order were unreliable. Template identity can affect an
adapter's predicted silhouette box.

`line2Dup_matches.hpp` first groups the existing equality key and retains its
smallest template ID, then orders results by score descending, template ID,
class, y and x. This intentionally corrects the raw-output contract; it does
not preserve faulty duplicate multiplicities. It does not change scores,
coordinates, candidate search or template generation. Scores produced by
matching are finite; arbitrary injected NaNs are outside the checked contract.

## Independent verification

- A literal test failed with the old sort/unique sequence, then passed with
  the helper. It checks 300 shuffled orders, minimum IDs, exact unequal scores,
  separate classes/coordinates, empty/singleton input and idempotence.
- Local SSE stress covers every legal feature count 1..8,191 and 1,024 random
  input streams across four recorded seeds. A scalar oracle checks 262,144
  patch positions, exact score bits and first-winner coordinates.
- Twenty-five image cases comprise the eight existing LED frames, case1 and
  all 16 tiny T-LESS **development** frames. Across 475 calls, all 400 current
  results equal an independent map-reduction oracle in complete ordered form.
  The other 75 frozen V10/V4 calls have equal semantic sets and equal canonical
  results. Current thread passes are 1/4/2/4, fallback/fused, repeated twice.
- Neither tiny heldout nor expanded scene/object holdouts were matched for
  this fix. The image matrix is single-class per call; literal tests cover
  multiple classes. It does not establish broad detection accuracy.

See `unit_results.json`, `full_verification.csv`, its provenance manifest,
`verification_audit.json` and `INDEPENDENT_REVIEW.md`. The frozen V10 snapshot
and its repeated-call reproduction are in `../local_center_optimization/`;
the directory name predates this fix and does not mean a center cache is active.

## Actual cost, including regressions

One coordinated CV1/OMP4 run uses cold1/warm2/measured7. The uninstrumented
current and frozen V10 calls alternate; each uses the V10 fused local kernel.
A separate diagnostic captures an identical pre-consolidation vector, copies
it outside timing, and rotates old/new consolidation order. Its instrumented
API includes extra work and is deliberately excluded from full-call results.

| Cases | V10 API ms | V11 API ms | V10 search ms | V11 search ms |
| --- | ---: | ---: | ---: | ---: |
| Eight LED images | 51.435 | 52.272 | 38.871 | 38.359 |
| case1 | 20.607 | 25.479 | 2.977 | 3.191 |
| Four T-LESS development images | 255.444 | 309.056 | 245.235 | 298.863 |

Rows are equal-weight means of per-image medians; absolute timing varies across
runs and cannot be compared with V10's earlier hardware-state samples as a
change effect. The T-LESS timing subset is two positive and two negative frames,
not all 800 expanded frames. Complete timings retain every measured sample.

For the same candidate vectors, LED consolidation adds a paired median of
0.0041–0.0107 ms per image; case1 adds 0.0025 ms. The four T-LESS vectors have
230,077–486,045 input records and add 20.7865–56.7213 ms. Complete canonical
deduplication reduces their output to 35,109–82,689 records. This is a
correctness fix with a substantial large-vector cost, not a speedup claim.
Further postprocessing optimization must retain the independently checked
contract and be measured separately.

`timing_v11_total.csv`, `timing_v11_stage.csv`, their summaries and
`timing_audit.json` record 260 complete calls and 130 diagnostic stage calls;
all complete calls pass canonical equality. Environment, inputs, source hashes,
executable hashes and before/after stability guards are retained. No local
center caching is in production or in these measurements.

## Reproduction

From the repository root in the recorded Windows/GCC/OpenCV environment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/match_consolidation/run_unit_tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/match_consolidation/run_verify.ps1 -Run -Output artifacts/match_consolidation/recheck.csv
py -3.10 artifacts/match_consolidation/audit.py
```

The image runner requires the frozen tiny dataset and template bank; its paths
and exact hashes are in the provenance files. Run performance independently
of compilation, compression and other matching jobs. See `run_timing.ps1`
for the recorded method and output arguments; keep the original evidence.
