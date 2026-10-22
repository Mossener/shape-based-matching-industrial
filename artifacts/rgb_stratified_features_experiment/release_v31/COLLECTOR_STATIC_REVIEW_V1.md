# V31 实际证据 collector 静态审查

2026-10-23。审查 `collect_actual_selection.py` 与 `test_collect_actual_selection.py` 当前文本，
并对照少量既有回执和 source checkpoint。**在已核范围内未发现 material issue**；未修改 collector 或测试源码。
本记录可供后续显式 supplement 纳入，不应成为源码继续变动或延迟真实验收的理由。

| 检查点 | 静态结论 |
| --- | --- |
| 显式白名单 | 从固定 source checkpoint、命名回执、声明的有限列表及 REPO_TEXTS/ROOT_TEXTS 收集；没有 glob/rglob/walk/iterdir、Git、subprocess 或 native 调用，也不递归追随任意 input_pins。重复相同路径 pin 可合并，冲突 pin 拒绝。 |
| stage closure | 固定 selftest/old_gate/pilot/development/timing 五阶段要求 completed/post_verification/exit=0，逐项加入完整 files 与 execution_files，补入声明的 build/input/selftest/previous/reservation/quality-audit 绑定；没有选择逐帧子集或旁路扫描目录。 |
| export 与恢复 | export 清单须匹配固定 SHA/字节、schema 与 46 成员数；每个 stored 成员均进入 selection，重复映射拒绝，stored 总字节核对。恢复 acceptance 绑定同一清单，加入恢复结果和六 guard 文件；不跟随恢复副本路径。 |
| source closure | 公共 RED/GREEN、两轮 mutation、V2 source handoff、V2 RED/GREEN/full-source、训练源验证和 root join reviews 均有命名展开。实际质量 V2 before/after 与 timing source pins 被收集；额外核对独立 geometry reservation 的六个仓内执行源 pin 与 source checkpoint 相等。完整实际闭包仍由后续 collector 和 payload 验收决定。 |
| failed V1 的 after=None | quality_source_records 只允许显式 failed_v1=True 且 passed=False 时缺省 after；调用点只在固定 real_development_audit_v1 失败历史分支设置该参数。成功源列表要求 before/after 完全相等；对应测试覆盖失败例外与成功拒绝分支。 |
| 历史源码 | snapshot 根据该 run 的 source pins 基名映射到其 source 副本，mutation 只替换变更角色；不把历史 README/run_selftest/origin 等 pin 强加到今日顶层源码。已知缺失历史快照显式进入 unavailable_historical_sources，未伪称完整可重放。 |
| 禁止项 | add_pin 拒绝图片、SMD、exe/dll/o 等后缀及 materialized restore 目录。唯一 bin 例外须为该固定 export 清单授权的同 pin pools_NNNNNN.bin.gz identity 成员；外部 source/runtime 仅记录引用，不选择二进制。 |
| self-cycle | selection 和 pathspec 均不能进入 files；pathspec 是有限已选路径加 selection 自身，以 NUL 分隔，不包含自身。selection 只 pin 稳定 collector/source 回执，不 pin 自身生成结果；输出采用 fresh existence gate 和 xb。 |
| 测试覆盖 | 静态读到 14 个隔离合约测试，覆盖路径、冲突 pin、payload 不读、二进制例外、旧 snapshot、mutation 角色、V1 after=None、stage 完成标志与 pathspec。未将这些小 fixture 测试描述为真实完整闭包或 payload 验收。 |

本审查读取的补充 metadata 包括 source checkpoint、训练 V1/V2 runner、V2 OUTPUT_PINS、质量 V2 runner、
计时 runner、geometry scan/independent runner 与 reservation/source-evidence、公共 source validation、
root join STATIC_REVIEW_RECEIPT 和 selftest stage freeze。没有读取 bank/raw/export payload、图像或恢复副本，
没有运行 tests、collector、native、Git、编译或大型 hash。

限制：这是固定当前 collector 的静态审查，不是对所有 metadata schema 的独立防篡改审计，也未遍历核对
全部实际 stage inventory 或重新证明每条传递闭包。collector 对已 pin payload 只核大小，后继 verifier
必须核真实字节/SHA；真实 selection、全 payload 和 Git index 的验收状态以 root 随后的实际回执为准。
两文件写出并非原子事务；若第二步失败，保留第一次产物作为失败证据，由新显式操作处理，不能覆盖重跑。
