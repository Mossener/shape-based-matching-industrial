# Contributing

Read [the provenance](docs/source-provenance.md) and [third-party notices](THIRD_PARTY_NOTICES.md). Preserve copyright and license notices and identify the source and license of new code.

Describe a reproducible problem and the resulting behavior. Include the compiler, OpenCV version, CPU, thread counts, template settings, image dimensions and threshold. Supply only images and templates you have permission to share.

Build the CMake example and run `match_example --synthetic`. For matcher changes, also check relevant image cases against an independent reference. Report regressions as well as improvements. A generated-image self-check establishes basic integration; it does not establish industrial accuracy or throughput.

Keep algorithm changes separate from optimizations intended to preserve output. Describe changes to quantization, thresholds, tie-breaking, template geometry or candidate filtering. Each concurrent match call needs its own workspace; avoid changing process-wide OpenCV/OpenMP settings inside the library.

Use paired, repeated measurements for performance claims. Report preprocessing, search and complete-call time separately, including warmup, compiler flags and thread counts. Evaluate recall, false positives and localization error separately from implementation parity.

Do not commit datasets, private images, generated results, build outputs, credentials or duplicated experiment snapshots. Keep research and bulk validation locally; use Git history for versioned source and add concise user-facing changes to [CHANGELOG.md](CHANGELOG.md).
