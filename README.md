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
- [历史“360 模板 / 7 ms”与当前 LED 的测试条件区别](artifacts/search_optimization/CALIBRATION.md)

### 当前范围

现有 LED 验证包含一张模板来源图及七张其他正样本，用于检查实现与耗时，尚未建立通用工业召回率、误检率或现场节拍保证。`LED/ku.smd` 导入仅适配当前文件布局，未验证通用 SMD 兼容性。

公开 T-LESS 数据已经扩展到 800 张测试图、576 张训练视图、8 个目标和 16 个新场景；开发与场景留出各 400 张，另保留两个物体作泛化检查。采集和独立校验已完成，完整识别评测仍在进行。先前单物体 tiny 开发实验误检较多，不能把更大数据量、实现等价或匹配分数当成准确率提高。

当前主线提供离散位置与姿态候选；通用亚像素/连续角度尺度精修、完善的多目标空间 NMS 和跨平台 CI 尚待实现。上游 README 的 ICP/subpixel/sim3 链接指向其他分支，不代表本分支已集成。

后续功能及验收标准见 [工业化路线图](docs/industrial-roadmap.md)，贡献与验证要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。
