# Local call and clamp distribution

Derived only from the completed run; no matching rerun or snapshot change. Counts are identical in all seven measured repetitions. X and Y clamping counts can overlap. Unique local centers and overlapping candidate windows were not recorded, so these values cannot establish cache hit rates.

| Dataset / image | Level | Features | Local calls | Retained | X clamped | Y clamped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LED/1.bmp | 0 | 236 | 10298 | 3.80% | 0 (0.00%) | 0 (0.00%) |
| LED/1.bmp | 1 | 111 | 10484 | 98.23% | 75 (0.72%) | 2280 (21.75%) |
| LED/2.bmp | 0 | 236 | 12483 | 3.89% | 0 (0.00%) | 0 (0.00%) |
| LED/2.bmp | 1 | 111 | 12533 | 99.60% | 80 (0.64%) | 1723 (13.75%) |
| LED/3.bmp | 0 | 236 | 10758 | 3.61% | 0 (0.00%) | 0 (0.00%) |
| LED/3.bmp | 1 | 111 | 10917 | 98.54% | 8 (0.07%) | 1440 (13.19%) |
| LED/4.bmp | 0 | 236 | 12284 | 1.72% | 0 (0.00%) | 0 (0.00%) |
| LED/4.bmp | 1 | 111 | 12764 | 96.24% | 0 (0.00%) | 2334 (18.29%) |
| LED/5.bmp | 0 | 236 | 13537 | 3.12% | 0 (0.00%) | 0 (0.00%) |
| LED/5.bmp | 1 | 111 | 13642 | 99.23% | 0 (0.00%) | 2495 (18.29%) |
| LED/6.bmp | 0 | 236 | 17729 | 2.61% | 0 (0.00%) | 0 (0.00%) |
| LED/6.bmp | 1 | 111 | 17772 | 99.76% | 138 (0.78%) | 1359 (7.65%) |
| LED/7.bmp | 0 | 236 | 13701 | 3.28% | 0 (0.00%) | 0 (0.00%) |
| LED/7.bmp | 1 | 111 | 13703 | 99.99% | 0 (0.00%) | 3611 (26.35%) |
| LED/8.bmp | 0 | 236 | 14147 | 1.32% | 0 (0.00%) | 0 (0.00%) |
| LED/8.bmp | 1 | 111 | 14416 | 98.13% | 0 (0.00%) | 3273 (22.70%) |
| case1/case1 | 0 | 131 | 123 | 17.07% | 0 (0.00%) | 0 (0.00%) |

LED local accumulation, equal mean of image medians:
- Level 1: 13278.9 local calls/image, 37.067 ms summed worker accumulation/image; 98.71% candidates retained.
- Level 0: 13117.1 local calls/image, 80.966 ms summed worker accumulation/image; 2.92% candidates retained.

These are worker elapsed intervals, not wall time. Level 0 uses 236-feature 16-bit accumulation; level 1 uses 111-feature 16-bit accumulation. LED coarse uses 46 features and the 8-bit kernel. The L0 candidate rejection occurs after its full 16×16 search; this is diagnostic evidence for targeting that kernel, not permission to alter thresholds.
