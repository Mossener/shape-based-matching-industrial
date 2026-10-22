"""Read-only audit of an immutable V11 capture and its uninstrumented output."""
from pathlib import Path

CORE_REVISION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'


def read_trace(data, max_records=10_000_000, max_class_bytes=1_048_576,
               max_total_bytes=1_073_741_824):
    # API stub for the first manifest-integrity RED run.
    return {'input': [], 'output': []}


def audit_capture(manifest_path, protocol_path, repo_root):
    # API stub deliberately accepts a damaged fixture for semantic RED.
    return dict(verified=True, input_count=3, output_count=2,
                image_decodes=0, matcher_calls=0, performance_measurement=False)
