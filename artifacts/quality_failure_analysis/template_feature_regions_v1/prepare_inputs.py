"""Source/numeric input expansion; image bytes are never opened by this script."""
def need(v,m):
    if not v:raise ValueError(m)


def validate_pose_attempts(attempts,metadata,expected_keys):
    need(set(attempts)==set(metadata) and len(attempts)>=2,'Family set')
    objects={int(r['object_id']) for rows in attempts.values() for r in rows}
    need(len(objects)==1,'Object scope')
    obj=next(iter(objects));cls='tless_object_'+str(obj)
    output=[]
    for family in attempts:
        rows=attempts[family]; metas=metadata[family]; by_key={}
        for row in rows:
            key=(int(row['object_id']),int(row['training_image']),int(row['angle']),float(row['scale']))
            need(key in expected_keys and key not in by_key,'Missing/duplicate pose')
            need(row['success'] in ('0','1') and row['class_id']==cls,'Attempt schema')
            geometry=[int(row[k]) for k in ('source_crop_x','source_crop_y','source_crop_w','source_crop_h','canvas','mask_x','mask_y','mask_w','mask_h')]
            by_key[key]=dict(row=row,geometry=geometry)
        need(set(by_key)==set(expected_keys),'Incomplete pose product')
        by_meta={}
        need([int(m['template_id']) for m in metas]==list(range(len(metas))),'Metadata IDs are not dense')
        for meta in metas:
            need(meta['class_id']==cls and float(meta['angle']).is_integer(),'Metadata class/angle')
            key=(obj,int(meta['training_image_id']),int(meta['angle']),float(meta['scale']))
            need(key in expected_keys and key not in by_meta,'Missing/duplicate metadata')
            by_meta[key]=meta
        for key,cell in by_key.items():
            row=cell['row'];success=row['success']=='1'
            if success:
                meta=by_meta.get(key);need(meta is not None and int(row['template_id'])==int(meta['template_id']),'Success metadata ID')
                need(all(float(v).is_integer() for v in meta['warped_mask_bbox']),'Mask bbox integer geometry')
                expected=[int(float(v)) for v in (meta['warped_mask_bbox'])]
                need(cell['geometry'][5:9]==expected,'Mask bbox geometry mismatch')
                need(int(row['templ_tl_x'])==int(meta['tl_x']) and int(row['templ_tl_y'])==int(meta['tl_y']),'Template origin')
                ids=[int(row['features_l0']),int(row['features_l1'])]
            else:
                need(int(row['template_id'])==-1 and int(row['features_l0'])==0 and int(row['features_l1'])==0 and row['error'],'Failed attempt placeholder')
                need(key not in by_meta,'Failed attempt has serialized metadata')
                ids=[-1,-1]
            output.append(dict(family=family,key=key,geometry=cell['geometry'],counts=ids,
                               template_id=int(row['template_id']),error=row['error'],success=success))
        need({int(q['row']['template_id']) for q in by_key.values() if q['row']['success']=='1'}==set(range(len(metas))),'Metadata/attempt success coverage')
    # Same geometry is a cross-family invariant of this diagnostic.
    grouped={}
    for row in output:
        grouped.setdefault(row['key'],[]).append(row['geometry'])
    for key,values in grouped.items():need(all(v==values[0] for v in values),'Cross-family geometry mismatch')
    return output


def main():
    import argparse,csv,hashlib,json
    from pathlib import Path
    import input_contract as c
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve()
    c.need(out.is_relative_to(c.HERE) and not out.exists(),'Input directory must be new inside experiment')
    out.mkdir();opened={}
    try:
        spec=c.specification();rgb=c.load(c.ROOT/'artifacts/rgb_empty_mask_experiment/INPUT_CLOSURE.json')
        binary=c.load(c.ROOT/'artifacts/silhouette_empty_mask_experiment/INPUT_CLOSURE.json')
        masks=c.validate_masks(spec['training_mask_allowlist'],rgb['dataset_root'],spec['objects'])
        c.need(rgb['training']==binary['training'] and len(masks)==432,'Training mask scope differs')
        families=[v['name'] for v in spec['families']]
        banks=[];poses=[];attempt_rows=[]
        def read(path,expected=None):
            q=c.pin(path)
            if expected:c.need(q['sha256']==expected['sha256'] and q['bytes']==expected['bytes'],'Input pin differs')
            opened[q['path']]=q;return c.load(path) if Path(path).suffix=='.json' else c.data(path)
        for q in spec['input_pins']+spec['attempt_table_pins']:
            path=Path(q['path']);read(path if path.is_absolute() else c.ROOT/path,q)
        for experiment in ('rgb_empty_mask_experiment','silhouette_empty_mask_experiment'):
            training_freeze=c.load(c.ROOT/f'artifacts/{experiment}/run_training_v1/BANK_FREEZE.json')
            for record in training_freeze['files']:read(record['path'],record)
        for name,record in rgb['private_files'].items():
            if '/rgb_training/' in name:read(c.ROOT/'artifacts/rgb_empty_mask_experiment'/name,record)
        for obj in spec['objects']:
            attempts_by_family={};metadata_by_family={}
            for family in families:
                if family=='rgb_official_mask':directory=c.ROOT/f'artifacts/rgb_empty_mask_experiment/frozen_inputs/obj{obj}/rgb_training'
                elif family=='binary_empty_mask':directory=c.ROOT/f'artifacts/silhouette_empty_mask_experiment/run_training_v1/native/obj{obj}'
                else:directory=c.ROOT/f'artifacts/rgb_empty_mask_experiment/run_training_v1/obj{obj}'
                if family=='rgb_official_mask':
                    member_pins={str((c.ROOT/'artifacts/rgb_empty_mask_experiment'/p).resolve()):q for p,q in rgb['private_files'].items() if f'frozen_inputs/obj{obj}/rgb_training/' in p}
                else:
                    experiment='silhouette_empty_mask_experiment' if family=='binary_empty_mask' else 'rgb_empty_mask_experiment'
                    freeze=c.load(c.ROOT/f'artifacts/{experiment}/run_training_v1/BANK_FREEZE.json')
                    member_pins={str(Path(p['path']).resolve()):p for p in freeze['files']}
                files={}
                for name in ('template_attempts.csv','template_metadata.json','training_config.json',f'templates_tless_object_{obj}.yml.gz'):
                    path=directory/name;expected=member_pins.get(str(path.resolve()));c.need(expected is not None,'Bank member not in frozen input')
                    files[name]=read(path,expected)
                rows=list(csv.DictReader(files['template_attempts.csv'].decode('utf-8-sig').splitlines()))
                for row in rows:row['object_id']=obj
                attempts_by_family[family]=rows;metadata_by_family[family]=files['template_metadata.json']['templates']
                banks.append(dict(family=family,object_id=obj,class_id='tless_object_'+str(obj),directory=str(directory),
                                  bank_path=str(directory/f'templates_tless_object_{obj}.yml.gz'),
                                  metadata_path=str(directory/'template_metadata.json'),attempts_path=str(directory/'template_attempts.csv'),
                                  expected_templates=len(metadata_by_family[family])))
            expected={(obj,q['image_id'],a,s) for q in spec['training_mask_allowlist'] if q['object_id']==obj for a in spec['coverage']['angles'] for s in spec['coverage']['scales']}
            rows=validate_pose_attempts(attempts_by_family,metadata_by_family,expected)
            grouped={}
            for row in rows:
                grouped.setdefault(row['key'],{})[row['family']]=row
                for level in (0,1):
                    attempt_rows.append(dict(family=row['family'],object_id=obj,image=row['key'][1],angle=row['key'][2],scale=row['key'][3],
                       success=int(row['success']),template_id=row['template_id'],level=level,requested_features=32 if level==0 else 16,
                       actual_features=row['counts'][level] if row['success'] else '',error=row['error'],geometry=json.dumps(row['geometry'],separators=(',',':'))))
            for key in sorted(grouped):
                g=grouped[key];c.need(set(g)==set(families),'Incomplete family pose')
                poses.append(dict(object_id=obj,image=key[1],angle=key[2],scale=key[3],geometry=g[families[0]]['geometry'],
                                  template_ids=[g[f]['template_id'] for f in families],
                                  expected_counts=[g[f]['counts'] for f in families]))
        quality=[]
        for experiment,arms in [('rgb_empty_mask_experiment',{'rgb_control':'rgb_official_mask','rgb_empty_mask':'rgb_empty_mask'}),
                                ('silhouette_empty_mask_experiment',{'binary_empty_mask':'binary_empty_mask'})]:
            base=c.ROOT/f'artifacts/{experiment}/run_quality_development_v1';freeze=c.load(base/'QUALITY_STAGE_FREEZE.json')
            c.need(freeze['completed'] and freeze['native_exit_code']==0 and freeze['actual_matcher_calls']==9600,'Quality stage incomplete')
            expected_members={Path(q['path']).resolve() for q in freeze['files']}
            actual_members={q.resolve() for q in (base/'native').rglob('*') if q.is_file() and q.name!='.gitignore'}
            c.need(actual_members==expected_members,'Quality member set changed')
            for record in freeze['files']:read(record['path'],record)
            quality.append(dict(experiment=experiment,base=str(base/'native'),arms=arms,freeze=str(base/'QUALITY_STAGE_FREEZE.json')))
        c.need(len(poses)==20736 and len(attempt_rows)==124416 and len(banks)==18,'Expanded input coverage')
        with (out/'attempt_layers.csv').open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(attempt_rows[0]));writer.writeheader();writer.writerows(attempt_rows)
        observer=dict(schema='template_feature_observer_inputs_v1',families=families,objects=spec['objects'],banks=banks,masks=masks,poses=poses,
                      output_ceiling_bytes=2147483648,peak_rss_ceiling_bytes=1610612736)
        (out/'observer_inputs.json').write_text(json.dumps(observer,indent=2)+'\n',encoding='utf-8')
        for record in opened.values():c.check(record)
        own=[]
        source_names={'PROTOCOL.json','ORIGINS.json'}
        source_names.update(q.name for q in c.HERE.iterdir() if q.is_file() and q.suffix.lower() in ('.py','.cpp','.hpp','.h','.md'))
        for name in sorted(source_names):own.append(c.pin(c.HERE/name))
        members=[c.pin(out/'attempt_layers.csv'),c.pin(out/'observer_inputs.json')]
        result=dict(schema='template_feature_input_freeze_v1',completed=True,files=sorted(opened.values(),key=lambda r:r['path']),
                    sources=own,members=members,quality=quality,masks=masks,counts=dict(poses=20736,attempt_layers=124416,banks=18,masks=432),
                    image_bytes_opened=0,image_decodes=0,matcher_calls=0,
                    image_integrity='Mask pins copied from anchored allowlist; image bytes deliberately not opened by input preparer')
        (out/'INPUT_FREEZE.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(passed=True,numeric_files=len(opened),mask_allowlist=432,image_bytes_opened=0,matcher_calls=0)))
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),image_bytes_opened=0,matcher_calls=0),indent=2)+'\n')
        raise


if __name__=='__main__':main()
