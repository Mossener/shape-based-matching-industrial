"""Audit recorded correctness and timing CSVs without rerunning matching."""
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def rows(path):
    with path.open(newline="",encoding="utf-8-sig") as stream:
        result=list(csv.DictReader(stream))
    if not result or any(None in r or any(v is None for v in r.values()) for r in result):
        raise ValueError(f"Empty or malformed CSV {path}")
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main():
    verification=rows(HERE/"full_verification.csv")
    current=[r for r in verification if r["implementation"]=="current_stable"]
    per_case=Counter((r["dataset"],r["image"]) for r in verification)
    actual_current={(r["dataset"],r["image"],int(r["pass"]),r["fused"],r["repeat"]) for r in current}
    expected_current={(d,i,p,str(f),str(r)) for d,i in per_case for p in range(4) for f in (0,1) for r in range(2)}
    failures={"semantic":sum(r["semantic_set_equal"]!="1" for r in verification),
              "canonical_oracle":sum(r["canonical_oracle_equal"]!="1" for r in verification),
              "current_full_ordered":sum(r["full_ordered_equal"]!="1" for r in current),
              "current_duplicates":sum(int(r["duplicate_count"])!=0 for r in current),
              "current_hash":sum(r["ordered_hash"]!=r["expected_ordered_hash"] for r in current),
              "missing_current_calls":len(expected_current-actual_current),
              "unexpected_current_calls":len(actual_current-expected_current),
              "incorrect_case_call_count":sum(n!=19 for n in per_case.values())}
    assert len(verification)==475 and len(current)==400 and len(per_case)==25
    assert len(actual_current)==400
    assert not any(failures.values()),failures
    index=json.loads((ROOT/"datasets/tless_tiny/index.json").read_text())
    paths=["datasets/tless_train_f32/templates_tless_object_1.yml.gz","datasets/tless_tiny/index.json",
           "LED/ku.smd","test/case1/test_templ.yaml","test/case1/test.png"]
    paths.extend(f"LED/{i}.bmp" for i in range(1,9))
    paths.extend("datasets/tless_tiny/"+r["rgb"] for r in index["test"] if r["split"]=="development")
    evidence=dict(calls=len(verification),current_calls=len(current),cases=len(per_case),
        cases_by_dataset=dict(Counter(d for d,i in per_case)),failures=failures,
        expected_rule="independent std::map(class,x,y,float_bits)->minimum template ID; output by score desc/id/class/y/x",
        input_sha256={p:sha(ROOT/p) for p in paths},csv_sha256=sha(HERE/"full_verification.csv"))
    (HERE/"verification_audit.json").write_text(json.dumps(evidence,indent=2)+"\n")
    total_path=HERE/"timing_v11_total.csv"
    stage_path=HERE/"timing_v11_stage.csv"
    if not total_path.exists() or not stage_path.exists():
        print(json.dumps({k:v for k,v in evidence.items() if k!="input_sha256"},indent=2));return
    total,stage=rows(total_path),rows(stage_path)
    assert len(total)==260 and len(stage)==130
    assert all(r["canonical_equal"]=="1" for r in total)
    assert Counter(r["phase"] for r in total)=={"cold":26,"warmup":52,"measured":182}
    assert Counter(r["phase"] for r in stage)=={"cold":13,"warmup":26,"measured":91}
    groups=defaultdict(list)
    for r in total:
        if r["phase"]=="measured":
            for metric in ("api_total_ms","search_ms"):
                groups[(r["dataset"],r["image"],r["implementation"],metric)].append(float(r[metric]))
    per_image=[dict(dataset=d,image=i,implementation=c,metric=m,samples=len(v),median=statistics.median(v))
               for (d,i,c,m),v in sorted(groups.items())]
    rolled=defaultdict(list)
    for r in per_image:rolled[(r["dataset"],r["implementation"],r["metric"])].append(r["median"])
    rollup=[dict(dataset=d,implementation=c,metric=m,images=len(v),mean_image_median=statistics.mean(v))
            for(d,c,m),v in sorted(rolled.items())]
    stage_group=defaultdict(list)
    for r in stage:
        if r["phase"]=="measured":
            stage_group[(r["dataset"],r["image"])].append(r)
    stage_image=[dict(dataset=d,image=i,samples=len(v),old_ms=statistics.median(float(r["old_ms"]) for r in v),
        new_ms=statistics.median(float(r["new_ms"]) for r in v),
        extra_ms=statistics.median(float(r["extra_ms"]) for r in v),
        input_count=statistics.median(int(r["input_count"]) for r in v),
        old_count=statistics.median(int(r["old_count"]) for r in v),
        new_count=statistics.median(int(r["new_count"]) for r in v)) for(d,i),v in sorted(stage_group.items())]
    for name,data in (("timing_summary_by_image.csv",per_image),("timing_summary_rollup.csv",rollup),("stage_summary_by_image.csv",stage_image)):
        with(HERE/name).open("w",newline="") as stream:
            writer=csv.DictWriter(stream,list(data[0]));writer.writeheader();writer.writerows(data)
    timing=dict(total_rows=len(total),stage_rows=len(stage),measured_total_rows=182,measured_stage_rows=91,
        cases=13,total_canonical_failures=0,method="CV1/OMP4 cold1/warm2/measured7; current/V10 order alternates",
        stage_scope="same pre-consolidation vector copied before timing; old/new order alternates; diagnostic API total is not reported",
        old_count_meaning="old std::unique depends on adjacency and can retain duplicates; count reductions are intentional correctness changes",
        rollup="mean of per-image medians; TLESS_dev timing uses two positive and two negative development images only",
        source_csv_sha256={p.name:sha(p) for p in(total_path,stage_path)})
    (HERE/"timing_audit.json").write_text(json.dumps(timing,indent=2)+"\n")
    print(json.dumps(timing,indent=2));print(json.dumps(rollup,indent=2));print(json.dumps(stage_image,indent=2))


if __name__=="__main__":main()
