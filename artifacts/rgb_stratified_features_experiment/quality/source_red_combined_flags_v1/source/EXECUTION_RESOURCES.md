# V31 quality execution resources

Freeze this appendix with the quality source before any actual quality run.
These execution limits do not change the objects, images, arms, thresholds,
comparison rules, matching call caps, or the native raw-reference 1 GiB cap.

Each native stage runs through the pinned root `execution_guard.py`. The
observed process RSS ceiling is 1.5 GiB, total native output plus guard logs
is 4 GiB, and guard logs have a separate 64 MiB ceiling. Wall time is the
existing stage duration: 30 minutes for selftest/old_gate/pilot, 240 minutes
for development, and 90 minutes for timing. The guard polls at 50 ms; it is
an observation watchdog rather than an OS allocation sandbox.

The parent run directory must exist. `native/` and `guard/` must both be
fresh, separate children. All partial native files, guard records, and
failure evidence are retained. An exhausted resource budget is a failed
attempt and requires an explicitly recorded successor; the one-shot stage
reservation must never be reset or silently retried.

Compiler commands have a 300 second timeout and retain any stdout/stderr
captured before a timeout. This appendix is an execution resource constraint;
it makes no native correctness, recall, precision, or speed claim.
