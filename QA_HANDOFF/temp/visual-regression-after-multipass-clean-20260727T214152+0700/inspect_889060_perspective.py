import sys
import os
import json
import cv2
import numpy as np
from pathlib import Path

PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
DETECTOR_DIR = os.path.join(PROJECT_DIR, "jewelry_front_detector")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if DETECTOR_DIR not in sys.path:
    sys.path.insert(0, DETECTOR_DIR)

from jewelry_front_detector.image_processor import clean_final_object_crop

REGEN_DIR = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "visual-regression-after-multipass-clean-20260727T214152+0700" / "regenerated"

def main():
    img_path = REGEN_DIR / "889060 A_perspective_object.png"
    json_path = REGEN_DIR / "889060 A_perspective_result.json"

    print("=== INSPECTING 889060 A PERSPECTIVE ===")
    if not img_path.exists():
        print(f"File not found: {img_path}")
        return

    img = cv2.imread(str(img_path))
    cleaned_2nd, info_2nd = clean_final_object_crop(img, "PERSPECTIVE")

    print(f"2nd Pass info: {info_2nd}")
    print(f"Residual pixels total: {info_2nd['removed_total_pixels']}")

    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            vdata = json.load(f)
        print(f"Quality validation in JSON: {vdata.get('quality_validation')}")
        print(f"Clean object in JSON: {vdata.get('clean_object')}")

if __name__ == "__main__":
    main()
