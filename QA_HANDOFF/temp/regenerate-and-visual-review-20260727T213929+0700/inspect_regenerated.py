import sys
import os
import json
import cv2
import numpy as np
from pathlib import Path

PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
REGEN_DIR = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "regenerate-and-visual-review-20260727T213929+0700" / "regenerated"

samples = [
    "DF27.COMP017.12_DI_07072026",
    "889060 A",
    "889524-A"
]

views = ["front", "left", "back", "bottom", "perspective", "right", "top"]

def check_image(img_path, view_name):
    img = cv2.imread(str(img_path))
    if img is None:
        return {"exists": False}

    h, w = img.shape[:2]

    # Gray pixels (sat <= 35, val in 50..230)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    gray_mask = ((sat <= 35) & (val >= 50) & (val <= 230)).astype(np.uint8) * 255

    # Check top-left corner
    label_band = max(10, int(round(h * 0.15)))
    left_limit = max(10, int(round(w * 0.25)))
    corner_gray = gray_mask[0:label_band, 0:left_limit]
    top_left_gray = int(cv2.countNonZero(corner_gray))

    # Check bottom-left corner (PERSPECTIVE)
    bot_band = max(10, int(round(h * 0.15)))
    corner_bot_gray = gray_mask[h-bot_band:h, 0:left_limit]
    bot_left_gray = int(cv2.countNonZero(corner_bot_gray))

    # Red pixels count
    red_low = cv2.inRange(hsv, (0, 90, 90), (12, 255, 255))
    red_high = cv2.inRange(hsv, (165, 90, 90), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_low, red_high)
    red_px = int(cv2.countNonZero(red_mask))

    return {
        "exists": True,
        "size": f"{w}x{h}",
        "top_left_gray_px": top_left_gray,
        "bot_left_gray_px": bot_left_gray,
        "red_px": red_px
    }

def main():
    print("=== VISUAL & QUALITY INSPECTION OF 21 REGENERATED OBJECT CROPS ===")
    results_summary = {}

    for sample in samples:
        print(f"\n--- SAMPLE: {sample} ---")
        results_summary[sample] = {}

        for v in views:
            fname = f"{sample}_{v}_object.png"
            fpath = REGEN_DIR / fname
            info = check_image(fpath, v)

            # Check view json
            vjson_path = REGEN_DIR / f"{sample}_{v}_result.json"
            q_valid = None
            clean_info = None
            red_exp = None
            if vjson_path.exists():
                with open(vjson_path, "r", encoding="utf-8") as f:
                    vdata = json.load(f)
                q_valid = vdata.get("validation", {}).get("quality_valid")
                clean_info = vdata.get("clean_object")
                red_exp = vdata.get("red_annotation_expansion")

            results_summary[sample][v] = {
                "info": info,
                "quality_valid": q_valid,
                "clean_info": clean_info,
                "red_exp": red_exp
            }

            print(f"  [{v.upper()}] size={info.get('size')} | top_left_gray={info.get('top_left_gray_px')}px | bot_left_gray={info.get('bot_left_gray_px')}px | red={info.get('red_px')}px | quality_valid={q_valid}")
            if clean_info:
                print(f"       clean_object: removed_label={clean_info.get('removed_label_pixels')}, removed_grid={clean_info.get('removed_grid_pixels')}, protected_red={clean_info.get('protected_red_pixels')}")
            if red_exp and red_exp.get("attempted"):
                print(f"       red_exp: expanded={red_exp.get('expanded')}, bbox_after={red_exp.get('bbox_after')}")

if __name__ == "__main__":
    main()
