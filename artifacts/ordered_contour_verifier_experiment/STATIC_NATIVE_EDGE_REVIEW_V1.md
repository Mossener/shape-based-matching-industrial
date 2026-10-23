# Static Native Edge Review V1

Date: 2026-10-23. Static inspection found no material defect within the supplied-label contract in `native_edge_chains.hpp`, the bounded JSONL batch driver/protocol, or the independent fixture generator/auditor and coordinator. This review read source, hashes, and retained receipts only. It did not build, execute Python/native code, rerun tests, read images, use Git, or change the frozen header/tests.

The header preserves synchronous Zhang–Suen rounds and original labels, complete eight-neighbor edge decomposition and returning flags, canonical full-chain order, exact fixed-marker arclength sampling, lowest-chain ownership, original chain indices, and exact global 4×4 cell weights. Unsigned neighbor arithmetic and ID conversion avoid Windows narrowing; GMP imports the complete uint64 value and retains exact weights. The batch validates bounded input before factory calls, exposes full thinning/raw chains/raw samplings/template records, writes exact integer JSON tokens, and checks complete-response stdout budgets before writes. Empty thinned templates alone become `null`; unexpected factory errors remain fatal.

Retained [RED output](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/native_edge_red_v1/test_execution/stdout.txt) records 36 tests, 121 checks, 114 assertion failures, and zero errors. Retained [GREEN output](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/native_edge_green_v1/test_execution/stdout.txt) records the same 36 tests, 229 checks, zero failures, and zero errors. The additional GREEN checks are guarded full-record comparisons reached when the implementation supplies nonempty records; frozen test SHA-256 remains `81acdb4a0679f064cff18015f7c749a75bfb9ef8068529163ecfc7b13543dfe3`.

The [independent batch receipt](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/native_edge_oracle_green_v1/receipt.json) records successful guarded generation, build, native execution, and audit, all exit 0, with stable sources. All 615 synthetic grids were compared recursively with exact JSON types and every evidence field: all 512 3×3 occupancies, 100 fixed-seed 4×4/5×5 grids, a 160×160 isolated-point GMP fixture, and two longer paths. There were zero skips and five legal null templates; the large fixture requires LCM above uint64. Native stdout and independent expected JSONL are both 1,713,837 bytes and share SHA-256 `d692a43e2dfd6cfd92ec87d35e10b2834733e67ef9a85d190ab988969e5ae310`. Expected values come exclusively from `independent_edge_oracle.py`, whose decomposition, bisect sampling, and Fraction weighting differ from the native implementation. No optimized edge helper provides expected values.

These results establish supplied-label mathematics over the stated fixture domain. Runtime watchdogs observe individual-process working set, wall time, and output; compiler-job committed memory includes GCC children. They do not establish aggregate RSS, an OS allocation sandbox, end-to-end coordinator bounds, image accuracy, or native matching speed. Metadata/import preflight is outside child watchdogs, and PE provenance retains its documented OS/dynamic-import limits. Factory records remain mutable C++ value snapshots; subsequent adapters require unmodified factory evidence.

Reviewed current SHA-256 pins:

| Source | SHA-256 |
| --- | --- |
| `native_edge_chains.hpp` | `bc39ca22c1c1f80273d8ddbafa57941f9b07a66ac11f10f46e58e9db2ca7ffbf` |
| `native_edge_batch_v1.cpp` | `b650b26b60630bd0408b09a4b3a17a44ec2b57b8f8ad1ecf43c24191e69f51b2` |
| `NATIVE_EDGE_BATCH_PROTOCOL_V1.json` | `59f939d5d0bb99fd5ce5af1494bfcc74462ab8dd795e90d0231640b20f321f43` |
| `native_edge_oracle_fixtures_v1.py` | `50177747bf2d2a82f7530580c5401bab335597a98e1504f75a5dcbb17b21e7db` |
| `run_native_edge_oracle_checks_v1.py` | `c59c363db406c40630e8682d48210b9b950a238ef2c39f604145ac3900f01e3f` |
| `independent_edge_oracle.py` | `bca66cf17ab0036aecd3c7f6f141e925d50055385cd95d53fa9659299bab5315` |
