"""Inventory this numeric-only classifier directory; no Git or native operations."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE/'PUBLICATION_INVENTORY_V25.json'


def main():
    if OUTPUT.exists():
        raise ValueError('Fresh publication inventory required')
    files = []
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path == OUTPUT:
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(HERE) or path.suffix not in ('.py', '.json', '.csv', '.md', '.txt'):
            raise ValueError('Unexpected publication member: '+str(path))
        raw = path.read_bytes()
        files.append(dict(path=path.relative_to(ROOT).as_posix(), size_bytes=len(raw),
                          sha256=hashlib.sha256(raw).hexdigest()))
    result = dict(status='numeric_classification_ready_for_root_review_and_publication',
                  scope='This classifier directory only; __pycache__ excluded; inventory itself excluded from its hash list',
                  files=files, file_count=len(files), total_bytes=sum(value['size_bytes'] for value in files),
                  includes_failed_preparation=True, includes_frozen_prior_reports=True,
                  includes_private_image_or_smd_bytes=False, includes_serialized_template_bank_bytes=False,
                  dataset_image_bytes_opened=0, native_calls=0, git_commands=0,
                  accuracy_improvement_claim=False, speed_claim=False,
                  primary_report='AUDIT_ADOPTION.md',
                  paired_215='complete_pre_20261022_v1/paired_215.csv',
                  independent_audit_binding='audit_binding_20261022_v1.json')
    OUTPUT.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(completed=True, file_count=result['file_count'], total_bytes=result['total_bytes'],
                          inventory_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
