#include "matcher.hpp"
// generated/candidate/ is the literal V11 copy with one helper include and one
// consolidation-call replacement, bound by generated/SOURCE_RECEIPT.json.
#define line2Dup postprocessHashV11Core
#define shape_based_matching postprocessHashV11Shape
#define Timer PostprocessHashV11Timer
#include "generated/candidate/line2Dup.cpp"
#undef Timer
#undef shape_based_matching
#undef line2Dup
#define POSTPROCESS_CORE postprocessHashV11Core
#define POSTPROCESS_WRAPPER postprocess_hash_v11_api
#include "wrapper_methods.inc"
#undef POSTPROCESS_WRAPPER
#undef POSTPROCESS_CORE
