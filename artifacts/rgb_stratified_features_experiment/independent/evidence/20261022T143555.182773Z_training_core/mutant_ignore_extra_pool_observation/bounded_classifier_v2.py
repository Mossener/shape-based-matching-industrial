"""Exact radius4 saved-candidate classification without full-image distance BFS.

This does not calculate or approximate a signed distance. It directly decides
the two predicates needed by the frozen experiment: dilation membership and
inside distance greater than four. All numeric_oracle.py BFS code is retained.
"""
import numeric_oracle


def classify(candidates,mask,width,height):
    numeric_oracle._mask(mask,width,height)
    numeric_oracle._validate_candidates(candidates)
    result=[]
    for candidate in candidates:
        x,y=candidate.x,candidate.y
        if not (2<=x<width-2 and 2<=y<height-2):
            raise ValueError('candidate outside original two-pixel NMS margin')
        center_inside=mask[y*width+x]!=0
        found_opposite=False
        for neighbor_y in range(y-4,y+5):
            for neighbor_x in range(x-4,x+5):
                inside=(0<=neighbor_x<width and 0<=neighbor_y<height and
                        mask[neighbor_y*width+neighbor_x]!=0)
                if inside != center_inside:
                    found_opposite=True
                    break
            if found_opposite: break
        if center_inside:
            result.append('S' if found_opposite else 'I')
        elif found_opposite:
            result.append('S')
        else:
            raise ValueError('candidate outside radius4 mask domain')
    return result


def verify_equivalence_fixture():
    """Small mandatory runtime gate; full randomized equivalence is in tests."""
    width,height=17,15
    masks=[bytes(width*height),bytes([7]*(width*height)),
           bytes(1 if x==8 and y==7 else 0 for y in range(height) for x in range(width)),
           bytes(0 if 5<=x<=11 and 4<=y<=10 else 128 for y in range(height) for x in range(width)),
           bytes(255 if (x*19+y*7)%11==0 else 0 for y in range(height) for x in range(width))]
    compared=0
    for mask in masks:
        distances=numeric_oracle.signed_chebyshev(mask,width,height)
        valid=[]; expected=[]
        for y in range(2,height-2):
            for x in range(2,width-2):
                candidate=numeric_oracle.Candidate(compared,x,y,0,0x3F800000,0)
                compared+=1
                distance=distances[y*width+x]
                if distance is None or distance < -4:
                    try: classify([candidate],mask,width,height)
                    except ValueError: pass
                    else: raise ValueError('bounded classifier accepted BFS-outside fixture')
                else:
                    valid.append(candidate); expected.append('S' if distance<=4 else 'I')
        if classify(valid,mask,width,height)!=expected:
            raise ValueError('bounded classifier differs from original full BFS fixture')
    return {'passed':True,'mask_cases':len(masks),'compared_candidate_positions':compared,
            'original_signed_chebyshev_preserved':True}
