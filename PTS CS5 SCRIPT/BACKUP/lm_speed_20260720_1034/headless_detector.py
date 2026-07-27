import sys
import os
import time
import shutil
import json
from pathlib import Path
from typing import Optional

# Thêm đường dẫn tới module cũ để dùng chung hàm lmstudio_client
sys.path.insert(0, r"d:\CODE\Agent\AutoNhanDangAnh\jewelry_front_detector")

from lmstudio_client import send_image_to_model_all_views

from logger_utils import get_logger

# Thiết lập thư mục
BASE_DIR = Path(__file__).parent.resolve()
INPUT_DIR  = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
PROCESSING_DIR = INPUT_DIR / "_processing"
FAILED_DIR = PROCESSING_DIR / "_failed"
LOCK_FILE = BASE_DIR / ".detector.lock"
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger = get_logger("headless_detector")


def acquire_single_instance_lock():
    """
    Chi cho phep 1 instance (Windows msvcrt lock).
    Tra ve file handle neu thanh cong; None neu da co instance khac.
    """
    lock_f = open(LOCK_FILE, "w")
    try:
        import msvcrt
        msvcrt.locking(lock_f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock_f.close()
        return None

    lock_f.write(str(os.getpid()))
    lock_f.flush()
    return lock_f


def claim_image_file(src: Path) -> Optional[Path]:
    """Chuyen anh vao _processing ngay de instance khac khong lay trung."""
    PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSING_DIR / src.name
    try:
        shutil.move(str(src), str(dest))
        return dest
    except (FileNotFoundError, PermissionError, OSError):
        return None


def claim_job_file(src: Path) -> Optional[Path]:
    """Chuyen job JSON vao _processing de tranh xu ly trung."""
    PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSING_DIR / src.name
    try:
        shutil.move(str(src), str(dest))
        return dest
    except (FileNotFoundError, PermissionError, OSError):
        return None


def get_active_model() -> str:
    """Tự động lấy tên model đang load trong LM Studio."""
    import requests
    try:
        resp = requests.get("http://localhost:1234/v1/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0].get("id")
    except Exception:
        pass
    return "qwen/qwen3-vl-4b"  # fallback


def _noop_save(*args, **kwargs):
    """Hàm giả: không lưu ảnh gì cả (dùng để tắt image saving trong ip.process_image)."""
    pass


def _move_to_failed(img_path: Path):
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    dest = FAILED_DIR / img_path.name
    if dest.exists():
        dest.unlink()
    if img_path.exists():
        shutil.move(str(img_path), str(dest))


def process_image(
    img_path: Path,
    model_name: str,
    output_base_name: Optional[str] = None,
    move_source: bool = True,
):
    out_stem = output_base_name or img_path.stem
    t_total = time.perf_counter()
    timing = {}

    logger.info("=" * 50)
    logger.info(f"Xu ly anh: {img_path.name}")
    logger.info(f"Duong dan: {img_path}")
    logger.info(f"Su dung model: {model_name}")

    # --- Resize anh xuong max 1500px truoc khi gui AI (giu nguyen ty le) ---
    MAX_AI_SIZE = 1500
    from PIL import Image as _PILImage
    import tempfile, os as _os

    _ai_img_path = img_path
    _tmp_path    = None

    t0 = time.perf_counter()
    with _PILImage.open(img_path) as _im:
        _w, _h = _im.size
        if max(_w, _h) > MAX_AI_SIZE:
            _scale  = MAX_AI_SIZE / max(_w, _h)
            _nw, _nh = int(_w * _scale), int(_h * _scale)
            _tmp_fd, _tmp_path = tempfile.mkstemp(suffix=".jpg",
                                                   dir=img_path.parent,
                                                   prefix="_ai_resize_")
            _os.close(_tmp_fd)
            _ai_img_path = Path(_tmp_path)
            _im.resize((_nw, _nh), _PILImage.LANCZOS).save(
                _ai_img_path, "JPEG", quality=85
            )
            logger.info(f"Da resize: {_w}x{_h} -> {_nw}x{_nh} (gui AI nhanh hon)")
        else:
            logger.info(f"Khong can resize: {_w}x{_h} (<= {MAX_AI_SIZE})")
    timing["resize_ms"] = (time.perf_counter() - t0) * 1000
    logger.info(f"[TIMING] open+resize: {timing['resize_ms']:.0f}ms")

    # Chi 1 request / anh (retry_count=0)
    t0 = time.perf_counter()
    parsed_json_list, raw_response = send_image_to_model_all_views(
        _ai_img_path, model_name, retry_count=0
    )
    timing["lm_all_views_ms"] = (time.perf_counter() - t0) * 1000
    logger.info(f"[TIMING] LM ALL VIEWS (gom encode+HTTP): {timing['lm_all_views_ms']:.0f}ms")

    if _tmp_path and Path(_tmp_path).exists():
        Path(_tmp_path).unlink()

    if not parsed_json_list:
        logger.error(f"Phan tich that bai: {raw_response[:300]}")
        if move_source:
            _move_to_failed(img_path)
        return

    logger.info(f"Nhan dien thanh cong {len(parsed_json_list)} views.")

    import image_processor as ip
    import bbox_utils as bu
    from config import ENABLE_OPENCV_REFINE

    ip.save_cv2_image = _noop_save

    all_results = []
    t0 = time.perf_counter()
    for item in parsed_json_list:
        view_name = item.get("view", "UNKNOWN")
        t_view = time.perf_counter()
        logger.info(f"  Dang xu ly {view_name}...")

        scale_type, multiplier = bu.detect_coordinate_scale(item)
        if multiplier != 1.0:
            item = bu.rescale_response_coords(item, multiplier)

        result = ip.process_image(
            img_path,
            item,
            model_name,
            scale_type,
            enable_refine=ENABLE_OPENCV_REFINE,
            target_view=view_name,
            save_json=False
        )

        pixel = result.get("pixel", {})
        all_results.append({
            "view_name": view_name,
            "image_size": result.get("image_size", {}),
            "pixel": {
                "panel_bbox":   pixel.get("refined_panel_bbox") or pixel.get("ai_panel_bbox", []),
                "object_bbox":  pixel.get("refined_object_bbox") or pixel.get("ai_object_bbox", []),
                "object_center": pixel.get("object_center", []),
            }
        })
        view_ms = (time.perf_counter() - t_view) * 1000
        logger.info(f"  {view_name}: obj={all_results[-1]['pixel']['object_bbox']} | {view_ms:.0f}ms")

    timing["process_views_ms"] = (time.perf_counter() - t0) * 1000
    logger.info(f"[TIMING] process {len(all_results)} views (bbox/refine): {timing['process_views_ms']:.0f}ms")

    t0 = time.perf_counter()
    json_path = OUTPUT_DIR / f"{out_stem}_all_views_result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    timing["save_json_ms"] = (time.perf_counter() - t0) * 1000
    logger.info(f"Da luu JSON: {json_path.name}")
    logger.info(f"[TIMING] save JSON: {timing['save_json_ms']:.0f}ms")

    if move_source:
        t0 = time.perf_counter()
        output_img_path = OUTPUT_DIR / img_path.name
        if output_img_path.exists():
            output_img_path.unlink()
        shutil.move(str(img_path), str(output_img_path))
        timing["move_ms"] = (time.perf_counter() - t0) * 1000
        logger.info(f"Da chuyen anh sang: {output_img_path.name}")
    else:
        timing["move_ms"] = 0
        logger.info(f"Giu nguyen file goc: {img_path}")

    timing["total_ms"] = (time.perf_counter() - t_total) * 1000
    logger.info("-" * 50)
    logger.info(f"[TIMING SUMMARY] {out_stem}")
    logger.info(f"  1. open+resize     : {timing['resize_ms']:.0f}ms")
    logger.info(f"  2. LM ALL VIEWS    : {timing['lm_all_views_ms']:.0f}ms  << thuong la bottleneck")
    logger.info(f"  3. process views   : {timing['process_views_ms']:.0f}ms")
    logger.info(f"  4. save JSON       : {timing['save_json_ms']:.0f}ms")
    logger.info(f"  5. move source     : {timing['move_ms']:.0f}ms")
    logger.info(f"  TOTAL Detector    : {timing['total_ms']:.0f}ms ({timing['total_ms']/1000:.2f}s)")
    logger.info("=" * 50)

    # Ghi file timing de doi chieu voi Photoshop
    try:
        timing_path = BASE_DIR / "cache" / "last_detector_timing.json"
        timing_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "base_name": out_stem,
            "image": str(img_path),
            "model": model_name,
            "ms": timing,
            "views": len(all_results),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        timing_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Append dong tom tat
        log_txt = BASE_DIR / "cache" / "timing_log.txt"
        with open(log_txt, "a", encoding="utf-8") as lf:
            lf.write(
                f"{payload['ts']} | DETECTOR | {out_stem} | "
                f"resize={timing['resize_ms']:.0f}ms "
                f"lm={timing['lm_all_views_ms']:.0f}ms "
                f"views={timing['process_views_ms']:.0f}ms "
                f"json={timing['save_json_ms']:.0f}ms "
                f"total={timing['total_ms']:.0f}ms\n"
            )
    except Exception as e:
        logger.warning(f"Khong ghi duoc timing file: {e}")


def process_job(job_path: Path, model_name: str):
    """Doc job JSON tu Photoshop — chi tham chieu duong dan, khong copy/export anh."""
    t_job = time.perf_counter()
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Job JSON loi ({job_path.name}): {e}")
        return

    image_path = Path(data.get("image_path", ""))
    base_name = data.get("base_name") or image_path.stem
    job_age_ms = None
    try:
        # Uoc luong do tre nhan job: mtime job file
        job_age_ms = max(0, (time.time() - job_path.stat().st_mtime) * 1000)
    except OSError:
        pass

    if job_age_ms is not None:
        logger.info(
            f"[TIMING] Nhan job {job_path.name} | base={base_name} | "
            f"doi_trong_hang~{job_age_ms:.0f}ms"
        )
    else:
        logger.info(f"[TIMING] Nhan job {job_path.name} | base={base_name}")

    if not image_path.exists():
        logger.error(f"Khong tim thay anh trong job: {image_path}")
        return

    ext = image_path.suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        logger.error(f"Dinh dang khong ho tro: {image_path}")
        return

    try:
        process_image(
            image_path,
            model_name,
            output_base_name=base_name,
            move_source=False,
        )
    finally:
        try:
            job_path.unlink(missing_ok=True)
        except OSError:
            pass
        logger.info(f"[TIMING] process_job wall: {(time.perf_counter() - t_job)*1000:.0f}ms")


def main():
    lock_handle = acquire_single_instance_lock()
    if lock_handle is None:
        logger.info("Headless Detector da chay. Thoat.")
        return

    logger.info(f"[Headless Detector] PID {os.getpid()} - Dang theo doi: {INPUT_DIR}")
    logger.info("Nhan Ctrl+C de thoat.")
    try:
        while True:
            found_work = False

            for job in sorted(INPUT_DIR.glob("*.job.json")):
                if not job.is_file() or job.name.startswith("_"):
                    continue
                claimed_job = claim_job_file(job)
                if claimed_job is None:
                    continue
                found_work = True
                logger.info(f"Nhan job: {claimed_job.name}")
                t_model = time.perf_counter()
                model = get_active_model()
                logger.info(
                    f"[TIMING] get_active_model: {(time.perf_counter() - t_model)*1000:.0f}ms | {model}"
                )
                try:
                    process_job(claimed_job, model)
                except Exception as e:
                    logger.error(f"Loi xu ly job {claimed_job.name}: {e}")
                    try:
                        claimed_job.unlink(missing_ok=True)
                    except OSError:
                        pass

            for f in sorted(INPUT_DIR.glob("*")):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    continue
                if f.name.startswith("_"):
                    continue

                claimed = claim_image_file(f)
                if claimed is None:
                    continue
                found_work = True

                model = get_active_model()
                try:
                    process_image(claimed, model)
                except Exception as e:
                    logger.error(f"Loi xu ly {claimed.name}: {e}")
                    _move_to_failed(claimed)

            # Idle: poll nhanh (0.2s) de bat job ngay khi user mo Dialog Scale
            # Dang xu ly: khong can sleep — vong lap tiep theo se quet lai ngay
            if not found_work:
                time.sleep(0.2)
    except KeyboardInterrupt:
        logger.info("Da dung theo doi.")
    finally:
        lock_handle.close()
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
