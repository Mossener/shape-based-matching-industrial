215 个 RGB 正控全部在预定 native 邻点发出，并由追踪到的代表框完成目标 assignment。

在原 V22 的 67 个 RGB TP 损失身份中，二值同姿态路径分为：

| 固定邻点路径 | 数量 | 原 V22 整体结果 |
|---|---:|---|
| 全部可达 coarse 父被原阈值拒绝 | 23 | 23 个无 post-raw IoU>=0.5 |
| 存在 admitted 父，但其全部 window 最大值<85 | 44 | 34 个无 post-raw；10 个整体 NMS loss |

67 个物理锚点分数及其全部预定 native 邻点分数均<85。23 个 coarse 全拒案例即使看全部反事实细层 window，也没有 winner>=85；另 44 个中仅 1 个被拒父的反事实 window winner>=85，且它的预定邻点仍<85。因此不能把 23 个解释为仅粗层剪枝损失；单看粗层门槛并不足以解释这些固定位置的低细层分数。

67 个损失的追踪同姿态 occurrence 都没有 IoU>=0.5 支持；该结论只针对本次固定姿态/父集合。原 V22 的 10 个整体 NMS loss 本来有其它模板/位置的 post-raw 支持，所以两种分类并不矛盾。

148 个 retained 身份是对照：同姿态路径仍有 13 个 coarse 全拒、63 个 admitted window 最大值不足；另 26 个邻点低分但其它 winner 通过、25 个邻点通过但被 winner 位移、21 个邻点实际发出。不能把同姿态失败当作全类别检测失败。二值 215 个物理锚点有 179 个 off-grid（loss 52、retained 127），仅作注释。

详见 paired_215.csv 的215行成对记录、COUNTERFACTUAL_FINE_CHECK.json 的原始计数，以及 DEFINITIONS.md 的边界。完整逐臂430行位于 ../run_20261022_v2/per_gt_arm.csv。独立 Phase2 数字总审计尚是接受门槛；此报告没有修改算法或宣称准确率/速度提升。
