"""Create a paired numeric report; does not edit completed classification inputs."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from classify import HERE, V2, check, need, pin, rows, score

RESULT = HERE/'run_20261022_v2/result.json'
RESULT_SHA = 'b96383b4bcf32f809cefa46725154c06424992ca72edf1e2b7d655d69f4b5872'
DEFINITIONS = """本报告只解释固定 RGB TP 姿态、同一物理锚点和预先规定的 floor/ceiling native 网格邻点。215 个身份各含 RGB/二值两臂；所有结果均由已冻结数字证据推导，独立 Phase2 总审计仍是结论接受门槛。

native_neighbor_path 按以下顺序划分，分类互斥：

| 名称 | 精确定义 |
|---|---|
| no_reachable_parent | 预定邻点没有可达粗层父；本次为 0 |
| all_reachable_coarse_rejected | 没有任何可达父满足原粗层严格 score>85 |
| admitted_window_maximum_below85 | 有 admitted 父，但所有 admitted window 的 native winner 都不满足 score>=85 |
| neighbor_below85_while_window_winner_passes | 有 admitted window winner>=85，但 admitted 路径上所有预定邻点均<85 |
| neighbor_passes_but_local_winner_displaced | admitted 路径有邻点>=85，但没有预定邻点成为实际发出的首个行优先 winner |
| native_neighbor_emitted | 至少一个 admitted 父的已接受 native winner 就是某个预定邻点 |

physical_on_grid=0 仅表示原物理锚点不能直接编码为 T4/offset1 的 native 网格点。physical_in_domain=0 时独立物理分数未定义，不能当成零分或检测失败。本次所有 physical 分数都有定义。反事实被拒父的细层 window 已计算，但不会被当成原检测器的真实发出。

traced_propagation_path 另行跟踪可达父真实预测发出的 occurrence：pre_support/post_support 分别要求原模板框/完整跨模板 representative 框与目标 GT 的 IoU>=0.5；selected_support 还要求该 representative 经完整 full-class NMS 保留；assigned_target 还要求其 all-GT greedy assignment 的 TP ID 恰为目标 GT。按 assigned、selected、post、pre 的优先顺序分类。若 representative 更换后才提供 GT 支持，也保留 pre_support=False/post_support=True 的区别。

这里只是被追踪同姿态 occurrence 的支持，不能替代完整同模板或 full-class 检测支持。67 lost/148 retained 来自原 V22 全类别结果，另用冻结的完整 NMS/assignment 逐身份核对；不能由当前同姿态失败推断其它姿态或位置都失败。原 V22 的 57 个无 post-raw IoU>=0.5 与 10 个 NMS loss 仍是独立的整体结果分类。

图像 response-map、gradient/quantization 的正确性不由本报告独立证明。模板、阈值、NMS、默认算法均未更改；没有训练/留出图/磁片输入、原生调用或新增图像哈希。没有准确率提升、泛化、速度或内存优化结论。
"""


def report(output):
    result_pin = pin(RESULT);need(result_pin['sha256'] == RESULT_SHA, 'Wrong fixed classification result')
    result = json.loads(RESULT.read_bytes())
    for value in result['input_pins']+result['source_pins']+result['output_pins']:
        check(value)
    classified = list(rows(HERE/'run_20261022_v2/per_gt_arm.csv'))
    identities = defaultdict(dict)
    for row in classified:
        key = tuple(int(row[name]) for name in ('object_id', 'scene', 'image', 'gt_id'))
        need(row['arm'] not in identities[key], 'Repeated identity/arm');identities[key][row['arm']] = row
    need(len(identities) == 215 and all(set(value) == {'rgb', 'binary_empty_mask'} for value in identities.values()),
         'Paired identity membership differs')
    binary = {int(arms['binary_empty_mask']['job_id']): arms['binary_empty_mask'] for arms in identities.values()}
    lost = {job: row for job, row in binary.items() if row['v22_status'] == 'lost'}
    window_scores, neighbor_scores = defaultdict(list), defaultdict(list)
    links_path = V2/'probe_phase2_v1/native/parent_links.csv.gz'
    expected_links_pin = next(value for value in result['input_pins'] if Path(value['path']) == links_path)
    check(expected_links_pin)
    for row in rows(links_path):
        job = int(row['job'])
        if job in lost:
            window_scores[job].append(score(row['winner_score_bits']))
            neighbor_scores[job].append(score(row['point_score_bits']))
    counterfactual = {}
    for path in sorted({row['native_neighbor_path'] for row in lost.values()}):
        selected = [(job, row) for job, row in lost.items() if row['native_neighbor_path'] == path]
        counterfactual[path] = dict(identities=len(selected),
            v22_binary_categories=dict(Counter(row['v22_binary_category'] for _, row in selected)),
            any_reachable_window_winner_at_least85=sum(max(window_scores[job]) >= 85 for job, _ in selected),
            any_reachable_native_neighbor_at_least85=sum(max(neighbor_scores[job]) >= 85 for job, _ in selected),
            maximum_physical_score=max(float(row['physical_score']) for _, row in selected),
            maximum_native_neighbor_score=max(max(neighbor_scores[job]) for job, _ in selected))
    paired = []
    for identity, arms in sorted(identities.items()):
        rgb, binary_row = arms['rgb'], arms['binary_empty_mask']
        row = dict(zip(('object_id', 'scene', 'image', 'gt_id'), identity))
        row.update(v22_status=binary_row['v22_status'], v22_binary_category=binary_row['v22_binary_category'])
        for arm, value in (('rgb', rgb), ('binary', binary_row)):
            for field in ('job_id', 'template_id', 'training_image', 'angle', 'scale', 'physical_on_grid',
                          'physical_in_domain', 'physical_score', 'legal_native_points',
                          'coarse_admitted_parents', 'max_neighbor_score_any_parent',
                          'max_neighbor_score_admitted_parent', 'native_neighbor_path',
                          'traced_propagation_path', 'pre_support', 'post_support', 'selected_support', 'assigned_target'):
                row[arm+'_'+field] = value[field]
        paired.append(row)
    with (output/'paired_215.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    (output/'COUNTERFACTUAL_FINE_CHECK.json').write_text(json.dumps(counterfactual, indent=2)+'\n', encoding='utf-8')
    (output/'DEFINITIONS.md').write_text(DEFINITIONS, encoding='utf-8')
    text = """215 个 RGB 正控全部在预定 native 邻点发出，并由追踪到的代表框完成目标 assignment。

在原 V22 的 67 个 RGB TP 损失身份中，二值同姿态路径分为：

| 固定邻点路径 | 数量 | 原 V22 整体结果 |
|---|---:|---|
| 全部可达 coarse 父被原阈值拒绝 | 23 | 23 个无 post-raw IoU>=0.5 |
| 存在 admitted 父，但其全部 window 最大值<85 | 44 | 34 个无 post-raw；10 个整体 NMS loss |

67 个物理锚点分数及其全部预定 native 邻点分数均<85。23 个 coarse 全拒案例即使看全部反事实细层 window，也没有 winner>=85；另 44 个中仅 1 个被拒父的反事实 window winner>=85，且它的预定邻点仍<85。因此不能把 23 个解释为仅粗层剪枝损失；单看粗层门槛并不足以解释这些固定位置的低细层分数。

67 个损失的追踪同姿态 occurrence 都没有 IoU>=0.5 支持；该结论只针对本次固定姿态/父集合。原 V22 的 10 个整体 NMS loss 本来有其它模板/位置的 post-raw 支持，所以两种分类并不矛盾。

148 个 retained 身份是对照：同姿态路径仍有 13 个 coarse 全拒、63 个 admitted window 最大值不足；另 26 个邻点低分但其它 winner 通过、25 个邻点通过但被 winner 位移、21 个邻点实际发出。不能把同姿态失败当作全类别检测失败。二值 215 个物理锚点有 179 个 off-grid（loss 52、retained 127），仅作注释。

详见 paired_215.csv 的215行成对记录、COUNTERFACTUAL_FINE_CHECK.json 的原始计数，以及 DEFINITIONS.md 的边界。完整逐臂430行位于 ../run_20261022_v2/per_gt_arm.csv。独立 Phase2 数字总审计尚是接受门槛；此报告没有修改算法或宣称准确率/速度提升。
"""
    (output/'RESULTS.md').write_text(text, encoding='utf-8')
    for value in result['input_pins']+result['source_pins']+result['output_pins']:
        check(value)
    freeze = dict(completed=True, numeric_report_only=True, classification_result=result_pin,
                  counterfactual_input=expected_links_pin, source=pin(HERE/'report.py'),
                  output_pins=[pin(path) for path in sorted(output.iterdir()) if path.is_file()],
                  paired_identities=215, dataset_image_bytes_opened=0, native_calls=0,
                  independent_phase2_audit_required=True, accuracy_improvement_claim=False,
                  speed_claim=False)
    (output/'REPORT_FREEZE.json').write_text(json.dumps(freeze, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(completed=True, paired_identities=215, counterfactual=counterfactual)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();output = args.output.resolve()
    need(output.is_relative_to(HERE) and not output.exists() and output.parent.is_dir(), 'Fresh contained report output required')
    output.mkdir();report(output)
