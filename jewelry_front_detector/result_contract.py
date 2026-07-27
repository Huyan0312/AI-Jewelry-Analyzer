"""Contract kết quả dùng chung cho GUI, batch và test."""

import json
from pathlib import Path
from typing import Iterable, Optional


EXPECTED_VIEWS = (
    "FRONT",
    "LEFT",
    "RIGHT",
    "TOP",
    "BOTTOM",
    "BACK",
    "PERSPECTIVE",
)


def nonempty_file(path_value) -> bool:
    if not path_value:
        return False
    try:
        path = Path(path_value)
        return path.is_file() and path.stat().st_size > 0
    except (OSError, TypeError, ValueError):
        return False


def view_saved_ok(result: dict) -> bool:
    validation = result.get("validation", {})
    crop_file = result.get("output_files", {}).get("object_image")
    return bool(validation.get("valid", False) and nonempty_file(crop_file))


def build_all_views_result(
    *,
    sheet: Optional[dict],
    views: Iterable[dict],
    raw_response: str = "",
) -> dict:
    view_results = list(views)
    names = [str(item.get("view_name") or item.get("view") or "UNKNOWN").upper() for item in view_results]
    expected = set(EXPECTED_VIEWS)
    received_expected = {name for name in names if name in expected}
    duplicates = sorted({name for name in names if names.count(name) > 1})
    unknown = sorted({name for name in names if name not in expected})
    missing = sorted(expected - received_expected)
    failed_views = [
        names[index]
        for index, item in enumerate(view_results)
        if not view_saved_ok(item)
    ]
    saved = sum(1 for item in view_results if view_saved_ok(item))

    success = (
        not missing
        and not duplicates
        and not unknown
        and len(view_results) == len(EXPECTED_VIEWS)
        and saved == len(EXPECTED_VIEWS)
    )
    status = "SUCCESS" if success else "PARTIAL" if saved > 0 else "FAILED"
    validation = {
        "valid": success,
        "views_expected": len(EXPECTED_VIEWS),
        "views_received": len(received_expected),
        "views_saved": saved,
        "missing_views": missing,
        "duplicate_views": duplicates,
        "unknown_views": unknown,
        "failed_views": failed_views,
    }
    return {
        "status": status,
        "sheet": dict(sheet or {}),
        "views": view_results,
        "validation": validation,
        "raw_response": raw_response,
        "output_files": {},
    }


def save_json_with_self_path(payload: dict, path: Path, key: str = "json") -> bool:
    path = Path(path)
    output_files = payload.setdefault("output_files", {})
    output_files[key] = str(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        if not nonempty_file(path):
            raise OSError("JSON file không tồn tại hoặc rỗng sau khi ghi")
        return True
    except (OSError, TypeError, ValueError):
        output_files.pop(key, None)
        return False


def make_batch_view(result: dict) -> dict:
    pixel = result.get("pixel", {})
    opencv = result.get("opencv", {})
    object_meta = opencv.get("object_meta", {})
    bbox = pixel.get("refined_object_bbox") or pixel.get("ai_object_bbox") or []
    crop_size = []
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        crop_size = [max(0, int(bbox[2] - bbox[0])), max(0, int(bbox[3] - bbox[1]))]
    return {
        "view": str(result.get("view_name") or "UNKNOWN").upper(),
        "ai_bbox": pixel.get("ai_object_bbox", []),
        "final_bbox": bbox,
        "refine_success": bool(opencv.get("object_refine_success", False)),
        "fallback_reason": object_meta.get("fallback_reason"),
        "crop_size": crop_size,
        "crop_file": result.get("output_files", {}).get("object_image"),
        "validation": result.get("validation", {}),
    }


def make_batch_entry(image_name: str, all_views: dict, time_sec: float, image_size=None) -> dict:
    validation = dict(all_views.get("validation", {}))
    return {
        "image": image_name,
        "status": all_views.get("status", "FAILED"),
        "sheet": dict(all_views.get("sheet", {})),
        "views_expected": validation.get("views_expected", len(EXPECTED_VIEWS)),
        "views_received": validation.get("views_received", 0),
        "views_saved": validation.get("views_saved", 0),
        "validation": validation,
        "views": [make_batch_view(item) for item in all_views.get("views", [])],
        "image_size": image_size,
        "time_sec": round(time_sec, 2),
        "output_files": dict(all_views.get("output_files", {})),
    }
