# 有序轮廓数学核心：合成测试结果 V1

补充归档：root 已将 oracle result 中的六个 source pin 逐字节核对后，复制到
[synthetic_oracle_source_archive_v1/manifest.json](synthetic_oracle_source_archive_v1/manifest.json)
所列目录。它们是执行后补存、与原 pin 精确一致的副本；不能追认为执行时快照，
也没有修改原 result/provenance 或补足原运行的 RSS 观测。

日期：2026-10-23。范围仅为 supplied compatibility graph 上的 Python 数学原型。
已有运行支持小合成图上的精确最优值、对应合法性和平局规则检查；
**不支持像素来源、真实图像准确率、native 速度、端到端效果或生产就绪结论。**
生产默认及 V31 未由本结果变更。本文只整理已存在的小型源码、回执和日志，
没有重跑测试、执行 Git、读取图像/raw/bank，亦未改写历史回执。

## 已有执行证据

| 检查 | 已捕获结果 | 主要证据 |
| --- | --- | --- |
| 30 项手工回归 RED | 固定零桩；exit 1；`Ran 30 tests`、`FAILED (failures=47)` | [RED receipt](synthetic_red_v1/receipt.json)、[RED stderr](synthetic_red_v1/stderr.txt) |
| 同一份 30 项手工回归 GREEN | 实现精确稀疏递推后 exit 0；30 项 `OK` | [GREEN receipt](synthetic_green_v1/receipt.json)、[GREEN stderr](synthetic_green_v1/stderr.txt) |
| 独立 tiny oracle GREEN | exit 0；21 项测试 `OK`，含下述全部穷举、有限案例和 mutation 检查 | [oracle result](synthetic_oracle_green_v1/result.json)、[oracle stderr](synthetic_oracle_green_v1/stderr.txt) |
| 核心源码静态审查 | `No material findings`；这是静态一致性结论 | [STATIC_REVIEW_V1.md](STATIC_REVIEW_V1.md) |

RED 和 GREEN 的手工测试 SHA256 都是
`64c2a2ac907a41434a14871db9176153ecc54f24fab07365042cdb38675d04b5`。
因此这条 RED→GREEN 证据使用的是同一份测试，改动来自零桩到核心实现。
RED 的 47 是 unittest 汇总的失败记录数，包含子案例，不能写成 47 个测试方法。
RED 核心 SHA256 是
`4db9b8f1db41473d77c46e9a1c681bc66146f5e30afcc07bea4104b297d9368c`；
GREEN 核心为下表所列 `190204…`。
独立 oracle 没有另存一条 RED 执行，不能将手工测试的 RED 经历扩展为 oracle 的 RED→GREEN。

oracle 的实际命令为：

```text
F:\mysys2\ucrt64\bin\python.exe -B -m unittest -v test_independent_tiny_oracle
```

工作目录为 `D:\h\shape_based_matching-master\artifacts\ordered_contour_verifier_experiment`。
21 项由 15 个 oracle/回归方法与 6 个 mutation 方法组成。
日志记录 `Ran 21 tests in 5.069s`；这只是本次 unittest 运行报告的时间，
不是单候选性能、native 耗时、完整 matcher 耗时或正式速度基准。

## 独立性及覆盖范围

[independent_tiny_oracle.py](independent_tiny_oracle.py) 直接枚举部分单射：
每个模板点可不匹配，或选择一个尚未使用的兼容场景点。
最优分子由原始开链/循环顺序谓词判断，不调用生产原型的 Fenwick、cut、validation
或 witness helper，也不先使用单侧切点化简来决定最优值。
闭链谓词对唯一原始索引的循环闭合序列计数下降沿，要求至多一圈的原始循环次序。

对达到全局最优值的对应，oracle 另以显式物理顺序 walk 检查合同声明的 case 域，
从全部物理切点出发再筛选合法域，比较
`(scene_chain_id, +1优先, template_cut, scene_cut)`，
随后比较反向原始 edge-ID 序列。这一平局检查使用了合同中的 case 定义，
但没有参与独立的分子最优值判定。
`audit_result` 同时核对所选 scene、原始边存在、两侧不复用、单圈顺序、
witness 在所选 case 内的输出顺序、witness 权重、完整权重和 `B≤A≤total`，
并要求与 oracle 的精确最优值及完整平局结果一致。

穷举域为 `n,m=0..3`、全部 `2^(n*m)` 二分兼容图、四种开闭类型、
两组正物理 ID（含保持给定拓扑的非单调 ID），以及模板点的所有 cell 成员分区，
模掉不影响权重的 cell 标签重命名。
实际比较数由通过的测试断言核对，而非只取 result 中的 `expected_*` 字段：

| 部分 | 比较数 | 含义 |
| --- | ---: | --- |
| bbox 可实现 cell 分区 | 19,552 | 用不同整数坐标实际构造，并由合同的整数 4×4 bbox 规则重新计算 cell/权重 |
| 仅抽象 cell 成员分区 | 5,360 | `n>1` 全部点在同一 cell 的成员分区；明确不称为实际 bbox 可实现 |
| 合计 | 24,912 | 每项均比较精确分子、合法 witness、case tie 与 witness tie |

这些数包含空模板、空场景和空边图，不是 24,912 张图像。
计数式为 `2 × 4 × Σ[n=0..3] Bell(n) × Σ[m=0..3] 2^(n*m)`。
每个点的权重均由 cell 占用计算：`L=lcm(n_g)`、`W_i=L/n_cell(i)`、`D=C*L`；
没有拿任意小权重集合冒充实际 cell 权重。
当 bbox 只来自这些不同物理点时，`n>1` 全部点落在同一 cell 不可实现；
这 5,360 项保留为额外的抽象权重回归，不能合并宣传成真实坐标覆盖。
穷举不枚举所有整数坐标或全部图像几何。

另有固定 seed **20261023** 的 **100** 项有限案例，遍历每组 `n,m=4..8`
及四种开闭类型，每个模板点恰给两个兼容场景点，cell 权重来自实际合成坐标。
它们是稀疏有限案例，不是该尺寸的全部兼容图。
手写案例还覆盖同模板行/同场景点复用、闭链接缝、反向唯一解、两圈伪解、
权重最优与最多点数不同、`2^220` 与 `2^220+1` 的精度区别、
一条模板链只选一条 scene、不同模板链允许复用同一 scene pixel，以及完整平局规则。

## Mutation 检查

六项测试分别从原型源码制作临时副本、导入副本、运行指定小图，
再要求独立 `audit_result` 以 `AssertionError` 拒绝结果。
mutation 运行和 oracle 审计没有写入原始核心源码；临时文件由测试清理。
六项均在已捕获的 21 项 GREEN 日志中为 `ok`：

| 故障注入 | 必须拒绝的行为 |
| --- | --- |
| 同一模板行立即更新 Fenwick | 同一个模板点被累加多次 |
| 场景 prefix 改为非严格 | 同一个场景物理点被复用 |
| 删除场景周期切点枚举 | 丢失跨场景闭链接缝的最优解 |
| 删除模板周期切点枚举 | 丢失闭模板到开场景的最优解 |
| 分数改为 float 累加再转 int | 丢失相邻超大整数的区别 |
| witness 按原始 ID 排序 | 破坏所选 case 内的物理路径顺序 |

测试把 mutant 求解置于预期 `AssertionError` 区间之外；导入失败或 mutant 本身抛异常
会使测试失败。因此这六项 `ok` 不是靠 import/runtime error 代替 oracle 拒绝。
这是六个指定故障的检出证据，不是全部潜在实现错误的 mutation 覆盖率。

## 静态审查的作用和边界

[STATIC_REVIEW_V1.md](STATIC_REVIEW_V1.md) 对四种开闭情况、方向与切点完整性、
严格 prefix、行更新批次、任意精度整数、colex witness 的末边比较证明、
case 优先级、单 scene 选择、允许跨模板链复用、输入快照验证和工作计数做了源码审查，
结论为无实质发现。它不独立验证像素来源，也没有检查运行器的资源守护。
本次 tiny 穷举只支持上述小域；一般情况仍依赖合同中的切点完整性与递推最优子结构论证。

## 资源限制：已执行与仅声明必须分开

[execution_provenance.json](synthetic_oracle_green_v1/execution_provenance.json)
声明 `maximum_seconds=60`、`maximum_rss_bytes=536870912`、
`maximum_output_bytes=67108864`。
但 root 说明实际运行器使用的是 **`subprocess.run(timeout=60)`**：
实际施加了 wall timeout，**没有施加 RSS 上限或输出字节上限**。
provenance 里的后两项是期望预算字段，不是已执行的守护证明。
本文保留这个历史差异，不重写原 provenance/result，也不将本次运行写成“三项硬界均已验收”。

捕获的 stdout 为 0 字节，stderr 为 3,658 字节；它们的事后大小低于 64 MiB，
但事后大小不等于执行期间存在输出守护。峰值 RSS 未测量，不能证明小于 512 MiB。
后续如需要完整资源合规证据，应另立带实际 RSS/output 守护及观测记录的 successor 运行；
当前数学结果不自动补成资源预算通过，也不触发重跑或真实图像实验授权。

## Source pins 与可补充的归档证据

本文整理时只重新读取并计算小文件 SHA256，以下当前文件均与 oracle result 的 pin 一致：

| 源码/文档 | 字节数 | SHA256 |
| --- | ---: | --- |
| `weighted_ordered_match.py` | 13,015 | `190204b69ea3646b836ac216bc4254c2f2c7c7f11a4517b434659ddd1ea18a64` |
| `test_weighted_ordered_match.py` | 11,803 | `64c2a2ac907a41434a14871db9176153ecc54f24fab07365042cdb38675d04b5` |
| `independent_tiny_oracle.py` | 21,472 | `47fd4bb9545d64e72de03d78aa917c479e6909d316eb6a40a01f2db372b16e68` |
| `test_independent_tiny_oracle.py` | 12,213 | `23476268244bd7a1e3294e44ffa08ae5d7e33b0f5208fc4696795827b7450016` |
| `CORE_DECISIONS_V1.json` | 1,908 | `376a46f487d84b2998e74a3b3c968ed0325080fa4f633335e07efa84a70da6ad` |
| `STATIC_REVIEW_V1.md` | 8,311 | `c0ceb647145079f752244288fe1ee999012e554aff89f528f0bedcb3d5e2b7e6` |

已重新核对 oracle 输出的 hash：stdout 为
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，stderr 为
`082d085fbdaa00e668435d1ec3717f648e8fadbb2c16f703fc329197261c128f`，与 result 一致。
手工 GREEN 目录已保存核心、手工测试和 decisions 的精确内容副本，
其 hash 与当前文件及 oracle pin 相同；RED 目录保存了零桩与同一份手工测试副本。

**当前归档缺口：** `synthetic_oracle_green_v1` 只有 result、execution provenance、stdout、stderr，
未在该运行归档内保存独立 oracle、oracle 测试或静态审查的精确源码/文档副本。
运行时 hash 加上本文核对时仍匹配的工作区内容可定位当前版本，
但 hash 不能在工作区内容日后变化时恢复源码。
可补充一份单独的、不可变的 source snapshot 与新增 manifest，保存以上六项精确内容
（或保存缺少的三项，并显式引用手工 GREEN 里 hash 相同的三项副本），
在复制前后核对已有 pin；不覆盖或改写历史 result/provenance。
这项归档补充及实际资源守护的 successor 记录目前都未由本文执行。

决策仍以 [CORE_DECISIONS_V1.json](CORE_DECISIONS_V1.json) 的
`accepted_for_synthetic_core_implementation_only` 为边界。
没有实施细化、链提取、采样所有权、RGB/warp/梯度来源、真实候选几何、
NMS/GT 全流程或完整 development audit；没有准确率提升或速度提升主张。
