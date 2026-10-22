本报告只解释固定 RGB TP 姿态、同一物理锚点和预先规定的 floor/ceiling native 网格邻点。215 个身份各含 RGB/二值两臂；所有结果均由已冻结数字证据推导，独立 Phase2 总审计仍是结论接受门槛。

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
