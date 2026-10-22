# Preserved failures and incomplete checks

- `tests_red_20261022_a`: expected TDD RED. The first fixed-factor test failed
  because `PROTOCOL.json` did not yet exist. Test source, stdout, stderr and
  exit code are retained. This was a standard-library test, with zero native
  calls and dataset decodes.
- Root exploratory unfinished-source run: root ran the current 14 source
  tests before `run_training.py` had been created. Thirteen passed and one
  errored on the missing runner source. Root reports that the tool output
  exists in its thread, but no persistent stdout/stderr receipt was captured.
  This is not represented as a frozen RED run or as an algorithm failure.
- An exploratory `py_compile artifacts/rgb_dilated_mask_experiment/*.py`
  command failed because Windows passed the wildcard literally to Python.
  It did not compile or execute native code. Subsequent AST checks enumerate
  actual files. Its output exists only in the tool transcript.
- An exploratory PowerShell `rg` command using brace expansion failed at shell
  parsing. It was rerun with explicit paths; it performed no filesystem edits.
- `run_literal_control_red_v1`: genuine expected native RED. Compilation
  succeeded; the original erosion core compiled with the dilation expectation
  returned 1. Raw native stderr is exactly `FAIL literal morphology acceptance
  differs` after CRLF-to-LF normalization. The original core's `too few
  features, abort` stdout is retained. The independent successor oracle was
  written before this run; the verifier rejects any other reason for failure.
- `tests_all_20261022_a`: 13 pass, one failure. The initial static-suite test
  still asserted that no executable existed anywhere in experiment build
  directories, which was true only before the authorized toy stage. It failed
  after legitimate toy builds. Source/logs are retained. The corrected test
  checks that every runner rejects missing CPU authorization before creating
  output or accessing compiler/build inputs and that the test creates no new
  executable. No algorithm or native source was changed by this correction.
- A first attempt to create the v2 builder through an inline PowerShell/Python
  quoted replacement failed at PowerShell parsing. No file was created by that
  command. It was immediately replaced with a literal PowerShell here-string;
  the successful creation's origin JSON records exact parent/new source pins.
- `tests_acceptance_red_20261022_a`: two expected TDD failures because the
  independent-audit acceptance implementation did not exist. Source and raw
  logs are retained. After implementation, `tests_acceptance_green_20261022_a`
  passed both numeric fixture tests. No real audit or dataset was read.
