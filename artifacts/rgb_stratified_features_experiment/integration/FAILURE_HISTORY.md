# Shared integration failure history

All runs used numeric in-memory Mats only, with zero image decodes, zero real
dataset files and zero matcher calls. No receipt or source snapshot was replaced.

1. `run_missing_header_red_v1`: expected compile RED before
   `shared_training.hpp` existed. The compiler failed specifically for the
   missing header. The runner preserved exact source/tool pins and stderr.
2. `run_green_v1`: the first implementation compiled and passed four integration
   cases. The real-gradient checkerboard fixture failed the assertion requiring
   more than four accepted candidates. Summary: passed4/failed1, 183 assertions,
   three synthetic pose calls. This was retained as a failed attempt, not GREEN.
   This run was started prematurely during a collector-source handoff; the
   scheduling mistake was reported immediately to the root and collector agents,
   and native work stopped before subsequent coordinated runs. Its evidence is
   historical only and is not the final collector/source acceptance.
3. `run_small_checker_diagnostic_red_v2`: the same 96x128/8-pixel checkerboard
   signal, with added layer observations, reproduced the expected failure.
   L0 produced356 accepted candidates /356 NMS maxima. L1 produced0 accepted
   candidates /108 NMS maxima. Its blocks become4 pixels after downsampling,
   followed by the frozen7x7 blur, so assuming strong accepted edges at L1 was
   unjustified. Summary: expected failed case only, seven assertions, one pose.
4. `run_green_v3`: only the numeric checker fixture changed to the fixed
   256x256/32-pixel-block signal proposed by the parent. No algorithm, threshold,
   mask semantics, collector or sampler rule changed for this repair. All five
   cases passed with191 assertions and three synthetic poses. Actual checker
   pools were L0=924/NMS4288 and L1=350/NMS494. The header's copied cross-layer
   crop body passed the complete frozen-source text gate.

The current native bridge/header and test source are byte-identical to the
successful run's captured source. The current evidence manifest separately pins
all historical runs and their source versions. Full real-pool training,
independent oracle acceptance, quality gates and performance measurement remain
separate parent experiment stages.
