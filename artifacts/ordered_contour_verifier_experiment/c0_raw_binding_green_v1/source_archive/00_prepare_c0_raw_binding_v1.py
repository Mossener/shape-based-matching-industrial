"""Replay only the exact C0 raw/NMS/inherited-GT projection connection.

No dataset file, index, image, bank, native library or evaluator is opened.
The allowed payloads are exactly 2400 C0 fallback gzip CSVs, their 2400
manifests, six own metadata JSONs and three pinned projection CSVs. Source,
plan and inventory bootstrap metadata are separate explicit fixed paths.
This does not recreate official annotations or regenerate matcher outputs.
"""
from collections import Counter
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys

import c0_numeric_binding_v1 as projection
import prepare_c0_payload_inventory_v2 as stable

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
QUALITY = ROOT / 'artifacts/rgb_stratified_features_experiment/independent_quality'
STAGE = ROOT / 'artifacts/rgb_stratified_features_experiment/quality/run_development_v1'
BANKS = ROOT / 'artifacts/rgb_empty_mask_experiment/frozen_inputs'
PLAN = HERE / 'C0_INPUT_PLAN_V1.json'
INVENTORY = HERE / 'c0_inventory_hash_v2_payload/inventory.json'
PLAN_PIN = dict(path=str(PLAN), bytes=2215868,
                sha256='62610add5d6e40c219a3f9929edb1aa2f87c831d8a678ec4848cf282eb8236c0')
INVENTORY_PIN = dict(path=str(INVENTORY), bytes=6349773,
                     sha256='59edd80d4c6083286d14044326a665daa41ce999ef11414fb5c9da9cb9ab2ec4')
OBJECTS = (1,2,5,8,12,17)
SCENES = (1,4,6,7,8,10,12,13)
MAX_FILE = 67108864
MAX_TOTAL = 536870912
MAX_OUTPUT = 16777216
MIN_FREE = 83886080
RAW_HEADER = ('scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,'
              'match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h').split(',')


def load_pure(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Both helpers are pure at import time. Reader/contract/audit classes and
# dataset-reading entry points are never imported or called by this source.
evidence = load_pure('_c0_binding_evidence_v1', QUALITY / 'evidence.py')
numeric = load_pure('_c0_binding_numeric_v1', QUALITY / 'numeric.py')
need = evidence.need


def source_paths():
    return [Path(__file__).absolute(), HERE / 'c0_numeric_binding_v1.py',
            HERE / 'prepare_c0_payload_inventory_v2.py', QUALITY / 'evidence.py',
            QUALITY / 'numeric.py', Path(sys.executable).absolute()]


def bootstrap_json(pin):
    actual, data = stable.inspect_file(pin['path'], MAX_FILE, capture=True)
    stable.pin_equal(actual, pin)
    return evidence.loads(data)


def registrations(plan, inventory):
    """Derive only fixed admitted paths; this function never stats payloads."""
    need(inventory['schema'] == 'c0_payload_inventory_v1' and inventory['status'] == 'byte_inventory_only'
         and inventory['mode'] == 'hash' and inventory['payload_hashing_complete'] is True
         and inventory['sources_before_after_equal'] is True, 'Accepted hash inventory required')
    need(inventory['file_count'] == inventory['declared_pins_verified'] + inventory['newly_observed_pins'] == 6094
         and inventory['declared_pins_verified'] == 6082 and inventory['newly_observed_pins'] == 12
         and inventory['total_input_bytes'] == 333625244, 'Inventory completion scope differs')
    expected = stable.build_whitelist(plan)  # Metadata only, including no dataset stat/read.
    files = inventory['files']
    need(type(files) is list and len(files) == 6094, 'Inventory file list differs')
    observed = {record['path']:record for record in files}
    need(len(observed) == len(files) and set(observed) == {record['path'] for record in expected},
         'Inventory paths duplicate or differ from plan')
    selected = []
    for record in expected:
        old = observed[record['path']]
        need(all(old[field] == record[field] for field in ('role','identity','path','declared','pin_origin')),
             'Inventory role/identity/declared pin differs')
        if record['role'] in ('candidate_raw','candidate_manifest','own_metadata'):
            need(old['observed'] == record['declared'], 'Selected inherited pin was not verified')
            selected.append(dict(role=record['role'], identity=record['identity'], pin=record['declared']))
    need(Counter(row['role'] for row in selected) == dict(candidate_raw=2400,candidate_manifest=2400,own_metadata=6),
         'Exact numeric payload roles differ')
    declarations = inventory['gt_result_declarations']
    need(declarations['status'] == 'declarations_only_not_opened' and
         declarations['independently_reconstructed'] is False, 'Inherited GT declaration scope differs')
    declared = {row['path']:row for row in declarations['files']}
    need(len(declared) == len(declarations['files']), 'Duplicate projection declarations')
    projection_bytes = 0
    for name in ('ground_truth.csv','per_frame_metrics.csv','selected_detections.csv'):
        path = str(STAGE / 'native' / name)
        need(path in declared, 'Missing fixed projection declaration')
        pin = declared[path]
        evidence.pin_schema(pin)
        projection_bytes += pin['bytes']
        selected.append(dict(role=name, identity={}, pin=pin))
    need(len(selected) == 4809 and projection_bytes == 7983802, 'Exact numeric registration count/bytes differ')
    return selected


class RestrictedReader:
    """Exact registered payloads, bounded stable handles and verified hashes."""
    def __init__(self, records):
        self.pins, self.stamps, self.roles, self.seen = {}, {}, {}, set()
        self.read_count = 0
        total = 0
        for record in records:
            pin = record['pin']; evidence.pin_schema(pin)
            path = stable.canonical(pin['path'])
            key = str(path)
            need(key not in self.pins, 'Duplicate registered numeric path')
            need(not path.is_relative_to(ROOT / 'datasets'), 'All dataset access forbidden')
            role, identity = record['role'], record['identity']
            if role == 'own_metadata':
                expected = BANKS / f"obj{identity['object_id']}/rgb_training/template_metadata.json"
            elif role in ('candidate_raw','candidate_manifest'):
                suffix = '_fallback_raw.csv.gz' if role == 'candidate_raw' else '_fallback_raw_manifest.json'
                expected = (STAGE / f"native/obj{identity['object_id']}/rgb_control" /
                            f"s{identity['scene_id']}_i{identity['image_id']}{suffix}")
            else:
                need(role in ('ground_truth.csv','per_frame_metrics.csv','selected_detections.csv'),
                     'Unrecognized numeric payload role')
                expected = STAGE / 'native' / role
            need(path == expected, 'Payload path differs from fixed role/identity')
            info = stable.safe_stat(path)
            limit = 1048576 if role == 'candidate_manifest' else MAX_FILE
            need(info.st_size == pin['bytes'] <= limit, 'Preflight pin size/role ceiling differs')
            self.pins[key], self.stamps[key], self.roles[key] = pin, stable.stamp(info), role
            total += info.st_size
        need(len(self.pins) == 4809 and total <= MAX_TOTAL, 'Numeric payload count/total ceiling differs')
        self.total_bytes = total

    def read(self, path):
        path = stable.canonical(path)
        key = str(path)
        need(key in self.pins and not path.is_relative_to(ROOT / 'datasets'),
             'Unregistered/dataset read forbidden')
        pin = self.pins[key]
        actual, data = stable.inspect_file(path, pin['bytes'], capture=True, expected_stamp=self.stamps[key])
        stable.pin_equal(actual, pin)
        self.seen.add(key); self.read_count += 1
        return data

    def json(self, path):
        return evidence.loads(self.read(path))

    def recheck(self):
        need(self.seen == set(self.pins), 'Not all registered payloads were actually read')
        for key, pin in self.pins.items():
            actual, _ = stable.inspect_file(key, pin['bytes'], expected_stamp=self.stamps[key])
            stable.pin_equal(actual, pin)


def metadata(reader, obj):
    path = BANKS / f'obj{obj}/rgb_training/template_metadata.json'
    document = reader.json(path)
    records = document['templates']
    need(type(records) is list and len(records) > 0, 'Nonempty template metadata required')
    result = {}
    for index, row in enumerate(records):
        need(type(row['template_id']) is int and row['template_id'] == index and
             row['class_id'] == f'tless_object_{obj}', 'Own metadata class/id/order differs')
        need(type(row['training_image_id']) is int and row['training_image_id'] >= 0 and
             type(row['tl_x']) is int and type(row['tl_y']) is int, 'Own pose/origin types differ')
        need(type(row['warped_mask_bbox']) is list and len(row['warped_mask_bbox']) == 4,
             'Own metadata bbox shape differs')
        box = tuple(evidence.number(value) for value in row['warped_mask_bbox'])
        need(box[2] > 0 and box[3] > 0, 'Own metadata bbox extents differ')
        evidence.number(row['angle']); evidence.number(row['scale'], True)
        result[index] = row
    return result


def parse_raw(reader, declaration, meta, rgb, budget):
    obj, scene, image = (declaration[name] for name in ('object_id','scene_id','image_id'))
    path = Path(declaration['raw_declared']['path'])
    manifest = reader.json(declaration['manifest_observed']['path'])
    header = {'scene_id','image_id','rgb','variant','class_id','class_ids','raw_candidate_count',
              'format','path','compressed_bytes','uncompressed_bytes','zlib_version'}
    need(set(manifest) == header, 'Raw manifest schema differs')
    need((evidence.native_count(manifest['scene_id']),evidence.native_count(manifest['image_id']),
          manifest['variant'],manifest['class_id'],manifest['class_ids'],manifest['rgb']) ==
         (scene,image,'fallback',f'tless_object_{obj}',[f'tless_object_{obj}'],rgb),
         'Raw manifest identity/class/variant/RGB differs')
    need(stable.canonical(manifest['path']) == path and
         manifest['format'] == 'gzip CSV; all candidates retained, 17 significant score digits' and
         type(manifest['zlib_version']) is str and len(manifest['zlib_version']) > 0,
         'Raw manifest path/format differs')
    count = evidence.native_count(manifest['raw_candidate_count'],1000000)
    need(count == declaration['candidate_count_declared'], 'Declared raw candidate count differs')
    expected = evidence.native_count(manifest['uncompressed_bytes'], MAX_FILE)
    need(budget['decoded_bytes'] + expected <= 268435456, 'Combined decoded raw byte ceiling exceeded')
    budget['decoded_bytes'] += expected
    encoded = reader.read(path)
    need(evidence.native_count(manifest['compressed_bytes'],MAX_FILE) == len(encoded),
         'Raw compressed byte count differs')
    with gzip.GzipFile(fileobj=io.BytesIO(encoded), mode='rb') as archive:
        decoded = archive.read(expected+1)
    need(len(decoded) == expected, 'Raw decoded byte count differs or exceeds ceiling')
    rows = evidence.table(decoded, RAW_HEADER)
    need(len(rows) == count, 'Raw row count differs including zero frames')
    result = []
    for rank,row in enumerate(rows):
        need((evidence.integer(row['scene']),evidence.integer(row['image']),row['variant'],
              evidence.integer(row['rank'])) == (scene,image,'fallback',rank), 'Raw rank/frame/variant differs')
        template = evidence.integer(row['template_id'],0)
        need(row['class_id'] == f'tless_object_{obj}' and template in meta, 'Raw own class/template differs')
        own = meta[template]
        bits = numeric.float_bits(evidence.number(row['score']))
        need(evidence.number(row['score']) == numeric.score(bits) and 85 <= numeric.score(bits) <= 100,
             'Raw score float32 bits/threshold differs')
        x,y = evidence.integer(row['match_x']), evidence.integer(row['match_y'])
        box = tuple(evidence.number(row['bbox_'+axis]) for axis in ('x','y','w','h'))
        sx,sy,w,h = (evidence.number(value) for value in own['warped_mask_bbox'])
        need(box == (x-64+sx-own['tl_x'],y-64+sy-own['tl_y'],w,h), 'Raw own origin/bbox conversion differs')
        pose = (evidence.integer(row['training_image'],0),numeric.float_bits(evidence.number(row['angle'])),
                numeric.float_bits(evidence.number(row['scale'],True)))
        need(pose == (own['training_image_id'],numeric.float_bits(evidence.number(own['angle'])),
                      numeric.float_bits(evidence.number(own['scale'],True))), 'Raw own pose differs')
        result.append((row['class_id'],template,x,y,bits,box,pose))
    need(result == sorted(result,key=numeric.candidate_order), 'Complete canonical raw order differs')
    return result


def canonical_digest(records):
    return hashlib.sha256(json.dumps(records, separators=(',',':'), allow_nan=False).encode('utf-8')).hexdigest()


def write_json(path, value):
    data = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8')
    need(len(data) <= MAX_OUTPUT, 'Output file exceeds ceiling')
    with path.open('xb') as stream:
        stream.write(data)


def replay(name):
    need(os.name == 'nt', 'Windows stable-handle implementation required')
    need(sys.flags.optimize == 0 and sys.flags.ignore_environment == 1 and __debug__, 'Run with -E -B without optimization')
    need(re.fullmatch('[a-z][a-z0-9_]{0,79}',name) is not None, 'Fresh simple output name required')
    stable.safe_stat(HERE,directory=True)
    out = HERE / name
    need(not os.path.lexists(out), 'Fresh replay output required')
    need(shutil.disk_usage(HERE).free >= MIN_FREE + MAX_OUTPUT, 'Insufficient output headroom')
    out.mkdir()
    phase = 'bootstrap'
    try:
        sources = [stable.hash_file(path) for path in source_paths()]
        plan, inventory = bootstrap_json(PLAN_PIN), bootstrap_json(INVENTORY_PIN)
        records = registrations(plan,inventory)
        reader = RestrictedReader(records)
        frames = tuple((row['scene_id'],row['image_id']) for row in plan['development_declared'])
        need(len(frames) == len(set(frames)) == 400 and
             Counter(scene for scene,_ in frames) == {scene:50 for scene in SCENES}, 'Development schedule differs')
        rgb = {(row['scene_id'],row['image_id']):row['rgb'] for row in plan['development_declared']}
        phase = 'projection'
        bound = projection.bind_projection(OBJECTS, frames,
            evidence.table(reader.read(STAGE/'native/ground_truth.csv'),projection.GT_HEADER),
            evidence.table(reader.read(STAGE/'native/per_frame_metrics.csv'),projection.PER_HEADER),
            evidence.table(reader.read(STAGE/'native/selected_detections.csv'),projection.SELECTED_HEADER))
        need(len(bound['retained_gt_ids']) == 215, 'Original C0 215 GT identities differ')
        phase = 'metadata'
        banks = {obj:metadata(reader,obj) for obj in OBJECTS}
        need(sum(len(bank) for bank in banks.values()) == 18199, 'Own successful-template total differs')
        phase = 'raw_nms_assignment'
        per_combo, totals, eligible_totals = [], Counter(), Counter()
        zero = 0; identities, eligible_ids = [], []
        budget = dict(decoded_bytes=0)
        for index,declaration in enumerate(plan['candidates']):
            key = tuple(declaration[name] for name in ('object_id','scene_id','image_id'))
            obj,scene,image = key
            raw = parse_raw(reader,declaration,banks[obj],rgb[scene,image],budget)
            kept = numeric.nms(raw,threshold=.3)
            truth = bound['truth'][key]
            all_counts, all_labels = numeric.evaluate(kept,truth,False,threshold=.5)
            eligible, eligible_labels = numeric.evaluate(kept,truth,True,threshold=.5)
            need(kept == bound['selected'][key], 'Full C0 NMS selected tuple/order/score bits differ')
            need(all_labels == bound['all_labels'][key] and eligible_labels == bound['eligible_labels'][key],
                 'Full C0 GT assignment identity/labels differ')
            counts = dict(raw=len(raw),selected=len(kept),tp=all_counts['tp'],fp=all_counts['fp'],
                fn=all_counts['fn'],gt=all_counts['gt'],eligible_tp=eligible['tp'],eligible_fp=eligible['fp'],
                eligible_fn=eligible['fn'],eligible_gt=eligible['gt'],ignored=eligible['ignored'],
                all_iou_sum=all_counts['matched_iou_sum'],eligible_iou_sum=eligible['matched_iou_sum'],
                negative_fp=all_counts['fp'] if not truth else 0)
            need(counts == bound['per'][key], 'Full C0 per-frame metrics differ')
            own_ids = [(*key,gid) for label,gid in all_labels if label == 'TP']
            own_eligible = [(*key,gid) for label,gid in eligible_labels if label == 'TP']
            identities.extend(own_ids); eligible_ids.extend(own_eligible)
            zero += not raw
            totals.update({name:all_counts[name] for name in ('tp','fp','fn','gt','ignored')})
            totals.update(raw=len(raw),selected=len(kept),negative_fp=counts['negative_fp'])
            eligible_totals.update({name:eligible[name] for name in ('tp','fp','fn','gt','ignored')})
            per_combo.append(dict(object_id=obj,scene=scene,image=image,counts=counts,
                canonical_raw_sha256=canonical_digest(raw),canonical_selected_sha256=canonical_digest(kept),
                allGT_TP_ids=own_ids,eligible_TP_ids=own_eligible))
            if (index+1) % 100 == 0:
                print(json.dumps(dict(phase=phase,combinations=index+1,raw_rows=totals['raw'])),flush=True)
        need(len(per_combo) == 2400 and totals['raw'] == 457279 and zero == 390,
             'Complete C0 raw/zero scope differs')
        need((totals['tp'],totals['fp'],totals['fn'],totals['gt']) == (215,42112,185,400),
             'C0 TP/FP/FN/GT baseline differs')
        need(tuple(sorted(identities)) == bound['retained_gt_ids'] and
             tuple(sorted(eligible_ids)) == bound['eligible_retained_gt_ids'], 'Original GT identities not retained exactly')
        phase = 'end_recheck'
        reader.recheck()
        for pin in sources:
            stable.pin_equal(stable.hash_file(pin['path']),pin)
        bootstrap_json(PLAN_PIN); bootstrap_json(INVENTORY_PIN)
        write_json(out/'per_combination.json',per_combo)
        write_json(out/'original_c0_gt_identities.json',dict(allGT=identities,eligible=eligible_ids,
            gt_projection_independently_reconstructed=False))
        result = dict(schema='c0_raw_nms_projection_binding_v1',passed=True,
            scope='Complete C0 fallback raw, own metadata, NMS and inherited GT/result projection replay',
            objects=list(OBJECTS),frames=400,object_frame_combinations=2400,raw_rows=totals['raw'],
            zero_raw_combinations=zero,selected_rows=totals['selected'],allGT=dict(totals),eligible=dict(eligible_totals),
            original_allGT_identity_count=len(identities),original_allGT_identities_exact=True,
            full_raw_fields_order_score_bits_pose_and_bbox_checked=True,full_selected_fields_and_labels_exact=True,
            per_frame_metrics_exact=True,source_pins=sources,plan=PLAN_PIN,inventory=INVENTORY_PIN,
            payload_pins=[record['pin'] for record in records],payload_unique_files_read=len(reader.seen),
            payload_content_reads=reader.read_count,payload_end_hash_rechecks=len(reader.pins),
            payload_total_unique_bytes=reader.total_bytes,own_templates=sum(map(len,banks.values())),
            decoded_raw_bytes=budget['decoded_bytes'],maximum_decoded_raw_bytes=268435456,
            maximum_single_payload_bytes=MAX_FILE,maximum_total_unique_payload_bytes=MAX_TOTAL,
            maximum_output_bytes=MAX_OUTPUT,
            geometry=dict(width=848,height=848,padding_ltrb=[64,64,64,244]),
            nms_iou=.3,assignment_iou=.5,eligible_visibility=.5,
            python_flags=dict(optimize=sys.flags.optimize,ignore_environment=sys.flags.ignore_environment,debug=__debug__),
            gt_projection_independently_reconstructed=False,dataset_files_opened=0,dataset_indexes_opened=0,
            image_reads=0,image_decodes=0,bank_payload_reads=0,native_calls=0,matcher_calls=0,
            real_pixel_input_freeze=False,real_pixel_execution=False,quality_improvement_claim=False,
            performance_claim=False,production_promotion=False,
            limitations=['GT is inherited frozen projection; no official annotation reconstruction performed',
                         'Raw matcher output is replayed, not regenerated from pixels',
                         'No all-attempt bank/pixel operator replay, new verifier score or quality measurement',
                         'No OS filesystem lock; stable handle/path stamps, SHA pins and end hashes are observations'])
        write_json(out/'result.json',result)
        need(sum(path.stat().st_size for path in out.iterdir()) <= MAX_OUTPUT, 'Combined output ceiling exceeded')
        print(json.dumps(dict(passed=True,combinations=2400,raw_rows=457279,original_GT_identities=215,
                              result=stable.hash_file(out/'result.json'))),flush=True)
        return 0
    except BaseException as error:
        write_json(out/'failure.json',dict(passed=False,phase=phase,error=repr(error),
            dataset_files_opened=0,image_reads=0,native_calls=0,production_promotion=False))
        raise


if __name__ == '__main__':
    need(len(sys.argv) == 2, 'usage: prepare_c0_raw_binding_v1.py fresh_output_name')
    raise SystemExit(replay(sys.argv[1]))
