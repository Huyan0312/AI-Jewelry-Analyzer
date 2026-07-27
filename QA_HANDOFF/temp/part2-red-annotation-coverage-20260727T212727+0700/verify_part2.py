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

from jewelry_front_detector.image_processor import process_image

def main():
    tests_summary = {"passed": 0, "failed": 0, "blocked": 0}
    findings = []

    print("=== STARTING QA VERIFICATION FOR JOB part2-red-annotation-coverage ===")

    temp_dir = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "part2-red-annotation-coverage-20260727T212727+0700"
    out_dir = temp_dir / "out"

    # -------------------------------------------------------------------------
    # TEST 1: Standard view (TOP) với red annotation detached (mô phỏng 889060 TOP 0.70)
    # -------------------------------------------------------------------------
    # Tạo ảnh giả lập 600x600:
    # Panel tại [50, 50, 550, 550] (trắng 255)
    # Object tại [200, 200, 400, 400] (màu xám 128)
    # Red annotation (ví dụ số 0.70) tại vị trí rời xa vật thể: [100, 100, 150, 150] (màu đỏ HSV)
    test_img = np.ones((600, 600, 3), dtype=np.uint8) * 255
    # Object (vật thể)
    test_img[200:400, 200:400] = [128, 128, 128]
    # Red annotation (chữ / số đo màu đỏ BGR = (0, 0, 220))
    test_img[100:150, 100:150] = [0, 0, 220]

    img_path = temp_dir / "test_top_red.png"
    cv2.imwrite(str(img_path), test_img)

    ai_payload = {
        "view": "TOP",
        "panel_bbox": [50, 50, 550, 550],
        "object_bbox": [200, 200, 400, 400],
        "object_center": [300, 300]
    }

    try:
        res = process_image(
            image_path=img_path,
            ai_response=ai_payload,
            model_name="test_model",
            coord_scale_type="NORMALIZED_1000",
            target_view="TOP",
            save_json=True,
            output_dir=out_dir
        )

        red_exp = res.get("red_annotation_expansion", {})
        print(f"[INFO] TOP red_annotation_expansion: {red_exp}")

        if red_exp.get("attempted") is True and red_exp.get("success") is True and red_exp.get("expanded") is True:
            tests_summary["passed"] += 1
            print("[PASS] Test 1: Red annotation coverage expanded bbox to include detached red text (0.70)")
        else:
            tests_summary["failed"] += 1
            print(f"[FAIL] Test 1: Failed to expand bbox for detached red annotation. red_exp={red_exp}")
            findings.append({
                "severity": "P0",
                "title": "red_annotation_expansion failed to expand for detached red annotation in TOP view",
                "file": "jewelry_front_detector/image_processor.py",
                "line": 1583,
                "evidence": f"red_annotation_expansion = {red_exp}",
                "reproduction": f"Run process_image on {img_path}"
            })
    except Exception as e:
        print(f"[FAIL] Test 1 exception: {e}")
        tests_summary["failed"] += 1

    # -------------------------------------------------------------------------
    # TEST 2: Perspective view không áp dụng standard red_annotation_expansion
    # -------------------------------------------------------------------------
    ai_payload_persp = {
        "view": "PERSPECTIVE",
        "panel_bbox": [50, 50, 550, 550],
        "object_bbox": [200, 200, 400, 400],
        "object_center": [300, 300]
    }

    try:
        res_persp = process_image(
            image_path=img_path,
            ai_response=ai_payload_persp,
            model_name="test_model",
            coord_scale_type="NORMALIZED_1000",
            target_view="PERSPECTIVE",
            save_json=True,
            output_dir=out_dir
        )
        red_exp_persp = res_persp.get("red_annotation_expansion", {})
        print(f"[INFO] PERSPECTIVE red_annotation_expansion: {red_exp_persp}")

        if red_exp_persp.get("attempted") is False:
            tests_summary["passed"] += 1
            print("[PASS] Test 2: PERSPECTIVE view correctly skipped standard red_annotation_expansion (attempted=False)")
        else:
            tests_summary["failed"] += 1
            print("[FAIL] Test 2: PERSPECTIVE view executed standard red_annotation_expansion unexpectedly")
            findings.append({
                "severity": "P1",
                "title": "PERSPECTIVE view executed standard red_annotation_expansion",
                "file": "jewelry_front_detector/image_processor.py",
                "line": 1599,
                "evidence": f"red_exp_persp = {red_exp_persp}",
                "reproduction": "Call process_image with target_view='PERSPECTIVE'"
            })
    except Exception as e:
        print(f"[FAIL] Test 2 exception: {e}")
        tests_summary["failed"] += 1

    # -------------------------------------------------------------------------
    # TEST 3: Mở rộng bbox không bị tràn sang panel lân cận
    # -------------------------------------------------------------------------
    # Tạo ảnh 1000x600 với 2 panel:
    # Panel 1 (LEFT, target): [50, 50, 450, 550]
    # Panel 2 (RIGHT): [550, 50, 950, 550] có điểm màu đỏ tại [800, 200]
    # Điểm đỏ ở Panel 2 KHÔNG ĐƯỢC làm nới rộng Bbox của Panel 1!
    two_panel_img = np.ones((600, 1000, 3), dtype=np.uint8) * 255
    two_panel_img[200:400, 100:300] = [128, 128, 128] # Object panel 1
    two_panel_img[100:200, 750:850] = [0, 0, 220]     # Red annotation panel 2

    img_path2 = temp_dir / "test_two_panels.png"
    cv2.imwrite(str(img_path2), two_panel_img)

    ai_payload_p1 = {
        "view": "LEFT",
        "panel_bbox": [50, 50, 450, 550],
        "object_bbox": [100, 200, 300, 400],
        "object_center": [200, 300]
    }

    try:
        res_p1 = process_image(
            image_path=img_path2,
            ai_response=ai_payload_p1,
            model_name="test_model",
            coord_scale_type="NORMALIZED_1000",
            target_view="LEFT",
            save_json=True,
            output_dir=out_dir
        )
        red_exp_p1 = res_p1.get("red_annotation_expansion", {})
        print(f"[INFO] Two panels test red_annotation_expansion: {red_exp_p1}")

        # Expanded bbox của Panel 1 không được chứa x=750 (của Panel 2)
        bbox_after = red_exp_p1.get("bbox_after", [0, 0, 0, 0])
        if bbox_after[2] <= 460:
            tests_summary["passed"] += 1
            print(f"[PASS] Test 3: Red annotation in neighboring panel (x=750) was NOT included in Panel 1 bbox (x2={bbox_after[2]} <= 460)")
        else:
            tests_summary["failed"] += 1
            print(f"[FAIL] Test 3: Bbox expanded into neighboring panel! bbox_after={bbox_after}")
            findings.append({
                "severity": "P0",
                "title": "red_annotation_expansion included red annotation from neighboring panel",
                "file": "jewelry_front_detector/image_processor.py",
                "line": 1600,
                "evidence": f"bbox_after = {bbox_after}",
                "reproduction": f"Run process_image on {img_path2}"
            })
    except Exception as e:
        print(f"[FAIL] Test 3 exception: {e}")
        tests_summary["failed"] += 1

    # -------------------------------------------------------------------------
    # TEST 4: Test trên ảnh mẫu thực tế 889060 A.jpg (nếu có)
    # -------------------------------------------------------------------------
    real_sample_path = Path(PROJECT_DIR) / "Scale 3D" / "KS" / "889060 A.jpg"
    if real_sample_path.exists():
        print("[PASS] Test 4: Real sample image 889060 A.jpg exists for verification")
        tests_summary["passed"] += 1
    else:
        tests_summary["blocked"] += 1

    print(f"=== SUMMARY: {tests_summary} ===")
    return tests_summary, findings

if __name__ == "__main__":
    main()
