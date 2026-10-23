# 标签网格上的轮廓链：合成验证 V1

日期：2026-10-23。细化、链分解、采样、所有权和精确格权重已在小型输入上通过两种实现对照。
这些结果不构成真实图像准确率、原生速度或生产推广依据；生产核心保持 V11，留出数据继续封存。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 手写测试 RED | 25 methods；66 assertion failures；无 errors；固定空桩 | [receipt](edge_chains_red_v1/receipt.json) |
| 原测试 GREEN | 25/25；测试字节与 RED 相同 | [receipt](edge_chains_green_v1/receipt.json) |
| 独立参考 RED | 14 methods；629 assertion failures；无 errors；独立空桩 | [receipt](independent_edge_red_v1/receipt.json) |
| 独立参考 GREEN | 14/14；包含全部 512 个 3×3 位图及 seed 20261023 的 100 个 4×4/5×5 小图 | [receipt](independent_edge_green_v1/receipt.json) |
| 临时源码故障 | 6/6 被独立结果比较拒绝；导入和计算异常不会算作检出 | [receipt](edge_faults_green_v1/receipt.json) |

612 个有限案例逐个比较完整细化网格及每轮删除数、原网格和细化网格的全部链与采样、
完整模板所有权、样本字段、16 格计数、LCM 和分母。还直接按坐标点对验证每条 8 邻接边
恰好出现一次、节点覆盖、最大 trail、闭环和规范顺序。全空及细化后全空的模板都必须报错。
这不是所有图像尺寸、全部标签排列或真实图像的穷举。

独立参考不导入被检组件的 helpers。图分解采用 degree-2 诱导子图的组件及 boundary attachments，
而被检实现从分叉沿未使用边走 trail；采样参考使用累计长度与 bisect；权重参考先计算
`Fraction(1, occupied_cells * cell_count)`，再还原精确整数。共同的合同定义和 Python 运行库仍是共享依赖。

六个故障分别是异步删点、删除对角边、闭环重复起点、跳过恰落采样标记的节点、
把共享点交给最大 chain ID，以及漏计闭合边弧长。每项都实际导入临时修改源码，正常生成结果后
才要求独立全字段比较失败；原组件和历史回执不变。

本轮由 Windows watchdog 约每 50 ms 观测一个子进程的 peak working set、wall 和输出目录，
上限为 60 s、512 MiB、64 MiB。三条 GREEN 的峰值分别为 18,808,832、20,873,216、22,781,952 bytes，
均退出 0，未触发上限。它是观测后终止机制，不能称作 OS 分配硬隔离；完整边界见
[组件静态审查](STATIC_CHAIN_REVIEW_V1.md)。unittest 用时不作为匹配性能指标。

可在本目录用标准库 Python 运行：

```text
python -B -m unittest -v test_edge_chains test_independent_edge_oracle test_edge_faults_v1
```

保留资源观测与源码快照的 Windows 入口：

```text
python -B run_chain_checks_v1.py edge GREEN fresh_edge_run
python -B run_chain_checks_v1.py oracle GREEN fresh_oracle_run
python -B run_synthetic_checks_v2.py faults GREEN fresh_fault_run
```

每次必须使用不存在的输出目录名。供应标签的图像来源、C0 原点连接、候选兼容图、NMS/GT
以及完整开发集识别和正式计时仍需各自验证；本报告不将它们追认为已通过。
