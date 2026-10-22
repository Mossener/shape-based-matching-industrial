"""Independent strict numeric serialization contracts; no target imports."""
RAW_HEADER = 'scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')


def parse_raw(encoded, manifest, frame, variant, obj, metadata):
    return []


def exact_stream(left, right):
    return None


def check_selected(rows, frame, obj, arm, metadata, kept, labels, eligible_labels):
    return None


def check_retention(rows, expected):
    return None


def finish(counts):
    return dict(counts)


def check_numeric(actual, expected, where):
    return None
