# supplied-label 轮廓链独立 oracle 静态审查 V1

2026-10-23。审查 `independent_edge_oracle.py` 与 `test_independent_edge_oracle.py` 完整源码，
并核对 [GREEN receipt](independent_edge_green_v1/receipt.json) 和实际保存的 unittest 日志。
**已核范围内未发现 material finding。** 结论限于 supplied-label 数学层级：细化、图分解、采样、所有权及整数格权重。
这不表示真实图像来源、梯度、候选验证器、准确率、native 性能或全量实验通过。

## 当前源码与既有执行的绑定

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| independent_edge_oracle.py | 13,628 | `bca66cf17ab0036aecd3c7f6f141e925d50055385cd95d53fa9659299bab5315` |
| test_independent_edge_oracle.py | 12,637 | `7736b81e046b693983b10ccc2c619b49de2881cc13eef3e7b2fd0e226a6a97cc` |

本轮读取并 hash 上述小源码及对应 GREEN 小快照：快照实际 pin、当前源码均相同。
GREEN 回执为 14 unittest methods、0 failures、退出 0，保存日志逐项包含两组批量案例并以 `OK` 结束。
unittest 日志用时 0.527 s；guard wall 0.687 s，观测 peak working set 20,873,216 bytes、14 次采样。
它是既有真实运行证据，本次没有再次执行 tests。资源上限及观测边界沿用
[链组件审查](STATIC_CHAIN_REVIEW_V1.md)，不能将这几个时间解释为图像匹配性能。

## 实现独立性与分解完整性

oracle 只导入标准库；没有导入或调用 `edge_chains`。两侧只共享规定的字段 schema。
测试模块分别导入两侧，使用 dataclasses.astuple 去掉类身份后比较字段，这是比较边界，不是 oracle 算法复用。

| 项目 | 独立方法与核对 |
| --- | --- |
| 细化 | 使用 `(x,y)` active 集，直接计算张量无关的布尔删除谓词；两轮各先求完整删除集再统一删除。环转换写成当前真且前一邻居假，含首尾；图外点不在 active，等价于零边界。合法标签与矩形校验也自行实现。 |
| 8 邻接图 | 枚举物理节点的全部坐标对，以 Chebyshev 距离恰为 1 建无向图；不同于 core 的固定 offset 邻居展开。 |
| trail 分解 | 先把 degree≠2 节点当 boundary，直接加入 boundary-boundary 边及孤点；再找 degree2 诱导子图的连通分量。每个该分量内部最大度≤2，只能是路径或环。纯环没有 boundary attachment；路径恰有两个 attachment，因此内部边加两端边完整形成最大 trail。 |
| 返回环 | 两 attachment 的 outside boundary 相同即 returning；序列只加一次该 junction，closing edge 由 closed 标记补足。不同 boundary 时是开链；零 attachment 时必须走完整纯环。分量路径/环均检查访问节点等于完整 component，异常形状直接报错。 |
| 分解无遗漏 | boundary-boundary、boundary-degree2、degree2-degree2 三种边分别由直接边、attachment、分量内部覆盖；degree0 由孤点覆盖。不依赖 core 的全局 used-edge traversal。 |
| 自有 canonical | 闭链显式列出所有循环移位及反向移位取最小，独立于 core 的“唯一最小 ID 起点、只比较两方向”化简。开链取正反序最小；直接 boundary 边的较小 ID 在前。最终按序列/开闭排序分配 chain ID。 |
| 弧长采样 | 自行形成包含 closed closing edge 的整数长度累计序列，再用 bisect_left 找首次达到严格 `<total` 标记的节点。闭边到达索引用 modulo 回到首点；去重后按原链顺序返回。与 core 的递增游标实现不同。 |
| 所有权与完整字段 | 原始采样 memberships 决定最小 chain ID ownership；bbox/cells 在 owned 物理点上计算。零 owned 链仍在 chains/samplings 中；整个空模板报错。chain_index 自 owner 的完整 canonical 序列查得。 |

## Fraction 与整数 L/W/D

oracle 先给占用格 g 的每点独立赋 `Fraction(1, C*n_g)`，而不是调用 core 的 LCM 权重函数。
这些分数分子均为 1，分母公倍数
`D=lcm(C*n_g)=C*lcm(n_g)`，因此 `common=D//C` 恰为合同的 L，
点权 `Fraction(1,C*n_g)*D` 恰为 `L/n_g`。所有运算为精确 Fraction/整数。
`cell_counts` 由 cells.count 独立形成；源码明确检查缩放后分母为 1。
测试另核每格质量 `1/C`、所有质量和为 1、权重和为 D，以及每点 `W/D` 恰等于该分数。
不等格数 `(3,2,3,3)` 的 literal 还固定要求 `L=6,D=24`，避免仅验证某个等比例缩放分数。

## 612 个批量案例实际比较什么

批量源代码枚举所有 `range(512)` 的 3×3 **占用 bitmap**，每个 bitmap 配确定性的 0..7 标签；
另以 seed=20261023 生成 100 个 4×4/5×5 多标签案例，各尺寸 50 个。
这不是所有 3×3 多标签赋值，也不承诺随机案例各不相同。两个方法都检查最终案例计数；
时间不足会 self.fail 标记 incomplete，不能静默跳过尾部。GREEN 日志确认两批方法都为 OK。

每个案例的 `assert_complete_grid` 都执行下列检查，而不是只比较最终点数：

1. 完整 ThinningResult：width/height、eligible 原标签、幸存标签、每轮删除数；输入维度/eligible 直接由 source 核对，
   终止轮 `(0,0)`、删除数守恒及幸存标签不改写另有不变量。
2. 对原 grid **及** thinned grid 都重建 oracle chains，随后完整 chain 字段与 core 比较。
   独立 graph partition 从全部坐标对重新形成 expected edges：represented 节点恰覆盖全图，
   observed 无向边 Counter 恰为每条 expected edge 一次，故同时排除漏边、额外边和重复边。
3. graph partition 还检查 ID 连续、单链物理点唯一、开链内部 degree2 且两端非 degree2、
   孤点 degree0、闭链长度≥3，以及 returning 恰有一个非 degree2 junction、纯环没有 junction。
   开/闭 canonical 及全局排序直接核对，因而并非只让两侧错误分解相互一致。
4. 每条原图/细化图链的采样都比较完整 chain_id、采样物理 ID 序和总弧长。
5. 若幸存节点为空，两侧模板入口都必须 ValueError；否则以 astuple 递归比较整个 TemplateEvidence：
   thinning、chains、samplings、ownership、所有 WeightedSample 字段、16 个 cell counts、C、L、D，未只挑选汇总字段。
6. 对非空模板再次核 Fraction 质量、W/D、格计数和权重和；另有返回环、共享所有权、闭边标记、
   原方向保留、2×2 擦除及不等格 literal，拒绝共享 fixed-empty stub 造成的虚假一致。

## 六项语义 fault 的补充静态核对

另静态读取 `test_edge_faults_v1.py`、`run_synthetic_checks_v2.py` 和
[faults GREEN receipt](edge_faults_green_v1/receipt.json)：六个临时源码改动分别为 batch 内删除、
删除对角边、闭链重复起点、跳过恰落标记节点、最大 chain ID 所有权、遗漏闭边弧长。
`rejected()` 先在正对照 core 上比较独立 expected，再导入真实临时源码并在 assertRaises **外**执行 operation；
仅后续全字段比较在 assertRaises(AssertionError) 内，故导入、anchor 或运行失败不能冒充被检出的语义 fault。
六个改动按源码均会产生可返回的错误结果；已有回执为 6/6 methods GREEN、退出 0、峰值工作集 22,781,952 bytes，
不是一次新的全量 oracle 验证。临时副本由 TemporaryDirectory 删除，未作为六份持久 mutant 字节证据保留。
v2 只为 faults/candidate 定义显式 suite/source 列表，继续使用同一快照、guard、RED/GREEN 判断逻辑；
本补充不审 candidate 算法，也不声称 `%TEMP%` 临时副本受 payload 目录字节监控。旧 v1 和既有测试未改。

## 限制与修改范围

静态检查没有发现需要新增 RED 再修复的实质问题，未改 oracle、测试、执行器或旧回执。
按 root 指示，已将上一份 `STATIC_CHAIN_REVIEW_V1.md` 首个合同链接的 fragment 删除，保留文件链接。

本轮只读这些小源码/快照/回执/日志，并做小源码 pin 核对；没有运行测试、Git、native、编译，
没有读取真实图片、数据索引、bank/raw 或封存数据。未单独重新审计 oracle RED 回执或完整运行库闭包。
一般图正确性的支持来自上述分量分解及权重推导，有限案例本身不能证明所有尺寸和全部 API 负输入。
尚无来自 RGB 的独立像素算子审计，也未覆盖后续坐标、兼容边、链对 DP、witness、NMS/GT 或工业泛化。
