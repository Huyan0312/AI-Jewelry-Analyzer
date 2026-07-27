"""Batch runner cho ảnh trong ``AUTO_TEST_DIR``."""

import argparse
import json
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import bbox_utils as bu
import image_processor as ip
import lmstudio_client as lm
from config import (
    AUTO_TEST_DIR,
    AUTO_TEST_RESULTS_DIR,
    ENABLE_OPENCV_REFINE,
    LMSTUDIO_BASE_URL,
    OUTPUT_DIR,
)
from logger_utils import get_logger
from result_contract import (
    build_all_views_result,
    make_batch_entry,
    save_json_with_self_path,
)

logger = get_logger("auto_test_runner")
RESULTS_DIR = AUTO_TEST_RESULTS_DIR


def clean_old_results(
    results_dir: Path = RESULTS_DIR,
    allowed_root: Path = OUTPUT_DIR,
) -> None:
    """Xóa nội dung results sau khi xác nhận nó nằm trong allowed_root."""
    resolved_results = Path(results_dir).resolve()
    resolved_root = Path(allowed_root).resolve()
    if resolved_results == resolved_root or not resolved_results.is_relative_to(resolved_root):
        raise ValueError(
            f"Từ chối clean ngoài thư mục output cho phép: {resolved_results}"
        )

    if resolved_results.exists():
        print(f"🧹 Đang xóa kết quả cũ trong {resolved_results}...")
        for item in resolved_results.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    resolved_results.mkdir(parents=True, exist_ok=True)
    print("✅ Đã làm sạch thư mục kết quả!")


def get_loaded_model(base_url: str = LMSTUDIO_BASE_URL) -> str:
    ok, msg, models = lm.check_connection(base_url)
    if not ok or not models:
        raise RuntimeError(f"Không kết nối được LM Studio tại {base_url}: {msg}")
    for model in models:
        if any(token in model.lower() for token in ("vl", "flash", "llava")):
            print(f"🤖 Tìm thấy Vision Model: {model}")
            return model
    print(f"🤖 Dùng model mặc định: {models[0]}")
    return models[0]


def _failed_view(view_name: str, error: Exception) -> dict:
    return {
        "view_name": view_name,
        "error": str(error),
        "output_files": {},
        "validation": {"valid": False, "warnings": [str(error)]},
    }


def run_batch_test(
    *,
    clean: bool = False,
    model_name: str = None,
    auto_test_dir: Path = AUTO_TEST_DIR,
    results_dir: Path = RESULTS_DIR,
    base_url: str = LMSTUDIO_BASE_URL,
    send_all_views=None,
) -> list:
    """Chạy batch và trả danh sách entry summary để có thể unit test."""
    started = time.time()
    created_at = datetime.now(timezone.utc).isoformat()
    auto_test_dir = Path(auto_test_dir).resolve()
    results_dir = Path(results_dir).resolve()

    if clean:
        clean_old_results(results_dir, allowed_root=results_dir.parent)
    else:
        results_dir.mkdir(parents=True, exist_ok=True)

    selected_model = model_name or get_loaded_model(base_url)
    sender = send_all_views or lm.send_image_to_model_all_views
    image_files = sorted(
        path
        for path in auto_test_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".png", ".jpeg", ".webp"}
    )
    print(f"🚀 Bắt đầu test {len(image_files)} ảnh trong {auto_test_dir.name}...\n")

    batch_summary = []
    counts = {"SUCCESS": 0, "PARTIAL": 0, "FAILED": 0}

    for index, image_path in enumerate(image_files, 1):
        print("=" * 50)
        print(f"[{index}/{len(image_files)}] Đang xử lý: {image_path.name}")
        file_started = time.time()
        sub_folder = results_dir / image_path.stem
        sub_folder.mkdir(parents=True, exist_ok=True)

        try:
            response = sender(
                image_path,
                model=selected_model,
                base_url=base_url,
            )
            parsed_views = response.get("views") or []
            sheet = response.get("sheet") or {}
            raw_response = response.get("raw_response", "")
            view_results = []

            if not response.get("error"):
                for item in parsed_views:
                    view_name = str(item.get("view", "UNKNOWN")).upper()
                    try:
                        scale_type, multiplier = bu.detect_coordinate_scale(item)
                        if multiplier != 1.0:
                            item = bu.rescale_response_coords(item, multiplier)
                        result = ip.process_image(
                            image_path,
                            item,
                            selected_model,
                            scale_type,
                            enable_refine=ENABLE_OPENCV_REFINE,
                            target_view=view_name,
                            save_json=False,
                            output_dir=sub_folder,
                        )
                        result["view_name"] = view_name
                        view_results.append(result)
                    except Exception as view_error:
                        logger.error(
                            f"{image_path.name}/{view_name} thất bại: "
                            f"{traceback.format_exc()}"
                        )
                        view_results.append(_failed_view(view_name, view_error))

            all_views = build_all_views_result(
                sheet=sheet,
                views=view_results,
                raw_response=raw_response,
            )
            if response.get("error"):
                all_views["status"] = "FAILED"
                all_views["validation"]["valid"] = False
                all_views["validation"].setdefault("errors", []).append(
                    str(response["error"])
                )

            master_path = sub_folder / f"{image_path.stem}_all_views_result.json"
            if not save_json_with_self_path(all_views, master_path, "json"):
                all_views["status"] = "PARTIAL" if view_results else "FAILED"
                all_views["validation"]["valid"] = False
                all_views["validation"].setdefault("errors", []).append(
                    "Không lưu được master JSON"
                )

            width, height = ip.read_image_size(image_path)
            elapsed = time.time() - file_started
            entry = make_batch_entry(
                image_path.name,
                all_views,
                elapsed,
                image_size=[width, height],
            )
            batch_summary.append(entry)
            counts[entry["status"]] += 1
            print(
                f"{entry['status']}: received={entry['views_received']}/7, "
                f"saved={entry['views_saved']}/7, time={elapsed:.2f}s"
            )
        except Exception as error:
            logger.error(f"Lỗi ảnh {image_path.name}: {traceback.format_exc()}")
            entry = {
                "image": image_path.name,
                "status": "FAILED",
                "sheet": {},
                "views_expected": 7,
                "views_received": 0,
                "views_saved": 0,
                "validation": {"valid": False, "errors": [str(error)]},
                "views": [],
                "time_sec": round(time.time() - file_started, 2),
                "output_files": {},
            }
            batch_summary.append(entry)
            counts["FAILED"] += 1

    summary_path = results_dir / "batch_summary.json"
    summary_payload = {
        "created_at": created_at,
        "model": selected_model,
        "counts": counts,
        "items": batch_summary,
        "output_files": {},
    }
    if not save_json_with_self_path(summary_payload, summary_path, "json"):
        raise OSError(f"Không lưu được batch summary: {summary_path}")

    total_time = time.time() - started
    print("=" * 50)
    print(f"TỔNG KẾT: {counts} | {total_time:.2f}s")
    print(f"File tổng hợp: {summary_path}")
    return batch_summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Chạy batch AutoTest")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Xóa kết quả cũ trong AutoTest_Results trước khi chạy",
    )
    args = parser.parse_args(argv)
    run_batch_test(clean=args.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
