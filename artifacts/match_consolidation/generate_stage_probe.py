"""Generate a private V10 copy that times both consolidations on identical candidates."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"artifacts/local_center_optimization/baseline"
OUT=Path(__file__).resolve().parent/"build/stage_source"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files={}
    for name in ("line2Dup.cpp","line2Dup.h","line2Dup_local.hpp","line2Dup_search.hpp","line2Dup_response.hpp","line2Dup_spread.hpp"):
        data=(BASE/name).read_bytes();files[name]={"original_sha256":hashlib.sha256(data).hexdigest().upper()}
        if name=="line2Dup.cpp":
            source=data.decode()
            original="""    std::sort(matches.begin(), matches.end());
    std::vector<Match>::iterator new_end = std::unique(matches.begin(), matches.end());
    matches.erase(new_end, matches.end());"""
            replacement="""    // Copies and instrumentation do not belong to the timed stages.
    std::vector<Match> old_matches = matches;
    diagnostic_last.input_count = matches.size();
    diagnostic_last.old_first = (++diagnostic_calls % 2) != 0;
    auto old_path = [&]() {
        const auto begin = std::chrono::steady_clock::now();
        std::sort(old_matches.begin(), old_matches.end());
        old_matches.erase(std::unique(old_matches.begin(), old_matches.end()), old_matches.end());
        diagnostic_last.old_ms = std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
    };
    auto new_path = [&]() {
        const auto begin = std::chrono::steady_clock::now();
        detail::consolidateMatches(matches);
        diagnostic_last.new_ms = std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
    };
    if (diagnostic_last.old_first) { old_path(); new_path(); }
    else { new_path(); old_path(); }
    diagnostic_last.old_count = old_matches.size();
    diagnostic_last.new_count = matches.size();"""
            if source.count(original)!=1:raise ValueError("V10 consolidation anchor changed")
            source=source.replace(original,replacement)
            anchor="namespace line2Dup\n{"
            declaration="""struct StageDiagnostic { double old_ms=0,new_ms=0; std::size_t input_count=0,old_count=0,new_count=0; bool old_first=false; };
static StageDiagnostic diagnostic_last;
static unsigned diagnostic_calls=0;
"""
            if source.count(anchor)!=1:raise ValueError("V10 namespace anchor changed")
            source=source.replace(anchor,declaration+anchor,1)
            source='#include "line2Dup_matches.hpp"\n'+source
            data=source.encode()
        (OUT/name).write_bytes(data)
        files[name]["generated_sha256"]=hashlib.sha256(data).hexdigest().upper()
    helper=(ROOT/"line2Dup_matches.hpp").read_bytes();(OUT/"line2Dup_matches.hpp").write_bytes(helper)
    files["line2Dup_matches.hpp"]={"current_sha256":hashlib.sha256(helper).hexdigest().upper()}
    (OUT/"manifest.json").write_text(json.dumps({"reference_commit":"c41f04762fb62ca5598f60e5d66ea9cfa2fbc2a0","files":files},indent=2)+"\n")
    print("Generated stage-only diagnostic; its API total includes extra work and must not be used as production latency")


if __name__=="__main__":main()
