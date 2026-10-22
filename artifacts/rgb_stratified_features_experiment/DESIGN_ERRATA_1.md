# V31 design erratum 1: floor-half nearest-resize test claim

This additive erratum corrects a test claim in the frozen V31 documents. It
does not change the algorithm, mask-resize specification, parameters, budgets,
data scope, frozen document bytes or source pins. Where the following test
claims conflict, this erratum takes precedence.

## Corrected claim

`DESIGN.md` says odd source sizes require the actual ratio rather than sampling
every second pixel. `IMPLEMENTATION_PLAN.md` consequently requires an
even-index odd-size implementation to fail a literal floor-half resize test.
That distinction does not hold for the actual V31 floor-half geometry.

For one source axis of length `n`, the target length is `q=floor(n/2)`.
For each valid output coordinate `0 <= j < q`, nearest-resize source indexing
is `floor(j*n/q)`. If `n=2q`, this is `2j`. If `n=2q+1`, then

```
floor(j*n/q) = floor(2j + j/q) = 2j, since 0 <= j/q < 1.
```

Thus every-second-pixel sampling is equivalent for both even and odd source
axes under this exact floor-half nearest geometry. The result applies
independently to both axes and to each successive layer. For the planned
7x5-to-3x2 fixture, source columns are `[0,2,4]` and rows are `[0,2]`.
The test must not claim that an equivalent every-second-pixel implementation
is RED on that fixture.

The normative implementation remains actual
`cv::resize(Vcurrent, Vnext, size, 0, 0, cv::INTER_NEAREST)` with the specified
floor-half target size, followed by nonzero folding. This erratum does not
authorize replacing that call in the experiment. Equivalence is limited to
the stated geometry: for arbitrary 5-to-3 nearest resizing the indices are
`[0,1,3]`, while every-second sampling would give `[0,2,4]`.

## Distinguishable RED fixtures

Keep literal mask coverage, including nonzero values 1, 7, 128 and 255, and
the actual 7x5-to-3x2 resize fixture. Replace the invalid every-second-pixel
mutation expectation with mutations that really differ:

- Rounded-coordinate indexing: for 7-to-3, `round(j*7/3)` selects `[0,2,5]`,
  while nearest floor indexing selects `[0,2,4]`. Distinct source values at
  indices 4 and 5 expose the mutation.
- Threshold-128 folding: source axis `[7,0]` resized 2-to-1 retains byte 7,
  which belongs to the object under nonzero semantics. A threshold of 128
  rejects it and must fail the fixture.
- Grayscale `pyrDown` of the mask: a 4x4 mask whose every row is
  `[0,255,0,0]` has an all-zero 2x2 nearest-resized mask. Gaussian reduction
  mixes the positive neighboring column into the outputs, changing nonzero
  support. This is a mathematical fixture specification; no native OpenCV
  execution is claimed here.

Candidate-collection, strata, quota, sampler and integration mutation
requirements otherwise remain unchanged. These RED cases must be executed
and retained by their respective implementation tests; this document is not
evidence that those native tests have run.

## Independent arithmetic check

A standard-library rational-arithmetic check independently enumerated both
`n=2q` and `n=2q+1` for every `q` from 1 through 128:

```python
from fractions import Fraction

dimension_cases = 0
coordinates = 0
for q in range(1, 129):
    for n in (2*q, 2*q+1):
        dimension_cases += 1
        for j in range(q):
            x = Fraction(j*n, q)
            assert x.numerator // x.denominator == 2*j
            coordinates += 1
assert dimension_cases == 256
assert coordinates == 16512
```

All 256 source-dimension cases and 16,512 output coordinates passed. This
check uses exact rational arithmetic, reads no images or bank payloads and
does not run native code. It verifies the indexing identity, not OpenCV's
runtime implementation.

The four original frozen documents remain pinned as follows:

| File | SHA256 |
|---|---|
| DESIGN.md | `907ad86ae561340a68e91bf895bcaa0ee2af780967cce87225338f92fc0e48fd` |
| PROTOCOL.json | `628b260bbca50bca666858f54b181afc5fb92e01eaab9b2ed46d6b4ac6e8f19b` |
| IMPLEMENTATION_PLAN.md | `c6d8912091d16b055c1c43814c1a4ca83b1f44e97658d696a782de8400a33468` |
| SOURCE_ORIGINS.json | `ed264fe4b2d0569646384d271ef7549757053eb3ecf18f8541a4cb7d7f349446` |
