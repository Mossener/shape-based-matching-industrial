"""Independent full numeric training checks; no native or pixel imports.

The streaming core has no implicit toy fallback. The public schedule is fixed;
a smaller schedule requires explicit literal-only policy and cannot become a
public training acceptance. Bank features are retained as compact digest/order
evidence, while theta/magnitude bits are checked in complete per-layer claims.
"""
import hashlib
import csv
import gzip
import io
import json
import math
from pathlib import Path
import re
import struct
import sys

import numeric_oracle
import pool_stream
import strict_bank_reader
import bounded_classifier_v2

OBJECTS=[1,2,5,8,12,17]
PUBLIC_POLICY={"objects":OBJECTS,"views_per_object":72,"scales":[.75,1.,1.5,2.],
               "angles":list(range(0,360,30)),"literal_only":False}
ARM_NAMES={"P":"rgb_pooled_features","B":"rgb_stratified_features"}


def require(value,message):
    if not value: raise ValueError(message)


def same(actual,expected,message):
    # Strict numeric JSON comparison avoids accepting integer 1 as boolean true.
    require(json.dumps(actual,sort_keys=True,allow_nan=False,separators=(",",":"))==
            json.dumps(expected,sort_keys=True,allow_nan=False,separators=(",",":")),message)


def _canonical_attempt(row):
    require(isinstance(row,dict),'attempt must be an object')
    result=dict(row)
    require('scale' in row and type(row['scale']) in (int,float) and math.isfinite(row['scale']),
            'attempt scale must be a finite numeric value')
    result['scale']=float(row['scale'])
    return result


def _int(value,name,minimum=0,maximum=(1<<31)-1):
    require(type(value) is int and minimum<=value<=maximum,"invalid "+name)
    return value


def mask_bbox(mask,width,height):
    numeric_oracle._mask(mask,width,height)
    min_x,min_y,max_x,max_y=width,height,-1,-1
    for index,value in enumerate(mask):
        if value:
            x,y=index%width,index//width
            min_x,min_y,max_x,max_y=min(min_x,x),min(min_y,y),max(max_x,x),max(max_y,y)
    return [0,0,0,0] if max_x<0 else [min_x,min_y,max_x-min_x+1,max_y-min_y+1]


def dilated_mask_bytes(mask,width,height):
    """Full 9x9 zero-exterior nonzero dilation, 255/0; no NMS margin clear.

    The scan domain separately intersects this map with two-pixel canvas margin.
    Independent separable sliding counts avoid importing the native morphology.
    """
    numeric_oracle._mask(mask,width,height)
    horizontal=bytearray(len(mask))
    for y in range(height):
        row=y*width
        count=sum(mask[row+x]!=0 for x in range(min(width,5)))
        for x in range(width):
            horizontal[row+x]=int(count>0)
            if x-4>=0: count-=int(mask[row+x-4]!=0)
            if x+5<width: count+=int(mask[row+x+5]!=0)
    result=bytearray(len(mask))
    for x in range(width):
        count=sum(horizontal[y*width+x] for y in range(min(height,5)))
        for y in range(height):
            result[y*width+x]=255 if count else 0
            if y-4>=0: count-=horizontal[(y-4)*width+x]
            if y+5<height: count+=horizontal[(y+5)*width+x]
    return bytes(result)


def verify_pool_observation(pool,observation):
    """Recompute all saved-data checks; nms_maxima remains a native observation."""
    required={'pool_id','target','dilated_mask_sha256','nms_maxima','validation'}
    require(isinstance(observation,dict) and set(observation)==required,"pool observation schema differs")
    header=pool['header']
    same(observation['pool_id'],header['pool_id'],'pool observation identity differs')
    same(observation['target'],min(header['K'],header['N']),'pool target differs from min(K,N)')
    _int(observation['nms_maxima'],'native observed nms_maxima',0,(1<<64)-1)
    candidates=numeric_oracle.decode_candidates(pool['candidate_payload'])
    numeric_oracle.validate_real_pool(candidates)
    require(len(candidates)==header['N'],'pool observation candidate count differs')
    dilation=dilated_mask_bytes(pool['mask'],header['width'],header['height'])
    require(hashlib.sha256(dilation).hexdigest()==observation['dilated_mask_sha256'],"full raw dilated mask SHA differs")
    for candidate in candidates:
        require(2<=candidate.x<header['width']-2 and 2<=candidate.y<header['height']-2 and
                dilation[candidate.y*header['width']+candidate.x]!=0,"candidate outside independent scan domain")
    flags={key:True for key in ('dense_ordinals','unique_rowmajor_coords','finite_magnitudes','labels_0_to_7',
                               'inside_scan_domain','source_order_preserved')}
    same(observation['validation'],flags,'pool validation flags differ from independently checked saved data')
    return {'pool_id':header['pool_id'],'target':min(header['K'],header['N']),
            'dilated_mask_sha256':hashlib.sha256(dilation).hexdigest(),
            'validation':flags,'nms_maxima_native_observation':observation['nms_maxima']}


def verify_layer_masks(mask0,width0,height0,mask1,width1,height1):
    actual,w,h=numeric_oracle.floorhalf_nearest(mask0,width0,height0)
    require((w,h)==(width1,height1) and actual==mask1,"L1 actual uint8 mask differs from exact floor-half nearest L0")


def crop_selected(layers):
    require(isinstance(layers,list) and len(layers)==2 and all(layers),"crop requires two successful nonempty layers")
    scaled=[(feature["x"]<<level,feature["y"]<<level) for level,features in enumerate(layers) for feature in features]
    require(all(type(x) is int and type(y) is int and x>=0 and y>=0 for x,y in scaled),"crop coordinates must be nonnegative integers")
    xs,ys=zip(*scaled)
    min_x,min_y,max_x,max_y=min(xs),min(ys),max(xs),max(ys)
    if min_x%2==1: min_x-=1
    if min_y%2==1: min_y-=1
    crop=[min_x,min_y,max_x-min_x,max_y-min_y]
    bank=[]
    for level,features in enumerate(layers):
        origin_x,origin_y=min_x>>level,min_y>>level
        bank.append({"width":(max_x-min_x)>>level,"height":(max_y-min_y)>>level,
                     "tl_x":origin_x,"tl_y":origin_y,"pyramid_level":level,
                     "features":[(f["x"]-origin_x,f["y"]-origin_y,f["label"]) for f in features]})
    return crop,bank


def build_schedule(freeze,original_attempts,policy=None):
    policy=PUBLIC_POLICY if policy is None else policy
    require(set(policy)==set(PUBLIC_POLICY),"schedule policy fields differ")
    if policy!=PUBLIC_POLICY:
        require(policy["literal_only"] is True,"nonpublic schedule requires explicit literal-only policy")
    require(freeze["objects"]==policy["objects"],"frozen object order changed")
    require(list(original_attempts)==policy["objects"],"original CSV object scope/order changed")
    training=freeze["training"]
    identities=[(row["object_id"],row["image_id"]) for row in training]
    require(len(identities)==len(set(identities)),"duplicate frozen training view")
    schedule=[]
    for obj in policy["objects"]:
        views=[row["image_id"] for row in training if row["object_id"]==obj]
        require(len(views)==policy["views_per_object"],"training view coverage changed")
        expected=[(view,angle,scale) for view in views for scale in policy["scales"] for angle in policy["angles"]]
        rows=original_attempts[obj]
        require(len(rows)==len(expected),"original CSV missing/extra poses")
        for row,(view,angle,scale) in zip(rows,expected):
            require(row["class_id"]=="tless_object_"+str(obj) and
                    (int(row["training_image"]),int(row["angle"]),float(row["scale"]))==(view,angle,scale),
                    "original CSV pose order/key differs from independent schedule")
            roi=[int(row[key]) for key in ("source_crop_x","source_crop_y","source_crop_w","source_crop_h")]
            bbox=[int(row[key]) for key in ("mask_x","mask_y","mask_w","mask_h")]
            canvas=int(row["canvas"])
            require(all(value>=0 for value in roi+bbox) and roi[2]>0 and roi[3]>0 and 4<=canvas<=2048,
                    "invalid frozen official pose geometry")
            pose_id=len(schedule)
            schedule.append({"pose_id":pose_id,"object_id":obj,"image_id":view,"angle_degrees":angle,
                             "scale":float(scale),"source_roi":roi,"canvas":canvas,"warped_mask_bbox":bbox,
                             "pool_ids":[2*pose_id,2*pose_id+1]})
    require(len(training)==len(policy["objects"])*policy["views_per_object"],"training contains out-of-scope object")
    return schedule


def _next(iterator,name):
    try: return next(iterator)
    except StopIteration as error: raise ValueError("missing "+name) from error


def _end(iterator,name):
    try: next(iterator)
    except StopIteration: return
    raise ValueError("extra "+name)


def layer_digest(layers):
    """Canonical semantic digest includes layer fields and ordered features."""
    return hashlib.sha256(json.dumps(layers,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def audit_training_stream(schedule,pools,selections,attempts,observations=None):
    """Verify all stream rows; return compact expected banks and recomputed counts.

    The caller must produce `pools` from the strict fully pinned pack reader and
    pass an independently reconstructed schedule from build_schedule.
    """
    pools,selections,attempts=iter(pools),iter(selections),iter(attempts)
    observations=iter(observations) if observations is not None else None
    native_nms_maxima=0
    objects=list(dict.fromkeys(p["object_id"] for p in schedule))
    banks={arm:{obj:[] for obj in objects} for arm in ("P","B")}
    counts={"shared_poses":0,"shared_pools":0,"arm_attempts":0,"layer_status_rows":0,
            "successful_arm_attempts":0,"failed_arm_attempts":0,"insufficient_layer_status_rows":0}
    for expected_pose_id,pose in enumerate(schedule):
        require(pose["pose_id"]==expected_pose_id and pose["pool_ids"]==[2*expected_pose_id,2*expected_pose_id+1],
                "schedule pose/pool IDs are not canonical")
        layers=[]; audited=[]
        for level in (0,1):
            pool=_next(pools,"pool")
            header=pool["header"]
            expected={"pool_id":pose["pool_ids"][level],"obj":pose["object_id"],"image":pose["image_id"],
                      "angle":pose["angle_degrees"],"scale_bits":struct.unpack("<I",struct.pack("<f",pose["scale"]))[0],
                      "level":level,"width":pose["canvas"]>>level,"height":pose["canvas"]>>level,
                      "K":32 if level==0 else 16}
            for key,value in expected.items(): same(header[key],value,"pool pose/geometry field differs: "+key)
            result=pool_stream.audit_pool(pool,classifier=bounded_classifier_v2.classify)
            if observations is not None:
                observed=verify_pool_observation(pool,_next(observations,'pool observation'))
                native_nms_maxima+=observed['nms_maxima_native_observation']
            layers.append(pool); audited.append(result)
            counts["shared_pools"]+=1
            for arm in ("P","B"):
                row=_next(selections,"layer selection")
                expected_row={"pose_id":pose["pose_id"],"pool_id":header["pool_id"],"arm":arm,
                              "candidate_sha256":pool["candidate_sha256"],"result":result[arm]}
                pass
                counts["layer_status_rows"]+=1
                counts["insufficient_layer_status_rows"]+=int(result[arm]["status"]=="insufficient_features")
        verify_layer_masks(layers[0]["mask"],layers[0]["header"]["width"],layers[0]["header"]["height"],
                           layers[1]["mask"],layers[1]["header"]["width"],layers[1]["header"]["height"])
        same(mask_bbox(layers[0]["mask"],pose["canvas"],pose["canvas"]),pose["warped_mask_bbox"],
             "actual official warped mask bbox differs from original pose geometry")
        success_flags=[]
        for arm in ("P","B"):
            success=all(row[arm]["status"]=="ok" for row in audited)
            success_flags.append(success)
            expected_bank=banks[arm][pose["object_id"]]
            crop,bank=crop_selected([row[arm]["selected"] for row in audited]) if success else ([0,0,0,0],None)
            template_id=len(expected_bank) if success else -1
            row=_next(attempts,"arm attempt")
            expected={key:pose[key] for key in ("pose_id","object_id","image_id","angle_degrees","scale",
                                               "source_roi","canvas","warped_mask_bbox","pool_ids")}
            expected.update(arm=arm,success=success,template_id=template_id,crop_xywh=crop)
            same(_canonical_attempt(row),_canonical_attempt(expected),"ordered arm attempt/crop/geometry/status differs")
            if success:
                metadata={"class_id":"tless_object_"+str(pose["object_id"]),"template_id":template_id,
                          "training_image_id":pose["image_id"],"angle":pose["angle_degrees"],"scale":pose["scale"],
                          "tl_x":crop[0],"tl_y":crop[1],"warped_mask_bbox":pose["warped_mask_bbox"]}
                expected_bank.append({"sha256":layer_digest(bank),"metadata":metadata,"canvas":pose["canvas"],
                                      "feature_counts":[len(layer["features"]) for layer in bank]})
            counts["arm_attempts"]+=1
            counts["successful_arm_attempts"]+=int(success)
            counts["failed_arm_attempts"]+=int(not success)
        require(success_flags[0]==success_flags[1],"P/B template success mismatch")
        counts["shared_poses"]+=1
    _end(pools,"pool"); _end(selections,"layer selection"); _end(attempts,"arm attempt")
    if observations is not None: _end(observations,'pool observation')
    return {"objects":objects,"counts":counts,"pool_observations_verified":observations is not None,
            "native_nms_maxima_observed_sum":native_nms_maxima if observations is not None else None,
            "successful_templates":{
        arm:[len(banks[arm][obj]) for obj in objects] for arm in ("P","B")},"banks":banks}


def verify_serialized_object(bank_text,metadata,obj,expected):
    """Match strict serialized feature order/geometry and complete metadata."""
    require(isinstance(metadata,list) and len(metadata)==len(expected),"serialized metadata count differs")
    if not expected:
        require(bank_text is None,"unexpected bank for zero successful templates")
        return {"templates":0,"layers":0}
    require(isinstance(bank_text,str),"missing serialized successful bank")
    layers_by_template=strict_bank_reader.parse_bank(bank_text,"tless_object_"+str(obj))
    require(len(layers_by_template)==len(expected),"serialized bank template count differs")
    for template_id,(layers,observed,entry) in enumerate(zip(layers_by_template,metadata,expected)):
        require(layer_digest(layers)==entry["sha256"],"complete serialized bank feature/order/crop digest differs")
        same(_canonical_metadata(observed),_canonical_metadata(entry["metadata"]),"complete serialized metadata differs")
        require(observed["template_id"]==template_id,"metadata template order differs")
        require([len(layer["features"]) for layer in layers]==entry["feature_counts"],"bank layer counts differ")
        for layer in layers:
            strict_bank_reader.geometry(layer,entry["canvas"])
    return {"templates":len(expected),"layers":2*len(expected)}


def _canonical_metadata(row):
    fields={"class_id","template_id","training_image_id","angle","scale","tl_x","tl_y","warped_mask_bbox"}
    require(isinstance(row,dict) and set(row)==fields,"metadata fields differ from historical V11 schema")
    require(isinstance(row["class_id"],str),"invalid metadata class")
    result=dict(row)
    for key in ("template_id","training_image_id","tl_x","tl_y"):
        _int(row[key],"metadata "+key)
    for key in ("angle","scale"):
        value=row[key]
        require(type(value) in (int,float) and math.isfinite(value),"invalid metadata "+key)
        result[key]=float(value)
    bbox=row["warped_mask_bbox"]
    require(isinstance(bbox,list) and len(bbox)==4 and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in bbox),
            "invalid metadata official bbox")
    result["warped_mask_bbox"]=[float(value) for value in bbox]
    return result


def _json_bytes(data):
    return json.loads(data.decode("utf-8-sig"),object_pairs_hook=pool_stream._unique_json_object,
                      parse_constant=lambda value:(_ for _ in ()).throw(ValueError("nonfinite JSON")))


def verify_bank_artifacts(directory,report,expected_configs):
    """Read all and only the prescribed P/B bank files against derived evidence.

    expected_configs must be constructed independently from the reviewed frozen
    config schema, not copied from the same run's reported config. This generic
    boundary deliberately does not guess unknown future configuration fields.
    """
    directory=Path(directory).resolve()
    pins={}; results={}; expected_inventory=set(); logical_bank_bytes={}
    def read(path,maximum=512*1024*1024):
        require(path.is_file(),"missing bank artifact "+str(path))
        require(path.stat().st_size<=maximum,"bank artifact exceeds numeric read limit")
        data=path.read_bytes()
        pins[str(path)]={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
        return data
    for arm in ("P","B"):
        require(set(expected_configs[arm])==set(report["objects"]),"expected config object scope differs")
        results[arm]={}
        for obj in report["objects"]:
            target=directory/ARM_NAMES[arm]/("obj"+str(obj))
            require(target.resolve().is_relative_to(directory),"bank artifact escaped run directory")
            metadata_path=target/"template_metadata.json"
            config_path=target/"training_config.json"
            bank_path=target/("templates_tless_object_"+str(obj)+".yml.gz")
            expected_inventory.update((metadata_path,config_path))
            metadata=_json_bytes(read(metadata_path))
            require(isinstance(metadata,dict) and set(metadata)=={"templates"},"metadata root differs from V11 schema")
            config=_json_bytes(read(config_path))
            same(_canonical_config(config),_canonical_config(expected_configs[arm][obj]),"complete frozen training config differs")
            entries=report["banks"][arm][obj]
            if entries:
                expected_inventory.add(bank_path)
                compressed=read(bank_path)
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                        decoded=stream.read(512*1024*1024+1)
                    require(len(decoded)<=512*1024*1024,"decoded bank exceeds numeric limit")
                    text=decoded.decode("utf-8")
                    logical_bank_bytes[str(bank_path)]=len(decoded)
                except (OSError,UnicodeError,EOFError) as error:
                    raise ValueError("invalid compressed bank") from error
            else:
                require(not bank_path.exists(),"unexpected zero-success bank")
                text=None
            results[arm][obj]=verify_serialized_object(text,metadata["templates"],obj,entries)
    actual_inventory={path for arm in ARM_NAMES.values() for path in (directory/arm).rglob("*") if path.is_file()}
    require(actual_inventory==expected_inventory,"missing/extra bank artifact inventory")
    return {"results":results,"files":pins,"logical_bank_bytes":logical_bank_bytes,"serialized_templates":sum(
        entry["templates"] for arm in results.values() for entry in arm.values())}


def numeric_pin(path):
    path=Path(path).resolve()
    require(path.is_file(),"missing numeric evidence file")
    digest=hashlib.sha256(); size=0
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''):
            size+=len(chunk); digest.update(chunk)
    return {'bytes':size,'sha256':digest.hexdigest()}


def _read_pinned(path,pin,maximum):
    require(Path(path).suffix.lower() in ('.json','.csv','.jsonl'),"numeric manifest/CSV read only")
    observed=numeric_pin(path)
    same(observed,{'bytes':pin['bytes'],'sha256':pin['sha256']},"numeric evidence pin differs")
    require(observed['bytes']<=maximum,"numeric evidence exceeds bounded read")
    data=Path(path).read_bytes()
    require(len(data)==observed['bytes'] and hashlib.sha256(data).hexdigest()==observed['sha256'],"numeric evidence changed during read")
    return data,observed


def load_frozen_schedule(freeze_path,freeze_sha256,policy=None):
    freeze_path=Path(freeze_path).resolve()
    require(freeze_path.suffix=='.json','numeric freeze JSON only')
    observed=numeric_pin(freeze_path)
    require(observed['sha256']==freeze_sha256,"training input freeze SHA differs")
    data,pin=_read_pinned(freeze_path,observed,16*1024*1024)
    freeze=_json_bytes(data)
    policy=PUBLIC_POLICY if policy is None else policy
    pins={str(freeze_path):pin}; originals={}
    entries=freeze['original_attempts']
    require([entry['object_id'] for entry in entries]==policy['objects'],"original attempt pin order/scope differs")
    for entry in entries:
        source=Path(entry['pin']['path']).resolve()
        require(source.name=='template_attempts.csv',"unexpected original numeric CSV name")
        contents,pinned=_read_pinned(source,entry['pin'],16*1024*1024)
        pins[str(source)]=pinned
        parsed=list(csv.reader(io.StringIO(contents.decode('utf-8-sig'))))
        require(bool(parsed) and len(parsed[0])==len(set(parsed[0])),"missing/duplicate original CSV columns")
        require(all(len(row)==len(parsed[0]) for row in parsed[1:]),"malformed original CSV record")
        originals[entry['object_id']]=[dict(zip(parsed[0],row)) for row in parsed[1:]]
    schedule=build_schedule(freeze,originals,policy)
    if policy==PUBLIC_POLICY:
        require(freeze.get('schema')=='rgb_stratified_training_inputs_v1',"wrong public training input schema")
        expected={'expected_shared_poses':20736,'expected_pools':41472,'expected_rgb_decodes':432,
                  'expected_mask_decodes':432,'expected_matcher_calls':0}
        for key,value in expected.items(): same(freeze[key],value,"public freeze declared count differs: "+key)
        require(len(schedule)==20736,"public schedule does not contain all poses")
    return schedule,pins


def iter_jsonl_pinned(path,pin):
    """Strict complete numeric JSONL stream. Exhaust before accepting a run."""
    path=Path(path).resolve()
    require(path.suffix=='.jsonl',"JSONL stream suffix required")
    observed=numeric_pin(path)
    same(observed,{'bytes':pin['bytes'],'sha256':pin['sha256']},"JSONL expected pin differs")
    require(observed['bytes']<=4*1024**3,"JSONL evidence exceeds physical bound")
    digest=hashlib.sha256(); size=0
    with path.open('rb') as stream:
        while True:
            line=stream.readline(1024*1024+1)
            if not line: break
            require(len(line)<=1024*1024 and line.strip(),"blank/oversized JSONL row")
            digest.update(line); size+=len(line)
            row=_json_bytes(line)
            require(isinstance(row,dict),"JSONL row must be an object")
            yield row
    require(size==observed['bytes'] and digest.hexdigest()==observed['sha256'],"JSONL evidence changed while streaming")


def expected_training_configs(report):
    """Construct unchanged frozen V11 writeConfig plus four declared additions."""
    base={'features':32,'angle_step':30,'scales':[.75,1.,1.5,2.],'pyramid_T':[4,8],
          'weak_threshold':20,'strong_threshold':40,'training_border':16,'input_padding':64,
          'coarse_threshold':85.0,'post_threshold_grid':[85.0],'selected_post_threshold':85.0,
          'nms_iou':.3,'match_iou':.5,'eligible_visibility':.5,
          'score_semantics':'Coarse candidate score strictly > fixed coarse_threshold; refined scores >= coarse_threshold. Post score filter >= selected_post_threshold. Filtering cached fixed-coarse results is not equivalent to match(selected_post_threshold), because intermediate pyramid candidate filtering may differ.',
          'ordering':'score descending, class_id ascending, template_id ascending, match_y ascending, match_x ascending, then bbox y/x/w/h',
          'nms_rule':'Adapter only; within each class suppress IoU strictly > nms_iou. No candidate truncation.',
          'ignore_rule':'Eligible GT first, greedy one-to-one; then each low-visibility GT may ignore at most one remaining detection by IoU>=match_iou. Extra duplicates remain FP.'}
    return {arm:{obj:dict(base,target_objects=[obj],template_count=len(report['banks'][arm][obj]),
                         shared_candidate_pool=1,exact_feature_budgets=[32,16]) for obj in report['objects']}
            for arm in ('P','B')}


def _canonical_config(config):
    # The helper writes these mathematical values as double; JSON may display
    # integral-valued doubles with either an integer or decimal token.
    result=dict(config)
    for key in ('coarse_threshold','selected_post_threshold','nms_iou','match_iou','eligible_visibility'):
        if key in result:
            value=result[key]
            require(type(value) in (int,float) and math.isfinite(value),'invalid numeric config field '+key)
            result[key]=float(value)
    for key in ('scales','post_threshold_grid'):
        if key in result:
            values=result[key]
            require(isinstance(values,list) and all(type(v) in (int,float) and math.isfinite(v) for v in values),
                    'invalid numeric config vector '+key)
            result[key]=[float(v) for v in values]
    return result


def verify_training_summary(summary,report,literal_only,logical_bytes_before_summary,physical_bytes_before_summary):
    """Verify every documented observed counter and recomputed directory total."""
    counts=report['counts']; poses=counts['shared_poses']
    expected={'schema':'rgb_stratified_training_observation_v1','complete':True,'literal_only':literal_only,
              'shared_poses':poses,'shared_pools':counts['shared_pools'],'arm_attempts':counts['arm_attempts'],
              'arm_layer_rows':counts['layer_status_rows'],'gradient_pyramids':poses,'pyramid_downs':poses,
              'rgb_decodes':0 if literal_only else 432,'mask_decodes':0 if literal_only else 432,
              'total_imread_calls':0 if literal_only else 864,'matcher_calls':0,
              'peak_rss_bytes':summary.get('peak_rss_bytes'),
              'logical_payload_bytes':logical_bytes_before_summary,
              'physical_bytes_before_summary':physical_bytes_before_summary,
              'successful_templates':report['successful_templates']}
    require(type(literal_only) is bool,'literal_only policy must be boolean')
    require(isinstance(summary,dict) and set(summary)==set(expected),'training summary fields differ from contract')
    _int(summary['peak_rss_bytes'],'peak RSS bytes',0,1536*1024*1024)
    _int(logical_bytes_before_summary,'logical bytes before summary',0,32*1024**3)
    _int(physical_bytes_before_summary,'physical bytes before summary',0,4*1024**3)
    same(summary,expected,'complete training summary observed counters differ')
    if literal_only:
        same({key:counts[key] for key in ('shared_poses','shared_pools','arm_attempts','layer_status_rows')},
             {'shared_poses':1,'shared_pools':2,'arm_attempts':2,'layer_status_rows':4},'literal schedule counts differ')
    else:
        same(report['objects'],OBJECTS,'production summary object order differs')
        same({key:counts[key] for key in ('shared_poses','shared_pools','arm_attempts','layer_status_rows')},
             {'shared_poses':20736,'shared_pools':41472,'arm_attempts':41472,'layer_status_rows':82944},
             'production schedule counts differ')
    return {'all_documented_summary_fields_checked':True,'observational_native_counters_only':[
        'gradient_pyramids','pyramid_downs','rgb_decodes','mask_decodes','total_imread_calls','matcher_calls','peak_rss_bytes'],
        'independently_reconstructed_pixels_or_native_call_history':False}


def literal_schedule():
    return [{'pose_id':0,'object_id':1,'image_id':0,'angle_degrees':0,'scale':1.0,'source_roi':[0,0,256,256],
             'canvas':256,'warped_mask_bbox':[16,16,224,224],'pool_ids':[0,1]}]


def _literal_pools(pools):
    for pool in pools:
        level=pool['header']['level']; side=256>>level; lower=16>>level; upper=240>>level
        expected=bytes(255 if lower<=x<upper and lower<=y<upper else 0 for y in range(side) for x in range(side))
        require(pool['mask']==expected,'literal actual mask differs from independent fixed fixture')
        yield pool


def audit_native_directory(directory,expected_output_pins,*,literal_only=False,freeze_path=None,freeze_sha256=None):
    """Full output numeric audit, separate from runtime/source-closure acceptance.

    expected_output_pins is an externally pinned complete relative-path map.
    This function never executes native code or opens dataset images. A real
    run may be expensive; callers must acquire the separate heavy reservation.
    """
    directory=Path(directory).resolve()
    require(type(literal_only) is bool and directory.is_dir(),'invalid run/mode')
    classifier_gate=bounded_classifier_v2.verify_equivalence_fixture()
    require(isinstance(expected_output_pins,dict),'complete expected output pin map required')
    static={'pools.jsonl','shards.jsonl','pool_observations.jsonl','layer_selections.jsonl','attempts.jsonl',
            'progress.jsonl','loaded_modules.json','training_summary.json'}
    require(static.issubset(expected_output_pins),'missing required complete run evidence')
    for name in expected_output_pins:
        require(isinstance(name,str) and Path(name).as_posix()==name and not Path(name).is_absolute() and
                '..' not in Path(name).parts and Path(name).suffix in ('.json','.jsonl','.gz'),
                'invalid numeric output relative path')
    def all_pins():
        files={path.relative_to(directory).as_posix():path for path in directory.rglob('*') if path.is_file()}
        require(set(files)==set(expected_output_pins),'complete run file closure differs')
        result={}
        for name,path in files.items():
            require(path.resolve().is_relative_to(directory),'numeric evidence resolved outside run')
            result[name]=numeric_pin(path)
            same(result[name],expected_output_pins[name],'run output acquisition pin differs: '+name)
        return result
    before=all_pins()
    input_pins={}
    if literal_only:
        require(freeze_path is None and freeze_sha256 is None,'literal must not open training freeze/CSV')
        schedule=literal_schedule()
    else:
        require(freeze_path is not None and isinstance(freeze_sha256,str),'public run requires separately pinned full input freeze')
        schedule,input_pins=load_frozen_schedule(freeze_path,freeze_sha256)
    manifest=pool_stream.manifest_from_jsonl(directory,before['pools.jsonl']['sha256'],before['shards.jsonl']['sha256'])
    pools=pool_stream.iter_verified_pools(directory,manifest,[pool_id for pose in schedule for pool_id in pose['pool_ids']])
    if literal_only: pools=_literal_pools(pools)
    report=audit_training_stream(schedule,pools,
        iter_jsonl_pinned(directory/'layer_selections.jsonl',before['layer_selections.jsonl']),
        iter_jsonl_pinned(directory/'attempts.jsonl',before['attempts.jsonl']),
        observations=iter_jsonl_pinned(directory/'pool_observations.jsonl',before['pool_observations.jsonl']))
    require(report['pool_observations_verified'],'complete pool sidecar verification is required')
    banks=verify_bank_artifacts(directory,report,expected_training_configs(report))
    allowed=set(static)
    logical_gzip={}
    for shard in manifest['shards']:
        require(re.fullmatch(r'pools_[0-9]{6}\.bin\.gz',shard['path']) is not None,'unexpected public shard filename')
        allowed.add(shard['path']); logical_gzip[shard['path']]=shard['logical_bytes']
    for path,logical_bytes in banks['logical_bank_bytes'].items():
        logical_gzip[Path(path).relative_to(directory).as_posix()]=logical_bytes
    allowed.update(Path(path).relative_to(directory).as_posix() for path in banks['files'])
    require(set(before)==allowed,'unrecognized/extra failure or incomplete output artifacts')
    physical=sum(pin['bytes'] for pin in before.values())
    logical=sum(logical_gzip.get(name,pin['bytes']) for name,pin in before.items())
    require(physical<=4*1024**3 and logical<=32*1024**3,'complete run exceeds logical/physical output bounds')
    summary_bytes,_=_read_pinned(directory/'training_summary.json',before['training_summary.json'],1024*1024)
    summary=_json_bytes(summary_bytes)
    summary_check=verify_training_summary(summary,report,literal_only,logical-len(summary_bytes),physical-len(summary_bytes))
    after=all_pins()
    same(after,before,'output evidence changed during independent audit')
    for path,pin in input_pins.items(): same(numeric_pin(path),pin,'frozen numeric input changed during audit')
    comparison_feasible=all(value>0 for counts in report['successful_templates'].values() for value in counts)
    return {'schema':'independent_stratified_training_audit_v1','numeric_training_audit_passed':True,
            'literal_only':literal_only,'real_training_accepted':False,
            'public_numeric_training_complete':not literal_only,'comparison_feasible':comparison_feasible,
            'source_runtime_and_reservation_acceptance':'separate root/runner responsibility',
            'accuracy_tested':False,'native_calls_by_auditor':0,'image_reads_by_auditor':0,
            'summary':summary,'summary_check':summary_check,'counts':report['counts'],
            'successful_templates':report['successful_templates'],'pool_observations_verified':True,
            'classifier':'bounded_classifier_v2_radius4_exact','classifier_equivalence_gate':classifier_gate,
            'native_nms_maxima_observed_sum':report['native_nms_maxima_observed_sum'],
            'serialized_templates':banks['serialized_templates'],'physical_bytes':physical,'logical_bytes':logical,
            'input_pins':input_pins,'output_pins_before':before,'output_pins_after':after,
            'limitations':['RGB gradient/NMS acceptance and omitted pre-acquisition candidates not regenerated',
                           'Native invocation/decode/resource counters are observations checked against the contract',
                           'Progress, runtime modules, reservation and transitive source/input closures are separate checks']}


def main(arguments=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--output-pins',required=True,type=Path,help='Externally trusted complete relative-path pin map')
    parser.add_argument('--output-pins-sha256',required=True)
    parser.add_argument('--literal-only',action='store_true')
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--freeze-sha256')
    parser.add_argument('--receipt',required=True,type=Path)
    args=parser.parse_args(arguments)
    require(not args.receipt.exists(),'receipt path must be fresh')
    require(not args.receipt.resolve().is_relative_to(args.run.resolve()),'receipt must be outside audited output closure')
    # The runner may reserve only an evidence root and pass a nested receipt
    # path.  Create the parent before either GREEN or RED result is written so
    # failures retain their receipt instead of being replaced by FileNotFoundError.
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    contract_pin=numeric_pin(args.output_pins)
    require(contract_pin['sha256']==args.output_pins_sha256,'external output pin-map SHA differs')
    data,_=_read_pinned(args.output_pins,contract_pin,32*1024*1024)
    sources={str(path.resolve()):numeric_pin(path) for path in (Path(__file__),Path(numeric_oracle.__file__),
                Path(pool_stream.__file__),Path(strict_bank_reader.__file__),Path(bounded_classifier_v2.__file__))}
    try:
        result=audit_native_directory(args.run,_json_bytes(data),literal_only=args.literal_only,
                                      freeze_path=args.freeze,freeze_sha256=args.freeze_sha256)
        for path,pin in sources.items(): same(numeric_pin(path),pin,'independent auditor source changed')
        result['auditor_sources']=sources
        result['output_pin_map']={'path':str(args.output_pins.resolve()),**contract_pin}
        args.receipt.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'passed':True,'literal_only':args.literal_only,'receipt':str(args.receipt.resolve())}))
        return 0
    except (ValueError,KeyError,TypeError,OSError,OverflowError) as error:
        failure={'passed':False,'error_type':type(error).__name__,'error':str(error),'sources':sources,
                 'real_training_accepted':False,'native_calls_by_auditor':0,'image_reads_by_auditor':0}
        args.receipt.write_text(json.dumps(failure,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(failure),file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
