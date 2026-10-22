#pragma once
#include <string>
#include <vector>

// Implemented only inside exact_v11.cpp, using its existing private core.
// No third core translation unit or production adapter is linked.
namespace postprocess_fixture_banks {
struct Refinement {
    int template_id,level,width,height,border,required_width,required_height,max_x,max_y;
};
struct Bank {
    std::string yaml;
    int templates=0,padded_width=0,padded_height=0;
    std::vector<Refinement> refinements;
};
Bank led(const std::string& smd_path);
Bank zero();
Bank magnet(const std::string& smd_path);
}
