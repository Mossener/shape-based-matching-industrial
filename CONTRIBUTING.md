# 维护与贡献

本项目基于 meiqua/shape_based_matching 的本地源码快照独立开发。贡献前阅读 [来源声明](docs/source-provenance.md)、[第三方通知](THIRD_PARTY_NOTICES.md) 和 [工业化路线](docs/industrial-roadmap.md)。新代码和素材应记录来源，保留适用的版权与许可通知。

## 修改约定

1. 先说明可复现的问题或使用场景，写清输入、模板、阈值、搜索范围及期望行为。
2. 区分保持结果一致的优化与会改变结果的功能。阈值、量化、并列规则、位姿范围、采样步长和候选过滤的变化都应明确记录。
3. 不覆盖 `artifacts/*_optimization/baseline/` 或已有实验原始数据；增加新输出目录，保留哈希与配置。不要为适应实现改写独立参考结果。
4. 新的状态缓存必须验证尺寸/通道/模板/线程数变化与清零语义。每个并发调用独占 workspace，库内不要隐式改动全局线程设置。
5. 为实际边界或回归增加必要测试；对可逆的纯文档修改检查链接、声明和差异即可。

当前 coarse 阶段保留 `score > threshold`，局部精修过滤保留 `score < threshold` 的原语义；全零局部图的坐标为 `-1`。不要在性能优化中无意统一这些规则。改变规则应作为明确的行为变更审查。

## 验证

当前 Windows / GCC / OpenCV 4.12 验证入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/response_optimization/run_tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1 -Test
```

可使用 `-Compiler` 和 `-OpenCV` 指定本地路径。脚本目前固定链接 `opencv_world4120`；其他版本和平台尚需构建迁移。

性能实验与其他 CPU 基准分开运行。使用相同输入、模板、编译、线程与计时边界，在同轮交错对照；保留首次调用、预热和正式样本，分开汇总不同数据集。说明分位数和汇总方法，不跨实验轮次相减，不用局部内核提速推算整条流程的提升。

单独报告实现等价性、运行性能与识别质量。识别质量需要独立标注、正负样本和事先定义的正确匹配条件；现有正样本测试不代表工业召回率或误报率。

## 提交与版本记录

- 每次提交保持用途清晰，使用 `fix:`、`perf:`、`feat:`、`test:`、`build:` 或 `docs:` 等前缀。
- 在 [版本记录](docs/optimization_versions.md) 写明变更、验证命令/结果、实测收益或未见收益、环境及限制。没有性能测量就写明未测，不填写推算值。
- 稳定阶段保留可追溯标签；当前使用 `optimization-v0` 起的阶段标签，它们不是工业适用性或 ABI 稳定性认证。
- PR 中附最小复现、行为变化、测试证据和必要的测量链接。维护者确认验证材料后合并；不要提交编译输出、凭据或与项目无关的本地文件。

## 优先方向

先完成可移植构建、持续集成和 API 契约，再推进 ROI/姿态范围、候选合并/NMS、连续精修及工业数据验证。具体工作和验收条件见 [路线图](docs/industrial-roadmap.md)，不要同时引入多个无法独立评价的算法变化。
