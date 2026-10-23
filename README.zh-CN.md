# 基于形状的模板匹配

[English](README.md) | [简体中文](README.zh-CN.md)

一个根据边缘布局定位刚性目标的 C++ 库。它从模板提取稀疏梯度方向特征，在图像金字塔上搜索，返回位置、相似度、类别和模板编号，适合形状比纹理更稳定的目标。

核心保持本项目的 V11 匹配行为。本仓库提供库与可复现示例，需针对自己的工件进行配置与验证。**v0.1.1 增加真实图像示例与架构文档**，详见 [v0.1.1 发布页](https://github.com/Mossener/shape-based-matching-industrial/releases/tag/v0.1.1)。

完整架构图、评分与搜索算法、接入边界及后续优化方向见[架构与算法文章](docs/architecture.zh-CN.md)（[English](docs/architecture.md)）。

## 真实图像示例

以下示例使用项目现有的 LED 和磁片实拍图。两个姿态库均以 2° 步长覆盖整周，匹配分数阈值为 `75`。

| 样本 | 图像数（模板来源 + 其它） | 姿态模板数 | 其它图的最高分范围 |
| --- | --- | --- | --- |
| LED | 8（1 + 7） | 900 | 86.02–93.54 |
| 磁片 | 7（1 + 6） | 3,060 | 89.70–99.49 |

每张拼图展示三张非模板来源的开发图，三列依次为原图、最高分候选叠加、结果局部放大。绿色表示模板特征，黄色表示模型区域与中心，**不是真值标注**。

**LED：中央两电极**

![LED 匹配示例](docs/images/led-matching.jpg)

**磁片：外轮廓与中心孔**

![磁片匹配示例](docs/images/magnet-matching.jpg)

每张有结果的图只绘制相似度最高的一个候选，CSV 保留匹配 API 返回的候选；候选数量**不等于物体数量**，分数也不是概率。

模板来源图 `led/1.png` 和 `magnet/M01.png` 也包含在这 15 张搜索图中，其余 13 张也已用于开发。没有留出的测试集、完整独立真值或专门的负样本评估。样本来源、配置、耗时和逐图结果见[示例说明](docs/matching-examples.md)，实现见[演示源码](examples/showcase.cpp)；可按下方 `showcase_example` 命令复现。

## 能力与限制

- 支持灰度或彩色图像、模板掩膜、多类别和多模板。
- 使用八类梯度方向进行粗到细搜索，支持工作缓冲复用和可选的分段计时。
- 支持可选 SIMD 和 OpenMP 加速，线程数由调用方设置。
- 旋转和尺度变化通过**预先生成的姿态模板库**覆盖。单个模板不具备任意角度、任意尺度不变性；应用需保存模板编号对应的姿态元信息。

相似度是归一化到 0～100 的梯度响应分数，**不是识别概率，也不是经过校准的置信度**。应使用有代表性的正、负样本选择阈值。杂乱背景、遮挡、弱边缘、对称形状和模板库未覆盖的姿态都可能造成误检或漏检。

输出是离散候选。本库未提供通用亚像素定位、连续角度/尺度精修、通用 SMD/CAD 导入器或应用级空间 NMS。内部重复候选合并不能替代多目标检测的重叠抑制，也不代表已具备通用工业准确率或节拍保证。

## 构建

依赖：

- CMake 3.16 或更新版本，以及支持 C++14 的编译器。
- OpenCV 4 开发组件：`core`、`imgproc`、`highgui`、`imgcodecs`。
- 仓库附带的 MIPP 头文件；OpenMP 为可选依赖。

构建和运行库及示例不需要 Python。

在仓库根目录配置并构建：

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

若 CMake 找不到 OpenCV，在第一条命令中添加 `-DOpenCV_DIR=/path/to/opencv/cmake`。该目录需包含 `OpenCVConfig.cmake`。Windows 下应使用相互兼容的编译器与 OpenCV 构建，并将运行时 DLL 所在目录加入 `PATH`。

| CMake 选项 | 用途 |
| --- | --- |
| `SBM_ENABLE_SIMD` | 启用 SIMD；x86 GCC/Clang 默认使用 SSE4.1，要求 CPU 支持。 |
| `SBM_ENABLE_OPENMP` | 在可用时启用 OpenMP 模板搜索并行。MSVC 默认关闭；当前不支持在 MSVC 下启用，CMake 会明确拒绝。 |
| `SBM_BUILD_EXAMPLE` | 构建命令行程序 `match_example` 和 `showcase_example`。 |

需要标量构建时，配置 `-DSBM_ENABLE_SIMD=OFF`；关闭 OpenMP 使用 `-DSBM_ENABLE_OPENMP=OFF`。

开发使用过 Windows、GCC 和 OpenCV 4。本版不宣称已验证 Linux、MSVC 或 ARM 构建。

## 运行示例

复现真实图像示例时，先创建输出目录，再从仓库根目录运行：

```sh
mkdir showcase-output
build/showcase_example examples/data showcase-output
```

`showcase_example` 使用样本 SMD 模型中保存的轮廓构建姿态库，再对 LED 和磁片图像输出可视化图像与候选 CSV。它的 SMD 读取器仅处理这两个样本模型已验证的布局，并非通用 SMD 导入器。

Windows 下使用 `build/showcase_example.exe`；多配置生成器通常将其放在 `build/Release/showcase_example.exe`，`match_example` 的路径规则相同。

运行无需图像文件的合成自检：

```sh
build/match_example --synthetic
```

从一张图训练单个模板，再搜索另一张图：

```sh
build/match_example template.png scene.png
build/match_example template.png scene.png 85 matches.png
```

命令格式：

```text
match_example --synthetic
match_example TEMPLATE SCENE [THRESHOLD] [OUTPUT]
```

`match_example` 的阈值默认为 `85`。该程序自动处理搜索图补边和尺寸对齐，打印原始返回候选；指定 `OUTPUT` 可保存可视化图像。输出框表示**场景坐标中的裁剪后特征范围**，并非分割得到的目标边界或标注真值框。候选可能重叠，`match_example` 未实现通用 NMS 流程。它只演示输入模板的一个姿态，旋转或尺寸不同的目标需由应用建立姿态库。

## 使用库接口

构建提供静态库目标 `shape_based_matching` 及其别名 `shape_based_matching::shape_based_matching`。在上层 CMake 项目中：

```cmake
add_subdirectory(path/to/shape_based_matching)
target_link_libraries(my_app PRIVATE shape_based_matching::shape_based_matching)
```

也可以先安装构建好的库：

```sh
cmake --install build --config Release --prefix /path/to/install
```

外部 CMake 项目随后使用：

```cmake
find_package(shape_based_matching CONFIG REQUIRED)
target_link_libraries(my_app PRIVATE shape_based_matching::shape_based_matching)
```

配置该项目时添加 `-DCMAKE_PREFIX_PATH=/path/to/install`，让 CMake 找到安装前缀；OpenCV 也需能被 CMake 找到。

包含 `line2Dup.h`。通常先训练或加载模板，再跨帧复用工作区：

```cpp
#include "line2Dup.h"
#include <stdexcept>

line2Dup::Detector detector(32, {4, 8}, 20.0f, 40.0f);
const int id = detector.addTemplate(template_image, "part", template_mask);
if (id < 0)
    throw std::runtime_error("Not enough template features");

line2Dup::MatchWorkspace workspace;
line2Dup::MatchOptions options;
line2Dup::MatchTimings timings;
auto matches = detector.match(prepared_scene, 85.0f, workspace,
                              options, &timings);
```

其中图像由应用提供，类型为 `CV_8UC1` 灰度图或 `CV_8UC3` BGR 图，`template_mask` 为同尺寸的 `CV_8UC1` 掩膜。模板掩膜用于选择特征位置，本身不是目标检测器。搜索图需满足**整个模板库**所需的补边和金字塔对齐条件；`match_example` 演示了单模板的准备方式。

每个结果包含 `x`、`y`、`similarity`、`class_id` 和 `template_id`。位置表示裁剪后的模板特征原点在输入搜索图中的坐标；若搜索图补过边，转回原图坐标时需减去补边。可通过 `getTemplates(class_id, template_id)` 和保存的姿态/目标元信息解释特征范围，或构造应用自己的目标框。仅凭 `x,y` 不能得到角度、尺度或原模板图像的原点。

**每个并发调用必须独占一个 `MatchWorkspace`。** 模板不变的 detector 可由多个独立工作区共享，只读匹配；训练、加载或修改模板不能与匹配并发进行。库不修改全局 OpenCV/OpenMP 线程设置，嵌套并行需由应用控制。

## 来源与许可证

本项目基于 [meiqua/shape_based_matching](https://github.com/meiqua/shape_based_matching) 的本地源码快照继续开发，沿用 [OpenCV LINEMOD](https://docs.opencv.org/4.x/d7/d07/classcv_1_1linemod_1_1Detector.html) 相关的梯度方向模板匹配思路，使用 [OpenCV](https://opencv.org/) 进行图像处理、[MIPP](https://github.com/aff3ct/MIPP) 封装 SIMD 运算。

原项目的 BSD-2-Clause 许可证保留在 [LICENSE](LICENSE)。依赖许可证与致谢见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。导入快照对应的上游提交尚未确定，详见[源码来源说明](docs/source-provenance.md)；发布变更见 [CHANGELOG.md](CHANGELOG.md)。
