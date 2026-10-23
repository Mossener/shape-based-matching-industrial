# 原生验证资源口径补充

本说明补充已有 `run_native_core_checks_v1.py` 和后继 batch runner 的口径，不修改已执行源码、输入或回执。

- 编译阶段：编译 helper 将自己及随后 GCC 子进程纳入 Windows Job，限制合计 **committed memory** 1 GiB，并启用关闭 Job 时终止成员。父进程另观测 helper peak working set、wall 和输出。committed memory 与 working set 不同，不能写成 aggregate RSS 硬隔离。
- 核心测试、fixture 生成、batch 求解和独立审计阶段：各自一个前台进程，50 ms 轮询其 peak working set、wall 和目录/日志字节；超限终止。这是观测后停止，不能阻止首次越界分配。
- `native_provenance.compiler_tools()` / `import_closure()` 为编译器和 PE 静态依赖查询启动 g++/objdump 元数据子进程。继承 helper 的这些查询使用 `capture_output`，未设置 timeout 或纳入上述 Job/进程 watchdog。故资源上限只适用于明确的 build/test/generate/native/audit 阶段，**不覆盖整个协调器与元数据预检**。本轮未据此声称整个协调器有总 wall/RSS/output 硬界。
- 记录实际 GCC dependency 文件、工具/库文件及非系统静态 PE 导入的执行前后 pin；OS/API DLL 仅按名称记录，动态加载不构成完整闭包。它们是本机复现线索，不是执行证明或供应链 attestation。

合成进程 wall 包含协议读写、启动及断言；编译 wall 更不能代替真实图像完整调用基准。本轮没有任何 native 加速或真实准确率收益结论。
