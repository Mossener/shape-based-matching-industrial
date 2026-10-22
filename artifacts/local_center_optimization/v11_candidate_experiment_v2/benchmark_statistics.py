"""Pure descriptive arithmetic for the frozen paired-round timing protocol."""
import math
import statistics


def describe(values):
    values = [float(value) for value in values]
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Nonempty finite nonnegative observations required")
    ordered = sorted(values)

    def quantile(probability):
        location = (len(ordered) - 1) * probability
        lo, hi = math.floor(location), math.ceil(location)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (location - lo)

    geometric = 0.0 if min(values) == 0 else math.exp(statistics.mean(math.log(value) for value in values))
    return dict(count=len(values), median=statistics.median(values), geomean=geometric,
                p10=quantile(.1), p90=quantile(.9), min=min(values), max=max(values))


def paired_stats(numerator, denominator):
    numerator, denominator = list(numerator), list(denominator)
    if not numerator or len(numerator) != len(denominator):
        raise ValueError("Nonempty equal-length paired rounds required")
    a, b = [float(value) for value in numerator], [float(value) for value in denominator]
    if any(not math.isfinite(value) or value < 0 for value in a) or any(
            not math.isfinite(value) or value <= 0 for value in b):
        raise ValueError("Finite nonnegative numerators and strictly positive denominators required")
    ratios = [x / y for x, y in zip(a, b)]
    return dict(describe(ratios), ratios=ratios)
