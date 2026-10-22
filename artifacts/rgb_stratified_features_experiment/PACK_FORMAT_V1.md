# Training numeric pack format, version 1

Each `pools_NNNNNN.bin.gz` shard is a sequence of complete gzip members.
One member contains one pool: a 64-byte little-endian header, then the whole
actual uint8 mask in row-major order, then all candidate records in source
order. No image file or image encoding is stored.

Header Python format: `<8sIIIiIIIIIIQQ`.

| field | type |
|---|---|
| magic (`RGBPOOL1`) | 8 bytes |
| pool_id, object_id, image_id | uint32 each |
| angle_degrees | int32 |
| scale_float32_bits, level, width, height, K, N | uint32 each |
| mask_bytes, candidate_bytes | uint64 each |

`mask_bytes = width * height`; `candidate_bytes = 21 * N`. Candidate format
is `<IiiBII`: ordinal, x, y, label, magnitude bits, opaque theta bits.
Pool IDs are dense across all objects, poses and layers. A shard never splits
a pool. An individual member exceeding the shard limit fails the run.

`pools.jsonl` records pool identity, member shard/offset/compressed bytes,
logical bytes, payload SHA256, mask SHA256 and candidate SHA256. The SHA256
of the member's compressed bytes is separate. `shards.jsonl` records each
closed shard's whole compressed SHA256, size, logical bytes and ordered pool
IDs. Complete mask/candidate arrays are saved once and shared by P and B.

Layer selection rows bind the pool ID and candidate SHA256, retain every
selected candidate and sampling trace, including insufficient-feature rows.
These observations do not independently regenerate RGB gradients or NMS.

All training-created files use one checked output budget. A failed write or
resource check leaves its existing files intact; there is no truncating rerun.
The external execution guard also checks total directory bytes, process RSS,
elapsed time and free disk. This schema adds no matcher calls or dataset reads.
