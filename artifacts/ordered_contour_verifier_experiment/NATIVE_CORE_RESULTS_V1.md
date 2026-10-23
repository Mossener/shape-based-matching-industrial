# C++ 有序匹配核心：合成结果 V1

以 C++17/GMP `mpz_class` 移植 V32 的精确有序匹配数学核心，保留完整开闭链、周期切点、反向、严格 Fenwick 前缀、同模板行先查询后更新，以及 case/witness 平局规则。权重和分数使用任意精度整数，work counters 使用带溢出检查的 uint64。typed API 的 ID/bool 边界与 Python 动态类型检查不同；文本 driver 独立拒绝负数、溢出及非法布尔值。

| 实际阶段 | 覆盖和结果 |
| --- | --- |
| `native_core_red_v1/` | 固定零桩：40 tests、265 checks、174 failures、0 errors；编译通过，测试按预期失败 |
| `native_core_green_v1/` | 相同测试字节：40 tests、365 checks、0 failures、0 errors |
| `native_oracle_green_v1/` | 25,024 个完整结果与独立部分单射穷举精确一致，未跳过 |
| `native_protocol_green_v1/` | 33 个畸形文本输入均产生规定 fatal error，保留先前结果并停止，不执行尾部请求 |
| `coordinator_exit_red_v1/` | 注入末尾 pin 失败，复现错误零退出码：2 tests 中 1 assertion failure |
| `coordinator_exit_green_v1/` | 相同测试字节通过，末尾一致性失败同时影响回执和进程退出码 |

25,024 个对照由 24,912 个全域 tiny 图、100 个 seed=20261023 的 n/m=4..8 稀疏图和 12 个特殊抽象图构成。前者包含 19,552 个 bbox 可实现格分区与 5,360 个明确抽象分区；特殊图覆盖多场景链平局、反转输入顺序、最大 uint64 ID、超过 1,100 bit 的权重、空模板/空场景和无支持。它们是图比较次数，不是图片数量。

独立 expected 仅来自 `independent_tiny_oracle.brute_force` 的部分单射枚举及原始循环顺序谓词；逐一检查 B、A、完整分母、模板身份、完整选中 case 和原始 ID witness。生成器/审计器拒绝缺失、错序或额外输出。work counters **另与 Python 优化实现**逐字段比较，不称其为独立计数 oracle。完整 request、expected、response、源码快照和执行回执保留。

batch driver 先界定行、token、点数、边数及输出预算，再分配和求解。33 项输入覆盖负数/溢出 ID、非法 bool/count/weight、重复 sample/pixel/chain/edge、未知端点、unused malformed scene、缺/多 token、版本、空白、NUL/non-ASCII 和过长行。未测 100001 请求界限、正向 EOF 变体、64 MiB 全文件或累计输出压力；也未注入 OS I/O、分配失败或 uint64 工作计数溢出。error ID 断言允许 0/77，实际输出均符合各例；prefix R1 仅核前缀，完整数值由 25,024 gate 验证。

`native_assertion_acceptance_green_v1/` 又在显式 `-E -B` 子进程中重审保留的全部 25,024 个结果，非 assert 入口检查并记录 `optimize=0 / ignore_environment=1 / debug=true`，避免依赖 ambient Python 优化选项。它同时重审 33 个已执行协议序列，逐例核精确 error ID、完整零结果 prefix R1 和全部 counters。没有重编译或重跑 native solver；原回执及其限制保留。

原生 oracle 的实际观测如下。wall 含启动、协议和审计开销，**不是匹配性能基准**。

| 阶段 | 观测 wall | 进程 peak working set |
| --- | ---: | ---: |
| 独立 fixture 生成 | 8.172 s | 26,824,704 B |
| 编译 helper | 2.625 s | 22,249,472 B |
| native batch | 0.391 s | 6,377,472 B |
| 完整数值审计 | 4.250 s | 25,829,376 B |

编译 Job peak committed memory 为 222,711,808 B；Job 限额 1 GiB 包括 GCC 子进程。其他各进程 60 s / 512 MiB / 64 MiB 观测守护均未触发。committed memory 与 working set 口径不同；50 ms watchdog 也不是 OS 分配隔离。编译器/objdump 元数据预检在这些守护之外，ambient environment、实际 link/loaded DLL/Python 全闭包未完整证明，详见 `NATIVE_RESOURCE_SCOPE_SUPPLEMENT_V1.md`。

源码/依赖/静态 PE 导入 pin、实际 GCC dependency、编译和运行日志支持本机复现，不是完整 attestation。使用本机现有 GMP 头文件与导入库；没有发布 DLL 或编译产物。

本阶段没有真实像素输入、完整图像调用基准或准确率收益，也没有修改生产默认 V11。C0 输入计划另外核对了实际 V31 的 2,400 份小 manifest，声明完整 457,279 个候选和 390 个零组合；它未读 raw/bank/image payload，仍是 metadata selection，不能代替真实输入冻结、全部姿态回放和全量质量审计。native 链提取、候选与像素适配继续在后继阶段验证。
