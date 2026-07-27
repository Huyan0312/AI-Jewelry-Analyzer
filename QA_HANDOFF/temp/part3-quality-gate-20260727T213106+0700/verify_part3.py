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

from jewelry_front_detector.image_processor import validate_final_object_crop_quality, process_image
from jewelry_front_detector.result_contract import view_saved_ok, make_batch_view, build_all_views_result

def main():
    tests_summary = {"passed": 0, "failed": 0, "blocked": 0}
    findings = []

    print("=== STARTING QA VERIFICATION FOR JOB part3-quality-gate ===")

    temp_dir = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "part3-quality-gate-20260727T213106+0700"
    out_dir = temp_dir / "out"

    # -------------------------------------------------------------------------
    # TEST 1: View sạch hợp lệ -> quality_validation.valid = True
    # -------------------------------------------------------------------------
    crop_before = np.ones((200, 200, 3), dtype=np.uint8) * 255
    crop_before[50:150, 50:150] = [128, 128, 128] # Trang sức xám
    crop_after = crop_before.copy()

    clean_info = {"attempted": True, "success": True, "changed": False}
    q1 = validate_final_object_crop_quality(crop_before, crop_after, "FRONT", clean_info)
    print(f"[INFO] Test 1 Valid crop quality: {q1}")

    if q1.get("valid") is True and not q1.get("failure_reasons"):
        tests_summary["passed"] += 1
        print("[PASS] Test 1: Clean valid crop has quality_validation.valid = True")
    else:
        tests_summary["failed"] += 1
        print(f"[FAIL] Test 1: Clean valid crop failed quality check: {q1}")
        findings.append({
            "severity": "P0",
            "title": "Clean valid crop failed quality check unexpectedly",
            "file": "jewelry_front_detector/image_processor.py",
            "line": 1300,
            "evidence": f"q1 = {q1}",
            "reproduction": "Call validate_final_object_crop_quality on identical crops"
        })

    # -------------------------------------------------------------------------
    # TEST 2: Mất pixel màu đỏ vượt ngưỡng -> Quality Failure
    # -------------------------------------------------------------------------
    crop_before_red = np.ones((200, 200, 3), dtype=np.uint8) * 255
    # Vẽ đường đỏ BGR = (0, 0, 220)
    crop_before_red[50:60, 20:180] = [0, 0, 220]
    crop_after_red = crop_before_red.copy()
    # Xóa mất đường đỏ (chuyển thành màu nền 255)
    crop_after_red[50:60, 20:180] = [255, 255, 255]

    q2 = validate_final_object_crop_quality(crop_before_red, crop_after_red, "FRONT", clean_info)
    print(f"[INFO] Test 2 Red loss quality: {q2}")

    if q2.get("valid") is False and ("red_retained_ratio_below_threshold" in q2.get("failure_reasons") or "colored_or_red_pixels_modified" in q2.get("failure_reasons")):
        tests_summary["passed"] += 1
        print("[PASS] Test 2: Red pixel loss triggered quality failure correctly")
    else:
        tests_summary["failed"] += 1
        print(f"[FAIL] Test 2: Red pixel loss failed to trigger quality failure. q2={q2}")
        findings.append({
            "severity": "P0",
            "title": "Red pixel loss failed to trigger quality failure",
            "file": "jewelry_front_detector/image_processor.py",
            "line": 1300,
            "evidence": f"q2 = {q2}",
            "reproduction": "Call validate_final_object_crop_quality after removing red pixels"
        })

    # -------------------------------------------------------------------------
    # TEST 3: Xóa nhầm pixel màu kim loại/trang sức -> Quality Failure
    # -------------------------------------------------------------------------
    crop_before_colored = np.ones((200, 200, 3), dtype=np.uint8) * 255
    # Pixel màu kim loại vàng/đồng BGR = (50, 150, 200)
    crop_before_colored[80:120, 80:120] = [50, 150, 200]
    crop_after_colored = crop_before_colored.copy()
    # Xóa nhầm thành màu nền 255
    crop_after_colored[80:120, 80:120] = [255, 255, 255]

    q3 = validate_final_object_crop_quality(crop_before_colored, crop_after_colored, "FRONT", clean_info)
    print(f"[INFO] Test 3 Colored metal loss quality: {q3}")

    if q3.get("valid") is False and "colored_or_red_pixels_modified" in q3.get("failure_reasons"):
        tests_summary["passed"] += 1
        print("[PASS] Test 3: Modified colored jewelry pixels triggered quality failure correctly")
    else:
        tests_summary["failed"] += 1
        print(f"[FAIL] Test 3: Colored jewelry pixel loss failed to trigger quality failure. q3={q3}")
        findings.append({
            "severity": "P0",
            "title": "Colored jewelry pixel loss failed to trigger quality failure",
            "file": "jewelry_front_detector/image_processor.py",
            "line": 1300,
            "evidence": f"q3 = {q3}",
            "reproduction": "Call validate_final_object_crop_quality after modifying colored pixels"
        })

    # -------------------------------------------------------------------------
    # TEST 4: Chống SUCCESS giả trong view_saved_ok và batch result
    # -------------------------------------------------------------------------
    mock_result_failed_quality = {
        "validation": {
            "valid": True,          # Giả sử các bước trước valid=True
            "quality_valid": False, # Nhưng quality gate phát hiện lỗi
            "object_crop_valid": True
        },
        "output_files": {
            "object_image": str(temp_dir / "mock_crop.png")
        },
        "quality_validation": {
            "valid": False,
            "failure_reasons": ["colored_or_red_pixels_modified"]
        }
    }

    # Tạo file mock_crop.png giả lập
    mock_file = temp_dir / "mock_crop.png"
    with open(mock_file, "w") as f:
        f.write("mock")

    is_ok = view_saved_ok(mock_result_failed_quality)
    print(f"[INFO] Test 4 view_saved_ok for quality_valid=False: {is_ok}")

    if is_ok is False:
        tests_summary["passed"] += 1
        print("[PASS] Test 4: view_saved_ok correctly returned False when quality_valid=False (Anti-fake SUCCESS)")
    else:
        tests_summary["failed"] += 1
        print("[FAIL] Test 4: view_saved_ok allowed SUCCESS when quality_valid=False!")
        findings.append({
            "severity": "P0",
            "title": "view_saved_ok allowed SUCCESS when quality_valid=False",
            "file": "jewelry_front_detector/result_contract.py",
            "line": 29,
            "evidence": f"view_saved_ok returned {is_ok}",
            "reproduction": "Call view_saved_ok with quality_valid=False"
        })

    # -------------------------------------------------------------------------
    # TEST 5: Batch result chứa quality_valid và quality_validation
    # -------------------------------------------------------------------------
    batch_view = make_batch_view(mock_result_failed_quality)
    print(f"[INFO] Test 5 make_batch_view output: {batch_view}")

    if "quality_valid" in batch_view and "quality_validation" in batch_view and batch_view["quality_valid"] is False:
        tests_summary["passed"] += 1
        print("[PASS] Test 5: make_batch_view correctly included quality_valid=False and quality_validation dict")
    else:
        tests_summary["failed"] += 1
        print(f"[FAIL] Test 5: make_batch_view missing quality keys or wrong values. batch_view={batch_view}")
        findings.append({
            "severity": "P1",
            "title": "make_batch_view missing quality_valid or quality_validation",
            "file": "jewelry_front_detector/result_contract.py",
            "line": 110,
            "evidence": f"batch_view = {batch_view}",
            "reproduction": "Call make_batch_view on result dict"
        })

    print(f"=== SUMMARY: {tests_summary} ===")
    return tests_summary, findings

if __name__ == "__main__":
    main()
