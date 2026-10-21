# Static review: refinement geometry and automatic padding

Status: proposed adapter preflight only. No production or experiment code is
changed here. The pad64/pad256 self-match experiment is being run separately;
the following is static reasoning, not a measured result.

## The inverted interval explains a self-match failure

At refinement level l, `matchClass` computes:

```
border = 8*T_l
max_x = D_l - template.width - border
x = max(predicted_x, border)
x = min(x, max_x)
offset_x = (x/T_l - 8)*T_l
```

Y is identical. The order is only a valid clamp when `max_x >= border`.
Otherwise the second assignment undoes the lower bound. For the reported
L4 example at l=2, D=192x160, template about 103x69, T=8:

```
border=64
max_x=192-103-64=25
max_y=160-69-64=27
offset_x=(25/8-8)*8=-40
offset_y=(27/8-8)*8=-40
```

The C++ divisions above are integer divisions. Features whose adjusted
top-left coordinates are negative are skipped before constructing streams,
but all original features remain in the score denominator. More importantly,
the same feature is skipped for the entire 16x16 local patch even if that
feature would become in-bounds at the true winner's later row/column. This
can defeat self-matching without any orientation or score-kernel regression.
It does not establish that this is the only magnet failure; the isolated
padding A/B test must confirm it.

Source: `line2Dup.cpp`, `matchClass`, `similarityLocal`,
`similarityLocal_64`, `similarityLocalMaximum`; the fused helper's full-patch
readability contract is in `line2Dup_local.hpp`.

## Exact preflight quantities

Use `detector.pyramidLevels()`, `getT(l)`, `classIds()`, `numTemplates(class)`
and `getTemplates(class,id)`. Inspect every searched pose, class and level.
The SMD ROI 414x275 is not a substitute for the imported template's cropped,
rotated/scaled per-level width/height. The maximum X and maximum Y may come
from different poses. Keep a table identifying the pose responsible for
each constraint.

For every refined level `0 <= l < L-1`, a nonempty legal center interval
requires:

```
D_l >= max_template_width_l  + 16*T_l
H_l >= max_template_height_l + 16*T_l
```

At the coarsest level require at least one valid whole-template placement:
image dimensions must cover both the declared template extent and actual
maximum feature coordinate plus one. All input dimensions at level l must
be divisible by T_l, as the core explicitly asserts.

Record minimum/maximum feature coordinates and labels as a structural check.
Imported templates should be normalized consistently with their declared
extent and metadata. In particular, a declared width/height smaller than
the actual supported feature grid can invalidate a whole-patch safety
argument. Negative loaded feature coordinates are a separately supported
historical behavior of the core; do not silently rewrite or drop them in a
generic preflight. A specialized importer may normalize them with an explicit
coordinate transform, which must also update all output metadata.

## Minimal total-size padding policy

Let the original image size be W0xH0, and define the alignment

```
A = lcm(2^l * T_l for every level l)
required_width  = max(W0, max_refined_l 2^l*(max_width_l  + 16*T_l), coarse_width_requirement)
required_height = max(H0, max_refined_l 2^l*(max_height_l + 16*T_l), coarse_height_requirement)
W = align_up(required_width,  A)
H = align_up(required_height, A)
```

Alignment makes repeated integer pyrDown sizes exactly W/2^l and H/2^l,
and ensures each is divisible by T_l. Use checked wide arithmetic for shifts,
LCM, sums and image-byte estimates; fail with the required size if it exceeds
the explicit resource budget. Do not silently reduce levels, feature counts,
template poses or search thresholds to fit a memory budget.

Preserve an already-established left/top padding when possible. Ensure W and H
also cover `W0+left` and `H0+top`; add any remaining required area at the right
and bottom. Keep left/top multiples of A when choosing them anew to preserve
the original pyramid/grid phase. Store the four pad sizes in the result
provenance and use the actual left/top values for the output coordinate
transform. This avoids accidentally subtracting 64 after the adapter has
moved the source image by 256.

For the illustrative single-pose l2 extent 103x69 and L4 T=[4,8,8,8],
A=64. That layer requires at least 924x788 input pixels, rounded to
960x832. With a 640x480 source and left/top held at 64, pad sizes are
left=64, right=256, top=64, bottom=288. This adds 192 right and 192 bottom
pixels to the current 768x640 input, and keeps existing source coordinates
unchanged. Recompute this example using the actual full pose bank: rotated
and scaled poses can require larger extents.

This is the first policy to test. It restores a legal local patch without
assuming that an eight-cell margin is required on every source-image side.
The existing clamp is intended to move a full patch inward near image edges;
once its interval is nonempty, a center need not stay unclamped to obtain a
valid match. Preprocessing context, coarse grid sampling and spread still
make a literal border/self-match regression necessary.

## Conservative no-center-clamp policy

If an application explicitly wants the original frame's complete-template
placements to stay inside the center interval with no border clamping, a
sufficient per-side L0 margin is

```
P = max_refined_l 2^l * 8*T_l
```

Round P up to A, then still check the minimum total dimensions for every
template pose. L2 [4,8] gives P=32, L3 [4,8,8] gives P=128, and
L4 [4,8,8,8] gives P=256. This is deliberately more conservative than the
minimum-size policy; 256 is not a universal requirement or a universal
sufficient size for an arbitrary pose bank.

Using all six stored SMD levels with T=[4,8,8,8,8,8] would make the l4
nonempty-interval requirement alone roughly (25+128)*16 by (18+128)*16,
or 2448x2336 before 256-pixel total-size alignment (illustratively 2560x2560).
That is a major cost on a 640x480 source. The configured number of search
levels is therefore an explicit algorithm choice, not an importer rule that
must equal the number of stored SMD levels. Preserve all source data and
report which levels the experiment actually searches.

## Readability and overflow boundaries

An inverted center interval is strong evidence for wrong scoring, but does
not by itself prove an out-of-bounds read. With consistent nonnegative
feature extents, the upper clamp can still bound surviving stream tails even
when the lower clamp is undone. Do not label the observed miss a proven
memory error.

The current per-feature check only verifies the adjusted starting pixel.
The fused kernel then reads 16 rows of 16 consecutive linear-memory cells,
so an independent safety check must prove, for each stream, logical
`start_col+15 < W/T` and `start_row+15 < H/T`, and that the containing
linear-memory row allocation is readable. A malformed template's dimension
metadata can break this; a padding preflight should report such metadata
instead of claiming the start-pixel check is sufficient.

There is also an existing wider physical-load caveat in the word-accumulator
fallback: with SSE `mipp::N<uint8_t>()=16` and
`mipp::N<int16_t>()=8`, the col=8 iteration loads 16 bytes while accumulating
only its low eight. The load reaches logical column 23 although the score
uses only columns 8..15. Crossing into the next row can be benign inside the
allocation; the last allocation row needs a separate physical-read proof.
This is static evidence of a missing generic tail proof, not a reproduction
of an actual failing read. More padding alone cannot formally remove it,
because the core upper clamp follows the new image size. Keep this issue
separate from the self-match diagnosis and verify with a bounded allocation
or sanitizer experiment before making any memory-safety claim.

The score bound (<8192 features, each <=4) remains unrelated to padding.
Image-area/grid-span int products and pointer offsets need checked bounds
before allocating unusually large automatically padded images.

## Next isolated checks

1. Source M01, one pose (angle0/scale1), fixed L4 bank and threshold: compare
   existing pad64 with pad256, plus the computed minimum aligned dimensions
   while keeping left/top64. Save per-level dimensions, actual extents,
   legal-center intervals, candidate counts, feature-skip counts and winner.
   The minimum-size experiment must compute from the bank, not hardcode 103.
2. Run the full pose-bank preflight before matching and report its binding
   angle/scale/level. Pad256 is not a substitute for that scan.
3. Repeat source self-location for L2/L3/L4 and supplied non-source positives;
   verify original-image coordinates and overlay point alignment exactly.
   Keep the core/fused path toggles and threshold fixed within each A/B pair.
4. Check objects near each original-image edge and corner using known
   translations of the source image, with expected translated coordinates.
   Compare minimal padding with the conservative policy; preserve failures.
5. Include widths/heights at one below, equal to, and one above each
   `template_extent+16*T` boundary, odd source sizes, and nontrivial T lists.
   Assert every final pyramid size's divisibility and the exact coordinate
   unpadding transform. A preflight rejection must identify its binding layer.
6. Only after correctness, compare full external-call latency and allocation
   footprint. Padding changes preprocessing, coarse candidate count and every
   response-map size; a larger image can easily overwhelm a local-kernel gain.

No final edge-verification gate should be used to address an image for which
the core produces no candidate because this geometry precondition failed.
