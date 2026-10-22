"""Pure source contract checks; no image, bank, SMD or native execution."""
from pathlib import Path
import json
import re

HERE = Path(__file__).resolve().parent


def main() -> None:
    policy = (HERE / "rgb_empty_mask_policy.hpp").read_text(encoding="utf-8")
    source = (HERE / "rgb_empty_mask_source_test.cpp").read_text(encoding="utf-8")
    protocol = json.loads((HERE / "PROTOCOL.json").read_text(encoding="utf-8"))
    assert "detector.addTemplate(warped_gray, class_id, cv::Mat())" in policy
    assert policy.count("detector.addTemplate") == 1
    assert "silhouette_source" not in policy
    assert "cv::Mat source" not in policy
    assert "saw_empty_mask" in source and "source == &gray" in source
    assert protocol["experiment"] == "A_rgb_grayscale_source_empty_feature_selection_mask"
    assert protocol["change_surface"]["third_addTemplate_argument"] == "cv::Mat()"
    assert protocol["training"]["attempts_total"] == 20736
    assert protocol["geometry_gate"]["required_width"] == 848
    assert protocol["geometry_gate"]["required_height"] == 832
    assert protocol["stages"][0]["native_calls"] == 0
    print("PASS static_contract image_decodes=0 matcher_calls=0")


if __name__ == "__main__":
    main()
