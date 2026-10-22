# Isolated prototype correctness, 2026-10-21

Both owning-string-key and immutable-input-index hash candidates pass the
unchanged contract suite against the committed V11 helper and an independent
ordered-map/tuple oracle. Production core and frozen public sources were not
edited. No matcher or dataset image was accessed and no performance benchmark
was run. This is correctness evidence for consolidation, not detection accuracy.

The exact core revision is `b25df46f6ddf9c24fb43f5836f1414dc38c8caed`;
the helper Git blob is `bb885d2719dcb04d4cb8ee865e4cfa6e4d16989e` and its
SHA256 is `80c8d1ee482307a0472a46d7a1e4da868154f2f893fcdc32d53b9be8f35c0344`.
GCC 15.1 used C++14, `-O2 -Wall -Wextra -Werror`.

| Preserved run | Compile | Test | Meaning |
| --- | ---: | ---: | --- |
| `run_20261021_hash_red` | 1 | not run | Initial test-only allocator wrapper triggered GCC mismatched-new-delete; not semantic RED. |
| `run_20261021_hash_red_semantic` | 0 | 1 | Stub failed exact ordered owning output after 3 checks. |
| `run_20261021_trace_red` | 0 | 1 | Stub failed complete trace count after 1 check. |
| `run_20261021_hash_green` | 0 | 0 | 13,671,101 checks passed. |
| `run_20261021_trace_green` | 0 | 0 | 139 checks passed; 106 malformed cases rejected. |

The compile warning was fixed by marking the test allocation wrappers noinline,
without disabling warnings. Semantic RED and first GREEN used identical tests.
Hash GREEN includes 507 ordered-map oracle cases, 402 signed-zero cases,
130 constant-hash collision cases, 400 shuffled duplicate sets and 107
injected allocation failures. Assertion count includes complete-field traversal
of large synthetic vectors up to 486045 records; none is a captured real trace.

Minimum-template-ID selection preserves all five record fields. Nonfinite
scores fail before hashing; both zero signs take the exact whole-input V11
fallback so equal-minimum-ID signed-zero representatives retain V11's bits.
Both exception paths and successful calls preserve the original const input.
Maps are destroyed before sorting a separate output.

Trace tests cover independently constructed little-endian bytes, all record
fields and ordering, extreme integers, float bits, embedded NUL/non-ASCII class
bytes, every truncated prefix, bad headers, count/string bounds, unsigned count
overflow, trailing data and nonfinite scores. `max_total_bytes` limits encoded
bytes, not actual heap usage or RSS.

| Intentional snapshot mutation | Run suffix | Expected rejection |
| --- | --- | --- |
| Select maximum template ID | `mutant_maximum` | Exact output mismatch after 4 checks. |
| Remove both final sorts | `mutant_no_sort` | Exact output mismatch after 126 checks. |
| Remove finite pre-scan rejection | `mutant_no_finite` | Injected hasher was reached after 202909 checks. |
| Disable zero fallback | `mutant_no_zero_fallback` | Missing fallback diagnostic after 148080 checks. |
| Omit x from owning equality | `mutant_omit_x` | Forced-collision mismatch after 195 checks. |
| Accept trace trailing bytes | `mutant_trace_trailing` | Malformed trace accepted after 110 checks. |

All mutation runs use prefix `run_20261021_`, compiled successfully, failed with
test exit 1 and left the original source unchanged. Each run contains full
snapshot source, compiler version/hash, flags, compile/test logs, output hashes
and `validation.json`. A passing runner for RED means the intended test failure
was observed; it does not mean that mutated implementation is correct.

Independent static review is recorded in `INDEPENDENT_REVIEW.md`. Real capture,
manifest audit and replay-only performance remain later phases. No small-N
cutoff, production change or speed claim is selected by these results.
