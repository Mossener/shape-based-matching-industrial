# Numeric geometry execution resources

After complete training acceptance, the root may reserve one actual full-bank
scan. `run_guarded_scan.py` launches the existing `run_geometry.py` scanner
through the existing process watchdog, with these fixed ceilings:

- wall time: 1,800 seconds;
- observed peak process working set: 1,610,612,736 bytes;
- scanner output plus watchdog files: 268,435,456 bytes;
- watchdog logs and telemetry: 33,554,432 bytes.

The launch marker is exclusive and is created before the child. A failed or
killed launch remains consumed even if the scanner did not reach its own
consumed marker. Original reservations, outputs, diagnostics and receipts are
retained. The independent geometry audit uses its own separate reservation and
watchdog and runs afterward in the same exclusive heavy-work slot.

These are execution limits for numeric verification. They do not change the
frozen 18-bank padding formula, per-template training canvases, template or
feature counts, query canvas limits, quality rules or matcher-call budget.
Neither geometry process decodes images or calls the matcher. The watchdog
observes process resources; it is not an operating-system allocation sandbox.
