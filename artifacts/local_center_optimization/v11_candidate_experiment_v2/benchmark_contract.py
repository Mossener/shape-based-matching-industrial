"""Fixed five-case timing identity/order checks; no matcher or image access."""
from collections import Counter
import math
CASES = (("exact_v11", "exact_v11", -1), ("linear16_off", "linear16", 0),
         ("linear16_on", "linear16", 1), ("direct16_off", "direct16", 0),
         ("direct16_on", "direct16", 1))
PHASES = (("cold", 1, 0, 0), ("warm", 2, 1, 1), ("measured", 15, 3, 0))
TIMINGS = ("pyramid_ms", "gradient_ms", "spread_ms", "response_ms", "linearize_ms",
           "preprocess_ms", "search_ms", "total_ms", "adapter_wall_ms")
FIELDS = ("image", "image_index", "width", "height", "templates", "threshold", "phase", "round",
          "order_position", "case", "variant", "cache") + TIMINGS + ("result_count", "full_ordered_equal")


def order(image, phase, round_index):
    spec = next(value for value in PHASES if value[0] == phase)
    rotation = (image + spec[2] + round_index) % 5
    values = list(range(5))
    values = values[rotation:] + values[:rotation]
    if (image + round_index // 5 + spec[3]) % 2:
        values.reverse()
    return values


def validate_samples(rows, image_names):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def unsigned(value, label):
        require(isinstance(value, str) and value.isdigit() and value == str(int(value)),
                "Canonical nonnegative integer required: " + label)
        return int(value)

    require(len(image_names) == 25 and len(set(image_names)) == 25, "Fixed twenty-five image identities required")
    require(image_names[:9] == ["LED_" + str(i) for i in range(1, 9)] + ["case1"],
            "LED/case1 fixture identities changed")
    require(len(rows) == 2250, "Exactly2250 native-call rows required")
    offset, measured, histogram = 0, 0, Counter()
    for image, name in enumerate(image_names):
        geometry, count = None, None
        templates, threshold = (900, 75) if image < 8 else (361, 90) if image == 8 else (2212, 85)
        positions = Counter()
        for phase, rounds, _, _ in PHASES:
            for round_index in range(rounds):
                route = order(image, phase, round_index)
                for position, case in enumerate(route):
                    row = rows[offset]
                    offset += 1
                    require(set(row) == set(FIELDS), "Unexpected or missing benchmark CSV columns")
                    identity, variant, cache = CASES[case]
                    expected = dict(image=name, image_index=str(image), phase=phase, round=str(round_index),
                                    order_position=str(position), case=identity, variant=variant, cache=str(cache),
                                    templates=str(templates), threshold=str(threshold), full_ordered_equal="1")
                    require(all(row[key] == value for key, value in expected.items()),
                            "Fixed variant/options/ordered route differs at row " + str(offset - 1))
                    width, height = unsigned(row["width"], "width"), unsigned(row["height"], "height")
                    alignment = 32 if image < 8 else 16
                    require(width > 0 and height > 0 and width % alignment == height % alignment == 0,
                            "Benchmark geometry must retain matcher alignment")
                    current_geometry = (width, height)
                    if geometry is None:
                        geometry = current_geometry
                    require(geometry == current_geometry, "Geometry changed within an image")
                    current_count = unsigned(row["result_count"], "result_count")
                    if count is None:
                        count = current_count
                    require(count == current_count, "Result vector count changed within an image")
                    timing = {}
                    for key in TIMINGS:
                        try:
                            value = float(row[key])
                        except (ValueError, TypeError) as error:
                            raise ValueError("Invalid timing number: " + key) from error
                        require(math.isfinite(value) and value >= 0, "Finite nonnegative timing required: " + key)
                        timing[key] = value
                    require(timing["preprocess_ms"] + 1e-8 >= sum(timing[key] for key in TIMINGS[:5]),
                            "Preprocess timing is smaller than its measured component sum")
                    require(timing["total_ms"] + 1e-8 >= timing["preprocess_ms"] + timing["search_ms"],
                            "Total timing is smaller than preprocess plus search")
                    histogram[identity] += 1
                    if phase == "measured":
                        measured += 1
                        positions[case, position] += 1
        require(positions == Counter({(case, position): 3 for case in range(5) for position in range(5)}),
                "Each case must occupy each measured position exactly three times per image")
    require(offset == 2250 and measured == 1875 and histogram == Counter({case[0]: 450 for case in CASES}),
            "Fixed sample/case counts differ")
    return dict(rows=offset, measured_rows=measured, case_rows=dict(histogram),
                ordered_route_equal=True, complete_ordered_output_declared_equal=True)
