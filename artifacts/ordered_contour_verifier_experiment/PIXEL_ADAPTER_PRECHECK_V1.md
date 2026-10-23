# 真实像素适配器静态预检 V1

日期：2026-10-23。状态：**静态预检完成；真实像素执行输入未冻结，未实施/运行像素适配器或质量 pilot。**

本文只推荐一个后续 C0 输入，核对现有小型声明、训练元数据和公开源码，并列出真实回放前必须补齐的证据。它不授予图像执行入口，不追认真实梯度来源，不产生新的准确率或 native 速度结论。生产 V11 `b25df46f6ddf9c24fb43f5836f1414dc38c8caed`、V31 证据及已提交 V32 `141478d1fb639243e0218ebdbccd8801c2603447` 保持只读；本文未用 Git 检查这些提交。

本文中的 `R` 精确指 `D:/h/shape_based_matching-master`；表内路径均相对这个绝对根。所有 SHA 为 SHA-256。标记“实核”的文件实际读取或哈希；“声明”只抄录现有冻结文件里的 pin，未打开其 payload。本文没有解码/读取图像、读取 raw CSV 行、读取或解压 bank/raw 压缩 payload、读取 `datasets/**/index.json` 或封存数据，没有执行 tests、matcher、编译、Git 或基准。元数据访问限于六对象 `[1,2,5,8,12,17]` 的训练与全部 400 development 帧；未进入 old_gate、pilot、timing 或 heldout stage 的内容。

## 1. 唯一推荐 C0：实际 V31 development 的 rgb_control / fallback

后续选择应固定为：

```text
stage = R/artifacts/rgb_stratified_features_experiment/quality/run_development_v1/QUALITY_STAGE_FREEZE.json
arm   = rgb_control
path  = fallback
raw   = R/artifacts/rgb_stratified_features_experiment/quality/run_development_v1/native/obj{object}/rgb_control/s{scene}_i{image}_fallback_raw.csv.gz
scope = six objects × every frozen development frame, including target-negative and zero-candidate combinations
```

不是 `selected_detections.csv`，不是 TP、top-K 或正帧子集，也不是原始未剪枝搜索空间。V11 `Detector::match` 在返回前调用 `detail::consolidateMatches`；V31 `call` 固定 `match(padded,85.f,...)`，再将其结果转为 canonical raw 并归档，之后才运行 `postprocess(...,85)` / NMS。源码给出 refined 分数 `>=85`，因此推荐的是完整 **post-score85、pre-NMS consolidated** 候选。后续执行仍须逐行确认这些条件，不能用本次静态阅读代替数值验收。

这里有两个不同的 development stage，不能混用：

| stage | 用途 | query / LTRB |
| --- | --- | --- |
| V31 `quality/run_development_v1/QUALITY_STAGE_FREEZE.json` | 本文唯一推荐；由 `quality/QUALITY_AUDIT_ACCEPTANCE.json.development_stage` 明确 pin | **848×848；64,64,64,244** |
| V30 `rgb_dilated_mask_experiment/run_quality_development_v1/QUALITY_STAGE_FREEZE.json` | V31 `QUALITY_INPUT_FREEZE.inherited_c0_development_stage` 的明确路径；C0 的历史 equality reference | 848×832；64,64,64,228 |

V31 `QUALITY_INPUT_FREEZE.banks[].c0_common_raw` 指向第二行；V31 `quality_eval.cpp` 将实际 V31 C0 raw 和该历史 reference 逐字段、逐序、float32 score bits 比较。即使现有 acceptance 接受了这个等价关系，新像素场景网格仍必须绑定**第一行本身的 query padding**；不能因 raw 相同便把两个 padded 网格视为同一输入。V14 的旧 padding 和 old_gate 的 848×672 也不适用于本轮。

本次读取推荐 stage 的文件清单，并仅打开其中 2,400 个 C0 fallback 小 manifest。每个 manifest 的实核 SHA/大小均匹配 stage pin；每对象恰有 400 个唯一 `(scene,image)`，都属于 V31 冻结 development 清单；对应压缩 raw pin 也各有 400 项。manifest 的身份、fallback 和 own class 均一致。

| 对象 | manifest / raw pin 项数 | manifest 声明的候选数 | 零候选组合 |
| ---: | ---: | ---: | ---: |
| 1 | 400 / 400 | 78,590 | 0 |
| 2 | 400 / 400 | 74,574 | 0 |
| 5 | 400 / 400 | 8,417 | 45 |
| 8 | 400 / 400 | 93 | 345 |
| 12 | 400 / 400 | 19,778 | 0 |
| 17 | 400 / 400 | 275,827 | 0 |
| 合计 | **2,400 / 2,400** | **457,279** | **390** |

这些是 manifest 库存核对，和 stage summary 的 `raw_candidates=457279` 相符；未读取压缩 raw 的内容，因而**不构成本轮对 457,279 条候选的字段/score bits/顺序或 payload 完整性审计**。零候选组合必须有完成记录，不能丢弃。

## 2. own-bank 身份、origin 与姿态来源

推荐 C0 每对象的 `control_training` 都是：

```text
R/artifacts/rgb_empty_mask_experiment/frozen_inputs/obj{object}/rgb_training/
    template_metadata.json
    training_config.json
    template_attempts.csv
    templates_tless_object_{object}.yml.gz
```

目录名包含 `rgb_empty_mask_experiment`，但这个 `frozen_inputs/.../rgb_training` 是原始 V11 C0 银行的冻结副本；**不是** `train_rgb_empty_mask.cpp` 新训练的 empty-selection-mask 分支，也不是 V31 pooled/stratified bank。C0 是 **RGB 来源文件经 `IMREAD_GRAYSCALE` 解码后的单通道训练**，不能写成 RGB 三通道梯度。

六个 own metadata 实核哈希均匹配 V31 `bank_input_files` pin；class 唯一、ID 从 0 连续到 `count-1`，每对象成功记录覆盖 72 个 training member。metadata 字段为 `class_id,template_id,training_image_id,angle,scale,tl_x,tl_y,warped_mask_bbox`。候选只能通过**相同 bank SHA + object/class + template_id** 连接它；另一个 bank 的同整数 ID 没有对应语义。`training_image_id` 还必须和本对象一起解释。

| 对象 | own class | 成功模板 / ID 范围 | 完整姿态尝试 | 未成功数（差额） |
| ---: | --- | ---: | ---: | ---: |
| 1 | `tless_object_1` | 2,153 / 0..2152 | 3,456 | 1,303 |
| 2 | `tless_object_2` | 2,646 / 0..2645 | 3,456 | 810 |
| 5 | `tless_object_5` | 3,416 / 0..3415 | 3,456 | 40 |
| 8 | `tless_object_8` | 3,456 / 0..3455 | 3,456 | 0 |
| 12 | `tless_object_12` | 3,372 / 0..3371 | 3,456 | 84 |
| 17 | `tless_object_17` | 3,156 / 0..3155 | 3,456 | 300 |
| 合计 | 六个独立 class/bank | **18,199** | **20,736** | **2,537** |

完整尝试数由原始 `readFrames` 的每对象 72 训练成员合同和 config 的 4 scales×12 angles 得出；差额不是本次读取 CSV 得到的失败原因统计。实际执行要绑定并重放全部 20,736 个 attempt 的次序、成功/失败及异常状态，再核对 18,199 个成功 ID；不能只遍历成功 metadata，从而漏掉失败姿态或跳过 ID 形成过程。现有 `template_attempts.csv` 的 pin 见第 6 节，本次没有读取其行。

`tl_x/tl_y` 是 C0 `cropTemplates` 根据**两层训练特征联合范围**生成的 L0 origin，不是 mask bbox 左上角；metadata 的 `warped_mask_bbox` 只有四个数，不证明 warp 图、完整 mask、梯度标签或链的来源。V31 `loadBank` 检查 loaded L0 origin、层数和非空 features，也没有从源像素重训并逐字段比较本轮 C0。

## 3. V14 eligible 标签配方与实际 C0 训练的对照

原 C0 的可追踪训练入口是 `artifacts/public_evaluation/tless_eval.cpp:128`；V31 frozen helper 与它实核字节相同。obj1 `execution_provenance.json` 声明使用 V11 `b25df46...`；当前 V31 `control_v11/line2Dup.cpp/.h` 的实核 SHA 与这个历史 source pin 及 V31 build manifest 一致。这里检查的是源代码与元数据连接，未执行其操作。

| 项目 | V14 eligible 参考 | 实际 C0 / 本轮必须沿用的条件 |
| --- | --- | --- |
| decode | source RGB 和官方 mask 都 `IMREAD_GRAYSCALE` | 原 C0 训练也是这两个 grayscale decode；scene decode 明确检查 `CV_8UC1,720×540`。不能启用三通道最大梯度分支 |
| crop | `maskBox(mask)`，完整官方非零 mask 的 bbox | 相同；crop 是 ROI，允许非连续内存。源路径须由冻结训练清单按 object/class/member 连接，不能在此猜文件名 |
| canvas | `align16(ceil(hypot(crop_w,crop_h)*scale)+2*border)` | 相同；`border=16`。**先 ceil，再加32，再向上对齐16** |
| affine | `getRotationMatrix2D(Point2f(w/2.f,h/2.f),angle,scale)`，translation 加 `side/2.0-w/2.0` / `side/2.0-h/2.0` | 相同公开表达式；必须保存六个 double bit patterns，不能只保存十进制参数 |
| warp | 图 `INTER_LINEAR`，mask `INTER_NEAREST`，`BORDER_CONSTANT=0` | 相同；保留 full warped image/mask 行序字节 pin，而非只比较 bbox |
| dense eligible mask | 原官方 warped mask 非零；unspread label 有效；finite magnitude² **严格 >1600** | 新轮廓标签可按此配方；不得用 C0 内部 eroded mask 冒充官方 full mask |
| C0 稀疏训练 | V14 先用 `addTemplate(warp.image,class,warp.mask)` 回放旧 bank，再另建 dense 证据 | C0 `addTemplate` 使用官方 warped mask；内部先 erode mask 一次，再做5×5幅值 NMS、strict strong threshold、stable sort/scattered selection；请求32/16不代表每层必须恰有32/16个特征 |
| pyramid / origin | V14 旧 `sameTemplate` 比较所有已保存特征 | C0 L1 由 `pyrDown`（尺寸整数减半）及 mask nearest resize 生成；`cropTemplates` 联合两层范围，将奇数最小坐标向下调偶数，然后每层移 origin。必须重放本轮 own bank 的两层 |
| scene | exact padded grayscale，weak20 unspread labels | 本轮必须先补至 V31 **848×848 / 64,64,64,244 / constant0**，再计算标签；不能先算原图梯度再给标签网格补0 |

V14 的公开实现 `coverage_eval.cpp:47` 从 eligible 网格在固定2×2格内挑 strongest 点；这是 V14 的历史采样。新合同先构造**所有满足条件像素的 eligible 网格**，再按已约定细化/链采样；不得把 V14 的2×2点缓存当作新网格输入。二者沿用像素标签解释，不沿用历史采样输出。

具体标签 native 合同可从 V11 源码静态确定：

1. `GaussianBlur` 7×7、sigmaX/Y=0、`BORDER_REPLICATE`；单通道输入保持其原生类型。Sobel x/y：`CV_32F`、ksize3、scale1、delta0、`BORDER_REPLICATE`。
2. `magnitude` 实际保存平方幅值：分别 float32 multiply dx²/dy²，再 float32 add；`phase(...,true)` 输出角度。不要以 sqrt 或不同计算次序替换。
3. `hysteresisGradient` 用 OpenCV `convertTo(CV_8U,16.0/360.0)` 的原生量化，清零外边框，内部 `&7`；对3×3原始量化 bin 做 histogram，中心 magnitude² **严格 >20²=400**，最多票数至少5才生成 `1<<bin`。并列最高票通过严格比较选择较小 bin；histogram 邻居本身不再按幅值筛选。不能直接重算 `angle_ori` 的 bin。
4. `ColorGradientPyramid::quantize` 先将输出清0，再以 mask 作 copy；zero 是无标签，单 bit `1<<b` 解成 `b=0..7`，invalid 固定255；多 bit spread 必须拒绝。模板再显式应用官方 mask、finite magnitude² 与严格 `>1600`；scene 使用 weak20 的 quantize 结果，不加模板强阈值。

同 source、相同几何并不意味着 dense eligible 标签和 C0 已序列化 sparse features 相同。前者是新验证证据，后者是候选的原生 bank；两条链各自保留来源。V14 已对其**当时 bank** 从灰度源图重建，并比较所有 serialized pyramid 字段与有序 `(x,y,label)`；该事实不替代本轮六个 C0 own-bank 的重放。

## 4. 候选与像素坐标的唯一连接

候选身份固定 `(object,scene,image,original_rank)`，`original_rank` 是本 stage raw 中原始 canonical rank，不能用 gate 后或 NMS 后 rank 替换。原 raw 的字段、顺序、float32 score bits、class、template ID、match 坐标及 bbox 全部保持；pose/scale 只按 own metadata 解释。raw schema 是：

```text
scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h
```

模板 chain/sample 的位置已经在 crop 后 rotate/scale 后 canvas 中，按 signed int64、逐项检查溢出后只转换一次：

```text
p_rel      = p_canvas - own_C0_L0_tl
q_padded   = (match_x,match_y) + p_rel
q_original = q_padded - (64,64)
```

不再次 rotate/scale，不加 source crop origin，不再补一次边。原框与 `boxAtMatch` 一致：

```text
bbox_xy = match_xy - (64,64) + own_warped_mask_bbox_xy - own_C0_L0_tl
bbox_wh = own_warped_mask_bbox_wh
```

这个公式只用于一致性检查，不从新边缘 bbox 重造检测框。canonical 顺序是 score降序、class升序、template ID升序、match_y/x升序、bbox_y/x/w/h；NMS 为同 class IoU **严格 >0.3** 抑制，无截断。C0/A/B 各自独立从完整 retained pre-NMS 集合运行原 NMS，不能删除旧 NMS 输出后直接算结果。

沿用合同例：`p_canvas=(6,2),tl=(10,7),match=(64,70)`，则 `p_rel=(-4,-5),q_padded=(60,65),q_original=(-4,1)`。padded 内但原图外是诊断维度，仍可支持；padded 中心越界则 unsupported，即使半径2内还有合法像素也不能救回，分母不减。非对称 crop、非零 origin、负相对坐标、奇数宽、非连续 ROI、边界与非对称 padding 的 native 合成回归仍待真实适配器实现；本文没有运行这些回归。

## 5. native C0 逐层回放与执行冻结前的精确缺口

当前 V32 的 supplied-label / supplied-graph 接口只约束给定网格及坐标；`NATIVE_CORE_DECISIONS_V1.json` 也明确是 supplied-graph synthetic scope。它们不提供 image decode、warp、C0 重训、训练源清单或真实候选来源的证明。以下工作未完成，必须作为后续单独冻结/验收项：

1. **源文件闭包。** 从允许的冻结来源提取六对象432个训练 member 的精确 RGB/mask路径、大小/SHA及次序，和400 development RGB、GT来源、query形状/边界声明。只提取白名单，不能重开全 dataset index 或顺便读取留出。metadata 的 member ID 不足以替代这些 source pins。本预检未哈希图像。
2. **C0 payload 与全部尝试。** 后续明确授权的实际输入冻结才逐一实核六个 own bank 和 attempts payload，固定原始训练顺序 `member → scale → angle`；20,736次全回放保留失败/异常结果。核对18,199个成功ID和metadata pose，失败不消失、不变成新的dense-only成功模板。每次失败仍须保留来源和warp记录；不得从失败中重选参数。
3. **原生训练精确回放。** 使用 pinned V11 core、实际单通道decode、原crop/affine/mask/config；固定 OpenCV/编译器/运行依赖。成功模板两层合计**36,398个 layer**，逐层比较 `pyramid_level,width,height,tl_x,tl_y,feature_count` 与每个有序 `(x,y,label)`，并比较 class、模板ID顺序、pyramid层数及所有实际序列化matching字段。`Feature.theta` 不在 `Feature::write` 中，不能读取未保存/未初始化 theta 并误报完整比较。不能只检查L0 origin、数量或mask bbox。
4. **完整像素产物。** 每个attempt保存crop四整数、canvas宽高、decode flag与native类型、插值/边界模式、affine六double bit patterns、warp image/mask行序字节pin；每个成功模板保存完整eligible标签网格及其原点连接。scene保存完整848×848 eligible网格、原720×540尺寸、四向padding、constant0和行序pin。矩阵十进制日志、hash-only链输出或V14旧点缓存不足以构成合同的充分证据。
5. **候选载入闭包与C0正控。** 实际读取前固定2,400份raw/manifest清单及pins；载入后逐行核对全部457,279个候选的数量、唯一identity、16原字段、own-bank pose、float32 score bits、框和原顺序，包括390份空表完成记录。score17位十进制是归档表示，执行证据应显式保留float32 bits。重现C0原NMS及GT/assignment身份的完整正控；本预检既没有载入raw，也没有重算旧accuracy。
6. **新网格至验证器连接。** 将完整eligible网格交给冻结细化/链/所有权/权重流程，保留完整输出及native坐标回归证据。独立完整audit从eligible网格重建后续运算；如没有另写独立灰度/warp/blur/Sobel像素oracle，就不能称其为独立原像素梯度审计。native回放本身是来源/重放检查，不会补出这个更强主张。
7. **后续输入/源码/资源冻结。** 重新列完整input/source/build/runtime pins、唯一threshold与预算、reservation、原C0证据、完整输出/审计格式并经过独立审查。先完成这些前置条件，再运行唯一完整development；本文不替代合同第7节的资源验收、停止规则或执行许可，不用真像素小pilot调参数。

## 6. 已核对的 paths / pins

以下实核文件的SHA与引用它的现有声明一致（没有历史声明的项则作为本次静态阅读pin）；大JSON只解析其声明/文件清单，没有跟随读取其列出的raw、bank、index或留出payload。

| 实核路径（相对R） | bytes | SHA-256 |
| --- | ---: | --- |
| `docs/superpowers/plans/2026-10-23-ordered-contour-verifier-contract.md` | 22,780 | `921ffa61095963d909264a8f0718d8c258555add459263d196673147b535a473` |
| `artifacts/rgb_stratified_features_experiment/quality/QUALITY_INPUT_FREEZE.json` | 3,071,298 | `a23d18e84cfd2501371c617ba2c5d7915cdd7e25c7c307de8ad173e7724e3fc4` |
| `artifacts/rgb_stratified_features_experiment/quality/QUALITY_AUDIT_ACCEPTANCE.json` | 1,970 | `b1d30b7295786e7cf2f2c1114c98fb4b64edfb601cf66751297c31bdac2c1a4a` |
| `artifacts/rgb_stratified_features_experiment/quality/run_development_v1/QUALITY_STAGE_FREEZE.json` | 9,086,309 | `6070b474d29b112c822d7f6a94a2ec920e454d104c511c42c29bf78a1d77b47a` |
| `artifacts/rgb_dilated_mask_experiment/run_quality_development_v1/QUALITY_STAGE_FREEZE.json` | 5,825,410 | `c3073775ffea2c9f4a1d0058b2e1e884d7bcde9c97590a8cd6459063d03d0b88` |
| `artifacts/rgb_stratified_features_experiment/quality/COMMON_PADDING_FREEZE.json` | 146 | `a70a32ee54b1b6ca576b869ae333f036e4b874aa89beac8d4f1198261d151aec` |
| `artifacts/rgb_dilated_mask_experiment/run_plan_v1/common_padding_plan.json` | 353 | `6965565bf9c9c745e4cda1bb56cee5d0d02e1f9b310dd65897959eb55d3d8f8a` |
| `artifacts/rgb_stratified_features_experiment/quality/build_native_v1/build_manifest.json` | 257,248 | `24e872c5b735964e018d2b0a51f3077ced946e8412fd0664fb6912e927a138e0` |
| `artifacts/public_evaluation/tless_eval.cpp` 与 `artifacts/rgb_stratified_features_experiment/frozen_helpers/tless_eval.cpp`（二者相同） | 37,373 each | `c9e4016d1cd7ad6ce37d49bc04f49f1f3d496573a0047a9d1b8da951eb7204ef` |
| `artifacts/rgb_stratified_features_experiment/frozen_helpers/eval_metrics.hpp` | 4,985 | `1339092b5fbf2f5283dced01fc0b74eea467074223943d8248b89b6e48249de3` |
| `artifacts/rgb_stratified_features_experiment/control_v11/line2Dup.cpp` | 63,388 | `85b5eb328a3b5cae3e161561e261833873d25a9f57c7457c4410dd21e52083ab` |
| `artifacts/rgb_stratified_features_experiment/control_v11/line2Dup.h` | 12,702 | `c3a8f742fc897bdcfa83a82a9a025e6b304f410bc081c321695f5e6f7f461fc0` |
| `artifacts/rgb_stratified_features_experiment/control_v11/line2Dup_matches.hpp` | 1,452 | `80c8d1ee482307a0472a46d7a1e4da868154f2f893fcdc32d53b9be8f35c0344` |
| `artifacts/rgb_stratified_features_experiment/quality/quality_eval.cpp` | 18,886 | `cedc7f421c72a5698e82fd077fe8df4839f93b943ec085af1598c270ae0945f2` |
| `artifacts/rgb_stratified_features_experiment/quality/quality_support.hpp` | 11,120 | `b38696acadb48f238bad5e951e2934a2026098e1e7b1855ba795d8421719869f` |
| `artifacts/quality_coverage/coverage_eval.cpp` | 37,254 | `631e97cd9ed2d7e076085922aeab679851681f1ddb3108854350fe11c8694859` |
| `artifacts/quality_coverage/coverage_helper.hpp` | 7,424 | `73b372f5a984d293ce69b211ed9e3f21472d7bc518d4402437b87799a6ed9d6f` |

六个 C0 metadata 的完整路径按第2节展开；以下均实核：

| 对象 | metadata bytes | metadata SHA-256 |
| ---: | ---: | --- |
| 1 | 832,082 | `c57c0f22b8f908198f0bc2d11634d0dbbac8c71627fde8b5bb96647cd860d069` |
| 2 | 1,023,412 | `599ee8ef96d5bb14d379b6de060e9113dec0d40b940e6d8ee23f2e1d14eaf19f` |
| 5 | 1,324,636 | `20a31cfeccb400d377a5e5e558dddf6e8c759eea16840fc719eb8258558cd67c` |
| 8 | 1,345,188 | `f353b416ca55a1181f7ee56e810ca98cdab8742a120d6db609727c4e3b5704f0` |
| 12 | 1,309,286 | `2546aab5f7707f5c0f336a4a8704173c00965e9e50f9ce11ccbeac43f252b7e8` |
| 17 | 1,227,991 | `495a77668184071cca83d69e2991b60a3050e31bb61228734360d1a6e7d6d717` |

六个 `training_config.json` 均实读，参数相同：features32、angles0..330 step30、scales `[0.75,1,1.5,2]`、border16、T `[4,8]`、weak20、strong40；文件因object/path不同而哈希不同：

| 对象 | config bytes | config SHA-256 |
| ---: | ---: | --- |
| 1 | 1,414 | `db86c59f87066c3779e061e702268c2aae1313caab9dcbdcb6a2cc0885de3840` |
| 2 | 1,414 | `dc67c0122b86212cccecbb15bb1ad74b2b79c300ed4b4bdab0229b5834c2ecae` |
| 5 | 1,414 | `84cc1d297c575b0d7bb4083180284a320c8991ee0d3f43631e9b29f0461fa146` |
| 8 | 1,414 | `cfa902a1dcd0e419184914abcd1fb1677caf81a054365d1c6ca2870b813ca7e6` |
| 12 | 1,416 | `8cee385be8c1ff51077d2ef4c91591eb7f978c42ee02d8827740ab109a34a846` |
| 17 | 1,416 | `26c5de3f38ff0bd665e094f3e58f63b7b5afb12cdb5b52337c44cc21a1f7b61f` |

下表bank与attempts是 V31 `QUALITY_INPUT_FREEZE` 的**声明pins**，本次没有实读/哈希payload；完整路径按第2节展开：

| 对象 | `templates_tless_object_{object}.yml.gz` bytes / SHA-256 | `template_attempts.csv` bytes / SHA-256 |
| ---: | --- | --- |
| 1 | 553,232 / `e717461ba75e10a2a281ea6a6bbf7e12e11cd4a8b691d896d8062439e70b173e` | 288,224 / `8d8f74f44a16d679af9f3787c58c6df9c40e209f154b7afadd5ca162ae4be570` |
| 2 | 661,726 / `b149a0e1ea91b99b00e7da7456426fa6a26bf489f786b3f29f70f08ceea506ef` | 282,072 / `61372a9a12a37b2a9bf7114fc1821eb343540d25244646ccbe54a9c02147063d` |
| 5 | 936,016 / `cc804f08e51529d45f731fef13f9a770df196fad2157efa711ea9c77933d4656` | 279,417 / `06e12d8c2344391ce8a9ee9926e8395a32a3781ab1f01344fb1f84f426a81664` |
| 8 | 1,015,469 / `a0587d3d89ccf3236aa86a867ba0cde1cac7e97e5ef8a57ab3c062ead3a962c7` | 278,924 / `364e59a2a7b0e9fced7fb7a1d0e8fafaf3a6535fd47fb88c34c1666214ca54d0` |
| 12 | 893,985 / `685d860711aed978aadb8f78df849cfd2bcb8c148cbad2c67ad2876406862739` | 280,828 / `221d845ca6bb6370d1759ea59d53bbfcc88707b8972367d7856b983f7b16feeb` |
| 17 | 878,034 / `72b3c40d30cc138497c3c2cac6e1c7aa74965f416be157ae8c8d5a4dc4bbbcdf` | 287,815 / `31e8e776cc26b493fb48da8293f00f8e6883f688bfc69355f1a624e241959100` |

全部2,400个manifest的逐文件pin由本节推荐stage的 `files` 清单绑定，本文不复制清单。可定位的实核例子：

```text
R/artifacts/rgb_stratified_features_experiment/quality/run_development_v1/native/obj1/rgb_control/s1_i101_fallback_raw_manifest.json
bytes=600
sha256=5c44732556506ae57de546bb83a8022524a2d6c0f11e2e790427d3a5eaaa45e1
```

该manifest声明23候选；相应 `.csv.gz` 的path/bytes/hash仍仅作为冻结清单声明，本次未读其行或payload。最终结论限于：**C0 stage、own-bank元数据、灰度来源配方及坐标合同已可明确选定；真实像素来源与精确native逐层回放仍须另行建立和验收。**
