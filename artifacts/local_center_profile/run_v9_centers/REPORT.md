# Exact local-center repetition census

One instrumented V9 call per image, with one independent V4 call per image for exact semantic-set/raw-count validation. All nine checks passed. Strict-set differences: 0.

Center identity is `(image, class, template_id, pyramid level, x/T, y/T)` after clamping. Each template/level owns its frequency dictionary. The key therefore records the exact patch used by local accumulation, including integer division. Images, templates and levels are never merged into one cache key.

| Dataset / image | Level | Total local calls | Unique centers | Repeated calls | Repeated % | Max frequency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LED/1.bmp | 0 | 10298 | 2371 | 7927 | 76.98% | 19 |
| LED/1.bmp | 1 | 10484 | 9967 | 517 | 4.93% | 3 |
| LED/2.bmp | 0 | 12483 | 2392 | 10091 | 80.84% | 20 |
| LED/2.bmp | 1 | 12533 | 12161 | 372 | 2.97% | 4 |
| LED/3.bmp | 0 | 10758 | 2078 | 8680 | 80.68% | 19 |
| LED/3.bmp | 1 | 10917 | 10776 | 141 | 1.29% | 3 |
| LED/4.bmp | 0 | 12284 | 2595 | 9689 | 78.87% | 21 |
| LED/4.bmp | 1 | 12764 | 12225 | 539 | 4.22% | 3 |
| LED/5.bmp | 0 | 13537 | 2563 | 10974 | 81.07% | 19 |
| LED/5.bmp | 1 | 13642 | 13149 | 493 | 3.61% | 3 |
| LED/6.bmp | 0 | 17729 | 3400 | 14329 | 80.82% | 21 |
| LED/6.bmp | 1 | 17772 | 17452 | 320 | 1.80% | 3 |
| LED/7.bmp | 0 | 13701 | 2590 | 11111 | 81.10% | 18 |
| LED/7.bmp | 1 | 13703 | 12914 | 789 | 5.76% | 4 |
| LED/8.bmp | 0 | 14147 | 2327 | 11820 | 83.55% | 17 |
| LED/8.bmp | 1 | 14416 | 13147 | 1269 | 8.80% | 4 |
| case1/case1 | 0 | 123 | 123 | 0 | 0.00% | 1 |

| Dataset | Level | Images | Total calls | Unique centers | Repeated calls | Repeated % | Max frequency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LED | 0 | 8 | 104937 | 20316 | 84621 | 80.64% | 21 |
| LED | 1 | 8 | 106231 | 101791 | 4440 | 4.18% | 4 |
| case1 | 0 | 1 | 123 | 123 | 0 | 0.00% | 1 |

`center_frequency.csv` contains the full distribution: frequency k, number of unique scoped centers occurring k times, and k × count calls. `centers_by_template.csv` retains all template/level totals, including those with no candidates. The post-processing audit reconciles both with every image/level summary and verifies total/clamp counts against the previous V9 profile.

Repeated calls are the exact count of already-evaluated identical local windows within a template/level. A result cache may reuse their maximum and relative winner coordinates while retaining all candidates and their existing threshold checks. This count is an upper bound on local evaluations avoided by a full-lifetime cache, not a speedup estimate. Cache lookup/storage/allocation costs, memory footprint, and altered cache behavior require an uninstrumented paired benchmark. No production API, pose bank, thresholds, candidate multiplicity, or matcher semantics were changed.

This executable uses a copy of the saved 6b7be69 V9 diagnostic source. Its fixture builder is compiled against that private namespace; no current production matcher object is linked. The prior `search_profile/source`, manifest, and `run_v9` remain unchanged. Old stage clocks remain in the copied code, but no timing results are used or published.
