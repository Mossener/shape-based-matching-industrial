# Direct16 V2 correctness milestone

The fixed direct16 candidate and frozen V18 linear16 control matched the exact
V11 ordered outputs in all5504 comparisons. The three stages made exactly6609
native matcher API calls, with counters at the actual call sites. All stages
used the same separately compiled V11/linear/direct executable. No combined
`all` rerun or hidden oracle call was added.

| Stage | Exact V11 calls | Linear16 calls | Direct16 calls | Total calls | Ordered comparisons |
|---|---:|---:|---:|---:|---:|
| lifetime |68|38|38|144|76|
| core |512|1024|1024|2560|2304|
| flags |781|1562|1562|3905|3124|
| total |1361|2624|2624|6609|5504|

Comparison includes vector length, class string bytes, x/y, template identity,
float32 score bits and order. The fixed matrix retains32 input routes, both
cache settings, all128 optimization flags, 1/4/2/4 thread passes, masks,
empty/zero winners, changing sizes/Detectors, BGR input, defaults/legacy
overloads, move/reuse and two callers with independently owned workspaces.
The real images remain the same25 LED/case1/tiny development images; no heldout
RGB was opened or matched, and reserved objects25/29 were untouched.

Build evidence is `build/matcher_20261022_003331_222515/build_manifest.json`.
Executable SHA256:
`d53e7996b132d42ff0e07099051a7644affafbd0534e7c27657d9e5393950f17`.
Dependency discovery occurred before compilation; actual `-MD` ordered
occurrences agreed with each pre-scan, preserving repeated lexical aliases.
Source/input/protected/dependency/compiler/runtime/build/receipt/executable
pins stayed unchanged through each stage. These are local byte/dependency
receipts, with the scope limitations recorded in `SOURCE_CHANGES.md`.

Stage results and their full CSV/log pins:

- `correctness_lifetime_20261022_003453_156424/result.json`
- `correctness_core_20261022_003538_097850/result.json`
- `correctness_flags_20261022_005324_876657/result.json`

Parent independently reviewed the complete build pin gate and all three saved
CSV stage routes/counts in
`artifacts/independent_reviews/direct16_correctness_v2/root_review_all_stages_20261022.json`,
without native or image-decode reruns. Separate
benchmark and diagnostic sources are prepared, but neither has run. These
results establish equivalence only for this fixed regression matrix. They
do not establish an accuracy gain, a universal equality guarantee or a speed
gain. The experiment remains explicit off by default; no production adoption
or Git publication action is performed by this worker.
