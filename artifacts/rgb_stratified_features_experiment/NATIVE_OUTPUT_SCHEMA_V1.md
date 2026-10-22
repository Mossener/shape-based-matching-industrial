# Native training and literal output contract

This describes expected observations, not completed training. The synthetic
literal is one pose: object1/image0/angle0/scale1, source256x256, chess blocks32,
mask255 inside xywh[16,16,224,224] and zero outside. Source ROI is the entire
256x256 numeric Mat. No image decode, dataset index, matcher or GT is used.

Both literal and training emit these files in the new native directory:

- `pools.jsonl`, `shards.jsonl`, `pools_NNNNNN.bin.gz`: PACK_FORMAT_V1.md.
- `pool_observations.jsonl`: one row/pool, dense pool_id, target=min(K,N),
  dilated_mask_sha256 (full raw9x9 nonzero-mask dilation255/0, no cleared
  margin), nms_maxima (native observation only), validation object with all
  six bool keys: dense_ordinals,unique_rowmajor_coords,finite_magnitudes,
  labels_0_to_7,inside_scan_domain,source_order_preserved. Scan domain also
  imposes the two-pixel margin. No independent real-gradient claim follows.
- `layer_selections.jsonl`: one P then B row per pool, fields pose_id,pool_id,
  arm,candidate_sha256,result. Result exactly matches the independent oracle
  schema, including diagnostics, selected_indices, selected full records,trace.
- `attempts.jsonl`: one P then B row/pose, fields pose_id,object_id,image_id,
  angle_degrees,scale,arm,success(bool),template_id,source_roi(xywh),canvas,
  warped_mask_bbox(xywh),pool_ids(two),crop_xywh. Failed attempts retain ID-1.
- `rgb_pooled_features/objN/` and `rgb_stratified_features/objN/`: original
  `templates_tless_object_N.yml.gz`, `template_metadata.json`,
  `training_config.json`. Class/bank serialization, metadata and writeConfig
  are inherited from the unchanged V11 helper/core. Config adds target_objects,
  template_count,shared_candidate_pool=1,exact_feature_budgets=[32,16].
- `progress.jsonl`: resource/phase snapshot before each collector/sampler,
  pool write and pose, plus pose completion. Counters distinguish calls started,
  fully written pools/rows and completed poses. Each row retains pose/level/arm,
  phase, RGB/mask imread-call counters and logical/physical reservations.
- `loaded_modules.json`: normal-completion process module paths. Runner checks
  every non-system module against the separately frozen PE import closure.
- `training_summary.json`: schema rgb_stratified_training_observation_v1;
  complete, literal_only, shared_poses,shared_pools,arm_attempts,arm_layer_rows,
  gradient_pyramids,pyramid_downs,rgb_decodes,mask_decodes,total_imread_calls,
  matcher_calls,peak_rss_bytes,logical_payload_bytes,physical_bytes_before_summary,
  successful_templates:{P:[per-object counts],B:[per-object counts]}.

Literal expected counters: 1pose,2pools,2attempts,4layer rows,1gradient pyramid,
1pyrDown,0imread,0matcher; both arms have one successful template. Production
training uses the frozen432pair schedule:20736poses,41472pools/arm attempts,
82944layer rows,432RGB+432mask imread,0matcher. The actual count is unobserved
until the native run and independent output audit pass.

All text and uncompressed binary payloads count toward the32GiB logical limit;
gzip sizes count toward physical output. Summary counters exclude the summary
file itself, so adding its exact byte size must reproduce the full directory
physical/logical totals. All output is checked before write. Compression buffers
allocate no more than min(zlib bound,remaining physical budget,shard ceiling).
Each training mask canvas is preflight bounded to2048/axis and2097152pixels,
matching the strict numeric parser's declared bounds. This execution guard can
fail a run and never filters a pose/feature or changes its scale.

Native data reserves64MiB for execution logs and64KiB for failure evidence
within the4GiB physical ceiling. The watchdog checks native+execution bytes
together, process peak RSS and wall time. Allocation/write checks are in native;
the watchdog observes limits and may detect an offending allocation just after
it happens. It is not an OS sandbox.

An ordinary native exception appends a <=64KiB `native_failure.json` using that
reserved tail, with current phase/identity/counters/reservations and error.
A watchdog kill retains the most recently persisted progress, guard telemetry,
reservation and all partial files. Failure never produces complete acceptance.
The runner stores its reservation and provenance in fresh sibling paths and
allows one attempt per stage. An explicit successor is required after failure.
