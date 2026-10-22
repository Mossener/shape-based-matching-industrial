# Fixed whole-API runner

`run_full_api.py` never chains native stages automatically. Root supplies
`--cpu-slot-granted` and the exact reviewed `--source-manifest-sha256` for each
fresh run. Correctness and timing additionally require
`--dataset-stage-granted` before output creation or input hashing. No command
deletes or overwrites prior evidence. A failed build/run remains preserved;
source changes require a new reviewed manifest and a separately named fresh
run. A timed ratio cannot trigger another run or select a different candidate.

The initial source freeze is `FULL_API_SOURCE_MANIFEST.json`. If a failed
stage requires a source correction, keep that manifest and every failure log;
create `FULL_API_SOURCE_MANIFEST_v2.json` with
`freeze_manifest.py --name FULL_API_SOURCE_MANIFEST_v2.json`. Review its new SHA
and pass both `--source-manifest <absolute-new-path>` and
`--source-manifest-sha256 <new-SHA>` to a fresh build. Each later stage binds
that exact path/SHA and build, so an accepted old-source stage cannot authorize
new-source execution. Manifest creation always uses exclusive create; it never
replaces the first file or a previous numbered version.

| Phase | Native work | Full matcher calls | Image decodes |
| --- | --- | ---: | ---: |
| build | 7 TU compilations, 5 links, 2 synthetic contracts | 0 | 0 |
| replay | 25 captured numeric traces, 50 actual-Match helper calls, 50 full output archives | 0 | 0 |
| correctness | fixed complete matrix, 2,722 archives / 1,602 comparisons | 2,722 | 32 |
| benchmark | 25 fixtures × 2 variants × (1 cold + 2 warm + 16 formal), 950 archives | 950 | 25 |

Build runs `-M` before each TU compilation, scopes the complete discovered list
before reading those headers, pins it and requires ordered equality with the
actual `-MD` list. Repository dependencies may only be exact copied snapshot
files; external headers may only be under the fixed compiler/OpenCV trees.
All prepared source bytes, root origin evidence, original frozen 23-file tree,
compiler/objdump/Python, explicit OpenCV import library, runtimes, objects and
executables are pinned and rechecked. Two private core TUs are linked into
each actual-API executable; fixture-bank building lives in the existing exact
core TU. Replay includes actual frozen Match headers and the exact helper but
does not link a Detector/core.cpp. The synthetic fixture executable links
OpenCV only, with no core object, image decode or Matcher call.

The compile baseline is C++14, O3, SSSE3/SSE4.1 and the existing warnings. Only
the four API/core TUs compile/link with OpenMP. All five executables get an
explicit recursive PE import-file inspection. Permitted compiler DLLs and
`libopencv_world4120.dll` are copied beside the executables and pinned; system
DLL identities are names only. Compiler include/library override variables are
removed by name and not printed by value. This is local byte provenance, not
an attestation of every compiler helper/default linker input, every OS read,
or which DLL identities Windows loaded. After interrupted/timed-out work,
root checks for remaining native processes before granting another CPU slot.

No dataset byte is opened by build or source freezing. Fixture catalogs are
fully validated against the exact 29 common and 16 private allowlisted paths,
roles, sizes and canonical SHA values before any selected input byte is read.
Correctness selects both groups; timing uses only common fixture construction.
Revalidating prerequisite correctness evidence may also rehash its private
input pins outside clocks. Private images/SMD and previews stay local. The
runner counts native declared decode routes, not every OS/file-open/read
operation. It makes no per-open count claim for dataset stages.

Each later phase requires accepted evidence from the same source manifest and
build. The runner scopes and rechecks prior input/artifact pins and retains
the executable/runtime bytes before and after execution. Replay is required
before correctness, which is required before timing. The existing V21 numeric
capture/reference identities are frozen in `HISTORICAL_TRACE_PINS.json`; both
manifest/protocol bytes and actual numeric archive sizes/hashes are rechecked
when consumed. Their independent parser rejects nonfinite scores, malformed
counts/lengths, trailing bytes and a nonempty reference input vector.

Native CSV values are parsed with strict fields, canonical integer forms and
0/1 booleans. The runner reads only `outputs/call_NNNNNN.bin`, binds full byte
length and SHA, and writes enriched complete `calls.json` outside clocks. The
independent correctness module reconstructs all 2,722 routes and 1,602 pairs,
repeats every ordered-field/score-bit comparison and verifies legacy clocks,
workspace move/concurrent routes, masks, actual zero fallback and all 25
historical reference truth gates. The runner also reconstructs every one of
the 6,120 magnet preflight intervals. Concurrent correctness call IDs describe
deterministic archive order (worker 0 then worker 1), not wall execution order.

Timing uses CV1/OMP4, dynamic FALSE, max-active-levels 1 and PASSIVE wait with
normal process settings. It verifies the complete 8/8 position schedule before
any API call. Both cold results are buffered before the actual baseline cold
result becomes the oracle; there is no extra oracle call. Every output equals
both that oracle and its same-round baseline. Raw archives are mandatory for
all 950 calls; no native comparison boolean or result count can substitute.
The pure auditor repeats all equalities, exact stage/position counts, 16
paired ratios per fixture, arithmetic medians, nearest-rank descriptive
quantiles and group summaries, retaining every regression. All clocks used in
ratios must be finite and positive; a zero cannot be silently discarded or
presented as a speedup.

Every subprocess has a fixed timeout: 600 seconds for compiler/link/import or
synthetic/replay commands, 7,200 seconds for each full correctness/timing
process. The root's shell session can yield for progress while it runs. There
is no automatic retry. Results are local experiment evidence only; complete
independent evidence review still precedes publication or a production
integration decision. Exact-output consolidation does not improve accuracy.
