import sys
import os
import json
from pathlib import Path

PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"
REGEN_DIR = Path(PROJECT_DIR) / "QA_HANDOFF" / "temp" / "final-visual-regression-gray-mask-20260727T214356+0700" / "regenerated"

samples = [
    "DF27.COMP017.12_DI_07072026",
    "889060 A",
    "889524-A"
]

def main():
    print("=== FINAL VERIFICATION OF ALL 21 REGENERATED VIEWS ===")
    total_valid = 0

    for sample in samples:
        json_file = REGEN_DIR / f"{sample}_all_views_result.json"
        print(f"\n--- {json_file.name} ---")
        if not json_file.exists():
            print(f"MISSING: {json_file.name}")
            continue

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        status = data.get("status")
        views = data.get("views", [])

        # Note: check if batch status is SUCCESS now that all 7 views in each sample pass!
        for v in views:
            vname = v.get("view_name", "UNKNOWN")
            q_valid = v.get("quality_valid")
            q_val = v.get("quality_validation", {})
            val_info = v.get("validation", {})
            v_ok = val_info.get("valid")

            if q_valid is True and v_ok is True:
                total_valid += 1
                print(f"  [{vname}] PASS quality_valid=True, valid=True | file={v.get('crop_file')}")
            else:
                print(f"  [{vname}] FAIL quality_valid={q_valid}, valid={v_ok} | failure_reasons={q_val.get('failure_reasons')}")

    print(f"\nTotal Valid Views: {total_valid} / 21")

if __name__ == "__main__":
    main()
