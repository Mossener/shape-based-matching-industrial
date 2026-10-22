# Lossless public numeric evidence

The actual training directory contains a 419 MB JSONL layer-claim file. It
cannot be added directly to GitHub. The original output, provenance, failed
audits and reservations remain local and immutable. After full acceptance,
`preserve_training_evidence.py` exports only the original provenance's exact
numeric file allowlist. Text at least 16 MiB is gzip-compressed; numeric pool
and bank gzip files retain their original bytes. Images, executables, object
files and caches are outside this allowlist.

Every exported member records both original and stored byte lengths/SHA256.
The exporter reads every stored stream back and checks complete decoded bytes
against the original training pin. Public stored members must be at most
95 MiB, and the export at most 2 GiB. A rejected/partial export is preserved
and must not be substituted for a completed export. No truncation, selected-
only pool or lossy numeric conversion is permitted.

`restore` requires a new output directory and reconstructs original filenames
and exact original bytes. It checks the complete export inventory and stored
pins before writing. It neither runs training nor changes historic input pins.
Restoration into the original documented workspace path allows the existing
absolute-path provenance to be checked; another checkout must explicitly map
paths, retaining all original content hashes.

This is transport of evidence, not a quality or speed result. Final Git
staging uses an explicit public allowlist and excludes the large original
JSONL, binaries, caches and private magnetic/SMD images.
