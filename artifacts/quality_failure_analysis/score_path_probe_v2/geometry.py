"""Pure diagnostic geometry and independent scalar LM fixture model."""
import math


def physical_anchor(box, silhouette, origin):
    return (box[0] + 64 - silhouette[0] + origin[0],
            box[1] + 64 - silhouette[1] + origin[1])


def neighbors(x, y, t=4, offset=1):
    def axis(value):
        q = (value-offset) / t
        return sorted({math.floor(q)*t+offset, math.ceil(q)*t+offset})
    return [(xx, yy) for yy in axis(y) for xx in axis(x)]


def parents(point, size, template_size, coarse_t=8, fine_t=4, fine_offset=1,
            coarse_offset=3, border_cells=8):
    width, height = size
    template_width, template_height = template_size
    max_x = width-template_width-border_cells*fine_t
    max_y = height-template_height-border_cells*fine_t
    if (point[0]-fine_offset) % fine_t or (point[1]-fine_offset) % fine_t:
        raise ValueError('Off-grid point has no native fine-cell identity')
    def cxxdiv(value):
        return (1 if value >= 0 else -1)*(abs(value)//fine_t)
    result = []
    coarse_w, coarse_h = (width//2)//coarse_t, (height//2)//coarse_t
    for row in range(coarse_h):
        center_y = row*coarse_t+coarse_offset
        start_y = min(max(center_y*2+1, border_cells*fine_t), max_y)
        base_y = (cxxdiv(start_y)-border_cells)*fine_t
        if not base_y+15*fine_t+fine_offset >= point[1] or base_y+fine_offset > point[1]:
            continue
        for col in range(coarse_w):
            center_x = col*coarse_t+coarse_offset
            start_x = min(max(center_x*2+1, border_cells*fine_t), max_x)
            base_x = (cxxdiv(start_x)-border_cells)*fine_t
            if base_x+15*fine_t+fine_offset >= point[0] and base_x+fine_offset <= point[0]:
                result.append(dict(row=row, col=col, coarse_x=center_x, coarse_y=center_y,
                                   base=(base_x, base_y), start=(start_x, start_y)))
    return result


def coarse_values(lm, features, size, template_size, t):
    width, height = size
    w, h = width//t, height//t
    wf, hf = (template_size[0]-1)//t+1, (template_size[1]-1)//t+1
    count = (h-hf)*w+(w-wf)+1
    result = [0]*(h*w)
    columns = len(lm[0][0])
    for x, y, label in features:
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        row = (y % t)*t+(x % t)
        column = (y//t)*w+x//t
        flat = sum(lm[label], [])
        for index in range(count):
            at = row*columns+column+index
            if not 0 <= at < len(flat):
                raise ValueError('coarse native LM read outside actual storage')
            result[index] += flat[at]
    return result


def local_values(lm, features, size, base, t):
    width, height = size
    w = width//t
    result = [0]*256
    skipped = []
    for index, (x, y, label) in enumerate(features):
        x += base[0]; y += base[1]
        if x < 0 or y < 0 or x >= width or y >= height:
            skipped.append(index)
            continue
        row = (y % t)*t+(x % t)
        column = (y//t)*w+x//t
        flat = sum(lm[label], [])
        for rr in range(16):
            for cc in range(16):
                at = row*len(lm[label][0])+column+rr*w+cc
                if not 0 <= at < len(flat):
                    raise ValueError('local LM read outside flattened memory')
                result[rr*16+cc] += flat[at]
    return result, skipped


def physical_raw(lm, features, size, match, t, offset=1):
    width, height = size
    origin = (match[0]-offset, match[1]-offset)
    total = 0
    w = width//t
    for x, y, label in features:
        x += origin[0]; y += origin[1]
        if x < 0 or y < 0 or x >= width or y >= height:
            return None
        row = (y % t)*t+(x % t)
        column = (y//t)*w+x//t
        total += lm[label][row][column]
    return total


def winner(values):
    best = 0
    row = col = -1
    for index, value in enumerate(values):
        if value > best:
            best = value
            row, col = divmod(index, 16)
    return dict(raw=best, row=row, col=col, ties=values.count(best))
