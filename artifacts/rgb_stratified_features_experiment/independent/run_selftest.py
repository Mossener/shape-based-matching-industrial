"""Preserve fresh isolated GREEN and intentional mutant RED evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SOURCES = ["numeric_oracle.py","test_numeric_oracle.py","run_selftest.py","README.md"]
MUTATIONS = [
    ("ordinal_tie", "-c.ordinal", "+c.ordinal",
     "Literals.test_magnitude_ordinal_ties_duplicate_positions_theta_bits"),
    ("initial_stratum", 'requested = "S"\n', 'requested = "I"\n',
     "Literals.test_global_distances_quota_scheduler_and_pooled_ablation"),
    ("cross_stratum_distance",
     "minimum = min(_distance_squared(c,candidates[chosen]) for chosen in selected) if selected else 0",
     "minimum = min(_distance_squared(c,candidates[chosen]) for chosen in selected if strata[chosen] == strata[index]) if any(strata[chosen] == strata[index] for chosen in selected) else 0",
     "Literals.test_global_distances_quota_scheduler_and_pooled_ablation"),
    ("nearest_rounding", "(y*height//destination_height)*width + x*width//destination_width",
     "min(height-1,(y*height+destination_height//2)//destination_height)*width + min(width-1,(x*width+destination_width//2)//destination_width)",
     "Literals.test_floorhalf_nearest_preserves_bytes"),
    ("threshold128", "(value != 0) == target_inside", "(value >= 128) == target_inside",
     "Literals.test_nonzero_values_and_zero_exterior"),
    ("K_based_quota_diagnostics", '"initial_contour_quota":initial_s',
     '"initial_contour_quota":(budget+1)//2 if mode == "B" else 0',
     "Literals.test_t_based_small_pool_quotas_and_borrowing"),
    ("unsigned64_distance", "INT64_MAX = (1 << 63) - 1", "INT64_MAX = (1 << 64) - 1",
     "Literals.test_rejects_invalid_fields_duplicate_ordinal_and_overflow"),
]


def pin(path):
    data = path.read_bytes()
    return {"path":str(path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}


def invoke(directory, label, test=None):
    command = [sys.executable,"-B",str(directory/"test_numeric_oracle.py")]
    if test:
        command.append(test)
    environment = dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
    run = subprocess.run(command,cwd=directory,capture_output=True,text=True,env=environment)
    stdout,stderr = directory/(label+".stdout.txt"),directory/(label+".stderr.txt")
    stdout.write_text(run.stdout,encoding="utf-8")
    stderr.write_text(run.stderr,encoding="utf-8")
    return {"command":command,"cwd":str(directory),"exit_code":run.returncode,
            "stdout":pin(stdout),"stderr":pin(stderr)},run


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = HERE/"evidence"/stamp
    baseline = evidence/"source_snapshot"
    baseline.mkdir(parents=True,exist_ok=False)
    before = {name:pin(HERE/name) for name in SOURCES}
    for name in SOURCES:
        shutil.copyfile(HERE/name,baseline/name)
    inputs = [pin(HERE.parent/name) for name in ("DESIGN.md","PROTOCOL.json")]
    green,green_run = invoke(baseline,"green")
    runs = []
    source = (baseline/"numeric_oracle.py").read_text(encoding="utf-8")
    for name,needle,replacement,test in MUTATIONS:
        if source.count(needle) != 1:
            raise RuntimeError("mutation anchor is not unique: " + name)
        directory = evidence/("mutant_"+name)
        directory.mkdir()
        shutil.copyfile(baseline/"test_numeric_oracle.py",directory/"test_numeric_oracle.py")
        (directory/"numeric_oracle.py").write_text(source.replace(needle,replacement,1),encoding="utf-8")
        receipt,run = invoke(directory,"red",test)
        receipt.update(name=name,mutated_source=pin(directory/"numeric_oracle.py"),
                       detected=run.returncode == 1 and "FAIL:" in run.stderr and "ERROR:" not in run.stderr)
        runs.append(receipt)
    after = {name:pin(HERE/name) for name in SOURCES}
    passed = green_run.returncode == 0 and all(r["detected"] for r in runs) and before == after
    receipt = {"schema":"independent_numeric_oracle_selftest_v1","utc":stamp,
               "synthetic_only":True,"native_calls":0,"image_reads":0,"bank_reads":0,
               "interpreter":{"executable":sys.executable,"version":sys.version,
                              "executable_pin":pin(Path(sys.executable))},
               "sources_before":before,"source_snapshots":[pin(baseline/n) for n in SOURCES],
               "requirements_observed":inputs,"green":green,"mutant_red":runs,
               "sources_after":after,"original_sources_unchanged":before == after,
               "all_checks_passed":passed,
               "limitations":["No real RGB or candidate completeness proof",
                              "No full training/shard/crop/bank/quality/timing acceptance",
                              "Missing-module RED is preserved separately in tests_red_missing.txt",
                              "K-based mutant alters recorded initial quota only; full quota algorithm is covered by literals"]}
    target = evidence/"RECEIPT.json"
    target.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":passed,"receipt":str(target),"mutants_detected":sum(r["detected"] for r in runs)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
