# Complete fixed training and common padding

All six objects 1/2/5/8/12/17 completed their fixed 3,456 poses: 20,736 attempts
and 20,736 successful templates, with no extraction exceptions or failed poses.
The native process exited 0 and all before/after source/build/input gates
passed. The peak native RSS recorded 64,581,632 bytes.

The root independent standard-library reader reparsed all actual serialized
gzip YAML bank features and checked all 20,736 poses and 41,472 layers against
the CSV diagnostics. Its receipt is
`artifacts/independent_reviews/empty_mask_training_v1/root_training_audit_20261022.json`.
The local `numeric_quick_summary.json` is only a CSV/metadata summary and is
explicitly separate from that independent serialized-bank audit.

`run_training_v1/BANK_FREEZE.json` has SHA-256
`9d92659813a947ee9c4403324468e765e0e3fea0ac8268f2d1f3e1ee4f79b737`.
The native training summary has SHA-256
`f5bc4b08365cb3aa9ad3dab94b75157fd25871c2077767f6da45c5f1eb0b9f2e`.

After a separate root CPU grant, the unchanged training/planning executable
loaded the complete union of all twelve RGB and new banks (77,870 layers) and
planned a shared 848×832 input. Source dimensions remain 720×540, left/top stay
64 and right/bottom are 64/228, preserving the source origin and grid phase.
The geometric plan has 705,536 pixels and estimates 361,234,432 dynamic bytes.
No bank/template was filtered to obtain these dimensions.

`run_plan_v1/COMMON_PADDING_FREEZE.json` has SHA-256
`60608c3b1cd6b3d2f31b2a216e2886e43cb83cc1d74b96b80575f8ecbd9bfb50`.
The padding JSON SHA is
`c70b481ff51a8b7a051d60eb12b34dd76ab5c748f1b982672a3468ec3d6c251f`
and the complete loaded-layer CSV SHA is
`25f565342cd8959cb06176f6ab9a75a0cbc76803adf410be4da13e5d3a78cc66`.

This establishes extraction feasibility and a geometrically valid common
padding. It contains zero development-image decodes and zero matcher calls,
and does not establish matching accuracy or speed. The later fresh RGB/new-bank
comparison needs separately pinned quality sources, a reviewed native build,
the original-padding RGB gate and the fixed correctness pilot. The frozen
source-only predecessor remains untouched.
