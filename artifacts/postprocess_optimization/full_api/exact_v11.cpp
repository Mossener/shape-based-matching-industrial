#include "matcher.hpp"
// Literal frozen sources are bound by generated/SOURCE_RECEIPT.json. The
// separately reviewed build runner pins them before any compilation.
#define line2Dup postprocessExactV11Core
#define shape_based_matching postprocessExactV11Shape
#define Timer PostprocessExactV11Timer
#include "generated/baseline/line2Dup.cpp"
#include "fixture_bank_methods.inc"
#undef Timer
#undef shape_based_matching
#undef line2Dup
#define POSTPROCESS_CORE postprocessExactV11Core
#define POSTPROCESS_WRAPPER postprocess_exact_v11_api
#include "wrapper_methods.inc"
#undef POSTPROCESS_WRAPPER
#undef POSTPROCESS_CORE
