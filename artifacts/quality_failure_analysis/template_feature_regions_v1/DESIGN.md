# Full-bank feature-region diagnostic: static design

This is a read-only diagnostic design, not an implemented extractor change or
an accuracy claim. The proposed observer reads the three completed template
families and public training masks. It does not retrain templates, read RGB or
development images, run matching, change thresholds, or alter V27/V28 evidence.
No native build/run, image decode, or template-bank byte read was performed to
write this design. `PROTOCOL.json` pins the numeric/source anchors read here.
The static check re-read 18 attempt CSVs, confirmed the complete pose-key
product and the success/failure totals below, and cross-compared the 432 mask
records in both inherited closures. It did not verify those image bytes.

## Question and scope

Determine where the **already selected** features lie relative to the official
object mask and the rectangular RGB-crop support, and whether their location,
number and orientation distributions differ between the three families. Join
those descriptors to every recorded selected TP/FP, including negative frames,
and all raw template occurrences. Location association cannot establish why a
feature was selected or why a detection succeeded/failed.

Use all objects `[1,2,5,8,12,17]`, all 72 training views, 12 angles and four
scales. There are 20,736 pose keys **per family**, 62,208 family/pose attempts.
The families are RGB with official selection mask (18,199 successes), binary
source with empty selection mask (20,736), and RGB with empty selection mask
(20,712). These imply 59,647 successful templates and 119,294 serialized layers.
Retain all 2,561 failed attempts as explicit rows; failure does not mean a
zero-feature partial extraction. Every pose has two layer-status rows, giving
124,416 rows, with actual features unavailable for failed attempts.

The V27 RGB control is the single RGB occurrence source. The V22 RGB control
is a cross-check, not a fourth family or a repeated sample. Numeric quality
coverage is all 2,400 object/frame pairs for each family, with all 400 GT
identities and both visibility definitions. Use one fallback stream after
checking frozen fallback/fused equality; do not count the same output twice.
The three primary raw totals are 457,279 / 497,740 / 150,247. The selected
totals are 42,327 / 12,089 / 10,202, or 64,618 events, respectively.
These raw streams have already passed score threshold and cross-template
consolidation. Template-usage counts refer to the saved representative IDs,
not every template that generated a candidate before consolidation. Zero
saved usage is not evidence that a descriptor never matched.

## Source-grounded geometry

Use the exact V11 source and helper code named by the protocol, not the mutable
working-tree source as an unpinned reference. For every pose, independently
join attempts and metadata by `(object, training_image, angle, scale)`; template
IDs are local to a family. The attempt's crop/canvas/official warped bbox must
match all three families, including failed attempts.

For each of the 432 unique public masks, use `imread(..., IMREAD_GRAYSCALE)`
once, verify binary 0/255 and dimensions, and retain that decoded Mat only until
all poses for the view finish. The ROI comes from the exact `maskBox` helper and
must equal the attempt row. Do not open its paired RGB file. Rebuild affine
geometry with `getRotationMatrix2D({w/2.f,h/2.f}, angle, scale)` and the exact
canvas translation and 16-pixel alignment from the frozen trainer. Warp the
cropped mask with `INTER_NEAREST`, `BORDER_CONSTANT`, value zero.

Let `M0` be that binary warped official mask. `M1` is **resize** of `M0` with
`INTER_NEAREST` to `(floor(cols/2), floor(rows/2))`, matching V11 selection-mask
semantics. It is not a rewarped smaller mask, a rounded coordinate transform,
or thresholded `pyrDown(M0)`. The official family uses
`E_l = erode(M_l, default 3x3 kernel, one iteration, BORDER_REPLICATE)` as its
actual selection domain. The empty-mask families use no selection restriction;
`M_l/E_l` are reference regions for them, not masks they actually supplied.

In addition preserve binary-source **content** geometry:
`B0=M0`, `B1=pyrDown(B0, floor-half size, default BORDER_DEFAULT)`. `B1` is
grayscale; do not claim it equals `M1`. Record `B_l(x,y)` for every feature as
a content-opacity proxy (not gradient magnitude).

The RGB source crop is rectangular even where the object is nonrectangular.
Observe its support without RGB by warping an all-one `CV_32F` image of the
same crop dimensions using the RGB affine, `INTER_LINEAR`, constant-zero
border. Call the result `A0`; let `A1=pyrDown(A0)` with the exact source
pyramid size/default border. This records interpolation support weights,
not reconstructed RGB values or proof of artificial image gradients.
For each layer save full/partial/absent support (`A==1`, `0<A<1`, `A==0`),
plus exact float32 bits. Verify finite `[0,1]`; do not introduce a fitted epsilon.
`A_l` describes RGB rectangular-crop support. For the binary family it is only
a shared geometry reference; that family's source support follows `B_l`, so
an A-boundary flag must not be reported as its actual source edge.

For each bank feature use its own layer's `(tl_x,tl_y)`:
`absolute_x = feature.x + layer.tl_x`, likewise y. In particular, do not reuse
level-zero tl, multiply then round a coordinate, or infer layer-one origin
from an official bbox. Check against the actual canvas and the frozen feature
geometry CSV where available. Labels 0..7 are serialized; continuous `theta`
is not, so no continuous-angle histogram may be reported.

## Distances, regions and receptive support

Keep independent axes rather than mutually exclusive labels that hide overlap.
For `M_l` and crop support `R_l=(A_l>0)`, save integer Chebyshev distance to
opposite-valued pixels. Inside distance is positive, outside distance is
negative; an inside boundary pixel has distance +1, and an adjacent outside
pixel -1. Extend reference masks with zero outside the canvas when computing
these distances and record canvas distance separately. Save the signed
distance exactly. Also save membership in the eroded official domain and the
crop partial-alpha transition. Use exact morphology/distance definitions,
not an unspecified distance-transform approximation.

Fixed descriptive bands use radii 4, 5 and 6 at each actual pyramid layer;
report inner/outer/remote regions for **all three radii**, without choosing the
most favorable report after observing TP/FP. Preserve direct feature-row
membership so independent code can recompute every aggregate. Boundary-ring
quantities are measurements, not proposed filtering rules.

The source justifies distinct support statements:

| operation | support in current-layer source pixels |
| --- | --- |
| Gaussian 7x7 then Sobel 3x3 magnitude/angle at center | radius 4 |
| 3x3 hysteresis orientation vote | radius 5 |
| 5x5 neighboring-magnitude NMS comparisons | radius 6 |

Hysteresis checks the center weak threshold but votes with every neighboring
quantized direction, including low-magnitude neighbors. NMS validity marking
is traversal-dependent; scattered selection examines the global candidate
list. Therefore radius 6 is not a bound on all dependencies of the final
selected descriptor. At level one, the 5x5 source `pyrDown` adds radius 2 before
the factor-two scale: magnitude/orientation/local-NMS dependencies can reach
10/12/14 level-zero warped pixels, before considering RGB affine interpolation
and border handling. Tests must verify these claims with impulse/support
fixtures; 4px is only a possible future band, not an approved bandwidth.

For each feature record whether its r4/r5/r6 neighborhoods cross official,
crop-support or canvas boundaries. The content-opacity and distance axes
must remain distinguishable: support boundary of a downsampled crop is not
the same as its partial-alpha transition. RGB values and gradient strength are
unobserved. This observer cannot identify NMS blockers or rejected candidates;
that would require a separate extractor trace and new bounded RGB reads.

## Tables and joins

- `attempt_layers.csv`: complete family/pose/level product, success/ID/error,
  requested 32/16 targets, actual count or unavailable, crop/canvas/mask bbox.
- `features.csv.gz`: family/pose/template/level/feature ordinal, local and
  absolute integer coordinates, label, mask/erosion/crop memberships, exact
  alpha bits, binary-source content value, signed distances and r4/r5/r6 flags.
- `template_layers.csv`: descriptor count, all eight label counts, direction
  entropy `-sum(p_label * log2(p_label))` with zero terms omitted, occupied
  spatial cells, region counts/fractions and count-target
  deficit/surplus. Keep zero-count orientation cells. Spatial cells are a
  fixed 4x4 partition of the official bbox, with outside as a separate cell;
  no family-specific grid fit. Degenerate bboxes are rejected.
- `usage_events.csv.gz`: every selected detection joined by exact
  family/class/template ID to its pose/descriptor, complete original detection
  identity and score bits, allGT/eligible label and GT identity. Keep each
  event and distinguish instance-weighted from unique-template statistics.
- `raw_template_usage.csv`: for each family/template, complete raw occurrence
  count, selected TP/FP/IGNORE counts under each metric, positive/negative-frame
  counts and distinct frame counts. Include unused templates with zeros.
- `all_gt_usage.csv`: every one of the 400 GT identities for every family,
  including unmatched identities, with the exact selected TP link or none;
  failed/unavailable same-pose descriptors stay explicit, never dropped.
- `summary.json`: coverage/count gates, per-family/object/scene/metric and
  historical retained/lost/gained/neither groups, plus limitations. Histograms
  by actual feature count are exact integer bins; no fitted low-count cutoff.

Replay and verify NMS/GT labels against the frozen complete raw streams and
selected table before attaching features, or consume a separately frozen
independent audit with complete row-level bindings and verify those bindings.
Cross-check V22/V27 RGB identities and fields. Only V22 binary and V27 RGB
families enter primary statistics. Historical group identities are diagnostic
strata, never a template/filter selection rule. Do not infer pixel localization
quality from descriptor entropy or interpret repeated FP events as independent
templates.

## Minimal execution and provenance plan

1. Freeze this specification, exact observer/auditor/test sources and expanded
   numeric inputs. Static checks reject any image path outside the explicit
   432-mask allowlist and all paths to reserved/heldout data. No broad dataset
   crawler or inherited checker may silently open paired RGB/development bytes.
2. Build one isolated C++ observer linked to the same pinned OpenCV/runtime,
   using V11 bank loading and the unchanged pose/mask math; never call
   `addTemplate`, `match`, or gradient extraction. Pin actual compiler/dependency,
   link/runtime/executable closures before running. A single process reads the
   18 class banks and 432 masks and observes all 20,736 shared geometry poses.
   Separate family processing must not triple image decode counts.
3. The observer writes numeric maps/feature observations and complete row
   membership receipts to a new run directory. Persist regenerated per-pose
   M0/M1/A0/A1/B1 map bytes in compressed numeric packs with schema/dtype/dimensions
   and hashes if the independent auditor needs byte-exact pixel classification.
   This design requires full pixel-classification replay: use lossless row RLE
   (or bitpack for binary masks) in `jsonl.gz` packs, with alpha values encoded
   as exact uint32 float bits and B1 as uint8. Preserve every pixel and shape;
   no downsampling, epsilon, quantization or feature-only sampling is allowed.
   The independent reader may query exact distances directly from run intervals
   rather than expand all maps to Python objects. Compression is not a change
   in the validation scope.
   Never publish raster images; a numeric map pack must be explicitly selected
   and licensed as public training-derived data. Stream view-by-view and set
   a pre-run 1.5 GiB RSS and 2 GiB numeric-output ceiling; failure is incomplete,
   not permission to omit maps/poses or sample favorable cases.
4. Independent Python uses its own strict serialized-bank parser and recomputes
   restored coordinates, distances, flags, label counts, joins and aggregates
   from the full numeric packs. It does not import the observer or invoke OpenCV.
   This independently verifies numeric geometry and associations, not the
   native warp/pyrDown pixels; synthetic literal geometry fixtures cover those
   native transformations, and this limitation is reported explicitly.
   Omitting the complete packs would remove independent feature-region replay;
   it is a scope reduction requiring a separately revised protocol, not an
   automatic fallback when the output ceiling is reached.
5. Verify source/input bytes before and after; preserve successes and failures.
   Before execution, expand all transitive numeric members from the pinned
   closures with exact membership, not merely trust a manifest filename. Image
   SHA/size checking is limited to the 432-mask allowlist. Hash each image before
   and after its decode; record actual `imread` count 432 and file-byte accesses
   separately. Native matcher/training calls and RGB/development decodes are zero.

## Required tests and stop conditions

Use literal rectangle, concave object, hole, thin diagonal, odd crop, angle and
scale fixtures. Include level-one nearest-resize versus grayscale-pyrDown
disagreement, different per-layer tl, inside/outside and canvas-edge distances,
partial warp alpha, all eight labels, failed attempt placeholders, unused
templates, negative-frame events, and a repeated template producing both TP
and FP. Support fixtures must include hysteresis neighbors and NMS comparison
neighbors; do not call a one-pixel probe a proof of global selection support.

Mutation tests reject altered feature/order/label, wrong tl or pose join,
missing failures/level/zero bins, substituted training mask, duplicate usage,
omitted negative frames, count/score-bit changes, false fallback/fused equality,
wrong M1 construction and paths outside the allowlist. Anchored mask/model
coverage and totals are strict gates. Any mismatch stops the run with its
failure evidence; no image retry, threshold tuning, partial-quality result or
automatic band experiment follows.

The planned diagnostic measures selected feature position and association.
It cannot establish gradient causation, recover unrecorded partial features,
prove a border feature is artificial, infer NMS blockers, or guarantee that a
new descriptor policy preserves recall. Any algorithm change needs its own
fixed protocol, fresh complete quality evaluation and separate timing stage.
