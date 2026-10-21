"""Copy the immutable V9 diagnostic snapshot and add a count-only center census."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'search_profile'

def sha(raw):return hashlib.sha256(raw).hexdigest()

def generate():
    base_manifest=json.loads((BASE/'source_manifest.json').read_text(encoding='utf-8'))
    assert base_manifest['git_head']=='6b7be69f96cffc1a914674691c6f20d80ea09106'
    target=HERE/'source';target.mkdir(exist_ok=True)
    manifest={'base_git_head':base_manifest['git_head'],'base_production_sha256':base_manifest['source_sha256'],
              'base_instrumented_sha256':{},'generated_sha256':{}}
    fixture=subprocess.check_output(['git','show','6b7be69:artifacts/search_optimization/fixtures.hpp'],cwd=HERE.parent.parent)
    (HERE/'fixtures_v9.hpp').write_bytes(fixture)
    manifest['base_fixture_git_path']='6b7be69:artifacts/search_optimization/fixtures.hpp'
    manifest['generated_sha256']['fixtures_v9.hpp']=sha(fixture)
    for name,expected in base_manifest['generated_sha256'].items():
        raw=(BASE/name).read_bytes()
        assert sha(raw)==expected,name
        manifest['base_instrumented_sha256'][name]=expected
        if name=='source/line2Dup.cpp':
            old=b'                ++level_profile.local_calls;'
            assert raw.count(old)==1
            raw=raw.replace(old,old+b'\n                ++level_profile.centers[std::make_pair(x / T, y / T)];',1)
        (HERE/name).write_bytes(raw)
        manifest['generated_sha256'][name]=sha(raw)
    raw=(BASE/'profile.hpp').read_bytes()
    manifest['base_instrumented_sha256']['profile.hpp']=sha(raw)
    old=b'#include <cstdint>'
    assert raw.count(old)==1
    raw=raw.replace(old,old+b'\n#include <map>\n#include <utility>',1)
    old=b'    int feature_count=0;'
    assert raw.count(old)==1
    raw=raw.replace(old,old+b'\n    std::map<std::pair<int,int>,std::uint64_t> centers;',1)
    (HERE/'profile.hpp').write_bytes(raw)
    manifest['generated_sha256']['profile.hpp']=sha(raw)
    (HERE/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':generate()
