// Metadata-only test: no image decode, detector construction, or matching.
#define main tless_adapter_main_not_called
#include "tless_eval.cpp"
#undef main

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("Expected metadata-only schema2 dataset root");
        const fs::path root = fs::absolute(argv[1]);
        const auto development = readFrames(root, false, "development", {1});
        const auto heldout = readFrames(root, false, "heldout", {1});
        const auto training = readFrames(root, true, "", {1});
        const std::set<int> expectedDevelopment{1, 4, 6, 7, 8, 10, 12, 13};
        const std::set<int> expectedHeldout{11, 14, 15, 16, 17, 18, 19, 20};
        std::set<int> developmentScenes, heldoutScenes;
        for (const auto& frame : development) {
            if (frame.split != "development") throw std::runtime_error("Development split contamination");
            developmentScenes.insert(frame.scene);
        }
        for (const auto& frame : heldout) {
            if (frame.split != "heldout_scene") throw std::runtime_error("Schema2 heldout alias is wrong");
            if (fs::exists(root / frame.rgb)) throw std::runtime_error("Guard expects missing heldout RGB paths");
            heldoutScenes.insert(frame.scene);
        }
        if (developmentScenes != expectedDevelopment || heldoutScenes != expectedHeldout)
            throw std::runtime_error("Unexpected scene partitions");
        if (development.size() != 400 || heldout.size() != 400 || training.size() != 72)
            throw std::runtime_error("Unexpected metadata split sizes");
        std::cout << "PASS schema2 heldout alias: 400 development / 400 heldout / 72 object1 training; no RGB opened\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
