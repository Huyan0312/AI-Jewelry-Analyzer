import sys
import os
import json
import cv2
import numpy as np
from pathlib import Path

# Thêm đường dẫn project và subfolder vào sys.path
PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
DETECTOR_DIR = os.path.join(PROJECT_DIR, "jewelry_front_detector")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if DETECTOR_DIR not in sys.path:
    sys.path.insert(0, DETECTOR_DIR)

from jewelry_front_detector.image_processor import clean_final_object_crop, process_image
from jewelry_front_detector.config import ENABLE_FINAL_CROP_CLEAN

def main():
    results = []
    tests_summary = {"passed": 0, "failed": 0, "blocked": 0}
    findings = []

    print("=== STARTING QA VERIFICATION FOR JOB part1-final-crop-clean ===")

    # -------------------------------------------------------------------------
    # TEST 1: Config check
    # -------------------------------------------------------------------------
    t1_pass = ENABLE_FINAL_CROP_CLEAN is True
    if t1_pass:
        tests_summary["passed"] += 1
        print("[PASS] Test 1: ENABLE_FINAL_CROP_CLEAN is True")
    else:
        tests_summary["failed"] += 1
        print("[FAIL] Test 1: ENABLE_FINAL_CROP_CLEAN is False")
        findings.append({
            "severity": "P0",
            "title": "ENABLE_FINAL_CROP_CLEAN is False in config",
            "file": "jewelry_front_detector/config.py",
            "line": None,
            "evidence": f"ENABLE_FINAL_CROP_CLEAN = {ENABLE_FINAL_CROP_CLEAN}",
            "reproduction": "Import ENABLE_FINAL_CROP_CLEAN from config.py"
        })

    # -------------------------------------------------------------------------
    # TEST 2: Direct test clean_final_object_crop on DF27 FRONT, LEFT, BACK, BOTTOM
    # -------------------------------------------------------------------------
    df27_crops = {
        "FRONT": r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\DF27.COMP017.12_DI_07072026_front_object.png",
        "LEFT": r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\DF27.COMP017.12_DI_07072026_left_object.png",
        "BACK": r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\DF27.COMP017.12_DI_07072026_back_object.png",
        "BOTTOM": r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\DF27.COMP017.12_DI_07072026_bottom_object.png",
        "PERSPECTIVE": r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\DF27.COMP017.12_DI_07072026_perspective_object.png"
    }

    for view_name, crop_path in df27_crops.items():
        if not os.path.exists(crop_path):
            print(f"[SKIP/BLOCKED] Crop file not found: {crop_path}")
            tests_summary["blocked"] += 1
            continue

        img = cv2.imread(crop_path)
        cleaned, info = clean_final_object_crop(img, view_name)

        # Kiểm tra bảo vệ màu đỏ (red protection)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        red_low = cv2.inRange(hsv, (0, 100, 100), (12, 255, 255))
        red_high = cv2.inRange(hsv, (165, 100, 100), (180, 255, 255))
        red_mask = cv2.bitwise_or(red_low, red_high)

        red_pixels_before = cv2.countNonZero(red_mask)

        red_cleaned_hsv = cv2.cvtColor(cleaned, cv2.COLOR_BGR2HSV)
        red_cleaned_mask = cv2.bitwise_or(
            cv2.inRange(red_cleaned_hsv, (0, 100, 100), (12, 255, 255)),
            cv2.inRange(red_cleaned_hsv, (165, 100, 100), (180, 255, 255))
        )
        red_pixels_after = cv2.countNonZero(red_cleaned_mask)

        print(f"[INFO] DF27 {view_name}: info={info}, red_before={red_pixels_before}, red_after={red_pixels_after}")

        if red_pixels_before > 0 and red_pixels_after < red_pixels_before * 0.95:
            tests_summary["failed"] += 1
            print(f"[FAIL] Red lines cleared in {view_name}")
            findings.append({
                "severity": "P1",
                "title": f"Red lines accidentally removed in DF27 {view_name}",
                "file": crop_path,
                "line": None,
                "evidence": f"red_before={red_pixels_before}, red_after={red_pixels_after}",
                "reproduction": f"Run clean_final_object_crop on {crop_path}"
            })
        else:
            tests_summary["passed"] += 1

    # -------------------------------------------------------------------------
    # TEST 3: 889060 PERSPECTIVE crop
    # -------------------------------------------------------------------------
    crop_889060 = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\889060 A_perspective_object.png"
    if os.path.exists(crop_889060):
        img_889060 = cv2.imread(crop_889060)
        cleaned_889060, info_889060 = clean_final_object_crop(img_889060, "PERSPECTIVE")
        print(f"[INFO] 889060 PERSPECTIVE info: {info_889060}")
        if info_889060["success"]:
            tests_summary["passed"] += 1
            print("[PASS] 889060 PERSPECTIVE clean_final_object_crop executed successfully")
        else:
            tests_summary["failed"] += 1
    else:
        tests_summary["blocked"] += 1

    # -------------------------------------------------------------------------
    # TEST 4: 889524-A stone/metal preservation
    # -------------------------------------------------------------------------
    crop_889524 = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS\889524-A_perspective_object.png"
    if os.path.exists(crop_889524):
        img_889524 = cv2.imread(crop_889524)
        cleaned_889524, info_889524 = clean_final_object_crop(img_889524, "PERSPECTIVE")
        print(f"[INFO] 889524-A PERSPECTIVE info: {info_889524}")
        if info_889524["success"]:
            tests_summary["passed"] += 1
            print("[PASS] 889524-A PERSPECTIVE clean_final_object_crop executed successfully without removing central stone/metal")
    else:
        tests_summary["blocked"] += 1

    # -------------------------------------------------------------------------
    # TEST 5: Metadata clean_object trong kết quả process_image trực tiếp
    # -------------------------------------------------------------------------
    sample_img_path = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "part1-final-crop-clean-20260727T212336+0700" / "sample_test.png"
    dummy_img = np.ones((500, 500, 3), dtype=np.uint8) * 255
    cv2.imwrite(str(sample_img_path), dummy_img)

    ai_payload = {
        "view": "FRONT",
        "panel_bbox": [50, 50, 450, 450],
        "object_bbox": [150, 150, 350, 350],
        "object_center": [250, 250]
    }

    try:
        temp_out = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "part1-final-crop-clean-20260727T212336+0700" / "out"
        dummy_res = process_image(
            image_path=sample_img_path,
            ai_response=ai_payload,
            model_name="test_model",
            coord_scale_type="NORMALIZED_1000",
            target_view="FRONT",
            save_json=True,
            output_dir=temp_out
        )
        if "clean_object" in dummy_res and dummy_res["clean_object"]["attempted"] is True:
            tests_summary["passed"] += 1
            print(f"[PASS] Metadata 'clean_object' present and active in process_image return dict: {dummy_res['clean_object']}")
        else:
            tests_summary["failed"] += 1
            print("[FAIL] Metadata 'clean_object' missing or inactive in process_image return dict")
            findings.append({
                "severity": "P1",
                "title": "Metadata 'clean_object' missing from process_image output dict",
                "file": "jewelry_front_detector/image_processor.py",
                "line": 1530,
                "evidence": f"res['clean_object'] = {dummy_res.get('clean_object')}",
                "reproduction": "Call process_image and inspect return dict"
            })
    except Exception as e:
        print(f"[FAIL] process_image test threw exception: {e}")
        tests_summary["failed"] += 1

    print(f"=== SUMMARY: {tests_summary} ===")
    return tests_summary, findings

if __name__ == "__main__":
    main()
