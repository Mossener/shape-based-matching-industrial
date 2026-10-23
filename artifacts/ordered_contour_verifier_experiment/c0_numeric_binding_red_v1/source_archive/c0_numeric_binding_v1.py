"""Narrow C0 numeric projection contract, initially an intentional RED stub.

The pure projection entry point does not open files or import an evaluator.
Its eventual reader is restricted to C0 raw/manifest/own-metadata pins and the
three inherited projection CSV files. A projected GT is not an independent
reconstruction from official annotations.
"""

ARMS = ('rgb_control', 'rgb_pooled_features', 'rgb_stratified_features')
GT_HEADER = ('object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h').split(',')
PER_HEADER = ('object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,'
              'eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp').split(',')
SELECTED_HEADER = ('object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,'
                   'angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,'
                   'eligible_label,eligible_id').split(',')


def bind_projection(objects, frames, gt_rows, per_rows, selected_rows):
    """Bind exact tables to every object/frame, including zero/negative rows.

    Inputs are dictionaries from CSV parsing, with exact documented headers.
    Every known arm must have one per-frame row for every object/frame; GT is
    shared. Unknown identities/arms, malformed values, incomplete coverage,
    duplicate identities/ranks, or inconsistent labels/counts raise ValueError.
    Returned mappings contain only rgb_control and preserve full candidates,
    score float32 bits, pose bits, boxes, assignment labels and GT identities.

    RED preparation deliberately accepts everything and returns empty maps.
    Root must observe fixed behavioral test failures before implementation.
    """
    return dict(truth={}, per={}, selected={}, all_labels={}, eligible_labels={},
                retained_gt_ids=(), eligible_retained_gt_ids=(),
                gt_projection_independently_reconstructed=False)
