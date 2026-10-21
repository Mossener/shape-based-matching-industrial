"""Preserve and reject corrupted numeric-input fixtures without changing runs.

The synthetic input layer substitutes one decoded JSON/CSV object after normal
SHA attestation of original bytes, so semantic checks are tested separately from
the byte-integrity guard. Original run files are never edited.
"""
import argparse
import copy
import csv
import gzip
import io
import json
from pathlib import Path

import audit_results as audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', type=Path, required=True)
    parser.add_argument('--development', type=Path, required=True)
    parser.add_argument('--timing', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_directory
    audit.require(not output.exists(), 'Mutation output must be new')
    output.mkdir(parents=True)
    original_load, original_table = audit.load, audit.table
    outcomes = []

    def fixture(name, path, transform, expected, kind='json', timing=False):
        read = original_load if kind == 'json' else original_table
        changed = copy.deepcopy(read(path))
        transform(changed)
        directory = output/name
        directory.mkdir()
        (directory/'override.json').write_text(json.dumps(changed, indent=2)+'\n')
        (directory/'fixture.json').write_text(json.dumps(dict(
            original_input=str(path.resolve()), original_sha256=audit.sha(path),
            injection='Decoded '+kind+' numeric input only; original provenance files and image bytes unchanged',
            expected_rejection=expected), indent=2)+'\n')
        def overlay(candidate):
            return changed if Path(candidate).resolve() == path.resolve() else read(candidate)
        if kind == 'json':
            audit.load = overlay
        else:
            audit.table = overlay
        error = None
        try:
            if timing:
                audit.audit_timing(args.timing, args.development)
            else:
                audit.quality(args.pilot, 'pilot')
        except ValueError as caught:
            error = str(caught)
            audit.require(expected in error, 'Unexpected rejection for '+name+': '+error)
        finally:
            audit.load, audit.table = original_load, original_table
        audit.require(error is not None, 'Mutation accepted: '+name)
        result = dict(case=name, expected_rejection=expected, observed_rejection=error, rejected=True)
        (directory/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        outcomes.append(result)

    summary = args.pilot/'comparison_metrics.json'
    fixture('allgt_tp', summary, lambda m: m['baseline']['allGT'].__setitem__('tp', 1), 'None/baseline/allGT tp')
    fixture('eligible_fp', summary, lambda m: m['auto']['visibility_ge_0_5'].__setitem__('fp', 3), 'None/auto/visibility_ge_0_5 fp')
    fixture('retention_new_gt', summary, lambda m: m['auto'].__setitem__('new_gt', 1), 'None/auto retention new_gt')
    fixture('selected_box', args.pilot/'selected_detections.csv',
            lambda rows: rows[0].__setitem__('bbox_x', str(float(rows[0]['bbox_x'])+1)), 'Selected identities/order', kind='csv')
    fixture('geometry_fit', args.pilot/'geometry.csv',
            lambda rows: rows[0].__setitem__('old_declared_fit', str(1-int(rows[0]['old_declared_fit']))), 'Geometry derived fit mismatch', kind='csv')
    timing_summary = args.timing/'timing_metrics.json'
    fixture('timing_percentile', timing_summary,
            lambda m: m['variants'][0].__setitem__('match_median_ms', m['variants'][0]['match_median_ms']+1),
            "Timing variant ('baseline', 'fallback') match_median_ms", timing=True)
    fixture('timing_ratio', timing_summary,
            lambda m: m['paired_ratios_auto_over_baseline'][0].__setitem__('external_call_median', 1),
            'Paired timing fallback external_call_median', timing=True)
    fixture('timing_own_reference_count', args.timing/'timing_samples.csv',
            lambda rows: rows[0].__setitem__('raw', str(int(rows[0]['raw'])+1)),
            'Timed counts differ from own arm/path reference', kind='csv', timing=True)
    fixture('timing_rotating_order', args.timing/'timing_samples.csv',
            lambda rows: rows[0].__setitem__('order', '1'),
            'Order/warmup schedule changed', kind='csv', timing=True)

    # A real synthetic gzip+manifest pair exercises the raw-to-box relationship.
    directory = output/'raw_box_origin'
    directory.mkdir()
    verified = original_load(args.pilot/'verified_inputs.json')
    frame = next(f for f in verified['frames'] if f['raw_count'] > 0)
    source = Path(frame['fallback_raw'])
    rows = list(csv.DictReader(io.StringIO(gzip.decompress(source.read_bytes()).decode())))
    rows[0]['bbox_y'] = str(float(rows[0]['bbox_y'])+1)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    contents = stream.getvalue().encode()
    path = directory/'synthetic_fallback_raw.csv.gz'
    path.write_bytes(gzip.compress(contents, mtime=0))
    manifest = original_load(str(source).replace('_raw.csv.gz', '_raw_manifest.json'))
    manifest.update(path=str(path.resolve()), compressed_bytes=path.stat().st_size, uncompressed_bytes=len(contents))
    Path(str(path).replace('_raw.csv.gz', '_raw_manifest.json')).write_text(json.dumps(manifest, indent=2)+'\n')
    metadata = original_load(Path(verified['training_directory'])/'template_metadata.json')['templates']
    meta = {(m['class_id'], m['template_id']): m for m in metadata}
    error = None
    try:
        audit.raw(path, frame, 'fallback', meta)
    except ValueError as caught:
        error = str(caught)
        audit.require(error == 'Box/source-origin mismatch', 'Wrong raw-box rejection')
    audit.require(error is not None, 'Mutated raw box accepted')
    result = dict(case='raw_box_origin', expected_rejection='Box/source-origin mismatch', observed_rejection=error, rejected=True)
    (directory/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    outcomes.append(result)
    # Byte-integrity rejection is separate from semantic fixture injection.
    fixture('output_sha', args.pilot/'execution_provenance.json',
            lambda m: m['output_sha256'].__setitem__('candidate_equality.csv', '0'*64), 'Changed output: candidate_equality.csv')
    report = dict(passed=True, cases=len(outcomes), rejected=len(outcomes), results=outcomes,
                  original_run_files_changed=0, dataset_image_reads=0, image_decodes=0, matcher_calls=0,
                  auditor_sha256=audit.sha(Path(audit.__file__)), test_script_sha256=audit.sha(Path(__file__)))
    (output/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(outcomes), rejected=len(outcomes), image_decodes=0, matcher_calls=0)))


if __name__ == '__main__':
    main()
