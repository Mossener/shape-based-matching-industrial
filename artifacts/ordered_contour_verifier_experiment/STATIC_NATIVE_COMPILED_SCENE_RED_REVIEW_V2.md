# Static compiled-scene RED preparation review V2

No blocking defect was found in the RED-only source preparation. This review
does not establish compilation or runtime acceptance: no compiler, script,
test, native process or real payload was run/opened by this reviewer.

Reviewed source hashes:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `native_candidate_compiled_scene_v2.hpp` | 3,014 | `bfae22f63864c9aadf390a500fad76db219af81ea0076c4ddaa167998fc39cfd` |
| `native_candidate_compiled_scene_v2_test.cpp` | 21,014 | `95f1b5f64603f1d3cfad098779b14e56c2d50fc4c2c55736b3df847fe2addcc2` |
| `run_native_compiled_scene_checks_v2.py` | 8,429 | `a2a19c6fe4c3066eab35925d91c7ced80e78c81e076bfa030e3182dda50127e4` |

There are 28 named test bodies. Empty factory storage is a valid handle with
safe empty evidence/work; the score stub returns a complete default record.
Tests guard indexed chain access, use safe empty iteration and short-circuit
comparisons, and report expected missing rejection as ordinary assertion
failures. No obvious C++17 declaration/include or unused-parameter problem was
seen under the proposed `-Wall -Wextra -Werror` flags. Actual compiler success,
normal RED exit 1 and zero errors still require root execution.

The regression comparator covers every current `CandidateScore` field, every
`SampleSupport` field, complete `MatchResult` fields including all seven work
counters and selected-case fields, and complete `SceneEvidence` including
eligible/surviving grids, deletion rounds, chain flags/order and memberships.
The final test enumerates 512 occupancies by two label profiles by three
templates by two transforms: 6,144 v1/v2 comparisons, with six scores per
prepared scene. This is complete regression parity over that domain, not a
new independent algorithmic oracle. Literal fixtures add index counts,
topology, ownership, coordinate overflow, exact large integers and witnesses.

The proposed private `shared_ptr<const SceneStorage>` gives immutable owned
evidence lifetime across copies and moves; lookup values are offsets rather
than dangling raw pointers. Default shared-pointer moves empty the source.
The implementation must check storage before scoring moved-from handles and
construct both complete indexes once in the factory. A stable counter alone
cannot prove absence of hidden scans/rebuilds: final implementation inspection
must confirm no scene-wide map construction or v1 score wrapper per candidate.
The planned paired benchmark remains separate from correctness acceptance.

The coordinator freezes v1 sources, archives the v2 and v1 compilation inputs,
records GCC dependencies and rechecks source/executable/import pins. Inherited
limits still apply: committed memory for the compiler Job differs from observed
foreground working set; metadata/tool/static import queries are outside those
child watchdogs; ambient/runtime and dynamic/OS imports are not fully attested.
No measured speed ratio, real pixel quality or production change is proven.
