import sys
import os
import json
import cv2
import numpy as np
from pathlib import Path

# Path configuration
PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
DETECTOR_DIR = os.path.join(PROJECT_DIR, "jewelry_front_detector")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if DETECTOR_DIR not in sys.path:
    sys.path.insert(0, DETECTOR_DIR)

from jewelry_front_detector.image_processor import process_image
from jewelry_front_detector.result_contract import build_all_views_result, make_batch_view

REGEN_DIR = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "final-visual-regression-gray-mask-20260727T214356+0700" / "regenerated"

samples = [
    ("DF27.COMP017.12_DI_07072026.jpg", "DF27.COMP017.12_DI_07072026_all_views_result.json"),
    ("889060 A.jpg", "889060 A_all_views_result.json"),
    ("889524-A.jpg", "889524-A_all_views_result.json")
]

def main():
    print("=== REGENERATING 21 VIEWS FOR FINAL GRAY MASK REGRESSION REVIEW ===")
    REGEN_DIR.mkdir(parents=True, exist_ok=True)

    batch_summary = {}

    for img_name, json_name in samples:
        img_path = Path(PROJECT_DIR) / "Scale 3D" / "KS" / img_name
        json_path = Path(PROJECT_DIR) / "Scale 3D" / "KS" / json_name

        print(f"\nProcessing {img_name}...")
        if not img_path.exists() or not json_path.exists():
            print(f"ERROR: Missing file {img_path} or {json_path}")
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_resp = json.loads(data["raw_response"])
        views_payload = raw_resp["views"]
        sheet_info = {
            "drawing_number": raw_resp.get("drawing_number"),
            "metal": raw_resp.get("metal"),
            "brand": raw_resp.get("brand"),
            "metal_weight": raw_resp.get("metal_weight"),
            "coordinate_scale": raw_resp.get("coordinate_scale", 1000)
        }

        generated_views = []
        for view_item in views_payload:
            view_name = view_item["view"].upper()
            res = process_image(
                image_path=img_path,
                ai_response=view_item,
                model_name="qwen/qwen3-vl-4b-instruct",
                coord_scale_type="NORMALIZED_1000",
                target_view=view_name,
                save_json=True,
                output_dir=REGEN_DIR
            )
            res["target_view"] = view_name
            batch_v = make_batch_view(res)
            batch_v["view_name"] = view_name
            batch_v["view"] = view_name
            generated_views.append(batch_v)
            clean_info = res.get("clean_object", {})
            q_val = res.get("quality_validation", {})
            print(f"  [{view_name}] processed -> quality_valid={q_val.get('valid')} | passes_run={clean_info.get('passes_run')} | residual_artifacts={q_val.get('residual_artifact_pixels')}")

        all_res = build_all_views_result(
            sheet=sheet_info,
            views=generated_views,
            raw_response=data["raw_response"]
        )

        out_json_path = REGEN_DIR / f"{img_path.stem}_all_views_result.json"
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(all_res, f, ensure_ascii=False, indent=2)

        print(f"Saved batch JSON: {out_json_path} (status={all_res['status']})")
        batch_summary[img_name] = all_res['status']

    print(f"\n=== REGENERATION COMPLETE. SUMMARY: {batch_summary} ===")

if __name__ == "__main__":
    main()
