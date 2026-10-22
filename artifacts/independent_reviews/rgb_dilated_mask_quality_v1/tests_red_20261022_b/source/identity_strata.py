"""Cross frozen V22/V27/current GT identities without images or native execution."""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OBJECTS = [1, 2, 5, 8, 12, 17]
HEAD = ['object_id', 'scene', 'image', 'metric', 'gt_id']
OLD_HEADER = HEAD + ['rgb_detected', 'binary_detected', 'same_pose_if_both']
NEW_HEADER = HEAD + ['rgb_control_detected', 'rgb_dilated_mask_detected', 'same_pose_if_both']
STRATA = {(1, 1): 'prior_both', (1, 0): 'prior_rgb_only', (0, 1): 'prior_binary_only', (0, 0): 'prior_neither'}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def frozen_retention(experiment, old, reader=None, treatment_name='rgb_dilated_mask_detected'):
    run = ROOT / 'artifacts' / experiment / 'run_quality_development_v1'
    freeze_path = run / 'QUALITY_STAGE_FREEZE.json'
    freeze_data = reader.read(freeze_path) if reader else freeze_path.read_bytes()
    freeze = json.loads(freeze_data)
    need(freeze['stage'] == 'development' and freeze['completed'] is True and
         freeze['actual_matcher_calls'] == 9600 and freeze['native_exit_code'] == 0,
         'Incomplete quality stage')
    path = run / 'native/gt_retention.csv'
    data = reader.read(path) if reader else path.read_bytes()
    records = [p for p in freeze['files'] if Path(p['path']).resolve() == path.resolve()]
    need(len(records) == 1 and records[0]['bytes'] == len(data) and records[0]['sha256'] == digest(data),
         'GT retention does not match its stage freeze')
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    need(reader.fieldnames == (OLD_HEADER if old else HEAD+['rgb_control_detected', treatment_name, 'same_pose_if_both']), 'GT retention schema differs')
    rows = {}
    for row in reader:
        key = tuple(int(row[k]) if k != 'metric' else row[k] for k in HEAD)
        need(key not in rows and key[0] in OBJECTS and key[1] not in [11, 14, 15, 16, 17, 18, 19, 20] and
             key[3] in ('allGT', 'eligible'), 'Unexpected/duplicate GT identity')
        rgb_name, treatment_name = ('rgb_detected', 'binary_detected') if old else ('rgb_control_detected', treatment_name)
        rgb, treatment, pose = (int(row[k]) for k in [rgb_name, treatment_name, 'same_pose_if_both'])
        need(rgb in (0, 1) and treatment in (0, 1) and
             (pose in (0, 1) if rgb and treatment else pose == -1), 'GT indicator/pose value differs')
        rows[key] = (rgb, treatment, pose)
    pins = [dict(path=str(path), bytes=len(data), sha256=digest(data)),
            dict(path=str(freeze_path), bytes=len(freeze_data), sha256=digest(freeze_data))]
    return rows, pins


def summarize(old, new):
    need(set(old) == set(new), 'Historical/current GT identity coverage differs')
    groups = defaultdict(Counter)
    identities = []
    for key in sorted(old):
        obj, scene, image, metric, gt_id = key
        prior_rgb, prior_binary, _ = old[key]
        control, treatment, same_pose = new[key]
        need(control == prior_rgb, 'V27 control changed historical RGB GT identity')
        stratum = STRATA[(prior_rgb, prior_binary)]
        state = 'retained' if control and treatment else 'lost' if control else 'gained' if treatment else 'neither'
        values = dict(identities=1, control_tp=control, treatment_tp=treatment, **{state: 1})
        for scope in ((metric, 'ALL', None, None), (metric, 'ALL', obj, None),
                      (metric, 'ALL', None, scene), (metric, 'ALL', obj, scene),
                      (metric, stratum, None, None),
                      (metric, stratum, obj, None), (metric, stratum, None, scene),
                      (metric, stratum, obj, scene)):
            groups[scope].update(values)
        identities.append(dict(object_id=obj, scene=scene, image=image, metric=metric, gt_id=gt_id,
                               stratum=stratum, control_detected=control, treatment_detected=treatment,
                               status=state, same_pose_if_both=same_pose))
    # Explicit zero rows prevent a missing stratum/object/scene cell from being
    # mistaken for omitted evidence. All scopes share the frozen GT universe.
    scenes = sorted({key[1] for key in old})
    for metric in ('allGT', 'eligible'):
        for stratum in ['ALL', *STRATA.values()]:
            for obj in [None, *OBJECTS]:
                for scene in [None, *scenes]:
                    groups.setdefault((metric, stratum, obj, scene), Counter())
    rows = []
    for (metric, stratum, obj, scene), counts in sorted(groups.items(), key=lambda item: str(item[0])):
        row = dict(metric=metric, stratum=stratum, object_id=obj, scene=scene,
                   **{key: counts[key] for key in ('identities', 'control_tp', 'treatment_tp',
                                                    'retained', 'lost', 'gained', 'neither')})
        row['net_tp'] = row['gained'] - row['lost']
        need(row['identities'] == sum(row[k] for k in ('retained', 'lost', 'gained', 'neither')) and
             row['treatment_tp'] - row['control_tp'] == row['net_tp'], 'Identity accounting differs')
        rows.append(row)
    prior_counts = {metric: {name: sum(k[3] == metric and STRATA[old[k][:2]] == name for k in old)
                             for name in STRATA.values()} for metric in ('allGT', 'eligible')}
    need(prior_counts['allGT'] == dict(prior_both=148, prior_rgb_only=67, prior_binary_only=59, prior_neither=126),
         'Protocol historical allGT strata differ')
    need(prior_counts['eligible'] == dict(prior_both=147, prior_rgb_only=62, prior_binary_only=56, prior_neither=109),
         'Historical eligible strata differ')
    return dict(prior_strata_counts=prior_counts, groups=rows), identities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    need(output.is_relative_to(HERE) and not output.exists(), 'Fresh contained output required')
    old, old_pins = frozen_retention('silhouette_empty_mask_experiment', True)
    previous, previous_pins = frozen_retention('rgb_empty_mask_experiment', False, treatment_name='rgb_empty_mask_detected')
    new, new_pins = frozen_retention('rgb_dilated_mask_experiment', False)
    report, identities = summarize_three(old, previous, new)
    output.mkdir()
    report.update(passed=True, control_identity_unchanged=True, matcher_calls=0, image_decodes=0,
                  source_sha256=digest(Path(__file__).read_bytes()), input_pins=old_pins + previous_pins + new_pins,
                  comparison='Current RGB dilated-mask versus frozen RGB control, crossed with V22 strata and V27 identity groups',
                  scope='Fixed development GT identities; no tuning, default promotion, or heldout confirmation')
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    with (output / 'identities.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(identities[0])); writer.writeheader(); writer.writerows(identities)
    print(json.dumps({k: report[k] for k in ('passed', 'control_identity_unchanged', 'matcher_calls', 'prior_strata_counts')}))


if __name__ == '__main__':
    main()
