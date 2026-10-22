"""Independent standard-library numeric oracle for the frozen RGB experiment.

No RGB gradient/NMS regeneration is claimed. Inputs are complete numeric uint8
masks and source-pinned accepted-candidate records. Distances used for selection
are deliberately recomputed from every selected pair at every selection step.
"""
from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

RECORD = struct.Struct("<IiiBII")
INT64_MAX = (1 << 63) - 1


@dataclass(frozen=True)
class Candidate:
    ordinal: int
    x: int
    y: int
    label: int
    magnitude_bits: int
    theta_bits: int


def _integer(value, minimum, maximum, field):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + field)


def _magnitude(candidate):
    return struct.unpack("<f", struct.pack("<I", candidate.magnitude_bits))[0]


def _validate_candidates(candidates):
    seen = set()
    for c in candidates:
        if not isinstance(c, Candidate):
            raise ValueError("candidate must be Candidate")
        _integer(c.ordinal, 0, (1 << 32)-1, "ordinal uint32")
        _integer(c.x, -(1 << 31), (1 << 31)-1, "x int32")
        _integer(c.y, -(1 << 31), (1 << 31)-1, "y int32")
        _integer(c.label, 0, 7, "label")
        _integer(c.magnitude_bits, 0, (1 << 32)-1, "magnitude bits")
        _integer(c.theta_bits, 0, (1 << 32)-1, "opaque theta bits")
        if not math.isfinite(_magnitude(c)):
            raise ValueError("nonfinite float32 magnitude")
        if c.ordinal in seen:
            raise ValueError("duplicate ordinal")
        seen.add(c.ordinal)


def encode_candidates(candidates):
    """Pack pure API records. Real-pool source order is checked separately."""
    _validate_candidates(candidates)
    return b"".join(RECORD.pack(c.ordinal,c.x,c.y,c.label,c.magnitude_bits,c.theta_bits)
                    for c in candidates)


def decode_candidates(payload):
    if not isinstance(payload, bytes) or len(payload) % RECORD.size:
        raise ValueError("candidate payload must be complete 21-byte records")
    candidates = [Candidate(*record) for record in RECORD.iter_unpack(payload)]
    _validate_candidates(candidates)
    return candidates


def validate_real_pool(candidates):
    """Canonical real collectors visit unique coordinates in row-major order."""
    _validate_candidates(candidates)
    last = None
    for index, c in enumerate(candidates):
        position = (c.y, c.x)
        if c.ordinal != index or (last is not None and position <= last):
            raise ValueError("real pool requires dense ordinals and unique row-major coordinates")
        last = position


def _mask(mask, width, height):
    _integer(width, 1, (1 << 31)-1, "mask width")
    _integer(height, 1, (1 << 31)-1, "mask height")
    if not isinstance(mask, bytes) or len(mask) != width * height:
        raise ValueError("mask must contain the complete uint8 array")


def nearest_resize(mask, width, height, destination_width, destination_height):
    """Nearest uses floor(destination_index * source_size / destination_size)."""
    _mask(mask, width, height)
    _integer(destination_width, 1, (1 << 31)-1, "destination width")
    _integer(destination_height, 1, (1 << 31)-1, "destination height")
    return bytes(mask[(y*height//destination_height)*width + x*width//destination_width]
                 for y in range(destination_height) for x in range(destination_width))


def floorhalf_nearest(mask, width, height):
    destination_width, destination_height = width//2, height//2
    return (nearest_resize(mask,width,height,destination_width,destination_height),
            destination_width,destination_height)


def _distance_transform(mask, width, height, target_inside, exterior_zero):
    """Eight-neighbour multi-source shortest paths, independent of OpenCV."""
    distances = [None] * len(mask)
    queue = deque()
    for index, value in enumerate(mask):
        if (value != 0) == target_inside:
            distances[index] = 0
            queue.append(index)
    if exterior_zero:
        for y in range(height):
            for x in range(width):
                if (x == 0 or y == 0 or x == width-1 or y == height-1):
                    index = y*width+x
                    if distances[index] is None:
                        distances[index] = 1
                        queue.append(index)
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        next_distance = distances[index] + 1
        for dy in (-1,0,1):
            ny = y+dy
            if not 0 <= ny < height:
                continue
            for dx in (-1,0,1):
                nx = x+dx
                if not 0 <= nx < width or (dx == 0 and dy == 0):
                    continue
                adjacent = ny*width+nx
                if distances[adjacent] is None or next_distance < distances[adjacent]:
                    distances[adjacent] = next_distance
                    queue.append(adjacent)
    return distances


def signed_chebyshev(mask, width, height):
    """Inside +distance-to-zero; outside -distance-to-nonzero.

    All-zero masks have no finite distance to object: outside values are None
    (negative infinity), and their candidate domain is empty.
    """
    _mask(mask, width, height)
    to_zero = _distance_transform(mask,width,height,False,True)
    to_inside = _distance_transform(mask,width,height,True,False)
    return [to_zero[i] if value else (-to_inside[i] if to_inside[i] is not None else None)
            for i,value in enumerate(mask)]


def classify(candidates, mask, width, height):
    """Rebuild nonzero membership, signed distances, radius4 domain and strata."""
    _validate_candidates(candidates)
    distances = signed_chebyshev(mask,width,height)
    strata = []
    for c in candidates:
        if not (2 <= c.x < width-2 and 2 <= c.y < height-2):
            raise ValueError("candidate outside original two-pixel NMS margin")
        distance = distances[c.y*width+c.x]
        if distance is None or distance < -4:
            raise ValueError("candidate outside radius4 mask domain")
        strata.append("S" if distance <= 4 else "I")
    return strata


def _distance_squared(a, b):
    dx, dy = a.x-b.x, a.y-b.y
    result = dx*dx + dy*dy
    if result > INT64_MAX:
        raise OverflowError("squared distance exceeds signed int64")
    return result


def sample(candidates, strata, budget, mode):
    """Return an exact independent P/B selection plus full diagnostics.

    Each eligible candidate's minimum is recalculated against the complete
    selected list at each step. No incremental minimum cache is maintained.
    """
    _validate_candidates(candidates)
    _integer(budget, 1, (1 << 32)-1, "budget")
    if mode not in ("P", "B") or len(strata) != len(candidates) or any(s not in ("S","I") for s in strata):
        raise ValueError("invalid arm or strata")
    count, target = len(candidates), min(budget,len(candidates))
    contour, interior = strata.count("S"), strata.count("I")
    initial_s = initial_i = quota_s = quota_i = into_s = into_i = 0
    if mode == "B":
        initial_s, initial_i = (target+1)//2, target//2
        quota_s, quota_i = initial_s, initial_i
        if contour < quota_s:
            into_i = quota_s-contour
            quota_s -= into_i
            quota_i += into_i
        if interior < quota_i:
            into_s = quota_i-interior
            quota_i -= into_s
            quota_s += into_s
    diagnostics = {"input_candidates":count,"requested_budget":budget,"target":target,
                   "contour_candidates":contour,"interior_candidates":interior,
                   "empty_contour":contour == 0,"empty_interior":interior == 0,
                   "quotas_apply":mode == "B","initial_contour_quota":initial_s,
                   "initial_interior_quota":initial_i,"final_contour_quota":quota_s,
                   "final_interior_quota":quota_i,"borrowed_into_contour":into_s,
                   "borrowed_into_interior":into_i,"selected_contour":0,"selected_interior":0}
    result = {"status":"insufficient_features" if count <= 4 else "ok",
              "selected":[],"selected_indices":[],"trace":[],"diagnostics":diagnostics}
    if count <= 4:
        return result
    selected = []
    selected_set = set()
    selected_counts = {"S":0,"I":0}
    quotas = {"S":quota_s,"I":quota_i}
    requested = "S"
    while len(selected) < target:
        if mode == "B" and selected_counts[requested] >= quotas[requested]:
            requested = "I" if requested == "S" else "S"
        best_index, best_key, best_distance = None, None, None
        for index,c in enumerate(candidates):
            if index in selected_set or (mode == "B" and strata[index] != requested):
                continue
            # This complete pairwise recomputation is intentionally slow/independent.
            minimum = min(_distance_squared(c,candidates[chosen]) for chosen in selected) if selected else 0
            key = (minimum, _magnitude(c), -c.ordinal)
            if best_key is None or key > best_key:
                best_index,best_key,best_distance = index,key,minimum
        if best_index is None:
            raise ValueError("internal quota contradiction")
        chosen = candidates[best_index]
        stratum = strata[best_index]
        result["selected"].append(dict(asdict(chosen),stratum=stratum))
        result["selected_indices"].append(best_index)
        result["trace"].append({"ordinal":chosen.ordinal,"stratum":stratum,
                                "has_distance":bool(selected),"minimum_squared_distance":best_distance})
        selected.append(best_index)
        selected_set.add(best_index)
        selected_counts[stratum] += 1
        if mode == "B":
            requested = "I" if requested == "S" else "S"
    diagnostics["selected_contour"] = selected_counts["S"]
    diagnostics["selected_interior"] = selected_counts["I"]
    return result


def _hex(value, field):
    if not isinstance(value,str):
        raise ValueError(field + " must be hexadecimal text")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError("invalid " + field) from error


def verify_resize_fixture(fixture):
    source = _hex(fixture["mask_hex"],"resize source mask")
    expected = _hex(fixture["expected_hex"],"resize expected mask")
    actual, _, _ = floorhalf_nearest(source,fixture["width"],fixture["height"])
    if actual != expected:
        raise ValueError("floor-half nearest mask claim differs")


def verify_claim(actual, claim):
    # JSON distinguishes bool/integer and rejects changed/missing/extra fields.
    if json.dumps(actual,sort_keys=True,separators=(",",":"),allow_nan=False) != json.dumps(
            claim,sort_keys=True,separators=(",",":"),allow_nan=False):
        raise ValueError("full selection claim differs from independent recomputation")


def audit_numeric(spec):
    """Audit one self-contained numeric pool; expected digests bind its origin.

    This is not a full-run/shard acceptance gate. A caller must bind supplied
    expected hashes/counts to its frozen acquisition manifest. A self-consistent
    edited pool with newly edited hashes is not detectable without that origin.
    """
    payload = _hex(spec["candidate_hex"],"candidate payload")
    mask = _hex(spec["mask_hex"],"mask payload")
    for field,value in (("candidate_sha256",payload),("mask_sha256",mask)):
        if hashlib.sha256(value).hexdigest() != spec[field]:
            raise ValueError(field + " does not match pinned payload")
    candidates = decode_candidates(payload)
    _integer(spec["expected_count"],0,(1 << 32)-1,"expected count")
    if len(candidates) != spec["expected_count"]:
        raise ValueError("complete candidate count differs")
    validate_real_pool(candidates)
    strata = classify(candidates,mask,spec["width"],spec["height"])
    for fixture in spec.get("resize_fixtures",[]):
        verify_resize_fixture(fixture)
    result = {"schema":"independent_numeric_pool_v1","candidate_count":len(candidates),
              "candidate_sha256":hashlib.sha256(payload).hexdigest(),
              "mask_sha256":hashlib.sha256(mask).hexdigest(),"strata":strata,
              "P":sample(candidates,strata,spec["budget"],"P"),
              "B":sample(candidates,strata,spec["budget"],"B")}
    claims = spec.get("claims")
    if claims is not None:
        if not isinstance(claims,dict) or set(claims) != {"P","B"}:
            raise ValueError("claims must contain complete P and B results")
        for arm in ("P","B"):
            verify_claim(result[arm],claims[arm])
    return result


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1:
        print("usage: python numeric_oracle.py self_contained_numeric_pool.json",file=sys.stderr)
        return 2
    try:
        spec = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
        print(json.dumps(audit_numeric(spec),sort_keys=True,allow_nan=False))
    except (ValueError,OverflowError,KeyError,TypeError,OSError) as error:
        print(type(error).__name__ + ": " + str(error),file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
