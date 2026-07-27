import sys
import os
import time
import shutil
import json
from pathlib import Path
from typing import Optional

# Dùng path tương đối hoặc override bằng JEWELRY_PROJECT_DIR.
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = Path(
    os.environ.get("JEWELRY_PROJECT_DIR", SCRIPT_DIR.parent / "jewelry_front_detector")
).expanduser().resolve()
sys.path.insert(0, str(PROJECT_DIR))

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
    sel_crop_path: Optional[Path] = None,   # Crop tu vung selection cua Photoshop
    expected_direction: str = "",           # "H"/"W"/"" tu aspect ratio selection
    selection_norm_bbox: Optional[list] = None, # [x1, y1, x2, y2] normalized 0-1000
):
    out_stem = output_base_name or img_path.stem
    t_total = time.perf_counter()
    timing = {}

    logger.info("=" * 50)
    logger.info(f"Xu ly anh: {img_path.name}")
    logger.info(f"Duong dan: {img_path}")
    logger.info(f"Su dung model: {model_name}")

    # Giong jewelry_front_detector GUI: gui ANH GOC (khong resize/re-JPEG)
    # → bbox / so do chuan hon pipeline ha size.
    logger.info("[TIMING] mode=original_file (giong GUI jewelry_front_detector)")
    timing["resize_ms"] = 0.0
    timing["encode_ms"] = 0.0
    timing["jpeg_bytes"] = 0
    timing["b64_kb"] = 0
    timing["send_w"] = 0
    timing["send_h"] = 0
    try:
        from PIL import Image as _PILImage
        with _PILImage.open(img_path) as _im:
            timing["send_w"], timing["send_h"] = _im.size
        logger.info(f"Gui LM kich thuoc goc: {timing['send_w']}x{timing['send_h']}")
    except Exception:
        pass

    t0 = time.perf_counter()
    res = send_image_to_model_all_views(
        image_path=img_path,
        model=model_name,
        retry_count=0,
    )
    timing["lm_all_views_ms"] = (time.perf_counter() - t0) * 1000
    logger.info(f"[TIMING] LM ALL VIEWS (encode goc+HTTP): {timing['lm_all_views_ms']:.0f}ms")

    parsed_json_list = res.get("views")
    raw_response = res.get("raw_response", "")
    sheet = res.get("sheet", {})
    error = res.get("error")
    error_type = res.get("error_type")

    if error or not parsed_json_list:
        logger.error(
            f"Phan tich that bai [{error_type or 'UnknownError'}]: "
            f"{error or raw_response[:300]}"
        )
        if move_source:
            _move_to_failed(img_path)
        return

    logger.info(
        f"Nhan dien thanh cong {len(parsed_json_list)} views | "
        f"drawing={sheet.get('drawing_number')} metal={sheet.get('metal')} brand={sheet.get('brand')}"
    )

    import image_processor as ip
    import bbox_utils as bu
    from config import ENABLE_OPENCV_REFINE

    orig_save = ip.save_cv2_image
    ip.save_cv2_image = _noop_save
    all_results = []
    t0 = time.perf_counter()
    try:
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
    finally:
        ip.save_cv2_image = orig_save

    timing["process_views_ms"] = (time.perf_counter() - t0) * 1000
    logger.info(f"[TIMING] process {len(all_results)} views (bbox/refine): {timing['process_views_ms']:.0f}ms")

    # =========================================================================
    # AI LẦN 2: Crop vung selection (neu co) hoac FRONT bbox → doc H/W/RD
    # =========================================================================
    front_dims = None
    try:
        # Re-check sel_crop trong INPUT_DIR tai day (sau AI lan 1 ~11s)
        # PS export crop ~0.5s sau khi gui job → chac chan da co file khi den buoc nay
        if sel_crop_path is None or not sel_crop_path.exists():
            _auto = INPUT_DIR / f"{out_stem}__sel_crop.jpg"
            if _auto.exists():
                sel_crop_path = _auto
                logger.info(f"[DIMENSION] Re-check found sel_crop: {_auto.name} "
                            f"({_auto.stat().st_size // 1024}KB)")

        if sel_crop_path and sel_crop_path.exists():
            # === CASE A: Dung crop tu vung selection Photoshop (uu tien) ===
            logger.info(f"[DIMENSION] Dung selection crop: {sel_crop_path.name} "
                        f"({sel_crop_path.stat().st_size // 1024}KB)")
            import io as _io, base64 as _base64
            from PIL import Image as _PILImage
            with _PILImage.open(sel_crop_path) as _cr:
                _cr = _cr.convert("RGB")
                _buf = _io.BytesIO()
                _cr.save(_buf, format="JPEG", quality=90)
                _b64 = _base64.b64encode(_buf.getvalue()).decode("utf-8")
                _crop_data_url = f"data:image/jpeg;base64,{_b64}"
            from lmstudio_client import send_image_to_model_dimensions
            t_dim = time.perf_counter()
            front_dims = send_image_to_model_dimensions(
                data_url=_crop_data_url,
                model=model_name,
                expected_direction=expected_direction,
            )
            timing["dimension_ms"] = (time.perf_counter() - t_dim) * 1000
            logger.info(f"[TIMING] AI lan 2 (selection crop): {timing['dimension_ms']:.0f}ms")
            # Xoa file crop tam sau khi dung xong
            try:
                sel_crop_path.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            # === CASE B: Spatial Grounding Fallback - Tim View trung khop voi selection_norm_bbox tu AI lan 1 ===
            target_view_result = None
            if selection_norm_bbox and len(selection_norm_bbox) == 4:
                sx1, sy1, sx2, sy2 = selection_norm_bbox
                # Tim view trong 7 views chua hoac trung khop tot nhat voi selection_norm_bbox
                best_view = None
                best_overlap = -1
                for r in all_results:
                    v_bbox = r["pixel"].get("panel_bbox") or r["pixel"].get("object_bbox")
                    if v_bbox and len(v_bbox) == 4:
                        from PIL import Image as _PILImage
                        with _PILImage.open(img_path) as _im_check:
                            _w_chk, _h_chk = _im_check.size
                        # Convert v_bbox pixel to norm 0-1000
                        vx1 = (v_bbox[0] / _w_chk) * 1000
                        vy1 = (v_bbox[1] / _h_chk) * 1000
                        vx2 = (v_bbox[2] / _w_chk) * 1000
                        vy2 = (v_bbox[3] / _h_chk) * 1000
                        # Tinh overlap
                        ox1, oy1 = max(sx1, vx1), max(sy1, vy1)
                        ox2, oy2 = min(sx2, vx2), min(sy2, vy2)
                        if ox2 > ox1 and oy2 > oy1:
                            overlap_area = (ox2 - ox1) * (oy2 - oy1)
                            if overlap_area > best_overlap:
                                best_overlap = overlap_area
                                best_view = r
                if best_view:
                    target_view_result = best_view
                    logger.info(f"[DIMENSION][SPATIAL] Nhan dien selection nam trong View '{best_view.get('view_name')}'")

            if not target_view_result:
                target_view_result = next((r for r in all_results if r.get("view_name") == "FRONT"), None)

            if target_view_result:
                v_name = target_view_result.get("view_name", "FRONT")
                target_bbox = target_view_result["pixel"].get("object_bbox") or target_view_result["pixel"].get("panel_bbox")
                if target_bbox and len(target_bbox) == 4:
                    x1, y1, x2, y2 = int(target_bbox[0]), int(target_bbox[1]), int(target_bbox[2]), int(target_bbox[3])
                    if x2 > x1 + 20 and y2 > y1 + 20:
                        from PIL import Image as _PILImage
                        import io as _io, base64 as _base64
                        with _PILImage.open(img_path) as _im:
                            _im = _im.convert("RGB")
                            pad = 20
                            _iw, _ih = _im.size
                            crop_box = (
                                max(0, x1 - pad), max(0, y1 - pad),
                                min(_iw, x2 + pad), min(_ih, y2 + pad),
                            )
                            _crop = _im.crop(crop_box)
                        _buf = _io.BytesIO()
                        _crop.save(_buf, format="JPEG", quality=90)
                        _b64 = _base64.b64encode(_buf.getvalue()).decode("utf-8")
                        _crop_data_url = f"data:image/jpeg;base64,{_b64}"
                        logger.info(
                            f"[DIMENSION] Fallback crop View '{v_name}': bbox={target_bbox} "
                            f"crop={_crop.size[0]}x{_crop.size[1]}"
                        )
                        from lmstudio_client import send_image_to_model_dimensions
                        t_dim = time.perf_counter()
                        front_dims = send_image_to_model_dimensions(
                            data_url=_crop_data_url,
                            model=model_name,
                            expected_direction=expected_direction,
                        )
                        timing["dimension_ms"] = (time.perf_counter() - t_dim) * 1000
                        logger.info(f"[TIMING] AI lan 2 (View {v_name} fallback): {timing['dimension_ms']:.0f}ms")
                    else:
                        logger.warning(f"[DIMENSION] Bbox View {v_name} qua nho, bo qua.")
            else:
                logger.warning("[DIMENSION] Khong tim thay target view, bo qua AI lan 2.")
    except Exception as _e:
        logger.warning(f"[DIMENSION] AI lan 2 that bai: {_e}")
        front_dims = None

    t0 = time.perf_counter()
    json_path = OUTPUT_DIR / f"{out_stem}_all_views_result.json"
    # Sheet goc + them front_width_mm / front_height_mm / scale_direction (neu co)
    sheet_out = {
        "drawing_number": sheet.get("drawing_number"),
        "metal":          sheet.get("metal"),
        "brand":          sheet.get("brand") or "NONE",
        "metal_weight":   sheet.get("metal_weight"),
    }
    if front_dims:
        sheet_out["front_width_mm"]  = front_dims.get("front_width_mm")
        sheet_out["front_height_mm"] = front_dims.get("front_height_mm")
        sheet_out["scale_direction"] = front_dims.get("scale_direction")
        sheet_out["dim_confidence"]  = front_dims.get("confidence")

    # Format moi: { sheet, views } — AI_AutoDetect van doc duoc (va format cu array)
    payload_out = {
        "sheet": sheet_out,
        "views": all_results,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload_out, f, ensure_ascii=False, indent=2)
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
    logger.info(
        f"  0. payload           : original {timing['send_w']}x{timing['send_h']} (giong GUI)"
    )
    logger.info(f"  1. prepare           : {timing['resize_ms']:.0f}ms (encode trong LM client)")
    logger.info(f"  2. LM ALL VIEWS     : {timing['lm_all_views_ms']:.0f}ms  << thuong la bottleneck")
    logger.info(f"  5. move source      : {timing['move_ms']:.0f}ms")
    logger.info(f"  TOTAL Detector     : {timing['total_ms']:.0f}ms ({timing['total_ms']/1000:.2f}s)")
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
            "mode": "original_file_like_gui",
        }
        timing_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Append dong tom tat
        log_txt = BASE_DIR / "cache" / "timing_log.txt"
        with open(log_txt, "a", encoding="utf-8") as lf:
            lf.write(
                f"{payload['ts']} | DETECTOR | {out_stem} | "
                f"mode=original "
                f"send={timing['send_w']}x{timing['send_h']} "
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

    # --- Xac dinh sel_crop_path ---
    # Uu tien: tu job JSON (neu job duoc ghi sau khi crop da co)
    sel_crop: Optional[Path] = None
    if data.get("selection_crop_path"):
        p = Path(data["selection_crop_path"])
        if p.exists():
            sel_crop = p

    # Auto-detect: PS export crop SAU khi ghi job (timing issue)
    # → Python kiem tra file crop trong INPUT_DIR theo naming convention
    if sel_crop is None:
        # Crop nam trong INPUT_DIR (chua bi move)
        auto_crop = INPUT_DIR / f"{base_name}__sel_crop.jpg"
        if auto_crop.exists():
            sel_crop = auto_crop
            logger.info(f"[DIMENSION] Auto-detected sel_crop: {auto_crop.name}")
        else:
            # Thu trong PROCESSING_DIR (neu bi move cung voi job)
            auto_crop2 = PROCESSING_DIR / f"{base_name}__sel_crop.jpg"
            if auto_crop2.exists():
                sel_crop = auto_crop2
                logger.info(f"[DIMENSION] Auto-detected sel_crop (processing): {auto_crop2.name}")

    # Lay expected direction & selection_norm_bbox tu job
    sel_expected_dir = data.get("sel_expected_dir", "")
    sel_norm_bbox = data.get("selection_norm_bbox", None)
    if sel_expected_dir:
        logger.info(f"[DIMENSION] sel_expected_dir tu job: '{sel_expected_dir}'")
    if sel_norm_bbox:
        logger.info(f"[DIMENSION][SPATIAL] selection_norm_bbox tu job: {sel_norm_bbox}")

    try:
        process_image(
            image_path,
            model_name,
            output_base_name=base_name,
            move_source=False,
            sel_crop_path=sel_crop,
            expected_direction=sel_expected_dir,
            selection_norm_bbox=sel_norm_bbox,
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
