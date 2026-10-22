"""Verify the sibling metadata closure without opening dataset images."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify() -> dict:
    closure = json.loads((HERE / "INPUT_CLOSURE.json").read_text(encoding="utf-8"))
    if closure.get("version") != "rgb_empty_mask_input_closure_v1":
        raise RuntimeError("unexpected RGB empty-mask closure version")
    if closure.get("protocol_sha256") != sha256(HERE / "PROTOCOL.json"):
        raise RuntimeError("protocol changed after input closure")
    if closure.get("private_source_freeze_sha256") != sha256(HERE / "PRIVATE_SOURCE_FREEZE.json"):
        raise RuntimeError("private source freeze changed after input closure")
    for relative, pin in closure.get("private_files", {}).items():
        path = HERE / relative
        if not path.is_file():
            raise RuntimeError(f"missing frozen metadata member: {relative}")
        if path.stat().st_size != pin["bytes"] or sha256(path) != pin["sha256"]:
            raise RuntimeError(f"frozen metadata member changed: {relative}")
    if closure.get("image_files_opened") != 0 or closure.get("image_decodes") != 0:
        raise RuntimeError("metadata closure reports image access")
    if closure.get("matcher_calls") != 0:
        raise RuntimeError("metadata closure reports matcher calls")
    return {
        "passed": True,
        "private_file_count": len(closure.get("private_files", {})),
        "image_files_opened": 0,
        "image_decodes": 0,
        "matcher_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
