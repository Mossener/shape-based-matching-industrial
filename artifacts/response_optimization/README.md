# LED 响应构建优化

实现三项可独立开关的优化：可分离位或扩散、响应查表与线性重排融合、跨帧缓冲区复用。匹配仍使用原梯度方向、模板、阈值和搜索范围。OpenCV/OpenMP 线程由应用设置，库内不修改全局线程数。

## 实测结果

768×576 的 8 张 LED 图，补边后 896×704；三层 `{4,8,8}`、900 个角度/尺度模板、阈值 75。每组 2 次预热、15 次测量，六种配置同进程轮换交错。下表为每张图的中位数再取八图平均，单位 ms；OpenCV1、OpenMP4。

| 配置 | 响应构建 | 完整匹配 |
|---|---:|---:|
| 独立原版 | 14.794 | 42.621 |
| 新接口，全优化关闭 | 15.334 | 44.505 |
| 仅可分离扩散 | 14.903 | 43.721 |
| 仅查表与重排融合 | 13.151 | 41.800 |
| 仅缓冲区复用 | 11.526 | 38.975 |
| 三项组合 | **9.677** | **36.983** |

相对独立原版，组合使构建耗时减少 **34.6%**，完整匹配减少 **13.2%**，约 **23.46→27.04 FPS**。这里的响应构建包括金字塔、梯度、扩散、查表和重排；完整匹配不含图像解码、模板生成、补边、绘制与保存。模板搜索仍约 27 ms，限制了整条流程的收益。

全关闭路径和原版的临时缓存生命周期、接口开销不同，适合用作单项消融对照；最终提升同时给出独立原版基线。原版适配器的外部总时间包含日志捕获及结果向量复制/转换开销，内部构建与搜索计时不含该转换；数据审计保留了这一区别。**单独启用扩散没有在完整流程上超过独立原版**，尽管它比新接口全关闭更快，不能把内核加速直接当作完整匹配收益。

| 组合配置的 OpenCV 线程数 | 响应构建 ms | 完整匹配 ms |
|---|---:|---:|
| 1 | 9.677 | 36.983 |
| 2 | 9.542 | 37.451 |
| 4 | 9.588 | 37.299 |

本次增加 OpenCV 线程没有明显端到端收益；当前 LED 例程保持 CV1/OMP4。线程组按 1→2→4 测量，跨线程差异还可能受运行状态影响，不把微小差异当作普遍结论。

完整验证包含 5184 次调用，位置、精确分数、模板编号和候选数量差异全部为零。19/19 源码及输入 SHA-256 核验通过，独立审计见 [AUDIT.md](led_benchmark/AUDIT.md)，原始数据及每图 median/p95 见 [led_benchmark](led_benchmark/)。[当前源码生成的八图效果](led_results/overview.png) 的分数为 86.0～98.4；绿色轮廓对应 SMD 中的两个电极特征。1.bmp 是模板来源，其他七张为正样本，结果不代表通用准确率或误检率。

## 使用

原来的 `detector.match(image, threshold, class_ids, mask)` 接口保持可用，默认启用三项优化，使用各线程自己的工作区，并关闭逐帧控制台日志。

需要控制开关或计时时，给每个并发工作线程一个独占的工作区：

```cpp
line2Dup::MatchWorkspace workspace;  // 在帧循环外创建
line2Dup::MatchOptions options;
line2Dup::MatchTimings timing;
auto matches = detector.match(frame, 75.f, workspace, options, &timing, {"LED"});
// timing.preprocess_ms：完整响应构建，含金字塔/梯度/扩散/查表/重排
// timing.search_ms：模板搜索、排序、去重
// timing.total_ms：含禁用复用时临时缓冲区释放的总时间
```

`options.separable_spread`、`fused_response`、`reuse_buffers` 可分别设为 `false`。`log_timing=true` 可打印构建和搜索耗时。融合路径的 `response_ms` 包含重排，因此 `linearize_ms=0`；不要把融合阶段与原版单独查表时间直接相比。

同一 Detector 可以供只读匹配并发使用，每个工作线程使用不同工作区。训练、读取模板和修改模态参数不能与匹配并发进行。工作区可以串行用于不同 Detector、尺寸、通道或 mask；每帧都会重算数据。原接口的线程工作区不支持同线程递归重入。

## 独立验证

- `spread_test`：3208 项，独立标量位或参考、窄图、任意 T、ROI、边界哨兵和别名。
- `response_test`：127 用例、1,610,176 字节比较，全部 256 掩码及原 LUT/重排语义。
- `pipeline_test`：1512 次逐行字节对照，包括浮点幅值和角度，覆盖灰度/彩色、mask、ROI 和三层金字塔。
- `workspace_test`：五种开关组合与独立编译的原版对照，覆盖连续 A/B/A、尺寸/通道/mask/像素/阈值变化、移动、跨 Detector 复用和两工作线程。
- `buffer_test`：52 帧分配计数。其他两项优化关闭时，896×704 灰度从 116 降为 27 次 `cv::Mat` 分配/帧，彩色从 146 降为 57 次；尺寸切换首帧重新分配，随后稳定。

分配计数只统计默认 `cv::MatAllocator` 的申请，不代表全部 `malloc/new`，也不等同于峰值内存。独立审查见 [REVIEW.md](REVIEW.md)，执行结果见 [test_results.json](test_results.json)。计时断言用 1e-9 ms 容差处理已复现的 1 ULP 浮点舍入。

## 复现

本机 Windows PowerShell，可通过参数替换 GCC/OpenCV 路径：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/response_optimization/run_tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/response_optimization/run_benchmark.ps1 -Run -Repeats 15 -Warmups 2
```

基准方法见 [BENCHMARK.md](BENCHMARK.md)，独立内核数据见 [kernel_result.md](kernel_result.md)，各本地版本见 [optimization_versions.md](../../docs/optimization_versions.md)。历史二/三层金字塔复现脚本固定使用 `baseline/` 中的原版，避免历史数据与当前优化版本混淆。
