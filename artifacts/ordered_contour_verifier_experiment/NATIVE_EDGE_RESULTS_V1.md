# C++ 标签网格链组件：合成结果 V1

本阶段把 V32 的 supplied-label 细化、链分解、弧长采样、共享点所有权与 bbox 格权重移植到 C++17/GMP。没有图像解码、OpenCV、真实梯度或生产 matcher 集成。`NATIVE_EDGE_DECISIONS_V1.json` 保留测试/零桩准备时的历史状态；后续执行以独立回执为准。

| 实际运行 | 覆盖与结果 |
| --- | --- |
| `native_edge_red_v1/` | 编译成功；36 tests、121 checks、114 failures、0 errors，零桩按预期失败 |
| `native_edge_green_v1/` | 同一份测试字节；36 tests、229 checks、0 failures、0 errors |
| `native_edge_oracle_green_v1/` | 615 个完整独立参考记录全部一致，0 跳过；5 个全空/细化后空模板保留 null |

615 个案例包括全部 512 个 3×3 occupancy 位图、100 个 seed=20261023 的 4×4/5×5 多标签网格、一个 160×160 隔离点大整数权重网格及两条更长路径。这些是人工标签网格，不是测试图片。

独立参考不导入优化链函数：以 degree-two 诱导组件分解链、all-pairs 坐标判断邻接、bisect 累计弧长采样、Fraction 格质量求精确权重。逐记录比较完整 thinning 原/结果标签与每轮删点数、原网格 raw chains/raw samplings、以及 TemplateEvidence 的全部字段，包括 returning/closed、canonical 完整点序列、所有权、原 chain_index、16 格计数、LCM、每点权重和分母。递归检查 JSON 类型以拒绝 bool/int 混淆，拒绝浮点、重复键、缺失和额外记录。

160×160 案例包含 16 格的互素点数，实际 LCM 超过 uint64，证明该有限输入的大整数路径确实被执行。无损保存全部请求、独立 expected、native response；expected 与 response 恰为相同 1,713,837 个字节，但验收还进行了完整递归数值/类型比较。literal 测试另外覆盖最大 uint64 standalone sampling、返回环、zero-owned 链、非数值顺序、非法 typed 输入等。

| 完整 oracle 阶段 | wall 观测 | 进程 peak working set |
| --- | ---: | ---: |
| 独立 fixture 生成 | 0.484 s | 28,315,648 B |
| 编译 helper | 2.843 s | 22,274,048 B |
| native batch | 0.062 s | 8,937,472 B |
| 独立完整审计 | 0.328 s | 26,324,992 B |

这些包括启动、协议和断言，不是算法或真实图像速度基准。编译 Job peak committed memory 为 256,839,680 B，限额 1 GiB 包含 GCC 子进程；其他进程 60 s / 512 MiB / 64 MiB 观测守护未超限。`-E -B` 审计子进程实际记录 optimize=0、ignore_environment=1、debug=true。metadata 子进程、OS/动态导入等限制继续适用 V33 的资源口径补充，不声称整体协调器有 RSS 硬隔离或完整 attestation。

G1 adapter 有输入/输出字节、维度和 token 逻辑上限，但本次 615 个合法输入不构成协议所有畸形/压力/I/O 路径的验证。原生候选坐标接口与真实像素适配尚需后继验证。本阶段没有真实识别准确率或端到端速度收益，不推广到生产默认。
