# LED 模板搜索优化与 7 ms 校准

README 的历史结果是 **360 个旋转模板搜索一张图约 7 ms**，不是 360 张图，也不是当前 LED 负载。此前同一轮 LED 对照中，未修改的原版搜索已为 **27.026 ms**，响应优化 V4 为 **27.219 ms**。构建从 14.794 降到 9.677 ms 后，搜索占比由约 63% 上升到约 74%；这不表示搜索从 7 ms 退化到了 27 ms。

当前 LED 为 900 个姿态（180 个角度 × 5 个尺度）、三层金字塔、阈值 75；case1 为 361 个模板、两层、阈值 90，特征数量和候选工作量也不同。同机使用不可变原版交错校准，case1 搜索中位数为 **2.568 ms**。历史硬件、编译和线程条件未知，当前 case1 补边后还是 1088×960，不能称为精确复现历史 1024×1024 的 7 ms。详见 [校准条件和原始数据](CALIBRATION.md)。

## 三项实现

- `integer_local_max`：局部图逐像素比较整数累加值，只对获胜值计算一次浮点分数；保留原算式、首个并列位置、全零 `-1` 坐标及阈值比较。
- `direct_8bit_search`：少于 64 个特征时直接扫描 8U 累加图，省去 8U→16U 转换；其他模板仍走 16U。
- `reuse_search_buffers`：每个 OpenMP worker 独占 coarse/local Mat 和候选 vector，重复使用容量；每个模板仍清空候选、完整清零矩阵。

三个 `MatchOptions` 开关默认开启，可以分别关闭。原 `match` 和受保护的 `matchClass` 签名保留。`reuse_buffers=false` 时整个工作区为调用内临时状态，搜索缓冲区仅能在该次调用的模板之间复用；不同并发调用仍须独占工作区。

## 本轮性能

Windows、i5-13500HX、GCC 15.1、OpenCV 4.12；`-O3 -mssse3 -msse4.1 -fopenmp`，CV1/OMP4，passive wait。预处理三项优化在所有配置中开启。每个输入、配置为 1 次初次调用、2 次预热、15 次正式测量，六种配置轮换并交替反转顺序，未并行运行其他性能基准。

下表单位 ms；LED 为八张图各自正式样本中位数的等权平均，case1 单独汇总。V4 是冻结的响应优化版本；“搜索全关”控制本次重构自身开销。完整调用采用内部 `api_total_ms`，排除 V4 适配器的结果转换；不含读图、模板生成、补边或绘图。

| 搜索配置 | LED 搜索 | LED 完整调用 | case1 搜索 | case1 完整调用 |
| --- | ---: | ---: | ---: | ---: |
| 冻结 V4 | 28.781 | 38.763 | 1.713 | 17.592 |
| 搜索三项全关 | 28.766 | 39.038 | 1.793 | 17.517 |
| 仅整数最大值 | 27.559 | 37.611 | 1.800 | 17.219 |
| 仅直接 8U | 28.845 | 38.717 | 1.820 | 17.326 |
| 仅 worker 缓冲复用 | 28.580 | 38.708 | 1.806 | 17.022 |
| 三项组合 | 27.666 | 37.873 | 1.783 | 17.140 |

本轮组合相对 V4，LED 搜索减少 **3.87%**，完整调用减少 **2.30%**（约 25.80→26.40 FPS）。相对搜索全关为 3.82% / 2.99%。整数最大值单项相对全关搜索减少 4.20%；直接 8U 单项稍慢，复用单项差异不到 1%，不能声称各项都有稳定收益，也不能把各项百分比相加。

组合在 6/8 张 LED 图的搜索中位数上更快，其中 6.bmp 贡献约一半汇总节省。V4→组合的配对搜索加速比中位数为 1.042×，样本 p05/p95 为 0.807×/1.312×，分布较宽；这些是描述性分位数，不是置信区间。case1 搜索从 1.713 到 1.783 ms，约慢 4.1%，配对加速比中位数约 0.997×；其完整调用下降还伴随未改动预处理阶段的波动，不能归为搜索收益。本轮支持“小幅 LED 收益”，不足以承诺跨图、跨机器稳定加速。后续若继续优化，应先细分候选收集、各层局部累加、最大值扫描及排序耗时，再针对主耗时步骤改动。

此前 V4 报告的 LED 总耗时为 36.983 ms，本轮 V4 为 38.763 ms；同机混合校准的原版 LED 搜索为 34.535 ms。它们来自不同运行，不能跨轮相减来评价本次优化。

## 独立验证

- kernel RED/GREEN：1876 张矩阵、34855 个 bit-exact 分数、278840 对阈值检查、9 个非法参数；覆盖 8U/16U、非连续 ROI、首个并列点、全零图、63/64 与 8191 特征边界。
- 冻结 V4 集成对照：480 次调用，全部八种开关组合，9 个正样本、mask、空结果、线程数 1→4→2→4、跨 Detector/尺寸/通道、move 和独立并发 workspace；位置/精确分数集合及数量全部相同，观测到的 strict 模板编号集合差异为 0。
- 性能实验共 972 次调用，其中 810 次正式测量，162 个配置/阶段组，语义、模板编号集合和数量差异均为 0；25/25 源码和输入哈希匹配。测试只覆盖现有样本，不代表通用识别准确率。
- 原有五项响应优化测试重新执行全部通过，包括 1512 次中间矩阵对照及 52 帧分配检查。

workspace 测试对 strict 模板编号差异仅记录，不能据此承诺并列模板身份的普遍确定性。内核对同一累加图的并列坐标和精确分数另外独立验证。审查见 [REVIEW.md](REVIEW.md)，执行证据见 [search_test_results.json](search_test_results.json)，独立数据审计见 [AUDIT.md](search_benchmark/AUDIT.md)。

## 复现与归档

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1 -Test
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1 -SkipCompile -Run -OutputDirectory artifacts/search_optimization/new_run
```

不带 `-Run` 只构建与检查配置；`-Test` 运行正确性测试。性能输出目录必须是新目录。构建路径可通过 `-Compiler` / `-OpenCV` 更改。单独原版校准运行 `run_calibration.ps1 -Run`。

- [raw.csv](search_benchmark/raw.csv)：逐调用原始计时、匹配数和对照结果。
- [summary_by_image.csv](search_benchmark/summary_by_image.csv)：各图 median/p95；[summary_rollup.csv](search_benchmark/summary_rollup.csv)：按数据集汇总；[paired_speedups.csv](search_benchmark/paired_speedups.csv)：同图同轮配对。
- [environment.json](search_benchmark/environment.json)、[config.json](search_benchmark/config.json)、[summary_validation.json](search_benchmark/summary_validation.json)：机器、来源哈希、输入配置与分组完整性。
- [baseline/manifest.json](baseline/manifest.json)：本次 V4 精确字节基线；更早原版仍在 `artifacts/response_optimization/baseline/`。
- [本地 Git 版本记录](../../docs/optimization_versions.md)。
