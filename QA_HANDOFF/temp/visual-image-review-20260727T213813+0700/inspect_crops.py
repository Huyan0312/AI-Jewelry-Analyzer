import sys
import os
import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime

PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
KS_DIR = os.path.join(PROJECT_DIR, "Scale 3D", "KS")

samples = [
    "DF27.COMP017.12_DI_07072026",
    "889060 A",
    "889524-A"
]

views = ["front", "left", "back", "bottom", "perspective", "right", "top"]

def check_image(img_path, view_name):
    img = cv2.imread(img_path)
    if img is None:
        return {"exists": False}

    h, w = img.shape[:2]
    # Check top-left label region (first 15% height, 25% width)
    label_band = max(10, int(round(h * 0.15)))
    left_limit = max(10, int(round(w * 0.25)))

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    # Gray pixels (sat <= 30, val in 60..225)
    gray_mask = ((sat <= 35) & (val >= 50) & (val <= 230)).astype(np.uint8) * 255

    # Check top-left corner
    corner_gray = gray_mask[0:label_band, 0:left_limit]
    cnt_top_left_gray = cv2.countNonZero(corner_gray)

    # Check bottom-left corner for PERSPECTIVE
    bot_band = max(10, int(round(h * 0.15)))
    corner_bot_left_gray = gray_mask[h-bot_band:h, 0:left_limit]
    cnt_bot_left_gray = cv2.countNonZero(corner_bot_left_gray)

    # Red pixels count
    red_low = cv2.inRange(hsv, (0, 90, 90), (12, 255, 255))
    red_high = cv2.inRange(hsv, (165, 90, 90), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_low, red_high)
    cnt_red = cv2.countNonZero(red_mask)

    mtime = datetime.fromtimestamp(os.path.getmtime(img_path)).strftime('%Y-%m-%d %H:%M:%S')

    return {
        "exists": True,
        "size": f"{w}x{h}",
        "mtime": mtime,
        "top_left_gray_px": int(cnt_top_left_gray),
        "bot_left_gray_px": int(cnt_bot_left_gray),
        "red_px": int(cnt_red)
    }

def main():
    report = {}
    print("=== VISUAL INSPECTION OF 21 OBJECT CROPS IN Scale 3D/KS ===")

    for sample in samples:
        report[sample] = {}
        print(f"\n--- SAMPLE: {sample} ---")
        for v in views:
            fname = f"{sample}_{v}_object.png"
            fpath = os.path.join(KS_DIR, fname)
            info = check_image(fpath, v)
            report[sample][v] = info
            if info["exists"]:
                print(f"  [{v.upper()}] {fname} | size={info['size']} | mtime={info['mtime']} | top_left_gray={info['top_left_gray_px']}px | bot_left_gray={info['bot_left_gray_px']}px | red={info['red_px']}px")
            else:
                print(f"  [{v.upper()}] MISSING: {fname}")

    # Check JSON result file timestamps
    print("\n--- JSON RESULT FILES TIMESTAMPS ---")
    for sample in samples:
        json_file = os.path.join(KS_DIR, f"{sample}_all_views_result.json")
        if os.path.exists(json_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(json_file)).strftime('%Y-%m-%d %H:%M:%S')
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            has_clean_obj = "clean_object" in str(data)
            has_quality = "quality_validation" in str(data)
            print(f"  {sample}_all_views_result.json | mtime={mtime} | has_clean_obj={has_clean_obj} | has_quality={has_quality}")
        else:
            print(f"  MISSING: {sample}_all_views_result.json")

if __name__ == "__main__":
    main()
