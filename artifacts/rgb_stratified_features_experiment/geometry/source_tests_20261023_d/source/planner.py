"""Pure Python V31 geometry planner for the common C0/P/B canvas.

The planner mirrors ``frozen_helpers/padding_plan.hpp``.  It consumes already
accepted, parsed bank records; it does not open bank files and does not apply
feature or pose filtering.  The caller must provide the accepted template
count for every one of the eighteen arm/object banks.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from typing import Any, Iterable, Mapping, Sequence


ARMS = ("C0", "P", "B")
OBJECTS = (1, 2, 5, 8, 12, 17)
SOURCE_SIZE = (720, 540)
BASE_PADDING = (64, 64, 64, 228)
PYRAMID_T = (4, 8)
DEFAULT_LIMITS = {
    "axis": 2048,
    "pixels": 2097152,
    "bytes_per_pixel": 512,
    "dynamic_bytes": 1073741824,
}
U64_MAX = (1 << 64) - 1
I64_MAX = (1 << 63) - 1
I32_MIN = -(1 << 31)
I32_MAX = (1 << 31) - 1


class GeometryError(ValueError):
    """Malformed, incomplete, duplicated, or inconsistent bank geometry."""


class ResourceError(GeometryError):
    """A complete geometry exceeds the frozen canvas resource budget."""


@dataclass(frozen=True)
class BankLayer:
    """Serialized detector layer as returned by the strict bank parser."""

    level: int
    width: int
    height: int
    tl_x: int
    tl_y: int
    features: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class BankTemplate:
    template_id: int
    layers: tuple[BankLayer, ...]
    # Training canvases vary by pose and are not the 720x540 query frame.
    # None retains the original literal API; the runner always supplies the
    # independently reconstructed training canvas explicitly.
    canvas_size: tuple[int, int] | None = None


@dataclass(frozen=True)
class Bank:
    arm: str
    object_id: int
    class_id: str
    templates: tuple[BankTemplate, ...]


@dataclass(frozen=True)
class Plan:
    source_size: tuple[int, int]
    width: int
    height: int
    alignment: int
    padding: tuple[int, int, int, int]
    pixels: int
    estimated_dynamic_bytes: int
    banks: int
    loaded_layers: int
    layer_requirements: tuple[dict[str, Any], ...]

    @property
    def estimated_bytes(self) -> int:
        """Compatibility spelling used by the inherited C++ ``Plan``."""
        return self.estimated_dynamic_bytes

    @property
    def padding_ltrb(self) -> tuple[int, int, int, int]:
        return self.padding

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON shape used by a future native planner."""
        return {
            "source_size": list(self.source_size),
            "width": self.width,
            "height": self.height,
            "alignment": self.alignment,
            "padding_ltrb": list(self.padding),
            "pixels": self.pixels,
            "estimated_dynamic_bytes": self.estimated_dynamic_bytes,
            "banks": self.banks,
            "loaded_layers": self.loaded_layers,
            "geometry_feasible": 1,
            "development_images_decoded": 0,
            "matcher_calls": 0,
            "layer_requirements": [dict(row) for row in self.layer_requirements],
        }


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _u64(value: Any, what: str) -> int:
    if not _is_int(value) or value < 0 or value > U64_MAX:
        raise GeometryError(f"{what} is outside unsigned 64-bit range")
    return int(value)


def _i64(value: Any, what: str) -> int:
    if not _is_int(value) or value < -I64_MAX - 1 or value > I64_MAX:
        raise GeometryError(f"{what} is outside signed 64-bit range")
    return int(value)


def _i32(value: Any, what: str) -> int:
    if not _is_int(value) or value < I32_MIN or value > I32_MAX:
        raise GeometryError(f"{what} is outside signed 32-bit range")
    return int(value)


def _add(a: int, b: int, what: str = "sum") -> int:
    a, b = _u64(a, what), _u64(b, what)
    if b > U64_MAX - a:
        raise OverflowError(f"{what} overflow")
    return a + b


def _multiply(a: int, b: int, what: str = "product") -> int:
    a, b = _u64(a, what), _u64(b, what)
    if a and b > U64_MAX // a:
        raise OverflowError(f"{what} overflow")
    return a * b


def _align(value: int, multiple: int) -> int:
    multiple = _u64(multiple, "alignment")
    if not multiple:
        raise GeometryError("Positive alignment required")
    return _multiply((_add(value, multiple - 1, "alignment sum") // multiple), multiple,
                     "aligned dimension")


def _feature_tuple(feature: Any, where: str) -> tuple[int, int, int]:
    if not isinstance(feature, (tuple, list)) or len(feature) != 3:
        raise GeometryError(f"{where} is not an x/y/label triple")
    x, y, label = (_i32(feature[0], where + " x"),
                   _i32(feature[1], where + " y"),
                   _i32(feature[2], where + " label"))
    if not 0 <= label <= 7:
        raise GeometryError(f"{where} has an invalid orientation label")
    return x, y, label


def _layer_geometry(layer: BankLayer, *, source_size: tuple[int, int],
                    bank_name: str, template_id: int) -> tuple[dict[str, Any], tuple[int, int]]:
    if not isinstance(layer, BankLayer):
        raise GeometryError(f"{bank_name} template {template_id} has an unknown layer record")
    level = _i64(layer.level, "layer level")
    if level not in (0, 1):
        raise GeometryError(f"{bank_name} template {template_id} has an invalid pyramid level")
    width = _i64(layer.width, "layer width")
    height = _i64(layer.height, "layer height")
    if width <= 0 or height <= 0:
        raise GeometryError("Malformed loaded bank layer: width and height must be positive")
    tl_x = _i32(layer.tl_x, "layer tl_x")
    tl_y = _i32(layer.tl_y, "layer tl_y")
    try:
        raw = tuple(_feature_tuple(p, f"{bank_name} template {template_id} feature")
                    for p in layer.features)
    except TypeError as exc:
        raise GeometryError("Malformed loaded bank layer: features must be iterable") from exc
    if not raw:
        raise GeometryError("Malformed loaded bank layer: empty feature list")
    xs, ys = zip(*((p[0], p[1]) for p in raw))
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    # This is the exact helper boundary: equality with width/height is valid.
    if min_x < 0 or min_y < 0 or max_x < min_x or max_y < min_y or max_x > width or max_y > height:
        raise GeometryError("Malformed loaded bank layer: feature extent exceeds template")

    source_w, source_h = source_size
    canvas_w = source_w >> level
    canvas_h = source_h >> level
    abs_x = tuple(tl_x + p[0] for p in raw)
    abs_y = tuple(tl_y + p[1] for p in raw)
    if (min(abs_x) < 0 or min(abs_y) < 0 or max(abs_x) >= canvas_w or
            max(abs_y) >= canvas_h):
        raise GeometryError("Serialized feature outside actual layer canvas")
    row = {
        "level": level,
        "width": width,
        "height": height,
        "tl_x": tl_x,
        "tl_y": tl_y,
        "actual_features": len(raw),
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
        "min_absolute_x": min(abs_x),
        "min_absolute_y": min(abs_y),
        "max_absolute_x": max(abs_x),
        "max_absolute_y": max(abs_y),
        "canvas_width": canvas_w,
        "canvas_height": canvas_h,
    }
    return row, (min_x, min_y)


def _normalise_counts(accepted_counts: Mapping[Any, Any]) -> dict[tuple[str, int], int]:
    if not isinstance(accepted_counts, Mapping):
        raise GeometryError("Accepted template counts must be a mapping")
    result: dict[tuple[str, int], int] = {}

    def put(arm: Any, object_id: Any, value: Any) -> None:
        if not _is_int(object_id) or arm not in ARMS or object_id not in OBJECTS:
            raise GeometryError("Accepted counts contain an unexpected bank")
        if (arm, object_id) in result:
            raise GeometryError("Duplicate accepted bank count")
        if not _is_int(value) or value <= 0:
            raise GeometryError("Accepted template counts must be positive integers")
        result[(arm, int(object_id))] = int(value)

    for key, value in accepted_counts.items():
        if key in ARMS and isinstance(value, Mapping):
            for object_id, nested_value in value.items():
                put(key, object_id, nested_value)
            continue
        if isinstance(key, tuple) and len(key) == 2:
            arm, object_id = key
        elif isinstance(key, str) and "/" in key:
            arm, object_text = key.split("/", 1)
            try:
                object_id = int(object_text)
            except ValueError as exc:
                raise GeometryError("Invalid accepted bank key") from exc
        else:
            raise GeometryError("Accepted bank keys must be (arm, object_id)")
        put(arm, object_id, value)
    expected = {(arm, object_id) for arm in ARMS for object_id in OBJECTS}
    if set(result) != expected:
        raise GeometryError("Accepted count evidence must cover all eighteen banks")
    return result


def plan_all(banks: Sequence[Bank], accepted_counts: Mapping[Any, Any], *,
             source_size: tuple[int, int] = SOURCE_SIZE,
             base_padding: tuple[int, int, int, int] = BASE_PADDING,
             pyramid_t: tuple[int, int] = PYRAMID_T,
             limits: Mapping[str, int] | None = None) -> Plan:
    """Plan the common canvas from every accepted C0/P/B bank layer.

    ``accepted_counts`` is evidence from the completed training acceptance;
    template records are never silently truncated to it.  Every supplied
    template and every layer is scanned before the result is produced.
    """
    if not isinstance(source_size, (tuple, list)) or len(source_size) != 2:
        raise GeometryError("Source size must contain width and height")
    source_w, source_h = (_u64(source_size[0], "source width"),
                          _u64(source_size[1], "source height"))
    if not source_w or not source_h:
        raise GeometryError("Nonempty source required")
    if not isinstance(base_padding, (tuple, list)) or len(base_padding) != 4:
        raise GeometryError("Base padding must contain left/top/right/bottom")
    left, top, right, bottom = tuple(_u64(x, "base padding") for x in base_padding)
    if not isinstance(pyramid_t, (tuple, list)) or not pyramid_t or len(pyramid_t) > 64:
        raise GeometryError("Pyramid T must be nonempty and have at most 64 levels")
    t = tuple(_u64(x, "pyramid T") for x in pyramid_t)
    if any(x == 0 for x in t):
        raise GeometryError("Positive pyramid T required")
    configured = dict(DEFAULT_LIMITS)
    if limits is not None:
        if not isinstance(limits, Mapping):
            raise GeometryError("Resource limits must be a mapping")
        configured.update(limits)
    lim = {name: _u64(configured[name], name + " limit")
           for name in ("axis", "pixels", "bytes_per_pixel", "dynamic_bytes")}

    counts = _normalise_counts(accepted_counts)
    if not isinstance(banks, Sequence):
        raise GeometryError("All-bank input must be a sequence")
    expected_keys = {(arm, object_id) for arm in ARMS for object_id in OBJECTS}
    by_key: dict[tuple[str, int], Bank] = {}
    for bank in banks:
        if not isinstance(bank, Bank):
            raise GeometryError("Unknown bank record")
        if not _is_int(bank.object_id):
            raise GeometryError("Bank object ID must be an integer")
        key = (bank.arm, bank.object_id)
        if key not in expected_keys or key in by_key:
            raise GeometryError("All-bank input must contain exactly one C0/P/B bank per object")
        if not isinstance(bank.class_id, str) or not bank.class_id:
            raise GeometryError("Bank class ID must be nonempty")
        by_key[key] = bank
    if set(by_key) != expected_keys:
        raise GeometryError("All-bank input must contain all eighteen banks")

    # Match the helper's checked LCM calculation and its level factors.
    factors: list[int] = []
    factor = 1
    alignment = 1
    for level, term_t in enumerate(t):
        factors.append(factor)
        term = _multiply(factor, term_t, "pyramid alignment")
        alignment = _multiply(alignment // gcd(alignment, term), term,
                              "pyramid alignment")
        if level + 1 < len(t):
            factor = _multiply(factor, 2, "pyramid factor")

    required_width = _add(source_w, _add(left, right, "base horizontal padding"),
                          "initial width")
    required_height = _add(source_h, _add(top, bottom, "base vertical padding"),
                           "initial height")
    rows: list[dict[str, Any]] = []
    seen_poses: set[tuple[str, str, int]] = set()
    loaded_layers = 0
    for key in sorted(expected_keys, key=lambda item: (ARMS.index(item[0]), OBJECTS.index(item[1]))):
        bank = by_key[key]
        count = counts[key]
        try:
            templates = tuple(bank.templates)
        except TypeError as exc:
            raise GeometryError("Bank templates must be iterable") from exc
        if len(templates) != count:
            raise GeometryError(f"{bank.arm}/{bank.object_id} count differs from accepted evidence")
        for expected_id, pose in enumerate(templates):
            if not isinstance(pose, BankTemplate) or pose.template_id != expected_id:
                raise GeometryError("Loaded template IDs must be dense and ordered")
            pose_key = (bank.arm, bank.class_id, pose.template_id)
            if pose_key in seen_poses:
                raise GeometryError("Duplicate loaded bank pose")
            try:
                layer_count = len(pose.layers)
            except TypeError as exc:
                raise GeometryError("Template layers must be a sequence") from exc
            if layer_count != len(t):
                raise GeometryError("Incomplete loaded pose pyramid")
            levels_seen: set[int] = set()
            for layer in pose.layers:
                if not isinstance(layer, BankLayer):
                    raise GeometryError("Unknown loaded bank layer")
                if layer.level in levels_seen:
                    raise GeometryError("Duplicate loaded bank layer")
                levels_seen.add(layer.level)
                if layer.level < 0 or layer.level >= len(t):
                    raise GeometryError("Invalid pyramid level")
                canvas_size = pose.canvas_size if pose.canvas_size is not None else (source_w, source_h)
                if (not isinstance(canvas_size, (tuple, list)) or len(canvas_size) != 2 or
                        any(not _is_int(value) or value <= 0 for value in canvas_size)):
                    raise GeometryError("Positive per-pose training canvas required")
                row, _ = _layer_geometry(layer, source_size=tuple(canvas_size),
                                          bank_name=f"{bank.arm}/{bank.object_id}",
                                          template_id=pose.template_id)
                level = row["level"]
                if level + 1 < len(t):
                    margin = _multiply(16, t[level], "non-last level margin")
                    needed_w = _add(row["width"], margin, "non-last level width")
                    needed_h = _add(row["height"], margin, "non-last level height")
                else:
                    needed_w = max(row["width"], _add(row["max_x"], 1, "last level max x"))
                    needed_h = max(row["height"], _add(row["max_y"], 1, "last level max y"))
                projected_w = _multiply(factors[level], needed_w, "projected width")
                projected_h = _multiply(factors[level], needed_h, "projected height")
                required_width = max(required_width, projected_w)
                required_height = max(required_height, projected_h)
                row.update({"arm": bank.arm, "object_id": bank.object_id,
                            "class_id": bank.class_id, "template_id": pose.template_id,
                            "needed_width": needed_w, "needed_height": needed_h,
                            "projected_width": projected_w, "projected_height": projected_h})
                rows.append(row)
                loaded_layers += 1
            if levels_seen != set(range(len(t))):
                raise GeometryError("Incomplete loaded pose pyramid")
            seen_poses.add((bank.arm, bank.class_id, pose.template_id))

    width, height = _align(required_width, alignment), _align(required_height, alignment)
    pixels = _multiply(width, height, "canvas pixels")
    estimated = _multiply(pixels, lim["bytes_per_pixel"], "estimated dynamic memory")
    if (width > lim["axis"] or height > lim["axis"] or pixels > lim["pixels"] or
            estimated > lim["dynamic_bytes"]):
        raise ResourceError("Full-bank padding exceeds declared resource budget")
    padding = (left, top, width - source_w - left, height - source_h - top)
    return Plan(source_size=(source_w, source_h), width=width, height=height,
                alignment=alignment, padding=padding, pixels=pixels,
                estimated_dynamic_bytes=estimated, banks=len(by_key),
                loaded_layers=loaded_layers, layer_requirements=tuple(rows))


def bank_from_records(arm: str, object_id: int, class_id: str,
                      templates: Iterable[Any]) -> Bank:
    """Adapt strict-reader dictionaries without opening files in this module."""
    parsed: list[BankTemplate] = []
    try:
        template_iterator = iter(templates)
    except TypeError as exc:
        raise GeometryError("Templates must be iterable") from exc
    for index, item in enumerate(template_iterator):
        if isinstance(item, Mapping):
            if "layers" not in item:
                raise GeometryError("Template mapping must contain layers")
            raw_layers = item["layers"]
        else:
            # strict_bank_reader.parse_bank returns each template as its
            # ordered two-layer list rather than wrapping it in a mapping.
            raw_layers = item
        layers: list[BankLayer] = []
        try:
            iterator = iter(raw_layers)
        except TypeError as exc:
            raise GeometryError("Template layers must be iterable") from exc
        for raw in iterator:
            if not isinstance(raw, Mapping):
                raise GeometryError("Layer mapping required")
            layers.append(BankLayer(level=raw["pyramid_level"], width=raw["width"],
                                    height=raw["height"], tl_x=raw["tl_x"],
                                    tl_y=raw["tl_y"], features=tuple(raw["features"])))
        parsed.append(BankTemplate(template_id=index, layers=tuple(layers)))
    return Bank(arm=arm, object_id=object_id, class_id=class_id, templates=tuple(parsed))

