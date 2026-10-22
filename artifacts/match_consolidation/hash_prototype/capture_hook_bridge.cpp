#include "capture_hook.hpp"
// The adapter arms in a different translation unit from the core wrapper.
void bridge_consolidate(std::vector<hash_proto::Match>& matches) {
    capture_trace::consolidate(matches);
}
