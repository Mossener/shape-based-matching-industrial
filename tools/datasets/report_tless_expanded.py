#!/usr/bin/env python3
"""Create committable GT-only coverage reports; never invokes a matcher."""
import csv
import json
from pathlib import Path
from collections import Counter,defaultdict

ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'artifacts/public_datasets'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    plan=read(ART/'tless_expanded_plan.json');manifest=read(ART/'tless_expanded_manifest.json');audit=read(ART/'tless_expanded_audit.json')
    index=read(ROOT/'datasets/tless_expanded/index.json');assert audit['passed'] and manifest['status']=='complete'
    objects=index['target_object_ids'];counts=defaultdict(Counter);scene_counts=defaultdict(Counter)
    vis_names=['vis_0_to_0_1','vis_0_1_to_0_25','vis_0_25_to_0_5','vis_0_5_to_0_75','vis_0_75_to_1']
    for row in index['test']:
        split=row['split'];present=set();scene=scene_counts[row['scene_id']];scene['frames']+=1
        for item in row['instances']:
            obj=item['obj_id'];scene['all_gt_instances']+=1
            if obj not in objects:scene['distractor_instances']+=1;continue
            present.add(obj);c=counts[obj,split];v=item['visib_fract'];assert 0<=v<=1
            c['instances']+=1;c['eligible_vis_ge_0_5']+=v>=.5
            position=0 if v<.1 else 1 if v<.25 else 2 if v<.5 else 3 if v<.75 else 4
            c[vis_names[position]]+=1
            scene['target_instances']+=1;scene['eligible_target_instances_vis_ge_0_5']+=v>=.5
        scene['joint_target_positive_frames' if present else 'joint_target_negative_frames']+=1
        for obj in objects:counts[obj,split]['positive_frames' if obj in present else 'negative_frames']+=1
    object_rows=[]
    for obj in objects:
        for split in ['development','heldout_scene']:
            c=counts[obj,split]
            object_rows.append({'obj_id':obj,'object_group':'development' if obj in index['development_objects'] else 'heldout_object',
                                'scene_split':split,**{field:c[field] for field in ['positive_frames','negative_frames','instances','eligible_vis_ge_0_5']+vis_names}})
    write_csv(ART/'tless_expanded_object_coverage.csv',object_rows)
    scene_rows=[{'scene_id':s,'split':plan['scenes'][str(s)]['split'],**{field:scene_counts[s][field] for field in
                ['frames','joint_target_positive_frames','joint_target_negative_frames','all_gt_instances','target_instances','eligible_target_instances_vis_ge_0_5','distractor_instances']}} for s in sorted(scene_counts)]
    write_csv(ART/'tless_expanded_scene_coverage.csv',scene_rows)
    view_rows=[{'obj_id':int(obj),**{k:v for k,v in row.items() if not isinstance(v,list)},
                'selected_elevation_min_deg':row['selected_model_frame_elevation_deg'][0],
                'selected_elevation_max_deg':row['selected_model_frame_elevation_deg'][1]} for obj,row in audit['training_view_direction_coverage'].items()]
    write_csv(ART/'tless_expanded_training_coverage.csv',view_rows)
    report=['# T-LESS 扩展获取与GT覆盖报告','',
        '已完成固定官方子集获取及独立离线校验，未运行训练、开发或留出匹配。旧tiny的文件、脚本和sealed heldout没有改动。','',
        '| 项目 | 最终计划 | 实际 |','| --- | ---: | ---: |',
        f'| 目标物体 / 新测试场景 | 8 / 16 | 8 / 16 |',
        f'| 训练RGB / 测试RGB | 576 / 800 | 576 / 800 |',
        f'| development场景 / heldout场景图像 | 400 / 400 | 400 / 400 |',
        f'| 原始保留成员 | 6,100 | {len(manifest["files"]):,} |',
        f'| 原始成员字节 | {plan["summary"]["disk_bytes_original_members"]:,} | {manifest["summary"]["member_bytes"]:,} |',
        f'| 获取Range响应体字节 | {plan["summary"]["planned_block_body_bytes"]:,} | {manifest["download"]["acquisition_response_body_bytes"]:,} |',
        f'| 含metadata的累计响应体字节 | 1,460,279,529 | {manifest["download"]["response_body_bytes"]:,} |','',
        '最终计划与实际没有数量或取样偏差。2,000,000,000 bytes硬预算剩余539,720,471 bytes；没有待取RGB或剩余请求。保留数据约614MiB，块内depth未落盘，完整ZIP未下载。全包SHA是官方LFS元数据，本次未声称验证全包哈希。','',
        '目标为1,2,5,8,12,17,25,29；前6类用于开发，25/29是未按匹配结果调参的物体泛化组。每物体72个训练视角，16场景各取全部50个官方BOP19帧。排除tiny全部场景2/3/5/9。scene11/13的GT-only交换及其原因已记录在冻结plan和协议。','',
        '## 每目标正负例与实例','',
        '一张图可对多个目标同时为正例；下表按one-vs-rest解释，不能把各行正例数相加当作唯一图像数。eligible是visib_fract≥0.5的实例。development场景中的25/29仅作封存物体组的GT覆盖记录，不授权使用其匹配结果调参。','',
        '| 目标 | 物体组 | dev正/负图 | dev实例/eligible | held场景正/负图 | held实例/eligible |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for obj in objects:
        a=counts[obj,'development'];b=counts[obj,'heldout_scene'];group='development' if obj in index['development_objects'] else 'heldout object'
        report.append(f"| {obj} | {group} | {a['positive_frames']}/{a['negative_frames']} | {a['instances']}/{a['eligible_vis_ge_0_5']} | {b['positive_frames']}/{b['negative_frames']} | {b['instances']}/{b['eligible_vis_ge_0_5']} |")
    report+=['','## 实例可见性分层','',
        '区间为[0,0.1)、[0.1,0.25)、[0.25,0.5)、[0.5,0.75)、[0.75,1]。只统计8个目标的GT实例；所有可见性值均保留，未按容易程度剔除图像。','',
        '| 场景split | <0.1 | 0.1–<0.25 | 0.25–<0.5 | 0.5–<0.75 | ≥0.75 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for split in ['development','heldout_scene']:
        report.append('| '+split+' | '+' | '.join(str(sum(counts[o,split][name] for o in objects)) for name in vis_names)+' |')
    report+=['','逐对象分层见`tless_expanded_object_coverage.csv`。','',
        '## 场景与干扰','',
        '| 场景 | split | 图像 | 对8目标联合正/负 | 目标实例/eligible | 其他物体实例 |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for r in scene_rows:
        report.append(f"| {r['scene_id']} | {r['split']} | {r['frames']} | {r['joint_target_positive_frames']}/{r['joint_target_negative_frames']} | {r['target_instances']}/{r['eligible_target_instances_vis_ge_0_5']} | {r['distractor_instances']} |")
    report+=['','每目标在两个场景split均有正负例。联合负例场景也保留。每个所选场景中全部物体的GT框和可见比例在便利索引中；其他物体可成为相似形状干扰，但本次没有据匹配结果预选“最相似”干扰或断言编号对应特定形态。','',
        '## 训练方向与独立核验','',
        '每类从1,296真实视角按官方旋转矩阵的确定性farthest规则选72项；精确ID在plan中。独立审计重算后完全一致。所选方向覆盖约-87°到+86°的模型坐标elevation；完整方向集到所选集合的最坏方向差23°–25.4°。逐对象数值在`tless_expanded_training_coverage.csv`，不将3D方向当作2D角度真值。','',
        '独立审计逐一核验全部6,100成员的CRC32、SHA-256和尺寸；核对每张RGB/mask尺寸、全部GT实例/框/可见性字段、每场景帧ID/数量、无depth、无旧tiny场景以及累计传输账本。便利索引schema2含target_object_ids、development_objects、strict_object_generalization，训练行直接含target_obj_id/class_id/mask，测试行保留所有GT。','',
        f"- 冻结plan SHA-256：`{audit['plan_sha256']}`",
        f"- acquisition manifest SHA-256：`{audit['manifest_sha256']}`",
        f"- 最终index SHA-256：`{audit['index_sha256']}`",'',
        '官方来源、CC BY 4.0署名、固定提交、传输请求、逐成员SHA/CRC分别见plan/manifest/audit；`docs/datasets/tless-expanded-protocol.md`说明冻结边界和运行命令。外部图像在本地忽略目录，报告、脚本和来源清单可提交。','',
        '本次只建立更广的真实数据与可复现分组，没有检测准确率、泛化分数或性能收益。参数须仅由development对象×development场景选择；新heldout场景和25/29物体匹配必须等完整配方冻结后进行。','']
    (ROOT/'docs/datasets/tless-expanded-acquisition.md').write_text('\n'.join(report),encoding='utf-8')
    print('Wrote GT-only object/scene/view CSV and docs/datasets/tless-expanded-acquisition.md')

if __name__=='__main__':main()
