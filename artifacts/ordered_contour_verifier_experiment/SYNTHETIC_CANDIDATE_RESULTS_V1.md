# 候选坐标与轮廓兼容图：合成结果 V1

本阶段为 V32 的后继。实现 `candidate_compatibility.py`，以未伪造的模板/场景 factory evidence 为输入，逐项检查 signed-int64 坐标，建立半径 2、unsigned8 环形方向差不大于 1 的完整兼容关系，计算独立支持 A 与有序支持 B。它没有解码图像、生成真实梯度或调用生产 matcher。

坐标严格按 `p_canvas-tl → match+relative → q_padded-(left,top)` 转换。padded 中心越界不允许借邻点救回；分母保留所有 owned 样本。原图外但 padding 内支持合法。完整场景链保留拓扑，owned 样本按原 `chain_index` 恢复顺序；同模板链内一对一，跨模板链可复用场景点。zero-owned 链保留完整零结果。

| 实际运行目录 | 方法数 | 结果 | 观测 wall / peak working set |
| --- | ---: | --- | ---: |
| `candidate_red_v1/` | 33 | 零桩出现 110 assertion failures，0 errors | 0.828 s / 26,800,128 B |
| `candidate_green_v1/` | 33 | 33/33，通过相同测试字节 | 0.938 s / 26,685,440 B |
| `candidate_oracle_red_v1/` | 34 | 独立参考零桩出现 694 assertion failures，0 errors | 1.391 s / 22,716,416 B |
| `candidate_oracle_green_v1/` | 34 | 34/34 | 6.594 s / 22,269,952 B |
| `candidate_faults_green_v1/` | 7 | 七项临时源码故障均被独立数值比较拒绝 | 0.843 s / 29,577,216 B |

独立参考使用独立网格链实现及部分单射穷举，不调用被测的坐标/兼容边或 Fenwick helpers。全部 512 个 3×3 occupancy、两种方向 profile、三个模板和两种坐标变换形成 **6,144 个完整候选比较**，另逐链进行 6,144 次 brute-force 比较。所有可观测字段逐项比较，仅排除算法特有 WorkCounters。case/witness 再核仍使用同一独立 brute 函数，不声称第三套算法。最大 owned 模板样本 3、场景链点 5，0 跳过；独立 API 明确拒绝超过 8 点的链，不截断。

七个故障分别是：越界中心借邻点、方向 7/0 不环绕、半径 2 错减为 1、owned 按 physical ID 错序、origin 减法变加法、A witness 错选最大 ID、精确阈值改浮点比较。import 和 scoring 在预期 assertion 之外，运行异常不能冒充语义检出。

最后一个故障使用真实 factory 生成的 160×160 合法标签网格、465 个隔离模板点和 231 个场景点，得 A=B=252,644,263,725,730,863、D=388,683,482,654,970,560，精确分子比 `13D/20` 小 1。整数比较拒绝，binary64 交叉乘积却舍入为相等。未伪造 evidence 或权重。

每次运行使用独立 fresh 目录、执行时源码快照和回执；50 ms 观测进程 wall/peak working set/output，限额 60 s / 512 MiB / 64 MiB，未触发上限。这是观测后停止，不是 OS 分配隔离。静态审查见 `STATIC_CANDIDATE_REVIEW_V1.md`、`STATIC_CANDIDATE_ORACLE_REVIEW_V1.md`。

这些是有限合成输入上的正确性证据，不是图片数量、原生速度、真实识别质量或工业泛化收益。真实像素来源、全部 C0 模板重训回放、native 链/候选适配和完整开发集审计仍需继续。
