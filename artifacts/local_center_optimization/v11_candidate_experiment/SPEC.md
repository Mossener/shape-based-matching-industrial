# V11 final-level center cache experiment

All experimental files live below this directory. Production files, public
evaluation snapshots and the older V10 failed experiment remain unchanged.
The baseline is exact Git bytes from V11 commit
`b25df46f6ddf9c24fb43f5836f1414dc38c8caed`: seven matcher files and all sixteen
vendored MIPP files. Candidate source starts from those same seven files and
compiles against the frozen MIPP tree.

The only intended matcher change is a sixteen-entry cache of complete
`detail::LocalMaximum` values in worker-exclusive `SearchScratch`. Reset the
cache at each template/level boundary. Its key is the signed C++ integer
`(x/T,y/T)` computed after the existing clamp. Enable lookup/insertion only
when `reuse_local_centers && l == 0 && candidates.size() > 1`. The new option
is independent and defaults false in this experiment; runs set it explicitly.
On a miss execute the unchanged selected fused/integer/float/byte/word path.
When full, retain the original sixteen entries and compute every unstored
miss completely. Do not remove, reorder or truncate candidates. Preserve raw,
float score bits, row and column without reconstructing any field.

Output equivalence means equal vector length and equality at every index of
class string bytes, x, y, template ID and float32 score bits. The V11 grouping
key is class/x/y/score equality, represented by the minimum template ID, then
ordered by score descending, template ID, class, y and x. Semantic sets or
V4/V10 canonicalization cannot substitute for the frozen V11 ordered result.
No matcher search, threshold, window, template, feature or consolidation
behavior may change.

Literal tests must first run against a no-op cache stub and fail because a
stored result cannot be retrieved. Compiler/dependency errors are not RED.
Keep that source, binary hash, output and exit code before implementing the
candidate. Exercise hits/misses without output mutation, zero and signed-zero
scores, signed/ordered keys, exact first-winner fields, reset, separate cache
instances, sixteen stored entries and complete ordered fallback after overflow.

Matcher regression includes all seven previous computational flags, both cache
settings, repeated frames, size/BGR/Detector changes, empty/full/partial masks,
empty candidates, thread passes 1/4/2/4, reusable/transient search scratch,
workspace move/reuse, default and legacy overloads, and concurrent callers
with separate workspaces. Use existing LED/case1 and development-only tiny
T-LESS data. Invalid template geometry must not be introduced merely to
exercise a branch. Signed clamp keys can be checked at the literal cache
boundary without making an invalid physical matcher read.

No compilation, matching or benchmark starts without the coordinated exclusive
CPU window. Performance claims require an uninstrumented interleaved off/on
measurement, complete correctness checks outside internal timers, recorded
compiler/input/source/executable hashes, cold/warm/measured phases and all
regressions retained. Existing timing fields are allowed; new cache counters
are excluded from measured binaries. Counted diagnostic builds, if needed,
must be separately identified and excluded from speed evidence.
