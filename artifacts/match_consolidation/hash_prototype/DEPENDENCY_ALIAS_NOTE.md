# Native GCC dependency aliases

The first synthetic parser rejected duplicate resolved paths. A separate real
MinGW discovery in the silhouette experiment demonstrated valid lexical aliases
for `cvdef.h`, `mipp.h` and `math/sse_mathfun.h`:402 lexical occurrences resolved
to399 distinct files. The reviewed source artifact was
`artifacts/silhouette_template_experiment/build_adapter_v1/core_before.d`, with
reported SHA256 `967141ba5a94e283bbcd3862fc670614578786ac0d00ddce372e6e193523d014`.
That artifact was statically read, not copied into this experiment or executed.

The new synthetic fixture independently constructs three lexical aliases for
one resolved header and requires all three ordered occurrences to survive,
including repeated metadata pins. The parser therefore does not deduplicate.
It still requires actual-MD and pre-M occurrence lists to agree completely.

Fresh synthetic evidence is `run_20261022_dependency_alias_green` (eight tests).
Fresh native evidence in this experiment is `build_20261022_capture_v1`, whose
capture/ref build manifests bind each original pre-M and actual-MD file's SHA,
all ordered dependency pins, object files and executable. These real artifacts
provide this experiment's dependency evidence; the external observation explains
why the synthetic duplicate-rejection assumption changed.

Header occurrences and assertion counts are neither image counts nor speed
measurements. The old synthetic GREEN snapshots remain immutable with their
original limitation.
