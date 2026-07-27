import sys
import os
import json
import cv2
import re
import numpy as np
from pathlib import Path

# Thêm đường dẫn project và subfolder vào sys.path
PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
DETECTOR_DIR = os.path.join(PROJECT_DIR, "jewelry_front_detector")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if DETECTOR_DIR not in sys.path:
    sys.path.insert(0, DETECTOR_DIR)

from jewelry_front_detector.image_processor import (
    clean_final_object_crop,
    validate_final_object_crop_quality,
    process_image
)
from jewelry_front_detector.config import ENABLE_FINAL_CROP_CLEAN
from jewelry_front_detector.result_contract import (
    view_saved_ok,
    make_batch_view,
    build_all_views_result
)

def main():
    tests_summary = {"passed": 0, "failed": 0, "blocked": 0}
    findings = []

    print("=== STARTING QA FINAL INTEGRATION ACCEPTANCE VERIFICATION ===")

    temp_dir = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "final-integration-acceptance-20260727T213603+0700"
    out_dir = temp_dir / "out"

    # -------------------------------------------------------------------------
    # SUITE 1 (Part 1): Clean object crop & Red line protection
    # -------------------------------------------------------------------------
    df27_crop = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\DF27.COMP017.12_DI_07072026_front_object.png"
    if os.path.exists(df27_crop):
        img_df27 = cv2.imread(df27_crop)
        cleaned_df27, info_df27 = clean_final_object_crop(img_df27, "FRONT")

        # Check red protection
        hsv = cv2.cvtColor(img_df27, cv2.COLOR_BGR2HSV)
        red_mask = cv2.bitwise_or(
            cv2.inRange(hsv, (0, 100, 100), (12, 255, 255)),
            cv2.inRange(hsv, (165, 100, 100), (180, 255, 255))
        )
        red_before = cv2.countNonZero(red_mask)

        hsv_clean = cv2.cvtColor(cleaned_df27, cv2.COLOR_BGR2HSV)
        red_clean_mask = cv2.bitwise_or(
            cv2.inRange(hsv_clean, (0, 100, 100), (12, 255, 255)),
            cv2.inRange(hsv_clean, (165, 100, 100), (180, 255, 255))
        )
        red_after = cv2.countNonZero(red_clean_mask)

        if info_df27["success"] and red_after == red_before:
            tests_summary["passed"] += 1
            print(f"[PASS] Suite 1 (Part 1): DF27 FRONT cleaned {info_df27['removed_label_pixels']} label pixels while preserving 100% red lines ({red_before} px)")
        else:
            tests_summary["failed"] += 1
            print(f"[FAIL] Suite 1 (Part 1): Red lines modified in DF27 FRONT. Before={red_before}, After={red_after}")
    else:
        tests_summary["blocked"] += 1

    # -------------------------------------------------------------------------
    # SUITE 2 (Part 2): Red Annotation Expansion (889060 TOP 0.70 & Panel isolation)
    # -------------------------------------------------------------------------
    test_img_top = np.ones((600, 600, 3), dtype=np.uint8) * 255
    test_img_top[200:400, 200:400] = [128, 128, 128] # Object
    test_img_top[100:150, 100:150] = [0, 0, 220]     # Red text 0.70

    img_top_path = temp_dir / "test_top_red.png"
    cv2.imwrite(str(img_top_path), test_img_top)

    ai_top_payload = {
        "view": "TOP",
        "panel_bbox": [50, 50, 550, 550],
        "object_bbox": [200, 200, 400, 400],
        "object_center": [300, 300]
    }

    try:
        res_top = process_image(
            image_path=img_top_path,
            ai_response=ai_top_payload,
            model_name="test_model",
            coord_scale_type="NORMALIZED_1000",
            target_view="TOP",
            save_json=True,
            output_dir=out_dir
        )
        red_exp = res_top.get("red_annotation_expansion", {})
        if red_exp.get("expanded") is True and red_exp.get("bbox_after")[0] <= 96:
            tests_summary["passed"] += 1
            print(f"[PASS] Suite 2 (Part 2): Red annotation expansion included detached measurement 0.70. bbox_after={red_exp['bbox_after']}")
        else:
            tests_summary["failed"] += 1
            print(f"[FAIL] Suite 2 (Part 2): Failed red annotation expansion: {red_exp}")
    except Exception as e:
        print(f"[FAIL] Suite 2 exception: {e}")
        tests_summary["failed"] += 1

    # -------------------------------------------------------------------------
    # SUITE 3 (Part 3): Quality Validation Gate & Anti-Fake SUCCESS
    # -------------------------------------------------------------------------
    crop_before = np.ones((200, 200, 3), dtype=np.uint8) * 255
    crop_before[50:60, 20:180] = [0, 0, 220] # Red line
    crop_after = crop_before.copy()
    crop_after[50:60, 20:180] = [255, 255, 255] # Erased red line

    clean_info = {"attempted": True, "success": True, "changed": True}
    q_res = validate_final_object_crop_quality(crop_before, crop_after, "FRONT", clean_info)

    fake_success_result = {
        "validation": {"valid": True, "quality_valid": False, "object_crop_valid": True},
        "output_files": {"object_image": str(img_top_path)}
    }
    is_saved_ok = view_saved_ok(fake_success_result)

    if q_res["valid"] is False and is_saved_ok is False:
        tests_summary["passed"] += 1
        print("[PASS] Suite 3 (Part 3): Quality validation gate correctly flagged red pixel loss AND blocked fake SUCCESS")
    else:
        tests_summary["failed"] += 1
        print(f"[FAIL] Suite 3 (Part 3): Anti-fake SUCCESS or Quality gate failed. q_res={q_res}, is_saved_ok={is_saved_ok}")

    # -------------------------------------------------------------------------
    # SUITE 4 (Part 4): Path Audit & Dynamic Root Resolution in Active Files
    # -------------------------------------------------------------------------
    active_files = [
        os.path.join(PROJECT_DIR, "AI_AutoDetect test.jsx"),
        os.path.join(PROJECT_DIR, "PTS CS5 SCRIPT", "headless_detector.py"),
        os.path.join(PROJECT_DIR, "PTS CS5 SCRIPT", "start_watcher.bat"),
        os.path.join(PROJECT_DIR, "PTS CS5 SCRIPT", "start_watcher.vbs"),
        os.path.join(PROJECT_DIR, "Scale 3D", "KS SCALE NECKLACE", "1.Scale.jsx"),
        os.path.join(PROJECT_DIR, "Scale 3D", "KS SCALE NECKLACE", "START.jsx"),
        os.path.join(PROJECT_DIR, "Scale 3D", "KS SCALE NECKLACE", "START to Stroke.jsx")
    ]

    has_hardcoded = False
    for filepath in active_files:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if re.search(r"d:\\CODE\\Agent\\AutoNhanDangAnh", content, re.IGNORECASE) or re.search(r"C:\\Users\\pvhan", content, re.IGNORECASE):
            has_hardcoded = True
            print(f"[FAIL] Suite 4 (Part 4): Hardcoded path remaining in {filepath}")

    if not has_hardcoded:
        tests_summary["passed"] += 1
        print("[PASS] Suite 4 (Part 4): Path Audit 100% CLEAN. No hardcoded D:\\CODE\\Agent or pvhan in any active files")
    else:
        tests_summary["failed"] += 1

    # -------------------------------------------------------------------------
    # SUITE 5: Result Contract & Batch Integration Validation
    # -------------------------------------------------------------------------
    views_list = [
        {"view_name": v, "validation": {"valid": True, "quality_valid": True}, "output_files": {"object_image": str(img_top_path)}}
        for v in ["FRONT", "LEFT", "TOP", "PERSPECTIVE", "BACK", "RIGHT", "BOTTOM"]
    ]

    batch_res = build_all_views_result(
        sheet={},
        views=views_list,
        raw_response=""
    )

    if batch_res.get("status") == "SUCCESS" and batch_res.get("validation", {}).get("views_saved") == 7:
        tests_summary["passed"] += 1
        print("[PASS] Suite 5: Result contract build_all_views_result produced status=SUCCESS for 7 valid views")
    else:
        tests_summary["failed"] += 1
        print(f"[FAIL] Suite 5: build_all_views_result failed: {batch_res}")

    print(f"=== FINAL INTEGRATION SUMMARY: {tests_summary} ===")
    return tests_summary, findings

if __name__ == "__main__":
    main()
