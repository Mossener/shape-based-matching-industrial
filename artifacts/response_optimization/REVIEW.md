# Independent response optimization review

Reviewed `line2Dup.h`, `line2Dup.cpp`, `line2Dup_spread.hpp` and
`line2Dup_response.hpp` against the immutable implementation in `baseline/`.
The reviewer did not modify the production implementation or run performance benchmarks.

## Findings

No unresolved correctness findings in the reviewed changes.

The timing-disjointness assertion initially used an exact comparison of sums of
independently converted double durations. A repeat run reproduced a one-ULP
rounding failure: inclusive `1.5410999999999999 ms`, sum
`1.5411000000000001 ms`, difference `-2.2204460492503131e-16 ms`.
The test now permits an absolute `1e-9 ms` (one picosecond) rounding tolerance,
well below clock resolution, and reports full-precision values on any failure.
This does not allow a clock-resolvable overlap.
After the adjustment, 30 consecutive full Workspace correctness runs passed;
see `workspace_timing_rounding.log` and `workspace_timing_repeat.log`.

One timing issue was identified and corrected during review: the no-reuse path
originally sampled `total_ms` before releasing its temporary buffers. The current
implementation resets its call-local state after sampling `search_ms` and before
sampling `total_ms`. No subsequent operation accesses the released state. This
includes cleanup in total time while keeping it out of template-search time.
External caller wall time remains the authoritative end-to-end benchmark.

### Grayscale magnitude scratch follow-up

Static review approves replacing `dx.mul(dx) + dy.mul(dy)` with two explicit
`cv::multiply` calls into separate workspace-owned float Mats followed by
`cv::add` into magnitude. This preserves the original two multiplications and
one addition, with default unit scale and unchanged float depth. The scratch
outputs must not alias the derivative inputs or magnitude. Each output is fully
overwritten on every grayscale call, and OpenCV recreates it when dimensions
change; the color path does not consume these buffers. This removes repeated
temporary image allocation without caching computed pixels.

The validation conditions are satisfied. Existing `test_results.json` confirms
all suites pass: spread 3,208 checks, response 127 cases / 1,610,176 compared
bytes, pipeline 1,512 byte-exact intermediate comparisons including float
magnitude after the multiply/add change, enhanced Workspace regression, and
52 allocation-counter frames across four scenarios. On stable warm frames,
grayscale allocation requests fall from 116 calls / 39,109,124 bytes to
27 calls / 516 bytes; color requests fall from 146 calls / 44,471,292 bytes to
57 calls / 1,020 bytes. These count requested bytes, not resident-memory usage
or a claim of zero allocations. Resize transitions and allocator restoration
also pass.

The existing benchmark `led_benchmark/summary_validation.json` records 5,184
calls, all 288 expected measured groups, and zero semantic-set, strict-set or
raw-count differences. `led_benchmark/AUDIT.md` independently confirms all 19
recorded source/input SHA-256 hashes match. This follow-up reviewed those saved
results only; no additional CPU tests or benchmarks were run by this reviewer.

## Correctness evidence

`tests/reference_matcher.cpp` builds the immutable baseline implementation in a
separate translation unit under renamed namespaces. Templates are transferred
through in-memory YAML, rather than retrained separately. Matching results are
compared as sorted tuples including class, coordinates, exact similarity and
template ID. Tests fix OpenCV and OpenMP threads to one for this comparison and
assert that the original implementation produces a positive match.

`tests/workspace_test.cpp` passed compilation and execution. Logs are
`workspace_build.log` and `workspace_green.log`. Coverage includes:

- All-false, spread-only, fusion-only, reuse-only and all-enabled options.
- 45 sequential input/configuration cases, including A/B/A, color/grayscale,
  changing image dimensions, non-contiguous ROI, and zero/full/partial/empty masks.
- Mutating pixels without changing the image data pointer and changing/restoring
  the modality weak threshold.
- Moving workspaces, move assignment, and reuse of a moved-from workspace.
- Changing options on one workspace, sharing it serially across detectors with
  different stride configurations and pyramid depths, then restoring the first.
- Two workers using separate workspaces and the legacy thread-local overload.
- Nonnegative timings, disjoint preprocessing stages, and zero separate
  linearization time on the fused path.

## Implementation assessment and boundaries

Each pyramid level owns distinct downsample destinations. Current source pixels,
mask and modality threshold are consumed on every call. Empty masks clear the
prior downsampled masks; masked quantization explicitly clears its output before
copying. Scratch allocations are resized through OpenCV rather than keyed on
image pointer identity. The fused lookup table is immutable after thread-safe
static initialization; intermediate image storage belongs to the workspace.

The old matching signature remains available; Detector remains copyable.
Workspace copying is prohibited and its pimpl lifecycle is defined out of line.
The old signature's default diagnostic stdout is now disabled, as specified by
the new options; callers requesting timings should use the explicit overload.

The caller must give each concurrent worker an exclusive workspace and must not
concurrently mutate detector templates or modality settings. Serial reuse across
detectors is supported. The thread-local wrapper is not designed for recursive
reentry on the same thread. Inputs must satisfy the supported 8-bit grayscale or
BGR format, mask requirements and per-level stride divisibility.

The existing template matcher has partial ordering of equal-score matches and
OpenMP reduction can change equal-score candidate order. The optimization does
not change this behavior. The independent adapter captures legacy stdout and
must be called serially; concurrency tests exercise only the current matcher.
The integration fixture is intentionally small; broader template banks and
real-image performance are covered by the separate pipeline/benchmark harness.
