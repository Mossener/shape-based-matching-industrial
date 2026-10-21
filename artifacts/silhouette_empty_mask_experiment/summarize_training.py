"""Quick numeric training summary, separate from the root serialized-bank audit."""
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path

import native_provenance as p

HERE=Path(__file__).resolve().parent
RUN=HERE/'run_training_v1'


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    output=RUN/'numeric_quick_summary.json';p.require(not output.exists(),'Quick summary must be fresh')
    bank_file=RUN/'BANK_FREEZE.json';bank=json.loads(bank_file.read_text())
    p.require(bank['native_exit_zero'] is True and bank['training_attempts_complete'] is True and bank['comparison_feasible'] is True,'Complete feasible native training required')
    for pin in bank['files']:
        p.check_pin(pin)
    objects=[];total=0
    for obj in [1,2,5,8,12,17]:
        directory=RUN/f'native/obj{obj}';attempts=rows(directory/'template_attempts.csv');features=rows(directory/'feature_geometry.csv')
        meta=json.loads((directory/'template_metadata.json').read_text())['templates']
        p.require(len(attempts)==3456 and len(features)==6912 and len(meta)==3456,'Complete native per-object counts changed')
        p.require(all(int(r['success'])==1 and r['error']=='' for r in attempts),'Unexpected failed native attempt')
        p.require([int(r['template_id']) for r in attempts]==list(range(3456)),'Successful template IDs are not dense')
        p.require(len({(int(r['training_image']),int(r['angle']),float(r['scale'])) for r in attempts})==3456,'Duplicate trained pose')
        by_pose={(int(r['training_image']),int(r['angle']),float(r['scale'])):r for r in attempts}
        geometry=['source_crop_x','source_crop_y','source_crop_w','source_crop_h','canvas','mask_x','mask_y','mask_w','mask_h']
        for original in [HERE/f'frozen_inputs/obj{obj}/rgb_training/template_attempts.csv',HERE/f'frozen_inputs/source_only_training/obj{obj}/template_attempts.csv']:
            originals=rows(original);p.require(len(originals)==3456,'Original pose coverage changed')
            for old in originals:
                actual=by_pose[(int(old['training_image']),int(old['angle']),float(old['scale']))]
                p.require(all(int(actual[key])==int(old[key]) for key in geometry),'Training pose geometry differs from original')
        distributions={};edges={};canvases={}
        for level in [0,1]:
            layer=[r for r in features if int(r['level'])==level];p.require(len(layer)==3456,'Missing successful feature layer')
            p.require([int(r['template_id']) for r in layer]==list(range(3456)),'Feature layer template coverage differs')
            counts=Counter(int(r['actual_features']) for r in layer)
            distributions[str(level)]=dict(minimum=min(counts),maximum=max(counts),histogram=dict(sorted(counts.items())))
            edges[str(level)]=dict(minimum=min(int(r['min_canvas_edge_distance']) for r in layer),maximum=max(int(r['min_canvas_edge_distance']) for r in layer))
            canvases[str(level)]=dict(minimum=min(int(r['canvas_width']) for r in layer),maximum=max(int(r['canvas_width']) for r in layer))
            for row in layer:
                x,y,w,h=[int(row[k]) for k in ['tl_x','tl_y','canvas_width','canvas_height']]
                a,b,c,d=[int(row[k]) for k in ['min_absolute_x','min_absolute_y','max_absolute_x','max_absolute_y']]
                p.require(a==x+int(row['min_x']) and b==y+int(row['min_y']) and c==x+int(row['max_x']) and d==y+int(row['max_y']),'Feature diagnostic absolute/local identity differs')
                p.require(0<=a<=c<w and 0<=b<=d<h and int(row['min_canvas_edge_distance'])==min(a,b,w-1-c,h-1-d),'Feature diagnostic edge differs or truly outside canvas')
                attempt=attempts[int(row['template_id'])]
                p.require(int(row['actual_features'])==int(attempt[f'features_l{level}']),'Attempt/layer feature count differs')
                if level==0:
                    p.require(x==int(attempt['templ_tl_x']) and y==int(attempt['templ_tl_y']),'L0 origin differs from attempt')
                p.require(w==h==int(attempt['canvas'])//(1<<level),'Actual recorded layer canvas differs from frozen floor-half V11 geometry')
        objects.append(dict(object_id=obj,attempts=3456,successful_templates=3456,failed_attempts=0,
                            feature_layers=6912,feature_counts=distributions,minimum_canvas_edge_distance=edges,canvas_dimensions=canvases,
                            all_rgb_and_source_only_pose_geometries_equal=True))
        total+=len(attempts)
    result=dict(passed=True,scope='Quick CSV/metadata count and geometry summary only; does not reparse serialized bank features and is not root independent audit',
                bank_freeze=p.file_pin(bank_file),summary=p.file_pin(RUN/'native/training_summary.json'),objects=objects,
                attempts=total,successful_templates=total,failed_attempts=0,feature_layers=total*2,
                dataset_image_reads=0,matcher_calls=0,development_image_decodes=0,summarizer=p.file_pin(Path(__file__)))
    output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,attempts=total,successful_templates=total,feature_layers=total*2,dataset_image_reads=0,matcher_calls=0)))


if __name__=='__main__':
    main()
