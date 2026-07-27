import sys
import os
import json
from pathlib import Path

PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
REGEN_DIR = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "regenerate-and-visual-review-20260727T213929+0700" / "regenerated"

samples = [
    "DF27.COMP017.12_DI_07072026",
    "889060 A",
    "889524-A"
]

views = ["front", "left", "back", "bottom", "perspective", "right", "top"]

def main():
    print("=== CHECKING INDIVIDUAL VIEW JSONS FOR QUALITY VALIDATION ===")
    all_quality_passed = True
    total_views = 0

    for sample in samples:
        print(f"\n--- {sample} ---")
        for v in views:
            total_views += 1
            vjson = REGEN_DIR / f"{sample}_{v}_result.json"
            if not vjson.exists():
                print(f"  [{v.upper()}] MISSING JSON: {vjson.name}")
                all_quality_passed = False
                continue

            with open(vjson, "r", encoding="utf-8") as f:
                data = json.load(f)

            q_val = data.get("quality_validation", {})
            q_valid = q_val.get("valid")
            clean_info = data.get("clean_object", {})
            red_exp = data.get("red_annotation_expansion", {})

            if q_valid is True:
                print(f"  [{v.upper()}] PASS quality_valid=True | clean_changed={clean_info.get('changed')} | red_exp={red_exp.get('expanded')}")
            else:
                all_quality_passed = False
                print(f"  [{v.upper()}] FAIL quality_valid={q_valid} | failure_reasons={q_val.get('failure_reasons')}")

    print(f"\nTotal Views Checked: {total_views} | All Quality Passed: {all_quality_passed}")

if __name__ == "__main__":
    main()
