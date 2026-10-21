# shape-based-matching-industrial

面向工业视觉轮廓定位持续改进的 C++ 梯度方向模板匹配器，由 [Mossener](https://github.com/Mossener) 独立维护。

**来源：本项目基于 [meiqua/shape_based_matching](https://github.com/meiqua/shape_based_matching) 的本地源码快照继续开发，原项目采用 BSD-2-Clause 许可证。** 感谢原作者及 OpenCV LINEMOD、MIPP 等相关项目的工作。原许可证和第三方声明保留；导入时的说明保存在 [README.upstream.md](README.upstream.md)。当前 Git 历史从本地基线开始，尚未核实快照对应的上游提交，详情见 [来源与维护边界](docs/source-provenance.md) 和 [第三方声明](THIRD_PARTY_NOTICES.md)。

目前处于工业化演进阶段，已完成 LED/SMD 样本验证和若干保持结果一致的性能优化；通用工业数据集、稳定跨平台构建、连续姿态精修和现场验收仍需继续建设。

## 工作原理与现有能力

模板保存稀疏特征点的相对位置和梯度方向。输入图像经过金字塔、梯度量化、方向扩散、响应查表及内存重排后，与模板做批量累加评分；先在粗层全图搜索，再逐层局部精修。

- 使用八类梯度方向，方向模 180°；当前查表响应为 0/3/4，最终分数归一化为 0～100，分数不是识别概率。
- 支持灰度/彩色输入、图像金字塔、mask、角度/尺度模板枚举和 OpenMP 模板并行；角度与尺度来自姿态模板，金字塔不替代尺度枚举。
- 提供独立优化开关、每调用线程独占的 `MatchWorkspace`、跨帧缓冲复用和构建/搜索分段计时。
- 保留原 `Detector::match` 调用接口；当前结果提供离散位置、模板编号及分数，可通过模板元数据取得角度和尺度。
- `LED/ku.smd` 的导入代码只适配当前提供的文件布局，不是通用 SMD 读取器，也不表示兼容任何商业软件的匹配引擎。

当前主线没有通用亚像素/连续角度尺度精修、完善的多目标空间 NMS 和通用工业准确率报告。上游 README 中的 ICP/subpixel/sim3 链接指向上游其他分支，不能视为本分支已实现的功能。

## 已验证的性能

测试机器为 Windows / i5-13500HX / GCC 15.1 / OpenCV 4.12，CV1/OMP4。LED 为八张 768×576 图，补边后 896×704，900 个姿态、三层金字塔、阈值 75。下表为各图正式样本中位数的等权平均，单位 ms。

| 实验 | 对照 → 优化 | 观察结果 |
| --- | --- | --- |
| V4 响应优化，同轮原版对照 | 构建 14.794 → 9.677；外部完整调用 42.621 → 36.983 | 构建减少 34.6%，完整调用减少 13.2% |
| V7 搜索优化，同轮冻结 V4 对照 | 搜索 28.781 → 27.666；内部完整调用 38.763 → 37.873 | 搜索减少 3.87%，完整调用减少 2.30% |

两行来自不同运行，计时范围也分别注明，不能跨行相减或相加。搜索收益较小、存在波动，整数最大值单项在本轮优于三项组合；直接 8U 和搜索缓冲复用未建立稳定的独立收益，case1 搜索未提速。

- [响应优化：实现、五项测试、原始数据和审计](artifacts/response_optimization/README.md)
- [搜索优化：八种组合验证、独立消融和审计](artifacts/search_optimization/README.md)
- [README 历史“360 模板 / 7 ms”与当前 LED 的区别](artifacts/search_optimization/CALIBRATION.md)
- [V0～V8 本地版本与测量记录](docs/optimization_versions.md)

正确性测试检查实现等价性；性能测试检查耗时。现有八张 LED 图含一张模板来源图及七张其他正样本，不能据此报告通用召回率、误检率或现场节拍保证。

## 本机复现

当前验证路径为 Windows PowerShell、GCC 15.1、OpenCV 4.12 和 Python 3.10。先准备依赖，在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/response_optimization/run_tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1 -Test
```

脚本默认使用 `F:\mysys2\ucrt64\bin\g++.exe` 和 `D:\opencv-4.12.0`，可通过 `-Compiler`、`-OpenCV` 参数替换路径。当前链接名固定为 `opencv_world4120`，更换 OpenCV 版本还需调整构建脚本，尚未实现版本无关的构建。

搜索性能实验须单独启动，避免同时运行其他 CPU 基准，输出目录必须是新目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1 -SkipCompile -Run -OutputDirectory artifacts/search_optimization/my_run
```

原 `CMakeLists.txt` 保留了上游 OpenCV 3 和 ROS 路径配置，尚未完成跨平台构建迁移。当前没有已验证的 GitHub Actions 测试流水线；相关工作列为路线图 P0。

## 匹配接口

训练或读取模板后，在帧循环外创建工作区：

```cpp
line2Dup::MatchWorkspace workspace;
line2Dup::MatchOptions options;
line2Dup::MatchTimings timing;

auto matches = detector.match(frame, 75.f, workspace, options, &timing, {"LED"});
// timing.preprocess_ms: 金字塔、梯度、扩散、响应和重排
// timing.search_ms: 模板搜索、精修、排序和去重
```

每个并发调用必须独占工作区。Detector 的只读匹配可使用不同工作区并发执行，训练和模板修改不得与匹配并发。库不更改 OpenCV/OpenMP 的全局线程配置。

六项优化开关为 `separable_spread`、`fused_response`、`reuse_buffers`、`integer_local_max`、`direct_8bit_search`、`reuse_search_buffers`，均默认开启。关闭开关可进行等价性检查和性能消融；`reuse_buffers=false` 时工作区状态仅在本次调用内存在。

## 持续维护

工业化工作按 [路线图与验收标准](docs/industrial-roadmap.md) 推进：先建立可移植构建、CI 和接口契约，再实现搜索范围与候选管理、连续精修、标注数据验证和部署观测。

修改前后保留独立基线，逐项验证功能和性能，每个版本记录具体改动、测量条件、结果及限制。提交规范和复现要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。问题可通过本仓库 Issues 报告，请附最小复现、依赖版本、模板配置及期望结果。

源码许可见 [LICENSE](LICENSE)，第三方代码、文献和样本来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
