# 搜索优化独立正确性复查

结论：在合法模板特征数 `1..8191`、每个并发调用独占 workspace 的现有约束下，本次复查未发现阻塞性的等价性、边界或并发问题；**无未解决 finding**。本记录不作性能收益结论，默认开关是否启用仍应由独立性能结果决定。

## 已读文件与复查范围

- `line2Dup_search.hpp`：`similarityScore`、整数局部最大值及其类型/参数检查。
- `line2Dup.cpp`：四种 similarity 累加函数、`SearchScratch`、workspace 所有权、worker 预分配、候选收集、浮点回退、两个 `matchClass` 重载、局部坐标更新及最终过滤。
- `line2Dup.h`：三个搜索开关、workspace 并发约定、旧 `matchClass` 签名与新增重载。
- `artifacts/search_optimization/baseline/line2Dup.cpp`、`.h` 与 manifest：冻结 V4 的浮点扫描、阈值及转换路径；更早的原始 baseline 不被替换。
- `tests/search_kernel_test.cpp` 与 `kernel_test_result.json`：独立标量参考、RED/GREEN 及数值覆盖。
- `tests/search_workspace_test.cpp`、`artifacts/search_optimization/fixtures.hpp`：组合开关、并发和跨帧状态测试的断言范围。

本次只读复查 core/helper；只新增本记录，未修改 core，也未运行 CPU 测试或性能基准。

## 分数、最大值与阈值等价性

`similarityScore` 保持旧算式 `(int(raw) * 100.f) / (4 * N)`，未改为预计算倒数、double 算式或整数阈值。coarse 收集函数也保留相同的浮点运算顺序。

合法输入中每特征响应至多为 4，故 `raw <= 4N <= 32764`。乘以 100 的整数结果不超过 3,276,400，小于 binary32 可精确表示整数的上限 `2^24`；归一化后相邻 raw 的最小分差约为 `100/32764 = 0.003052`，远大于 0..100 范围内的浮点间隔。因此整数大小顺序与旧逐像素浮点比较一致，整数 argmax 后只计算获胜分数可保持原结果。

- 扫描仍逐行、逐列，且只在 `raw > best.raw` 时替换。并列正分保留第一个 row-major 位置。
- 初始 `raw=0`、`score=0`、`row=col=-1`；全零图不会改为 `(0,0)`。局部坐标更新继续使用这两个 `-1`，没有新增跳过或修正零分的行为。
- coarse 使用 `score > threshold`，等于阈值不收集；局部最终仍仅删除 `score < threshold`，等于阈值保留。这两处不能统一成同一个比较符。
- coarse 没有新增 `raw==0` 快速跳过，所以负阈值下零分可入候选的旧行为仍在。NaN 阈值的原比较表达式也未改变。
- 独立测试检查等值、`nextafter` 上下邻值、负阈值、0/75/100 和 NaN；使用 float 位模式比较，未采用误差容差掩盖舍入变化。

## 8U / 16U 路径

- 特征数 `<64` 的最大和为 `63*4=252`，可直接扫描 8U；特征数 64 起使用原 16U 累加路径。
- 8191 特征最大和为 32764，仍在原 signed-16 SIMD 累加的安全范围；8192 及以上继续由原路径拒绝。
- direct 开关关闭时仍执行旧 8U→16U 转换；开启时按实际 `Mat.type()` 选择 `uchar` 或 `ushort` 读取。候选和局部浮点回退也按实际类型读取，没有 reinterpret 为错误元素宽度。
- 8U→16U 转换对已有值精确；helper 在两种类型上使用同一分数算式。测试单独核对相同 map 的两种深度输出。
- 特征数为零不属于本次支持契约；helper 明确拒绝零、负数和 8192。未声称支持非法空特征模板。

## Worker scratch、清零与尺寸变化

`search_workers` 在进入 OpenMP `parallel for` 前按调用线程的 `omp_get_max_threads()` 调整大小；进入循环后，每个 worker 仅访问 `search_workers[omp_get_thread_num()]`。循环内没有对该 vector 执行 resize。各模板的候选收集、局部细化和插入均在当前 worker 上完成，matches 仍使用原 OpenMP reduction。

同一 class 的循环结束存在隐式 barrier，多个 class 的调用按顺序进行，不会让两个 class 同时修改同一 worker scratch。不同并发调用继续要求不同 workspace，旧接口使用的 TLS workspace 也不在调用线程之间共享。本次没有扩大“同一个 workspace 可被并发使用”的契约。

- 每个模板开始都 `candidates.clear()`，只复用 capacity，不复用候选内容。
- 四种 similarity 函数都仍通过 `Mat::zeros(...)` 完整初始化目标；复用分配不意味着省略清零。因此无效/未写尾部仍为零，不会保留前一模板分数。
- Mat 的目标尺寸与类型由本次调用重新确定；coarse 图与 16×16 local 图独立，模板特征数跨越 63/64、金字塔层数、帧尺寸或 detector 改变时不会把旧深度当新深度读取。
- `reuse_search_buffers=false` 使用模板循环内部的 transient scratch；开启时使用 worker scratch。
- 若 `reuse_buffers=false`，整个 state 仍是 call-local，所以 search scratch 最多在本次调用的模板之间复用，不能跨帧滞留。两个开关组合的寿命行为清晰。

旧 `matchClass` 的声明和定义均保留。其 wrapper 构造独立 workspace、准备 worker 数并转发到新重载，未强迫已有调用者提供新参数。这证明旧签名的源码调用兼容；不据此宣称所有结构体的二进制 ABI 兼容。

## 独立 kernel GREEN 结果

首次构建因缺少 `line2Dup_search.hpp` 失败，RED 退出码 1。helper 实现后使用 g++ `-std=c++14 -O3 -mssse3 -msse4.1` 构建成功，测试退出码 0：

```text
PASS search kernels: 1876 maps, 34855 bit-exact scores,
278840 threshold pairs, 9 invalid arguments rejected
```

覆盖 N=`1,46,63,64,111,236,8191`；逐一穷尽这些 N 的所有合法 raw 分数；包含全零、跨行并列、尾像素最大值、8U/16U、非连续 ROI、1/16/17/33 宽和固定种子随机 map。参考实现保留旧逐像素 float strict-`>` 扫描，而非用另一个整数 argmax 当作 oracle。具体结果及测试/header SHA256 见 [kernel_test_result.json](kernel_test_result.json)。

## search_workspace_test 覆盖复查

该测试覆盖 8 个搜索开关组合；9 个正样本；全零、全满、部分 mask；阈值 101 的空候选；同一 workspace 上灰度/彩色、尺寸、detector 与金字塔配置切换；线程数 `1→4→2→4` 的 worker 缩放；workspace move；两个使用独立 workspace 的并发调用。断言包含分数/坐标的 semantic 集合、候选总数及计时非重叠。

没有必须追加的阻塞边界。全零 map 的 `-1` 索引、63/64 位宽交界、8191 上界及精确阈值已由 kernel 测试单独覆盖；没有必要为了这些数值边界再次扩大真实场景矩阵。

覆盖边界：workspace 测试对包含 `template_id` 的 strict 集合只记录差异，不将其作为失败条件。并列模板经现有排序/去重可能有身份选择歧义；因此该测试不能单独证明并列模板的 `template_id` 严格确定性一致。该说明不是本次已确认的新回归，也不影响 kernel 对同一 map 的首个 row-major 最大值保证。若后续要求稳定模板身份，应单独定义并验证确定性排序/去重契约。
