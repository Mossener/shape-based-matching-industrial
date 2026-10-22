# Numeric stream boundary

`pool_stream.py` accepts the native writer's `pools.jsonl`, `shards.jsonl` and
`.bin.gz` files. No native implementation is imported or inspected.

```python
import pool_stream

manifest = pool_stream.manifest_from_jsonl(
    directory, frozen_pools_jsonl_sha256, frozen_shards_jsonl_sha256)
for pool in pool_stream.iter_verified_pools(directory, manifest, frozen_pool_ids):
    independent = pool_stream.audit_pool(pool, claims={"P": p_result, "B": b_result})
# Only after the generator is exhausted may the caller accept this part of a run.
```

Expected manifest hashes and the ordered pool IDs must come from separately
pinned collection evidence and the frozen training schedule. A self-edited
manifest cannot prove its own completeness. Full training also needs all
pose/object/image/angle/scale/level identities checked against that schedule;
the parser checks allowed object/angle/scale/level/K but does not own the image
allowlist. Audit both layers and compare the complete L1 mask to
`numeric_oracle.floorhalf_nearest(L0_mask,L0_width,L0_height)`; independent
one-pool parsing does not imply that cross-layer check has happened.

Native `pools.jsonl` fields:

`pool_id, object_id, image_id, angle_degrees, scale_float32_bits, level, width,
height, K, N, shard, offset, compressed_bytes, logical_bytes, mask_sha256,
candidate_sha256, payload_sha256, compressed_sha256`.

Native `shards.jsonl` fields:

`shard, path, compressed_bytes, logical_bytes, sha256, pool_ids`.

Duplicate keys, blank JSONL rows, unknown/missing fields, non-finite JSON and
manifest byte hashes that differ are rejected. Shard IDs are dense and source
order is retained. Shard paths must be unique basenames resolved inside the
numeric pack directory.

Each member decompresses to exactly:

1. Header `<8sIIIiIIIIIIQQ>`, 64 little-endian bytes. Magic `RGBPOOL1`; fields
   `pool_id,obj,image,angle,scale_bits,level,width,height,K,N,mask_len,candidate_len`.
2. Complete raw uint8 row-major mask, `mask_len = width * height` bytes.
3. Complete canonical candidate pool, `candidate_len = 21*N` bytes, `<IiiBII>`.

The adapter normalizes native field aliases and lengths into a nested
`rgb_pool_shards_v1` manifest. Its top-level keys are `pool_count,shard_count,
physical_bytes,logical_bytes,shards`. Each shard has `path,bytes,logical_bytes,
sha256,pool_ids,members`. Each member has `pool_id,offset,compressed_bytes,
compressed_sha256,payload_bytes,payload_sha256,mask_sha256,candidate_sha256,
header`. The normalized header has the 12 named numeric fields above.

The parser verifies whole-shard hash/size before yielding its members, contiguous
offsets, exact ordered membership/counts/totals, each independent gzip footer/CRC,
no embedded second member, trailing or truncated bytes, every member/payload/
mask/candidate hash, exact header geometry/counts, and canonical size arithmetic.
It reads compressed chunks of at most 64KiB and caps decoded bytes before
accumulating a complete single pool. It keeps no RGB, raster decoder, template
bank or matcher dependency.

Static bounds are 64MiB per shard, 4GiB physical and 32GiB logical numeric data,
2,097,152 mask pixels/candidates per pool, and 2048 per mask axis. Acquisition
RSS, training duration, disk free space, temporary outputs, generator counts,
decode counts and failure receipts remain the orchestration's responsibility.
No resource guard here authorizes a real training or audit execution.

`audit_pool` independently validates dense row-major unique coordinates,
nonzero mask semantics, domain/strata, complete P/B selection, all original
record bits, diagnostic quotas/borrowing and trace. It returns pool ID, payload
pins, strata and full P/B results. Native enum status/stratum must be converted
to oracle strings before exact claim comparison. It does not perform cropping,
bank serialization, pixel candidate regeneration or full quality/timing audit.

The actual native writer's two synthetic members from
`packing/run_green_20261022_a/data/ok` have been parsed independently. This is
a byte-format cross-check, not a real collector/domain acceptance. Those masks
and candidate magnitudes are writer observations; no original pixels were read.
