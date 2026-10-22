# V31 bounded implementation plan

Status: documents frozen; no implementation or native work performed here.
Root coordinates CPU ownership and each one-shot execution reservation. This
plan is actionable without further user approval within the continuing task.
It does not itself grant a native CPU slot.

## 1. Prepare isolated sources and immutable contracts

- Create a new exact V11 source snapshot and record all23 inherited core/MIPP
  files, dependency headers, helper and transitive Python digests. The C0
  snapshot remains unchanged. Do not edit V30/production files.
- Write the r4 domain/mask contract and a standalone sampler API taking an
  immutable candidate span, K and independent region bits. Keep generation,
  quota scheduling and selection separate so tests can replace each part.
- Native candidate records preserve accepted ordinal/coordinates/label and
  float32 magnitude/theta bits. Check finite fields, unique ordinal,
  coordinate domain and integer-distance overflow before sampling.
- Source-contract tests reject altered r,K,thresholds, stratum pool rebuilds,
  object-specific switches, held-out paths and omitted stage budgets.

## 2. Prove mask/candidate and sampler behavior before real training

- First preserve an expected RED using a missing sampler or wrong quota rule.
- Literal masks cover zero, nonzero1/7/128/255, holes, concavity, thin object,
  odd7x5-to3x2 nearest resize, distinct per-layer origins, canvas edge and
  r4 boundaries. Vnext must be actual nearest resize before nonzero folding;
  grayscale pyrDown, threshold128 and even-index odd-size assumptions fail.
- Literal magnitude/angle maps verify mask-before-5x5-NMS suppression and
  exact row-major acceptance. A deliberate per-stratum NMS mutation fails.
- Pure candidate tests coverN0..5,15..17,31..33, missing/empty strata,
  t=min(K,N), t5 quotas3/2, S1/I4 borrowing1/4, equal scores/distances,
  repeated coordinates, theta preservation and checked overflow. Returned
  IDs must be unique and count exactlyt forN>4; both arms failN<=4.
- Independent Python uses an exhaustive pairwise-distance oracle, not the
  native running-min update. Mutation tests reject reversed initial stratum,
  K-based small-pool quotas, ignored cross-stratum distances, changed ties,
  missing candidates and changed mask resize. Preserve each RED and GREEN.
- Full integration toy covers a failed L0 with still-recorded L1, P/B shared
  pool address/digest and one collector invocation per pose/layer. Ensure
  legacyC0 behavior is byte-exact under its untouched entry point.

## 3. Prepare complete bounded training evidence

- Implement one shared gradient/mask pyramid per pose; collect both levels
  once even when a prior level failed. Feed the same immutable pool toP/B.
  Do not call two independent addTemplate loops to generate these pools.
- Assemble P/B templates only after both levels succeed, apply unchanged
  cross-layer cropping and save dense bank IDs/official-box metadata.
  Save all41,472 arm attempt rows and82,944 layer-status rows. Their success
  statuses must match; actual IDs are still local to each bank.
- Stream complete21-byte canonical candidate records and actual uint8 masks
  into lossless <=64MiB compressed shards. Save perpool/shard content and
  compressed hashes. Never keep every pool in RAM or dump selected-only data.
- Implement hard preallocation/output/RSS/wall guards fromPROTOCOL.json,
  including temporary files and physical/logical byte counters. Synthetic
  fault injection must prove partial preservation and no quality acceptance
  after exhaustion, disk shortage, malformed shard or incomplete member set.
- Expand the explicit432-training-pair allowlist and all numeric inputs before
  actual build/run. Do not use a broad dataset crawler. Keep current design
  source pins separate from the later full executable closure.
- Build under one separately granted CPU slot. Then reserve and execute one
  training run:20,736 shared poses /41,472 pools /41,472 arm attempts. Expected
  imread864 (432RGB+432mask), matcher calls0. Verify actual counters, pre/post
  image/source/tool/runtime bytes and all failed attempts; stop on exceptions,
  guard failure, missing pool, or any zero-success object.

## 4. Independent training and common geometry acceptance

- Read all candidate and mask packs with a strict independent parser. Rebuild
  strata, quotas, every selection and both banks from full payloads. Verify
  actual counts/origins, pose geometry and full82,944 layer-status coverage.
- Read all18 banks with an independent strict bank reader, includingC0, and
  plan one shared canvas from actual coordinates. Preserve left/top64 and
  alignment16. Apply the fixed minimum848x832/right-bottom-only formula;
  reject axis/pixel/dynamic-memory limits, never trim features or templates.
- Write separate training/plan acceptance markers only after the oracle and
  source/input/output member verification passes. Do not rewrite freezes.
- A new quality input freeze binds the three bank sets, full dataset frame
  schedule, official GT/box rules, common padding, accepted audit and complete
  Python/native execution closures. No inherited empty-mask arm names remain.

## 5. Fixed quality gates and complete execution

- Build/test the new three-arm adapter without running matcher images.
  Selftests preserve numeric ordering, scorebit and origin behavior.
- Reserve old-gate96 calls and require original848x672C0 raw to equal the
  historical reference. Pilot288 calls use all8 frozen pilot frames and all
  three arms/two paths; it may only stop on correctness/execution failure.
- Reserve development14,400 calls and save every full ordered raw stream,
  field/scorebit, metadata box, NMS selected row and allGT/eligible identity.
  Save zero results, negative frames and failed diagnostics explicitly.
- Require common-paddingC0 control exact equality toV30control for all400
  frames and fallback/fused equality within each arm. An unexpected geometry
  effect is retained as failure and blocks the primary interpretation.
- Independent standard-library audit recomputes all raw order/counts,
  float32 scores, NMS, GT/IGNORE, negative/object/scene/micro/macro metrics
  and identity changes. No threshold/arm/radius/quota changes follow results.
- Mark numeric audit and accuracy gate separately. B is judged by
  TP>=215 AND FP<42112; a passingP does not replace a failingB. Preserve
  all observed regressions and do not promote a development-only result.

## 6. Separate balanced timing, private regression and release

- After complete independent quality audit, reserve timing29,952 calls:
  six variants,64frames,6objects,1warmup+12formal rounds. Native full own-arm
  reference checks run every call. Validate all formal order positions2/2
  per object/frame/variant; no competing heavy process is permitted.
- Independently recompute27,648 formal rows,4,608 samples/variant, absolute
  and paired medians/p95, equal-frame/object summaries and all regressions.
  Decode/bank loads and matcher/external clocks are distinct.
- Keep local magnetic/SMD regression separate. Coordinate a fresh explicit
  regression budget before native execution; never publish its source images.
- Create results/decision/version notes only from accepted evidence, with
  original failures preserved. Root reviews an explicit public allowlist,
  checks exact index bytes and local commit/tag, pushes the authorized repo,
  and verifies remote refs. Never use git add dot or publish caches/binaries.
