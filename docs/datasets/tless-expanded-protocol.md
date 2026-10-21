# T-LESS 扩展固定取样与留出协议

本扩展用于降低只在 LED、case1 和单一 T-LESS 目标上调试所带来的过拟合风险。
它不运行匹配器，不替换现有 tiny 数据，不读取或修改 tiny 的 sealed heldout 图像。
官方来源、固定提交及 CC BY 4.0 署名沿用原有官方 Range 协议，分别记录在新增
`artifacts/public_datasets/tless_expanded_plan.json` 和最终 acquisition manifest。

## 最终取样

- 目标物体 ID：`1,2,5,8,12,17,25,29`，每类 72 个真实训练视角，共 576 图。
  ID 分布是预声明取样，不把编号解释为已经验证的形状类别；其他物体保留 GT，充当真实干扰。
- development 对象：`1,2,5,8,12,17`。`25,29` 为从未参与参数选择的物体泛化组。
  可准备它们的官方训练样本，但不得用匹配结果选择特征数、阈值、视角、尺度或 NMS。
- 排除 tiny 全部场景 `2,3,5,9`，而非只排除它已取的图像。
- development 场景：`1,4,6,7,8,10,12,13`，每场景全部 50 个官方 BOP19 帧，共 400 图。
- 新 heldout 场景：`11,14,15,16,17,18,19,20`，全部 50 帧，共 400 图。
  全部扩展 test 共 800 张真实图；图像 ID 由官方 GT 排序得出，没有依据匹配结果挑图。

最初纯编号分组把 scene11 放 dev、scene13 放 heldout。GT 调查发现物体5/8在该 heldout
没有正例，因此只依据 GT 交换11/13，保持400/400并让每个目标在两个场景 split 都有正负例。
该改动发生在首次取 RGB、首次运行任何扩展匹配之前，原因写入最终 plan。

参数和代码选择只能使用 development 对象 × development 场景。之后冻结完整算法、
训练配方、模板构建失败处理、特征数、阈值、尺度、NMS 和指标规则，再访问新 heldout 匹配结果。
对象25/29必须使用同一冻结配方构建模板，独立报告跨物体泛化；不能为其单独调参。
可以报告场景留出、物体留出及两者交集，但不得合并为一个不透明总分。

## 训练视角

每对象从全部 1,296 个官方真实视角中，以模型到相机旋转矩阵的 Frobenius 距离进行
确定性 greedy farthest selection：第一项取最小图像 ID，随后最大化到已选集合的最小距离，
相同距离取最小 ID，直至72视角。排序后的精确 ID 写入 plan。
这避免使用同一个固定 frame-ID 截面；没有根据图像是否容易匹配来筛选。

独立离线审计重新运行选择规则，并通过官方 R/t 计算模型坐标系中的相机方向覆盖。
8类所选方向的 elevation 大致跨越 -87° 至 +86°，接近各自完整视角集的上下极；
全部方向到最近所选方向的最大夹角约23°–25.4°。这些是3D视角覆盖诊断，不能当作
2D角度/尺度真值，也不意味着72模板充分覆盖任意外观。

## 下载、预算与验证

```powershell
# 默认只调查 ZIP 目录及官方 GT/camera JSON，不取RGB、不运行匹配。
py -3.10 tools/datasets/fetch_tless_expanded.py

# 使用冻结plan。新增目录，2,000,000,000响应体字节累计硬预算。
py -3.10 tools/datasets/fetch_tless_expanded.py --fetch

# 全部成员的离线CRC/SHA/尺寸/标注/视角重算验证。
py -3.10 tools/datasets/verify_tless_expanded.py
```

下载来自固定官方 BOP Hugging Face 提交
`5fd309a04476a842d93abfb584fba9ee7caecdf1`。
预计连续24个 object/scene Range 块为 **1,443,338,015 bytes**，加 metadata 调查
**16,941,514 bytes**，累计预计 **1,460,279,529 bytes**，低于2GB十进制响应体硬上限。
块在内存解析，只保存 plan 中指定的 RGB、目标物体 mask/mask_visib 及官方JSON。
块内未使用的 depth 及其他成员不落盘。保留的原始成员预计 **643,440,442 bytes**，
即约614MiB。此预算不包含 HTTP/TLS headers；完整大ZIP没有下载，不能声称验证全包 SHA。

每个保留成员核对 ZIP 中的 CRC32、原始字节数，并计算 SHA-256。Range 请求必须得到
精确206与Content-Range，否则拒绝整包降级。累计传输 ledger 在每块收到后立即保存；
重启时先验证已有成员，并把已收响应体计入剩余预算。中断后重复取同一块也会计入预算。

文件在 `datasets/tless_expanded/`，本地 `.gitignore` 排除外部图片。
`index.json` 是派生便利索引，保留全部物体GT框和可见比例；仅所选目标保存 mask。
GT pose 始终在官方 JSON 中，便利索引不将其转成2D角度。
许可单独附在数据目录，外部数据不继承代码仓库许可证。

本扩展增加真实视角、物体和场景覆盖，仍不是完整 T-LESS 成绩、工业产线代表性抽样，
也不证明缺陷检测或6D位姿能力。应保留每对象/场景/可见比例、正负例和模板提取失败的分项结果。
