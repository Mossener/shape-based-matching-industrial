# shape-based-matching-industrial

基于梯度方向和图像金字塔的 C++ 轮廓模板匹配器，用于 LED、电极、零件等刚性目标的视觉定位。

## 作用

从模板中保存稀疏边缘特征，在待检测图像中搜索相同形状，输出位置、匹配分数、类别和模板编号；结合模板元信息可取得角度和尺度。适用于目标外观纹理较少、需要根据边缘布局定位的场景。

匹配采用梯度方向响应累加，无需先把目标分割成完整的封闭轮廓。图像金字塔负责粗到细定位，旋转和大小变化通过预先生成的角度/尺度模板覆盖。

## 用法

### 环境与验证

当前已验证环境为 Windows PowerShell、GCC 15.1、OpenCV 4.12 和 Python 3.10。在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/response_optimization/run_tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1 -Test
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/local_search_optimization/run_tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/match_consolidation/run_unit_tests.ps1
```

脚本默认使用 `F:\mysys2\ucrt64\bin\g++.exe` 和 `D:\opencv-4.12.0`，可通过 `-Compiler`、`-OpenCV` 参数替换路径。当前链接名固定为 `opencv_world4120`，更换 OpenCV 版本还需调整脚本。

原 `CMakeLists.txt` 保留 OpenCV 3 和 ROS 路径配置，跨平台构建迁移与 CI 尚待完成。

### 匹配接口

先训练或读取模板，再在帧循环外创建工作区：

```cpp
line2Dup::MatchWorkspace workspace;
line2Dup::MatchOptions options;
line2Dup::MatchTimings timing;

auto matches = detector.match(frame, 75.f, workspace, options, &timing, {"LED"});
// matches: 位置、匹配分数、类别和模板编号
// timing.preprocess_ms: 金字塔、梯度、扩散、响应和重排
// timing.search_ms: 模板搜索、精修、排序和去重
```

每个并发调用必须独占工作区。Detector 可供不同工作区只读匹配，训练和模板修改不得与匹配并发。OpenCV/OpenMP 线程数由应用设置，库不修改全局线程配置。模板生成示例见 [test.cpp](test.cpp)，给定 SMD 样本的使用示例见 [led_demo.cpp](artifacts/led_match/led_demo.cpp)。

磁片样本的读取、全姿态补边预检和定位回归见 [磁片验证](artifacts/magnet_match/README.md)。使用本地 `磁片/` 原始文件时，可运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/magnet_match/run.ps1 -Run -Validate -OutputDirectory artifacts/magnet_match/my_new_coverage
```

该入口保留原 SMD 轮廓，按整个姿态模板库计算所需输入尺寸，并搜索 0.60～1.40 的尺度。它只适配已核验的磁片文件布局；输出目录须为新目录，原始素材需在本地提供。

优化开关为 `separable_spread`、`fused_response`、`reuse_buffers`、`integer_local_max`、`direct_8bit_search`、`reuse_search_buffers`、`fused_local_search`，默认开启，可分别关闭做对照。`fused_local_search` 在 SSE 且整数最大值开启时融合局部累加与最大值选择，其他路径保留已有实现。`reuse_buffers=false` 时工作区状态仅在本次调用内存在。

### 性能测试

完成上面的搜索测试构建后，单独运行基准，避免同时启动其他 CPU 基准；输出目录必须是新目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1 -SkipCompile -Run -OutputDirectory artifacts/search_optimization/my_run
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/local_search_optimization/run_benchmark.ps1 -Run -OutputDirectory artifacts/local_search_optimization/my_run
```

## 来源

本项目基于 [meiqua/shape_based_matching](https://github.com/meiqua/shape_based_matching) 的本地源码快照继续开发，沿用 LINEMOD 的梯度方向模板匹配思路，使用 OpenCV 进行图像处理、MIPP 进行 SIMD 计算。原项目采用 BSD-2-Clause 许可证，原许可证和第三方通知保留。

当前 Git 历史从本地基线开始，尚未核实快照对应的上游提交。导入时的原始说明保存在 [README.upstream.md](README.upstream.md)，来源细节见 [source-provenance.md](docs/source-provenance.md)，源码许可见 [LICENSE](LICENSE)，依赖、文献和样本声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本地新增工作包括响应构建与搜索优化、工作区复用、独立开关、分段计时、LED/SMD 样本适配和对照测试，详见 [版本记录](docs/optimization_versions.md)。

## 能力

- 支持灰度/彩色输入、mask、图像金字塔、多姿态模板和 OpenMP 模板并行。
- 使用八类梯度方向，方向模 180°；查表响应为 0/3/4，匹配分数归一化为 0～100，分数不是识别概率。
- 支持跨帧缓冲复用、构建/搜索分段计时，保留原 `Detector::match` 调用接口。
- 匹配结果在相同 `(class_id,x,y,exact score)` 上采用确定性的最小模板编号和完整排序；这使 OpenMP 合并顺序不会改变重复候选的身份。有限分数的契约、回归矩阵和独立 oracle 见 [V11 验证记录](artifacts/match_consolidation/README.md)。
- 已完成不可变基线对照、内核边界测试、八种搜索开关组合、工作区切换及独立并发验证。

### 实测性能

测试机器为 Windows / i5-13500HX / GCC 15.1 / OpenCV 4.12，CV1/OMP4。LED 为八张 768×576 图，补边后 896×704，900 个姿态、三层金字塔、阈值 75。下表为各图正式样本中位数的等权平均，单位 ms。

| 实验 | 对照 → 优化 | 观察结果 |
| --- | --- | --- |
| V4 响应优化，同轮原版对照 | 构建 14.794 → 9.677；外部完整调用 42.621 → 36.983 | 构建减少 34.6%，完整调用减少 13.2% |
| V7 搜索优化，同轮冻结 V4 对照 | 搜索 28.781 → 27.666；内部完整调用 38.763 → 37.873 | 搜索减少 3.87%，完整调用减少 2.30% |
| V10 局部累加融合，同轮关闭该项对照 | 搜索 31.835 → 20.463；内部完整调用 42.153 → 30.823 | 搜索减少 35.72%，完整调用减少 26.88% |

各行来自不同运行，不能跨行相减或相加。V7 的搜索收益较小且有波动，直接 8U 和搜索缓冲复用未建立稳定的独立收益。V10 的两轮 LED 搜索分别减少 25.39% 和 35.72%，8/8 图中位数均改善；case1 未建立稳定的完整调用收益，不能外推为普遍加速。

- [响应优化测试与原始数据](artifacts/response_optimization/README.md)
- [搜索优化测试与原始数据](artifacts/search_optimization/README.md)
- [局部累加融合、两轮数据与独立审查](artifacts/local_search_optimization/README.md)
- [搜索细分诊断](artifacts/search_profile/run_v9/REPORT.md)与[重复局部中心统计](artifacts/local_center_profile/run_v9_centers/REPORT.md)
- [T-LESS 扩展数据获取与覆盖报告](docs/datasets/tless-expanded-acquisition.md)和[固定评测协议](docs/datasets/tless-expanded-protocol.md)
- [确定性候选回归、阶段计时与独立审查](artifacts/match_consolidation/README.md)
- [公开开发评测与原始候选审计](artifacts/public_evaluation/README.md)
- [独立边缘覆盖实验、召回损失与误检结果](artifacts/quality_coverage/DEVELOPMENT_RESULTS_20261021.md)
- [历史“360 模板 / 7 ms”与当前 LED 的测试条件区别](artifacts/search_optimization/CALIBRATION.md)

### 当前范围

现有 LED 验证包含一张模板来源图及七张其他正样本，用于检查实现与耗时，尚未建立通用工业召回率、误检率或现场节拍保证。`LED/ku.smd` 导入仅适配当前文件布局，未验证通用 SMD 兼容性。

新增磁片回归定位了两种“完全无法识别”的原因：尺度未覆盖目标，以及大模板在深金字塔中没有可行的精修中心区间。统一扩大尺度范围、按模板库补边后，六张非来源图均通过 IoU≥0.5 的粗框定位检查；这六张都已参与开发观察，且没有负图，不能据此声称通用准确率或测量精度提高。原始失败、因果诊断和独立审查一同保留。

公开 T-LESS 数据包含800张测试图、576张训练视图、8个目标和16个新场景；开发与场景留出各400张，另保留两个物体作泛化检查。V15已完成目标1、2、5、8、12、17的固定actual-85开发基线：同一组400张图共2400个目标/图像配对，合计TP215/FP42098/FN185，召回率53.75%、精确率0.508%。目标8的部分大尺度模板还存在几何区间不可行的问题。当前配置既有误检也有漏检，不能把扩大数据量、实现等价或匹配分数当成准确率提高；[六目标完整结果](artifacts/public_evaluation/BASELINE_COMPLETION.md)保留每类指标及失败证据。

V14 的独立稠密边缘覆盖实验使用三个预先固定的阈值。在目标1的400张开发图上，覆盖阈值0.65保留37个已检测真值，误检从7842降到6397，但350张负图仍全部有误报；阈值0.80将误检降到1195，同时丢失6个原已检测真值并新增1个，总TP降为32。16张tiny开发图也观察到类似取舍。该实验保留为诊断工具，尚未接入默认匹配，也没有建立速度收益。

V16 单独检验目标8的全模板自动补边。848×800使全部6912个模板层满足所检查的几何约束，但400帧的原始候选与848×672基线逐字段及分数位完全相同，仍为TP1/FP68/FN49。64帧配对测试中，完整调用耗时的auto/baseline比值中位数为1.121（fallback）和1.115（fused）。这项实验说明补齐几何条件并未解决本例漏检，因此没有更改默认补边；[完整结果与独立复算](artifacts/obj8_padding_experiment/RESULTS.md)同时保留正确性、耗时和限制。

V17 对六目标的既有数值结果分解漏检，两套独立算法在2400个目标/图像配对上逐帧一致：185个漏检中，162个在原始候选中没有IoU≥0.5的框，23个对应原始到筛选后候选的最大一对一匹配容量下降。全部400个GT在理想平移下都有尺寸可兼容的既有模板框，因此仅扩大尺度或调整后处理不足以解释主要失败；[诊断、尺寸上界与独立复算](artifacts/quality_failure_analysis/RESULTS.md)保留推断限制。本版不改变匹配输出，也不宣称准确率提升。

V18 单独测试16项局部中心缓存，3985次正确性调用中的2880次完整有序比较，以及1350次计时调用的比较均通过，输出与冻结V11一致。LED八图的搜索中位数等权平均从25.041降到13.461 ms，内部完整调用从36.862降到25.714 ms；tiny十六图则从26.734增到27.637 ms。全部25图的完整调用配对比值中位数为0.9991，尚无普遍收益，因此缓存只保留在私有实验中，没有改为默认；[结果、全部退步样本与独立复算](artifacts/local_center_optimization/v11_candidate_experiment/RESULT.md)一并归档。

V19 检验直接使用二值轮廓作为训练图、保留原特征掩膜的方案。六目标共20,736个固定姿态全部因特征不足而未生成模板，独立数值审计核对了所有姿态、几何和失败记录。因此本轮没有可用的新模板库，也没有准确率或速度收益；[实验结果](artifacts/silhouette_template_experiment/RESULTS.md)与[独立验证](artifacts/independent_reviews/silhouette_training_v1/README.md)完整保留，后续特征掩膜实验单独进行。

V20 在独立实验中保持相同二值训练图，改用空特征选择掩膜，六目标20,736个姿态全部生成模板。独立审计逐层核对41,472个新模板层，并从全部12个新旧模板库重算77,870个层的共同几何需求，得到848×832的评测画布。该版解决的是此配方无法训练的问题；准确率和速度仍需后续图像对照，不据此更改默认模板配方。详见[训练与补边结果](artifacts/silhouette_empty_mask_experiment/TRAINING_RESULTS.md)和[独立验证](artifacts/independent_reviews/empty_mask_training_v1/README.md)。

V21 完成两项隔离速度实验。25份真实候选的哈希合并回放中，索引哈希预分配方案的配对耗时比中位数在LED+case1组为0.5100、tiny组为0.5929，但case1变慢；这只计合并阶段，尚无完整调用收益结论。16项直接映射缓存通过6609次正确性调用、5504次完整有序比较，但同轮五方案2250次调用中，相比线性缓存的搜索/完整调用配对比中位数为1.0102/1.0376，未证明更快。生产核心和默认行为保持V11；[哈希回放结果](artifacts/match_consolidation/hash_prototype/REPLAY_RESULTS_V21.md)与[缓存结果](artifacts/local_center_optimization/v11_candidate_experiment_v2/RESULT_V2.md)包含全部退化、原始计时和独立复算。

V22 完成六目标、400帧开发集的二值轮廓训练对照。空特征选择掩膜的模板库在固定共同补边下把误检从42,112降到11,882、精度从0.508%升到1.712%，F1从0.010064升到0.033149，但TP从215降到207、召回从53.75%降到51.75%；目标1出现F1退化，其他五目标改善。独立审计逐条重算raw、NMS、GT、分数位、源坐标和跨臂保留，未读取图像或调用matcher；[完整结果](artifacts/silhouette_empty_mask_experiment/QUALITY_RESULTS_V22.md)和[审计证据](artifacts/independent_reviews/empty_mask_quality_v1/run_development_audit_20261022_v3/result.json)保留了所有退化和限制。该训练策略仍不改生产默认，磁片和留出场景继续单独保留。

当前主线提供离散位置与姿态候选；通用亚像素/连续角度尺度精修、完善的多目标空间 NMS 和跨平台 CI 尚待实现。上游 README 的 ICP/subpixel/sim3 链接指向其他分支，不代表本分支已集成。

后续功能及验收标准见 [工业化路线图](docs/industrial-roadmap.md)，贡献与验证要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。
