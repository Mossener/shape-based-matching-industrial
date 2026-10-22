# Independent static review: capture-hook state and translation units

Reviewed by the magnet-review agent without recompilation or test execution. No blocking state-machine or two-TU issue found in the reviewed sources.

The inline `detail::store()` function's local `thread_local` static is a shared entity for each thread across translation units. The adapter's arm/take and bridge/core wrapper therefore address the same calling-thread state. This relies on the documented arrangement that the wrapper runs on the calling thread outside the template OpenMP region. The two-TU fixture exercises that arrangement; it is not a separate concurrency or scheduler test.

The idle path invokes the original V11 consolidation directly and creates no capture. The armed path stages a complete ordered input copy, calls the original helper, then stages complete output and publishes `ready`. A second consolidation is rejected before modifying either the ready trace or caller matches. `take` is one-shot, `cancel` clears any phase, and failed capture remains unusable until cancellation. Nonfinite input is rejected before original consolidation and before input mutation. String copying retains embedded nulls; the fixtures inspect complete fields and score bits, signed zero, subnormal data, binary class strings and extreme coordinates.

The catch path clears incomplete trace state and marks failure. It does not promise to roll back caller matches if an allocation fails after the original helper has already consolidated them; the capture run must remain failed in that case. This is consistent with preserving failure evidence rather than claiming a successful replacement output. Additional capture allocations and exceptions mean capture execution itself is not timing evidence.

`run_hook_tests.py` freezes both test TUs, support headers and exact Git helper bytes before compilation. It uses a standard-library-only correctness build with `-Werror` and records compile/test exits plus before/after source checks. The saved claimed 44 checks and 2 TU result were read as existing evidence; this reviewer has not independently rerun them. Runtime/compiler closure for a later real capture remains a separate requirement.

Reviewed SHA-256 values:

| Source | SHA-256 |
| --- | --- |
| capture_hook.hpp | de333136b6de2033f375ce6fa1d57c8263fc2ff81ab83523589c7c570c92d7f8 |
| capture_hook_test.cpp | b20ce1827d1bcaba7d002ed1457bfdb763d0d40a49cd98cea10c7aa3f25665cc |
| capture_hook_bridge.cpp | 330c07fe1ca38a091ff32c01c9ee82968bb0a07dc4792e526a866d3c3a97d435 |
| run_hook_tests.py | 2434039d9afe7bdad159f5e11395dc67fdfe5fca7afa699142058529d22d3eb4 |
