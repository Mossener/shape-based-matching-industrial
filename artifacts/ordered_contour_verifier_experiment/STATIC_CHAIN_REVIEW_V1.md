# 轮廓链组件独立静态审查 V1

2026-10-23。按[合同第 2 节](../../docs/superpowers/plans/2026-10-23-ordered-contour-verifier-contract.md)、
合同中的整数格权重定义及 [CHAIN_DECISIONS_V1.json](CHAIN_DECISIONS_V1.json)，审查
`edge_chains.py`、`test_edge_chains.py`、`run_chain_checks_v1.py` 与已有 RED/GREEN 小回执。
**已核源码范围内未发现 material finding。** 本报告不表示独立 oracle、原生实现、真实图像或完整质量验证已经通过。

## 审查绑定

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| edge_chains.py | 15,259 | `5f7e9890a57014653363cd73d4af304ee2f228f55e7f0c12777a50a3e62b8f3d` |
| test_edge_chains.py | 10,709 | `7175ecf4981492825343215e1e5fbcde6950d5705a5c7531a0107a215ebe2047` |
| run_chain_checks_v1.py | 4,933 | `7d7507705e89aeb6c8158c34b673e3f74a01c8a9ca6e50157de2a057b53db365` |
| CHAIN_DECISIONS_V1.json | 1,813 | `ee9ea5b3177e4fbd3e3010f6f988b3ef56111da94145ed4a38616850a47b9544` |

本次只 hash 上述小源码/决策文件及 GREEN 小源码快照；GREEN 的实现和测试快照 pin 均与实际字节、当前源码一致。
RED 与 GREEN 的测试源码实际逐字节相同，旧实现与新实现分别保留在自己的运行目录，未覆盖失败。

## 算法逐项核对

| 检查点 | 静态结论与边界 |
| --- | --- |
| 标签与输入 | `_grid` 拷贝非空矩形 list/tuple；严格要求 builtin int 0..7 或 255，拒绝 bool、浮点及 ragged/空行。label=0 仍为有效像素；不把 spread 多 bit 值当方向。输出网格为 tuple，幸存方向取原 eligible 值。 |
| Zhang–Suen 同 batch | `_delete_batch` 只读给定 active set；每个子迭代先算完整删除集，再统一 difference_update。第二子迭代读取第一批删除后的位图。邻序为 N/NE/E/SE/S/SW/W/NW，转换包含 NW→N；两组轴向三乘条件与合同一致，图外值为 0，保留终止 `(0,0)` 轮。 |
| 全 8 边恰好分解一次 | adjacency 包含全部合法 8 邻居，ID/邻居排序固定。degree≠2 起点逐条消费未用边，只沿 degree2 节点延伸，在第一个非 degree2 节点停下；不越过分叉拼链。起步跳过 used，途中重复边抛错，结束时 used 与完整无向 edge set 比较。 |
| 返回环、纯环与孤点 | `_walk` 回到 start 时记录 closed，不追加第二份 start。第一阶段的闭合 trail 标 returning；剩余全 degree2 边生成纯闭链，未闭合则错误。孤点保留单点开链。简单图中该走法的内部 degree2 节点不会重复；终点分叉可为不同链共享物理点。 |
| canonical 与稳定 ID | 开链取完整正反序最小值。闭链 ID 唯一，所有最小循环移位必从唯一最小 ID 起，因此只需比较该起点的两方向，等价于全旋转/反向最小值。按 `(canonical pixels, closed)` 排序编号；returning 不改变合同规定的排序键。 |
| 弧长与闭边采样 | axis=1000、diagonal=1414，全部使用整数。标记为严格小于总长的 2000*k，使用累计长度第一次达到标记的实际节点；开链首尾固定保留。闭链把闭边加入总长，落在闭边的标记映射到首点，并按原链顺序对物理 ID 去重。短链和单点不丢弃。 |
| 所有权与零贡献链 | memberships 只来自各链采到的物理点，owner 为最小 chain ID；ownership/sample 各物理 ID 仅一行。其余链的完整拓扑和原采样不删除，无 owned sample 的链保留且没有评分权重。整个模板无 owned sample 才抛输入合同错误；全无效场景仍可由 thin/extract 表示。 |
| 整数 cell/count/weight | bbox 沿全模板 owned 点固定，row/col 公式使用整数 floor，16 格计数包含零格。仅占用格计 LCM，点权为 L/n，分母 C*L；Python 任意精度整数避免 float/溢出歧义，正权和显式校验等于分母。chain_index 指向 owner 的完整 canonical 链位置，不等同于物理 ID 排序。 |
| 独立 API validation | sample_chain 拒绝非正 builtin-int width、非法 ID/flag、重复点、非 8 邻接步与少于三节点的闭链；closing edge 同样验证。没有 height/原 graph 的独立接口不能证明 graph 来源、最大 trail 或 thinning fixed point；源码与决策明确将它们放在接口边界外。prepare_template 自行组合 thin→extract→sample，避免该来源空缺。 |

未发现需要 root 先新增真实 RED 再修复的算法缺陷。这里的静态论证和手写测试不能替代独立枚举，
也不声称细化维持每个输入分量或每条厚边；例如全 2×2 eligible 块会被此固定规则消去，模板入口明确报错。

## 既有执行与资源观测

| 运行 | 现有实际结果 | 守护观测 |
| --- | --- | --- |
| [RED receipt](edge_chains_red_v1/receipt.json) | 25 unittest methods，66 assertion failures，退出 1；日志尾为 `FAILED (failures=66)`，没有 errors 项。`expected_phase_observed=true` 表示预期失败被观察到，不是算法通过。 | wall 0.563 s；Windows peak working set 18,550,784 bytes；11 次采样；reason=process_exit_nonzero。 |
| [GREEN receipt](edge_chains_green_v1/receipt.json) | 25 unittest methods，0 failure，退出 0；实际日志尾为 `OK`。 | wall 0.109 s；Windows peak working set 18,808,832 bytes；3 次采样；reason=null。 |

上述数值读取原回执，并静态核对实际保存日志尾部；本次没有重跑 tests。unittest 自身报告的 0.066/0.016 s
与 watchdog wall 不是同一计时口径，更不能解释为生产轮廓匹配耗时。native_output_bytes=0 指指定 payload
目录没有输出；stderr、guard logs、源码快照等仍存在，不能描述为整个实验零输出。

coordinator 使用 fresh 简单目录名，以 source 快照为实际 child cwd，执行 `python -B -m unittest -v`。
它检查当前 suite 源码执行前后 pin 相同、快照与 suite 当前字节相同；RED 还要求非资源故障的退出 1
和只含 failures 的 unittest 失败格式，GREEN 要求 guard passed、退出 0 和 OK。
suite 来源文件、guard、coordinator、Python executable 的前置 pin 在 invocation 中保留。

复用的 guard 对一个子进程按约 50 ms 查询 Windows peak working set、wall 以及 payload/execution
目录大小；含合并输出 64 MiB 检查，并单列 execution 64 MiB 检查。上限为 60 s、512 MiB、64 MiB。
这是观测后终止机制，可能在越界分配/写出后才观察到，不是 OS 内存或文件写入硬隔离；计时结束后写入的
最终 receipt、父目录 invocation 和静态源码快照不属于那次目录轮询的全部输出范围。
此 guard 不聚合额外子进程树；当前数学组件/测试没有启动额外 worker。

资源与证据限制还包括：suite 源码有执行后重查，guard/coordinator/Python 只有 invocation 前置 pin，
并非同等的执行后完整运行库审计；transitive Python runtime 未完整 attested。
这不改变现有 tiny 运行结果，但不支持把当前 observed limits 称为任意程序的强制隔离保证。

## 范围与后续门槛

已读完整上述组件、测试、coordinator、决策、合同，以及 RED/GREEN receipt、invocation、日志尾和复用 guard。
没有读取真实图像、eligible 真实网格、bank/raw 或封存数据，没有执行 tests、Git、native、编译或基准；未改代码或旧回执。

独立 oracle 当时仍在开发，本报告不审其实现、不追认其结果。真实来源、warp/标签生成、C0 origin/候选连接、
兼容图与稀疏 DP、witness/NMS/GT、完整数据质量及性能均未由这个链组件证明。
后续须按合同分别完成独立 tiny 对照、冻结输入/预算和真实执行审计；不能从本报告推出全量通过、准确率提升或生产推广。
