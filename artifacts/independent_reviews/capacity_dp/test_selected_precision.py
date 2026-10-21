"""Selected CSV precision must be bound to the full-precision metrics record."""
import argparse
import copy
import json
from pathlib import Path

import audit_capacity as audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    audit.need(not args.output.exists(), 'Output must be new')
    args.output.mkdir(parents=True)
    score = 89.423080444335938
    full = dict(rank=0, class_id='tless_object_1', score=score, template_id=1064,
                bbox_obj=[142, 390, 76, 102], allGT_label='FP', allGT_id=-1,
                eligible_label='FP', eligibleGT_id=-1)
    csv_row = dict(scene='10', image='103', rank='0', class_id='tless_object_1',
                   score='89.4231', template_id='1064', bbox_x='142', bbox_y='390',
                   bbox_w='76', bbox_h='102', allGT_label='FP', allGT_id='-1',
                   eligible_label='FP', eligibleGT_id='-1')
    (args.output/'literal.json').write_text(json.dumps(dict(selected_csv=csv_row, metrics=full), indent=2)+'\n')
    try:
        checked = audit.checked_selected(csv_row, full)
        audit.need(checked['identity'][2] == audit.bits(score) and
                   checked['identity'][2] != audit.bits(csv_row['score']), 'Full precision identity not restored')
        # Two distinct binary32 scores collapse to the same six-digit CSV value.
        collision = copy.deepcopy(full)
        collision['score'] = 89.42308807373047
        audit.need(format(score, '.6g') == format(collision['score'], '.6g') == csv_row['score'], 'Literal rounding collision')
        collided = audit.checked_selected(csv_row, collision)
        rejected = []
        for name, action, expected in [
            ('collision_not_raw', lambda: audit.analyze([checked], [collided], [], []), 'Selected identity absent from raw'),
            ('wrong_csv_score', lambda: audit.checked_selected(dict(csv_row, score='89.4232'), full), 'Selected CSV/metrics score projection'),
            ('wrong_csv_template', lambda: audit.checked_selected(dict(csv_row, template_id='1065'), full), 'Selected CSV/metrics identity'),
            ('wrong_csv_label', lambda: audit.checked_selected(dict(csv_row, allGT_label='TP'), full), 'Selected CSV/metrics labels')]:
            try:
                action()
            except ValueError as error:
                audit.need(expected in str(error), 'Unexpected rejection '+name)
                rejected.append(dict(case=name, reason=str(error)))
            else:
                raise AssertionError('Fixture accepted '+name)
        result = dict(passed=True, exact_binary32_identity=True, rounding_collision_rejected=True,
                      rejected=rejected, auditor_sha256=audit.digest(Path(audit.__file__).read_bytes()),
                      test_sha256=audit.digest(Path(__file__).read_bytes()), image_files_opened=0, matcher_calls=0)
        (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error)), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
