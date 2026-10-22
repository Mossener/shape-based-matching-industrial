# V30 template feature-region audit

This is a frozen, numeric-only diagnostic of the historical V22/V27 template families. It
does not change the production matcher, rebuild image pixels, or establish a
causal explanation for a detection loss.

## Scope and independent execution

The guarded run replayed 20,736 poses, 103,680 complete mask/alpha geometry maps,
124,416 attempted layers, 119,294 serialized layers, 2,905,834 features and
64,618 selected events across 7,200 quality frames and 2,400 GT links. It
opened zero image bytes, launched zero native executables and made zero matcher
calls. The process completed in 1,197.281 seconds with a peak RSS of
1,330,757,632 bytes; the 30-minute, 1.5 GiB RSS and 2 GiB output guards were
not triggered.

Root independently rechecked all 13 output hashes and the frozen scope. The
audit summary SHA256 is
`e2164f8f17bdbfc811ca0e6a1cb58ec0a64125cdfef46f7b24ece404dedb5fc6`.

## Descriptive observations

At level 0, the unique feature totals were:

| family | features | official-mask inside | mask cross4 |
|---|---:|---:|---:|
| binary empty mask | 683,436 | 52.15% | 100.00% |
| RGB official mask | 599,797 | 100.00% | 27.93% |
| RGB empty mask | 678,689 | 84.77% | 51.64% |

At level 1, mask-cross4 rates were approximately 100% for binary empty mask,
27.48% for RGB official mask and 69.12% for RGB empty mask. These counts show
that the feature support regions differ substantially between families. They
do not show which difference causes a true or false detection.

The allGT identity strata also remain descriptive. For the RGB empty-mask arm,
the prior identities were retained as 156/156 for the retained subset,
137/148 for identities detected by both prior arms, 18/59 for binary-only,
19/67 for RGB-only and 9/126 for prior-neither. These are post-consolidation
associations; representative IDs are not pre-consolidation causal traces.

## Interpretation and next experiment

The evidence supports testing feature-selection policies that preserve a
controlled amount of contour support while keeping the RGB source. A future
candidate must be registered as a new arm with a fixed quality gate, and be
evaluated on the full fixed development set before any threshold or default
change. This report does not authorize selecting a radius, object, scene or
threshold from these descriptive counts.

The native dilation quality result remains the controlling promotion evidence:
it reduced FP but lost 30 TP, so it is retained as an experiment and not as a
production default.
