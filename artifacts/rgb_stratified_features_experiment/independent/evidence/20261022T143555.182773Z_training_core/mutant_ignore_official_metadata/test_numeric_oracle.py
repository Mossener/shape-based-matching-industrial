"""Literal tests: expectations precede and do not import the native implementation."""
import copy
import hashlib
import importlib.util
import json
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.find_spec("numeric_oracle")
if SPEC is not None:
    import numeric_oracle as oracle


class Availability(unittest.TestCase):
    def test_independent_oracle_exists(self):
        self.assertIsNotNone(SPEC, "independent numeric_oracle is missing")


@unittest.skipIf(SPEC is None, "missing independent oracle; availability is the RED")
class Literals(unittest.TestCase):
    def candidate(self, ordinal, x, y=0, magnitude=1.0, label=0, theta=0):
        bits = struct.unpack("<I", struct.pack("<f", magnitude))[0]
        return oracle.Candidate(ordinal, x, y, label, bits, theta)

    def pool(self):
        return [self.candidate(0, 0, 0, 10), self.candidate(1, 10, 0, 9),
                self.candidate(2, 9, 0, 8), self.candidate(3, 0, 10, 7),
                self.candidate(4, 10, 10, 6), self.candidate(5, 5, 5, 5)]

    def ordinals(self, result):
        return [row["ordinal"] for row in result["selected"]]

    def test_nonzero_values_and_zero_exterior(self):
        # A threshold128 or no-exterior implementation breaks these literals.
        mask = bytes([0, 0, 0, 0, 0, 0, 1, 7, 128, 0, 0, 255, 255, 255, 0,
                      0, 255, 255, 255, 0, 0, 0, 0, 0, 0])
        self.assertEqual(oracle.signed_chebyshev(mask, 5, 5),
                         [-1, -1, -1, -1, -1, -1, 1, 1, 1, -1,
                          -1, 1, 2, 1, -1, -1, 1, 1, 1, -1, -1, -1, -1, -1, -1])
        self.assertEqual(oracle.signed_chebyshev(bytes([7] * 9), 3, 3),
                         [1, 1, 1, 1, 2, 1, 1, 1, 1])
        self.assertEqual(oracle.signed_chebyshev(bytes(9), 3, 3), [None] * 9)

    def test_hole_and_thin_mask(self):
        self.assertEqual(oracle.signed_chebyshev(bytes([1,1,1,1,0,1,1,1,1]), 3, 3),
                         [1,1,1,1,-1,1,1,1,1])
        self.assertEqual(oracle.signed_chebyshev(bytes([0,1,0,0,1,0,0,1,0]), 3, 3),
                         [-1,1,-1,-1,1,-1,-1,1,-1])

    def test_exhaustive_3x3_masks_against_direct_opposite_pixel_search(self):
        # Independent test method: direct exhaustive coordinate search, not BFS.
        exterior=[(x,y) for y in range(-1,4) for x in range(-1,4)
                  if x in (-1,3) or y in (-1,3)]
        for bits in range(512):
            mask=bytes(7 if bits & (1<<i) else 0 for i in range(9))
            inside=[(i%3,i//3) for i,v in enumerate(mask) if v]
            outside=[(i%3,i//3) for i,v in enumerate(mask) if not v]+exterior
            expected=[]
            for i,value in enumerate(mask):
                x,y=i%3,i//3
                opposite=outside if value else inside
                distance=min(max(abs(x-ox),abs(y-oy)) for ox,oy in opposite) if opposite else None
                expected.append(distance if value or distance is None else -distance)
            self.assertEqual(oracle.signed_chebyshev(mask,3,3),expected,"mask bits="+str(bits))

    def test_floorhalf_nearest_preserves_bytes(self):
        self.assertEqual(oracle.floorhalf_nearest(bytes(range(35)), 7, 5),
                         (bytes([0,2,4,14,16,18]), 3, 2))
        self.assertEqual(oracle.floorhalf_nearest(bytes(range(24)), 6, 4),
                         (bytes([0,2,4,12,14,16]), 3, 2))
        self.assertEqual(oracle.nearest_resize(bytes(range(7)), 7, 1, 4, 1),
                         bytes([0,1,3,5]))
        with self.assertRaises(ValueError):
            oracle.floorhalf_nearest(bytes([1]), 1, 1)

    def test_domain_margin_and_strata_recomputed(self):
        mask = bytes([255] * (13 * 13))
        pool = [self.candidate(0, 2, 2), self.candidate(1, 6, 6)]
        self.assertEqual(oracle.classify(pool, mask, 13, 13), ["S", "I"])
        # One nonzero pixel expands exactly four pixels; NMS margin is two.
        single = bytearray(15 * 15)
        single[7 * 15 + 7] = 1
        self.assertEqual(oracle.classify([self.candidate(0, 3, 7), self.candidate(1, 7, 7)],
                                         bytes(single), 15, 15), ["S", "S"])
        for x, y in [(2,7), (1,7), (13,7)]:
            with self.assertRaises(ValueError):
                oracle.classify([self.candidate(0, x, y)], bytes(single), 15, 15)
        with self.assertRaises(ValueError):
            oracle.classify([self.candidate(0, 5, 5)], bytes(225), 15, 15)

    def test_global_distances_quota_scheduler_and_pooled_ablation(self):
        pool, strata = self.pool(), ["S", "I", "I", "S", "S", "I"]
        balanced = oracle.sample(pool, strata, 5, "B")
        self.assertEqual(self.ordinals(balanced), [0,1,3,5,4])
        self.assertEqual([r["minimum_squared_distance"] for r in balanced["trace"]],
                         [0,100,100,50,50])
        self.assertEqual([r["has_distance"] for r in balanced["trace"]],
                         [False,True,True,True,True])
        self.assertEqual(balanced["selected_indices"], [0,1,3,5,4])
        d = balanced["diagnostics"]
        self.assertEqual([d["target"], d["initial_contour_quota"], d["initial_interior_quota"],
                          d["final_contour_quota"], d["final_interior_quota"]], [5,3,2,3,2])
        pooled = oracle.sample(pool, strata, 5, "P")
        self.assertEqual(self.ordinals(pooled), [0,4,1,3,5])
        self.assertFalse(pooled["diagnostics"]["quotas_apply"])
        self.assertEqual(pooled["diagnostics"]["final_contour_quota"], 0)

    def test_t_based_small_pool_quotas_and_borrowing(self):
        pool = [self.candidate(i, i, magnitude=10-i) for i in range(5)]
        for budget in [5,16,32]:
            result = oracle.sample(pool, ["S","I","I","I","I"], budget, "B")
            self.assertEqual(self.ordinals(result), [0,4,2,1,3])
            d = result["diagnostics"]
            self.assertEqual([d["initial_contour_quota"], d["initial_interior_quota"],
                              d["final_contour_quota"], d["final_interior_quota"],
                              d["borrowed_into_contour"], d["borrowed_into_interior"]],
                             [3,2,1,4,0,2])
        for strata, final, borrowed in [(["S"]*5,[5,0],[2,0]), (["I"]*5,[0,5],[0,3])]:
            d = oracle.sample(pool, strata, 32, "B")["diagnostics"]
            self.assertEqual([d["final_contour_quota"], d["final_interior_quota"]], final)
            self.assertEqual([d["borrowed_into_contour"], d["borrowed_into_interior"]], borrowed)

    def test_insufficient_features_still_reports_quotas(self):
        for n in range(5):
            pool = [self.candidate(i, i) for i in range(n)]
            for mode in ["B", "P"]:
                result = oracle.sample(pool, ["S"] * n, 32, mode)
                self.assertEqual(result["status"], "insufficient_features")
                self.assertEqual(result["selected"], [])
                self.assertEqual(result["diagnostics"]["target"], n)
                self.assertEqual(result["diagnostics"]["final_contour_quota"], n if mode == "B" else 0)

    def test_exact_full_budgets_16_32(self):
        pool = [self.candidate(i, i, magnitude=100-i) for i in range(40)]
        for budget in [16,32]:
            result = oracle.sample(pool, ["S"]*20 + ["I"]*20, budget, "B")
            self.assertEqual(len(result["selected"]), budget)
            self.assertEqual(len(set(self.ordinals(result))), budget)
            self.assertEqual(result["diagnostics"]["selected_contour"], budget//2)
            self.assertEqual(result["diagnostics"]["selected_interior"], budget//2)

    def test_magnitude_ordinal_ties_duplicate_positions_theta_bits(self):
        pool = [self.candidate(i, 3, 4, 1, i % 8, 0x7FC01234 + i) for i in [9,2,7,4,6]]
        result = oracle.sample(pool, ["S"]*5, 5, "P")
        self.assertEqual(self.ordinals(result), [2,4,6,7,9])
        self.assertEqual([r["minimum_squared_distance"] for r in result["trace"]], [0]*5)
        self.assertEqual(result["selected"][0]["theta_bits"], 0x7FC01236)
        self.assertEqual(result["selected"][0]["label"], 2)
        self.assertEqual(result["selected_indices"], [1,3,4,2,0])

    def test_rejects_invalid_fields_duplicate_ordinal_and_overflow(self):
        valid = [self.candidate(i, i) for i in range(5)]
        for field, value in [("ordinal", -1), ("ordinal", 2**32), ("x", 2**31),
                             ("y", -2**31-1), ("label", 8), ("label", -1),
                             ("magnitude_bits", 0x7F800000), ("magnitude_bits", 0x7FC00001),
                             ("theta_bits", 2**32), ("ordinal", True)]:
            fields = dict(valid[0].__dict__)
            fields[field] = value
            bad = [oracle.Candidate(**fields)] + valid[1:]
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                oracle.sample(bad, ["S"]*5, 5, "P")
        with self.assertRaises(ValueError):
            oracle.sample([valid[0]] + valid, ["S"]*6, 5, "B")
        wide = [self.candidate(0,-2**31,-2**31,10), self.candidate(1,2**31-1,0),
                self.candidate(2,0,0), self.candidate(3,1,1), self.candidate(4,2,2)]
        with self.assertRaises(OverflowError):
            oracle.sample(wide, ["S"]*5, 5, "P")
        sum_wide = [self.candidate(0,-2**31,-2**31,10)] + [
            self.candidate(i+1,i,i) for i in range(4)]
        with self.assertRaises(OverflowError):
            oracle.sample(sum_wide, ["S"]*5, 5, "P")
        for budget, mode, strata in [(0,"P",["S"]*5), (5,"X",["S"]*5),
                                     (5,"P",["S"]*4), (5,"P",["X"]*5)]:
            with self.assertRaises(ValueError):
                oracle.sample(valid, strata, budget, mode)

    def test_canonical_record_bytes_and_real_pool_contract(self):
        pool = [self.candidate(0,2,2,1,7,0x7FC00001), self.candidate(1,3,2,2,0,0x80000000)]
        expected = bytes.fromhex("000000000200000002000000070000803f0100c07f"
                                 "010000000300000002000000000000004000000080")
        self.assertEqual(oracle.encode_candidates(pool), expected)
        self.assertEqual(oracle.decode_candidates(expected), pool)
        for payload in [expected[:-1], expected + b"x"]:
            with self.assertRaises(ValueError):
                oracle.decode_candidates(payload)
        for bad in [[pool[1],pool[0]], [pool[0],self.candidate(1,2,2)],
                    [pool[0],self.candidate(2,3,2)]]:
            with self.assertRaises(ValueError):
                oracle.validate_real_pool(bad)

    def numeric_spec(self):
        # All coordinates inside full 13x13 mask; canonical source order.
        pool = [self.candidate(0,2,2,10), self.candidate(1,10,2,9),
                self.candidate(2,6,6,8), self.candidate(3,2,10,7),
                self.candidate(4,10,10,6)]
        payload = b"".join(struct.pack("<IiiBII", c.ordinal,c.x,c.y,c.label,
                                        c.magnitude_bits,c.theta_bits) for c in pool)
        mask = bytes([255]*169)
        return {"candidate_hex":payload.hex(),"mask_hex":mask.hex(),"width":13,"height":13,
                "budget":32,"expected_count":5,"candidate_sha256":hashlib.sha256(payload).hexdigest(),
                "mask_sha256":hashlib.sha256(mask).hexdigest()}

    def test_audit_checks_entire_payload_and_claims(self):
        spec = self.numeric_spec()
        result = oracle.audit_numeric(spec)
        self.assertEqual(result["strata"], ["S","S","I","S","S"])
        self.assertEqual(self.ordinals(result["B"]), [0,2,1,3,4])
        self.assertEqual(self.ordinals(result["P"]), [0,4,1,3,2])
        for name in ["P","B"]:
            spec.setdefault("claims", {})[name] = result[name]
        oracle.audit_numeric(spec)
        for kind in ["candidate", "mask"]:
            tamper = copy.deepcopy(spec)
            payload = bytearray.fromhex(tamper[kind+"_hex"])
            payload[-1] ^= 1
            tamper[kind+"_hex"] = payload.hex()
            with self.assertRaises(ValueError):
                oracle.audit_numeric(tamper)
        tamper = copy.deepcopy(spec)
        tamper["candidate_hex"] = tamper["candidate_hex"][:-42]
        with self.assertRaises(ValueError):
            oracle.audit_numeric(tamper)
        # Saved claims cannot silently change order, quota, trace, or opaque bits.
        for change in ["schedule", "quota", "cross_distance", "theta", "missing"]:
            tamper = copy.deepcopy(spec)
            claim = tamper["claims"]["B"]
            if change == "schedule": claim["selected"][0:2] = reversed(claim["selected"][0:2])
            if change == "quota": claim["diagnostics"]["initial_contour_quota"] = 16
            if change == "cross_distance": claim["trace"][2]["minimum_squared_distance"] = 128
            if change == "theta": claim["selected"][0]["theta_bits"] = 123
            if change == "missing": del claim["selected_indices"]
            with self.subTest(change=change), self.assertRaises(ValueError):
                oracle.audit_numeric(tamper)

    def test_resize_claims_reject_rounding_threshold_and_blur_mutants(self):
        source = bytes([1,7,128,255,0,0,0] + [0]*7 + [7,0,1,0,255,0,0] + [0]*14)
        fixture = {"mask_hex":source.hex(),"width":7,"height":5,
                   "expected_hex":bytes([1,128,0,7,1,255]).hex()}
        oracle.verify_resize_fixture(fixture)
        for bad in [bytes([1,255,0,0,0,0]), bytes([0,128,0,0,0,255]), bytes([20]*6)]:
            wrong = dict(fixture, expected_hex=bad.hex())
            with self.assertRaises(ValueError):
                oracle.verify_resize_fixture(wrong)

    def test_cli_uses_only_self_contained_numeric_json(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            source = pathlib.Path(directory) / "literal.json"
            source.write_text(json.dumps(self.numeric_spec()), encoding="utf-8")
            run = subprocess.run([sys.executable,str(HERE/"numeric_oracle.py"),str(source)],
                                 capture_output=True,text=True,check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["candidate_count"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
