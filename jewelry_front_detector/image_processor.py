"""
image_processor.py
Xử lý ảnh với OpenCV:
  - Tinh chỉnh panel FRONT bằng cách dò đường khung bảng.
  - Tinh chỉnh vật thể trang sức bằng color segmentation + contour.
  - Xử lý riêng View PERSPECTIVE ở chế độ bbox_only hoặc masked_object.
  - Vẽ bounding box lên ảnh kết quả.
  - Lưu ảnh output và debug.
"""

import json
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

import bbox_utils as bu
from config import (
    ENABLE_OPENCV_REFINE,
    PANEL_SEARCH_EXPAND_RATIO,
    PANEL_BOTTOM_EDGE_SNAP_RATIO,
    MIN_IOU_THRESHOLD,
    MAX_CENTER_DISTANCE_RATIO,
    PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO,
    PANEL_CONTOUR_MIN_AREA,
    MAX_PANEL_TRIM_RATIO,
    CONTENT_RETAINED_MIN_RATIO,
    OBJECT_SEARCH_MARGIN_RATIO,
    OBJECT_DILATION_KERNEL_SIZE,
    OBJECT_PADDING_PX,
    OBJECT_PADDING_RATIO,
    OBJECT_MIN_IOU_THRESHOLD,
    OBJECT_MAX_CENTER_DISTANCE_RATIO,
    OBJECT_MIN_AREA_RATIO,
    OBJECT_MAX_AREA_RATIO,
    OBJECT_MIN_CONTOUR_AREA,
    PERSPECTIVE_OUTPUT_MODE,
    PERSPECTIVE_SEARCH_EXPAND_RATIO,
    PERSPECTIVE_MIN_COMPONENT_AREA,
    PERSPECTIVE_MORPH_KERNEL_SIZE,
    PERSPECTIVE_PADDING_PX,
    PERSPECTIVE_MIN_IOU_THRESHOLD,
    PERSPECTIVE_MAX_CENTER_DISTANCE_RATIO,
    PERSPECTIVE_MIN_AREA_RATIO,
    PERSPECTIVE_MAX_AREA_RATIO,
    PERSPECTIVE_RED_MIN_SATURATION,
    PERSPECTIVE_RED_MIN_VALUE,
    PERSPECTIVE_RED_LOW_HUE_MAX,
    PERSPECTIVE_RED_HIGH_HUE_MIN,
    PERSPECTIVE_RED_ANNOTATION_MAX_THICKNESS,
    PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_SIZE,
    PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_AREA,
    PERSPECTIVE_GRAY_MAX_SATURATION,
    PERSPECTIVE_GRAY_MIN_VALUE,
    PERSPECTIVE_GRAY_MAX_VALUE,
    PERSPECTIVE_BACKGROUND_VALUE,
    OUTPUT_DIR,
    DEBUG_MODE,
    DEBUG_DIR,
    COLOR_PANEL,
    COLOR_AI_OBJECT,
    COLOR_REFINED_OBJECT,
    COLOR_CENTER,
    BOX_THICKNESS,
    FONT_SCALE,
    FONT_THICKNESS,
    OUTPUT_IMAGE_QUALITY,
)
from logger_utils import get_logger

logger = get_logger("jewelry_detector.image_processor")

BBox = List[float]


# =============================================================================
# TIỆN ÍCH ĐỌC ẢNH
# =============================================================================

def read_image_size(image_path: Path) -> Tuple[int, int]:
    """
    Đọc kích thước ảnh thật bằng Pillow.
    Trả về (width, height).
    """
    with Image.open(image_path) as img:
        return img.size  # (width, height)


def load_cv2_image(image_path: Path) -> np.ndarray:
    """Load ảnh bằng OpenCV, hỗ trợ đường dẫn Unicode."""
    raw = np.fromfile(str(image_path), dtype=np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"OpenCV không đọc được ảnh: {image_path}")
    return img


def save_cv2_image(img: np.ndarray, path: Path, quality: int = OUTPUT_IMAGE_QUALITY) -> bool:
    """Lưu ảnh OpenCV với hỗ trợ Unicode path. Trả về True nếu thành công."""
    if img is None or img.size == 0:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        elif ext == ".png":
            encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        else:
            encode_params = []
        success, buf = cv2.imencode(ext, img, encode_params)
        if success:
            buf.tofile(str(path))
            return path.is_file() and path.stat().st_size > 0
        return False
    except Exception as e:
        logger.error(f"Lỗi khi lưu ảnh {path}: {e}")
        return False


def _normalize_refine_meta(
    meta: Optional[dict],
    *,
    attempted: bool,
    success: bool,
    method: str,
    ai_bbox: BBox,
    final_bbox: BBox,
    thresholds: dict,
    fallback_reason: Optional[str],
) -> dict:
    """Chuẩn hóa metadata theo bbox cuối mà pipeline thực sự sử dụng."""
    normalized = dict(meta or {})
    normalized["attempted"] = bool(normalized.get("attempted", attempted))
    normalized["success"] = bool(success)
    normalized["method"] = normalized.get("method", method)
    normalized["ai_bbox"] = [float(v) for v in ai_bbox]
    normalized.setdefault("candidate_bbox", None)
    normalized["final_bbox"] = [float(v) for v in final_bbox]
    normalized.setdefault("iou_with_ai", 0.0)
    normalized.setdefault("center_distance_ratio", 0.0)
    normalized.setdefault("area_ratio", None)
    normalized["thresholds"] = {**thresholds, **normalized.get("thresholds", {})}
    if success:
        normalized["fallback_reason"] = None
    else:
        normalized["fallback_reason"] = normalized.get("fallback_reason") or fallback_reason
    return normalized


# =============================================================================
# TINH CHỈNH PANEL FRONT BẰNG OPENCV
# =============================================================================

def _find_table_borders(roi_gray: np.ndarray) -> np.ndarray:
    """
    Dùng Canny + morphology để tìm các đường kẻ bảng trong vùng ROI.
    Trả về binary mask của các đường thẳng.
    """
    blurred = cv2.GaussianBlur(roi_gray, (3, 3), 0)
    canny = cv2.Canny(blurred, 30, 100)

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    h_lines = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, h_kernel)

    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    v_lines = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, v_kernel)

    combined = cv2.bitwise_or(h_lines, v_lines)
    return combined


def refine_panel_bbox_opencv(
    img_bgr: np.ndarray,
    ai_panel_bbox_px: BBox,
    expand_ratio: float = PANEL_SEARCH_EXPAND_RATIO,
    min_iou: float = MIN_IOU_THRESHOLD,
) -> Tuple[Optional[BBox], dict]:
    """
    Tinh chỉnh panel_bbox từ AI bằng cách dò đường biên bảng.
    """
    h, w = img_bgr.shape[:2]
    meta = {
        "attempted": True,
        "success": False,
        "method": "opencv",
        "ai_bbox": [float(v) for v in ai_panel_bbox_px],
        "candidate_bbox": None,
        "final_bbox": [float(v) for v in ai_panel_bbox_px],
        "iou_with_ai": 0.0,
        "center_distance_ratio": 0.0,
        "area_ratio": 1.0,
        "detected_red_annotation_pixels": 0,
        "thresholds": {
            "min_iou": float(min_iou),
            "max_center_distance_ratio": float(MAX_CENTER_DISTANCE_RATIO),
            "prefilter_max_center_distance_ratio": float(PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO),
            "min_contour_area": int(PANEL_CONTOUR_MIN_AREA),
        },
        "fallback_reason": None,
    }
    debug_imgs = {"meta": meta}

    search_box = bu.expand_pixel_bbox(ai_panel_bbox_px, expand_ratio, w, h)
    sx1, sy1, sx2, sy2 = search_box

    roi = img_bgr[sy1:sy2, sx1:sx2].copy()
    if roi.size == 0:
        meta["fallback_reason"] = "ROI_empty"
        logger.warning("ROI trống sau khi mở rộng vùng tìm kiếm panel.")
        return None, debug_imgs

    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    debug_imgs["gray"] = roi_gray

    border_mask = _find_table_borders(roi_gray)
    debug_imgs["canny"] = border_mask

    contours, _ = cv2.findContours(
        border_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    best_bbox = None
    best_score = -1.0
    best_dist_ratio = 0.0

    ai_relative = [
        ai_panel_bbox_px[0] - sx1,
        ai_panel_bbox_px[1] - sy1,
        ai_panel_bbox_px[2] - sx1,
        ai_panel_bbox_px[3] - sy1,
    ]

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < PANEL_CONTOUR_MIN_AREA:
            continue

        x, y, cw, ch = cv2.boundingRect(cnt)
        candidate = [float(x), float(y), float(x + cw), float(y + ch)]

        iou = bu.bbox_iou(candidate, ai_relative)
        if iou < min_iou * 0.5:
            continue

        dist = bu.center_distance(candidate, ai_relative)
        diag = bu.bbox_diagonal(ai_relative)
        dist_ratio = (dist / diag) if diag > 0 else 0.0
        if dist_ratio > PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO:
            continue

        score = iou - dist_ratio * 0.3
        if score > best_score:
            best_score = score
            best_bbox = candidate
            best_dist_ratio = dist_ratio

    if best_bbox is None:
        meta["fallback_reason"] = "no_matching_contour_found"
        logger.info("OpenCV không tìm được contour phù hợp cho panel. Giữ bbox AI.")
        return None, debug_imgs

    refined_abs = [
        best_bbox[0] + sx1,
        best_bbox[1] + sy1,
        best_bbox[2] + sx1,
        best_bbox[3] + sy1,
    ]
    meta["candidate_bbox"] = refined_abs

    final_iou = bu.bbox_iou(refined_abs, ai_panel_bbox_px)
    meta["iou_with_ai"] = float(final_iou)
    meta["center_distance_ratio"] = float(best_dist_ratio)
    logger.info(f"OpenCV panel refine IoU = {final_iou:.3f}")

    if final_iou < min_iou:
        meta["fallback_reason"] = f"iou_below_threshold ({final_iou:.3f} < {min_iou})"
        logger.info(f"IoU {final_iou:.3f} < ngưỡng {min_iou}. Giữ bbox AI thay vì bbox OpenCV.")
        return None, debug_imgs

    if best_dist_ratio > MAX_CENTER_DISTANCE_RATIO:
        meta["fallback_reason"] = f"center_distance_above_threshold ({best_dist_ratio:.3f} > {MAX_CENTER_DISTANCE_RATIO})"
        logger.info(f"Center distance ratio {best_dist_ratio:.3f} > ngưỡng {MAX_CENTER_DISTANCE_RATIO}. Giữ bbox AI.")
        return None, debug_imgs

    meta["success"] = True
    meta["final_bbox"] = refined_abs
    logger.info(f"Panel refined: {[int(v) for v in refined_abs]}")
    return refined_abs, debug_imgs


# =============================================================================
# CLEAN PANEL CROP (Auto-trim Grid Lines on Edges)
# =============================================================================

def clean_panel_crop(panel_crop_raw: np.ndarray) -> Tuple[np.ndarray, dict]:
    """
    Trim các đường viền bảng dài nằm sát mép (grid lines) của panel crop.
    Chỉ cắt tối đa MAX_PANEL_TRIM_RATIO (18%) mỗi chiều. 
    Không cắt lẹm nội dung khác (bảo vệ bằng diện tích và nội dung).
    """
    h, w = panel_crop_raw.shape[:2]
    info = {
        "success": False,
        "raw_size": {"width": w, "height": h},
        "clean_size": {"width": w, "height": h},
        "trim": {"left": 0, "top": 0, "right": 0, "bottom": 0},
        "content_retained_ratio": 1.0,
        "fallback_reason": None,
    }
    
    if w < 50 or h < 50:
        info["fallback_reason"] = "Crop gốc quá nhỏ để clean"
        return panel_crop_raw.copy(), info

    gray = cv2.cvtColor(panel_crop_raw, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
    )

    hsv = cv2.cvtColor(panel_crop_raw, cv2.COLOR_BGR2HSV)
    _, s, _ = cv2.split(hsv)
    gray_mask = (s < 60).astype(np.uint8) * 255
    binary = cv2.bitwise_and(binary, binary, mask=gray_mask)

    _, content_mask_raw = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    h_len = max(10, int(w * 0.55))
    v_len = max(10, int(h * 0.55))

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))

    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
    
    max_trim_w = int(w * MAX_PANEL_TRIM_RATIO)
    max_trim_h = int(h * MAX_PANEL_TRIM_RATIO)

    trim_left = 0
    trim_right = 0
    trim_top = 0
    trim_bottom = 0

    v_contours, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_left = []
    valid_right = []
    for c in v_contours:
        cx, cy, cw, ch = cv2.boundingRect(c)
        if ch >= h * 0.50:
            if cx < max_trim_w:
                valid_left.append(cx + cw)
            elif cx + cw > w - max_trim_w:
                valid_right.append(w - cx)

    if valid_left:
        trim_left = max(valid_left) + 1
    if valid_right:
        trim_right = max(valid_right) + 1

    h_contours, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_top = []
    valid_bottom = []
    for c in h_contours:
        cx, cy, cw, ch = cv2.boundingRect(c)
        if cw >= w * 0.50:
            if cy < max_trim_h:
                valid_top.append(cy + ch)
            elif cy + ch > h - max_trim_h:
                valid_bottom.append(h - cy)

    if valid_top:
        trim_top = max(valid_top) + 1
    if valid_bottom:
        trim_bottom = max(valid_bottom) + 1
        
    trim_left = min(trim_left, max_trim_w)
    trim_right = min(trim_right, max_trim_w)
    trim_top = min(trim_top, max_trim_h)
    trim_bottom = min(trim_bottom, max_trim_h)

    if trim_left == 0 and trim_right == 0 and trim_top == 0 and trim_bottom == 0:
        info["fallback_reason"] = "No trim performed (all trim values = 0)"
        return panel_crop_raw.copy(), info
    
    new_w = w - trim_left - trim_right
    new_h = h - trim_top - trim_bottom
    
    if new_w < 50 or new_h < 50:
        info["fallback_reason"] = "Crop panel quá nhỏ (<50px)"
        logger.warning(f"Clean panel fallback: {info['fallback_reason']}")
        return panel_crop_raw.copy(), info
        
    lines_combined = cv2.bitwise_or(h_lines, v_lines)
    lines_dilated = cv2.dilate(lines_combined, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    real_content_mask = cv2.bitwise_and(content_mask_raw, cv2.bitwise_not(lines_dilated))
    real_pixels_raw = cv2.countNonZero(real_content_mask)
    
    if real_pixels_raw > 0:
        real_content_mask_clean = real_content_mask[trim_top:h-trim_bottom, trim_left:w-trim_right]
        real_pixels_clean = cv2.countNonZero(real_content_mask_clean)
        retained = real_pixels_clean / real_pixels_raw
    else:
        retained = 1.0
        
    info["content_retained_ratio"] = float(retained)
    
    if retained < CONTENT_RETAINED_MIN_RATIO:
        info["fallback_reason"] = f"Mất nội dung (retained {retained:.2%} < {CONTENT_RETAINED_MIN_RATIO:.0%})"
        logger.warning(f"Clean panel fallback: {info['fallback_reason']}")
        return panel_crop_raw.copy(), info
        
    info["trim"] = {"left": trim_left, "top": trim_top, "right": trim_right, "bottom": trim_bottom}
    info["clean_size"] = {"width": new_w, "height": new_h}
    info["success"] = True
    
    panel_crop_clean = panel_crop_raw[trim_top:h-trim_bottom, trim_left:w-trim_right].copy()
    
    logger.info(
        f"Clean panel crop: raw_size={w}x{h} "
        f"trim_left={trim_left} trim_top={trim_top} "
        f"trim_right={trim_right} trim_bottom={trim_bottom} "
        f"content_retained={retained:.1%} success=True"
    )
    
    if DEBUG_MODE:
        info["_debug_raw"] = panel_crop_raw.copy()
        info["_debug_gray"] = gray
        info["_debug_hlines"] = h_lines
        info["_debug_vlines"] = v_lines
        info["_debug_clean"] = panel_crop_clean.copy()
        
    return panel_crop_clean, info


# =============================================================================
# TINH CHỈNH OBJECT (Auto-trim whitespace)
# =============================================================================

def refine_object_bbox_opencv(
    clean_panel_bgr: np.ndarray,
    ai_obj_bbox_in_clean_panel: BBox,
    clean_panel_offset: Tuple[int, int],
    img_width: int,
    img_height: int
) -> Tuple[Optional[BBox], dict]:
    """
    Tinh chỉnh Object Bounding Box bằng cách tìm các vùng nội dung (contours) 
    giao nhau (intersect) với bounding box của AI trên ảnh panel ĐÃ CLEAN.
    Sử dụng DILATION để nối liền các nét đứt, mũi tên, và số với nhau.
    """
    ph, pw = clean_panel_bgr.shape[:2]
    px, py = clean_panel_offset
    ai_full = [
        float(ai_obj_bbox_in_clean_panel[0] + px),
        float(ai_obj_bbox_in_clean_panel[1] + py),
        float(ai_obj_bbox_in_clean_panel[2] + px),
        float(ai_obj_bbox_in_clean_panel[3] + py),
    ]

    meta = {
        "attempted": True,
        "success": False,
        "method": "opencv",
        "ai_bbox": ai_full,
        "candidate_bbox": None,
        "final_bbox": ai_full,
        "iou_with_ai": 0.0,
        "center_distance_ratio": 0.0,
        "area_ratio": 1.0,
        "thresholds": {
            "min_iou": float(OBJECT_MIN_IOU_THRESHOLD),
            "max_center_distance_ratio": float(OBJECT_MAX_CENTER_DISTANCE_RATIO),
            "min_area_ratio": float(OBJECT_MIN_AREA_RATIO),
            "max_area_ratio": float(OBJECT_MAX_AREA_RATIO),
            "min_contour_area": int(OBJECT_MIN_CONTOUR_AREA),
            "search_margin_ratio": float(OBJECT_SEARCH_MARGIN_RATIO),
        },
        "fallback_reason": None,
    }
    debug_imgs = {"meta": meta}

    if clean_panel_bgr.size == 0 or pw == 0 or ph == 0:
        meta["fallback_reason"] = "clean_panel_empty"
        return None, debug_imgs

    # Bbox của AI trong tọa độ clean panel (nới lỏng margin theo config)
    ax1, ay1, ax2, ay2 = [int(round(v)) for v in ai_obj_bbox_in_clean_panel]
    margin_x = int(pw * OBJECT_SEARCH_MARGIN_RATIO)
    margin_y = int(ph * OBJECT_SEARCH_MARGIN_RATIO)
    search_ax1 = max(0, ax1 - margin_x)
    search_ay1 = max(0, ay1 - margin_y)
    search_ax2 = min(pw, ax2 + margin_x)
    search_ay2 = min(ph, ay2 + margin_y)
    
    a_rect = (search_ax1, search_ay1, search_ax2, search_ay2)
    ai_core_rect = (ax1, ay1, ax2, ay2)
    ai_center_x = (ax1 + ax2) / 2.0
    ai_center_y = (ay1 + ay2) / 2.0
    ai_diag = max(1.0, float(np.hypot(ax2 - ax1, ay2 - ay1)))

    gray = cv2.cvtColor(clean_panel_bgr, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
    )

    hsv = cv2.cvtColor(clean_panel_bgr, cv2.COLOR_BGR2HSV)

    # Loại chỉ nét/chữ annotation đỏ mảnh trước khi dilation. Không xóa mảng
    # đỏ/hồng lớn vì đó có thể là một phần vật thể trang sức.
    red_1 = cv2.inRange(
        hsv,
        (0, PERSPECTIVE_RED_MIN_SATURATION, PERSPECTIVE_RED_MIN_VALUE),
        (PERSPECTIVE_RED_LOW_HUE_MAX, 255, 255),
    )
    red_2 = cv2.inRange(
        hsv,
        (
            PERSPECTIVE_RED_HIGH_HUE_MIN,
            PERSPECTIVE_RED_MIN_SATURATION,
            PERSPECTIVE_RED_MIN_VALUE,
        ),
        (180, 255, 255),
    )
    red_pixels = cv2.bitwise_or(red_1, red_2)
    red_annotation_mask = _red_annotation_mask(
        red_pixels,
        clean_panel_bgr,
        preserve_embedded_red=True,
    )
    red_annotation_mask = cv2.dilate(
        red_annotation_mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
        iterations=1,
    )
    meta["detected_red_annotation_pixels"] = int(
        cv2.countNonZero(red_annotation_mask)
    )
    debug_imgs["red_annotation_mask"] = red_annotation_mask

    gray_mask = cv2.inRange(hsv, (0, 0, 0), (180, 60, 210))
    top_strip_mask = np.zeros_like(gray_mask)
    
    max_label_y = int(ph * 0.18)
    max_label_x = int(pw * 0.45)
    top_strip_mask[0:max_label_y, 0:max_label_x] = 255
    label_mask = cv2.bitwise_and(gray_mask, top_strip_mask)
    view_label_mask = np.zeros_like(label_mask)
    
    label_contours, _ = cv2.findContours(label_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in label_contours:
        lx, ly, lw, lh = cv2.boundingRect(c)
        if ly < max_label_y * 0.6 and lx < max_label_x * 0.8:
            label_start = (max(0, lx - 2), max(0, ly - 2))
            label_end = (min(pw, lx + lw + 2), min(ph, ly + lh + 2))
            cv2.rectangle(binary, label_start, label_end, 0, -1)
            cv2.rectangle(view_label_mask, label_start, label_end, 255, -1)
    debug_imgs["view_label_mask"] = view_label_mask

    # 2. Xóa các đường thẳng ngang/dọc (viền bảng đen/xám) còn sót lại ở sát mép
    gray_lines_mask = (hsv[:, :, 1] < 25).astype(np.uint8) * 255
    binary_gray_lines = cv2.bitwise_and(binary, binary, mask=gray_lines_mask)

    h_len = max(20, int(pw * 0.3))
    v_len = max(20, int(ph * 0.3))
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))
    h_lines = cv2.morphologyEx(binary_gray_lines, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(binary_gray_lines, cv2.MORPH_OPEN, v_kernel)

    edge_mask = np.zeros_like(binary)
    bw, bh = max(10, int(pw * 0.1)), max(10, int(ph * 0.1))
    edge_mask[0:bh, :] = 255
    edge_mask[-bh:, :] = 255
    edge_mask[:, 0:bw] = 255
    edge_mask[:, -bw:] = 255

    h_lines = cv2.bitwise_and(h_lines, edge_mask)
    v_lines = cv2.bitwise_and(v_lines, edge_mask)
    
    binary = cv2.subtract(binary, h_lines)
    binary = cv2.subtract(binary, v_lines)

    # Dilation theo config OBJECT_DILATION_KERNEL_SIZE
    kernel_s = OBJECT_DILATION_KERNEL_SIZE
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_s, kernel_s))
    binary_dilated = cv2.dilate(binary, kernel)
    
    debug_imgs["content_mask"] = binary_dilated

    contours, _ = cv2.findContours(binary_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_x, min_y = pw, ph
    max_x, max_y = 0, 0
    found = False

    for c in contours:
        area = cv2.contourArea(c)
        if area < OBJECT_MIN_CONTOUR_AREA:
            continue

        x, y, w, h = cv2.boundingRect(c)
        if w < 5 and h < 5:
            continue
            
        ix1 = max(a_rect[0], x)
        iy1 = max(a_rect[1], y)
        ix2 = min(a_rect[2], x + w)
        iy2 = min(a_rect[3], y + h)

        if ix1 >= ix2 or iy1 >= iy2:
            continue

        # Check connection with core AI bbox or center distance to reject distant margin noise
        core_ix1 = max(ai_core_rect[0], x)
        core_iy1 = max(ai_core_rect[1], y)
        core_ix2 = min(ai_core_rect[2], x + w)
        core_iy2 = min(ai_core_rect[3], y + h)
        has_core_intersection = (core_ix1 < core_ix2) and (core_iy1 < core_iy2)

        c_center_x = x + w / 2.0
        c_center_y = y + h / 2.0
        dist_to_ai_center = float(np.hypot(c_center_x - ai_center_x, c_center_y - ai_center_y))
        dist_ratio = dist_to_ai_center / ai_diag

        if not has_core_intersection and dist_ratio > (OBJECT_MAX_CENTER_DISTANCE_RATIO * 1.5):
            continue

        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)
        found = True

    if not found:
        meta["fallback_reason"] = "no_intersecting_contour_with_ai_bbox"
        logger.info("Không tìm thấy nội dung giao với AI Object Bbox.")
        return None, debug_imgs

    # Dilation hợp nhất vật thể với các mũi tên/số đo liên quan; thêm padding
    # để đầu mũi tên và ký tự kích thước không chạm mép crop.
    pad = max(OBJECT_PADDING_PX, int(min(pw, ph) * OBJECT_PADDING_RATIO))
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(pw, max_x + pad)
    max_y = min(ph, max_y + pad)

    refined_full = [
        float(min_x + px),
        float(min_y + py),
        float(max_x + px),
        float(max_y + py),
    ]
    meta["candidate_bbox"] = refined_full

    # ---- ACCEPTANCE GATE CHECKS FOR OBJECT REFINE ----
    # 1. Candidate bbox valid in image bounds
    ok_cand, msg_cand = bu.validate_pixel_bbox(refined_full, img_width, img_height, "candidate_object_bbox")
    if not ok_cand:
        meta["fallback_reason"] = f"candidate_bbox_invalid: {msg_cand}"
        logger.info(f"Object candidate bbox invalid: {msg_cand}")
        return None, debug_imgs

    # 2. Candidate inside panel bounds (with 5% tolerance)
    panel_abs = [float(px), float(py), float(px + pw), float(py + ph)]
    tol_x = pw * 0.05
    tol_y = ph * 0.05
    if (refined_full[0] < panel_abs[0] - tol_x or
        refined_full[1] < panel_abs[1] - tol_y or
        refined_full[2] > panel_abs[2] + tol_x or
        refined_full[3] > panel_abs[3] + tol_y):
        meta["fallback_reason"] = "candidate_outside_panel"
        logger.info("Object candidate vượt ngoài ranh giới panel.")
        return None, debug_imgs

    # 3. Area ratio check
    ai_area = max(1.0, (ai_full[2] - ai_full[0]) * (ai_full[3] - ai_full[1]))
    cand_area = max(1.0, (refined_full[2] - refined_full[0]) * (refined_full[3] - refined_full[1]))
    area_ratio = float(cand_area / ai_area)
    meta["area_ratio"] = area_ratio
    if area_ratio < OBJECT_MIN_AREA_RATIO:
        meta["fallback_reason"] = f"area_ratio_below_threshold ({area_ratio:.3f} < {OBJECT_MIN_AREA_RATIO})"
        logger.info(f"Object area ratio {area_ratio:.3f} < {OBJECT_MIN_AREA_RATIO}. Giữ bbox AI.")
        return None, debug_imgs
    if area_ratio > OBJECT_MAX_AREA_RATIO:
        meta["fallback_reason"] = f"area_ratio_above_threshold ({area_ratio:.3f} > {OBJECT_MAX_AREA_RATIO})"
        logger.info(f"Object area ratio {area_ratio:.3f} > {OBJECT_MAX_AREA_RATIO}. Giữ bbox AI.")
        return None, debug_imgs

    # 4. IoU check
    iou = bu.bbox_iou(refined_full, ai_full)
    meta["iou_with_ai"] = float(iou)
    if iou < OBJECT_MIN_IOU_THRESHOLD:
        meta["fallback_reason"] = f"iou_below_threshold ({iou:.3f} < {OBJECT_MIN_IOU_THRESHOLD})"
        logger.info(f"Object IoU {iou:.3f} < {OBJECT_MIN_IOU_THRESHOLD}. Giữ bbox AI.")
        return None, debug_imgs

    # 5. Center distance check
    dist = bu.center_distance(refined_full, ai_full)
    diag = bu.bbox_diagonal(ai_full)
    dist_ratio = float(dist / diag) if diag > 0 else 0.0
    meta["center_distance_ratio"] = dist_ratio
    if dist_ratio > OBJECT_MAX_CENTER_DISTANCE_RATIO:
        meta["fallback_reason"] = f"center_distance_above_threshold ({dist_ratio:.3f} > {OBJECT_MAX_CENTER_DISTANCE_RATIO})"
        logger.info(f"Object center distance {dist_ratio:.3f} > {OBJECT_MAX_CENTER_DISTANCE_RATIO}. Giữ bbox AI.")
        return None, debug_imgs

    meta["success"] = True
    meta["final_bbox"] = refined_full

    logger.info(
        f"Trimmed Object (ảnh gốc): {[int(v) for v in refined_full]} "
        f"| AI bbox gốc: {[int(v) for v in ai_full]}"
    )
    return refined_full, debug_imgs


def _red_annotation_mask(
    red_pixels: np.ndarray,
    source_bgr: Optional[np.ndarray] = None,
    preserve_embedded_red: bool = False,
) -> np.ndarray:
    """
    Giữ lại trong mask chỉ các nét đỏ có hình học giống đường kích thước/chữ.

    Không thể xóa toàn bộ màu đỏ vì model trang sức có thể chứa kim loại hoặc
    chi tiết màu đỏ/hồng. Các mảng màu lớn phải được xem là một phần vật thể.
    """
    # Opening giữ các mảng đỏ/hồng đủ dày và loại các nhánh mảnh, kể cả khi
    # đường kích thước đang nối với mũi tên hoặc chữ thành một contour lớn.
    kernel_size = max(3, int(PERSPECTIVE_RED_ANNOTATION_MAX_THICKNESS) + 1)
    if kernel_size % 2 == 0:
        kernel_size += 1
    thick_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
    )
    thick_regions_raw = cv2.morphologyEx(
        red_pixels, cv2.MORPH_OPEN, thick_kernel
    )
    # Mũi tên đỏ có thể còn một lõi dày sau opening. Chỉ bảo toàn các mảng
    # đủ lớn để có khả năng là vật thể màu đỏ/hồng.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        thick_regions_raw, connectivity=8
    )
    thick_object_regions = np.zeros_like(red_pixels)
    min_object_area = int(PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_AREA)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) > min_object_area:
            thick_object_regions[labels == label] = 255
    annotation_mask = cv2.subtract(red_pixels, thick_object_regions)

    # Bảo đảm chữ/số đỏ nhỏ được loại trọn contour, không chỉ phần nét mảnh.
    contours, _ = cv2.findContours(
        red_pixels, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        is_small_glyph = (
            cw <= PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_SIZE
            and ch <= PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_SIZE
            and area <= PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_AREA
        )
        if is_small_glyph:
            component_mask = np.zeros_like(red_pixels)
            cv2.drawContours(component_mask, [contour], -1, 255, thickness=-1)

            # Chữ đỏ khắc/in ngay trên vật thể phải được giữ. Annotation số đo
            # thường được bao quanh bởi nền giấy trắng.
            embedded_in_object = False
            if (
                preserve_embedded_red
                and source_bgr is not None
                and source_bgr.shape[:2] == red_pixels.shape
            ):
                ring = cv2.dilate(
                    component_mask,
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
                    iterations=1,
                )
                ring = cv2.subtract(ring, component_mask)
                hsv_source = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2HSV)
                paper = (
                    (hsv_source[:, :, 1] < 60)
                    & (hsv_source[:, :, 2] > 225)
                )
                ring_count = int(cv2.countNonZero(ring))
                if ring_count:
                    paper_count = int(np.count_nonzero(paper & (ring > 0)))
                    embedded_in_object = (paper_count / ring_count) < 0.10

            if embedded_in_object:
                annotation_mask[component_mask > 0] = 0
            else:
                annotation_mask[component_mask > 0] = 255

    if (
        preserve_embedded_red
        and source_bgr is not None
        and source_bgr.shape[:2] == red_pixels.shape
    ):
        protected_object_red = cv2.dilate(
            thick_object_regions,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        annotation_mask[protected_object_red > 0] = 0
        hsv_source = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2HSV)
        paper = (
            (hsv_source[:, :, 1] < 60)
            & (hsv_source[:, :, 2] > 225)
        ).astype(np.float32)
        nearby_paper_ratio = cv2.blur(paper, (11, 11))
        annotation_mask[nearby_paper_ratio < 0.35] = 0
    return annotation_mask


def refine_perspective_object_opencv(
    img_bgr: np.ndarray,
    ai_obj_bbox_px: BBox,
    width: int,
    height: int,
    mode: Optional[str] = None,
    panel_bbox_px: Optional[BBox] = None,
) -> Tuple[Optional[BBox], dict]:
    """
    Tinh chỉnh object cho PERSPECTIVE.

    ``bbox_only`` chỉ dùng mask để tìm bbox rồi crop pixel ảnh gốc.
    ``masked_object`` áp mask và tạo crop nền trắng trong ``_masked_object_crop``.
    """
    selected_mode = mode or PERSPECTIVE_OUTPUT_MODE
    if selected_mode not in {"bbox_only", "masked_object"}:
        logger.warning(
            "PERSPECTIVE_OUTPUT_MODE=%r không hợp lệ; dùng bbox_only.",
            selected_mode,
        )
        selected_mode = "bbox_only"

    ai_bbox = [float(v) for v in ai_obj_bbox_px]
    meta = {
        "attempted": True,
        "success": False,
        "method": "perspective_opencv",
        "mode": selected_mode,
        "bbox": ai_bbox[:],
        "ai_bbox": ai_bbox[:],
        "candidate_bbox": None,
        "final_bbox": ai_bbox[:],
        "mask_available": False,
        "mask_applied": False,
        "selected_components": 0,
        "removed_red_pixels": 0,
        "removed_text_grid_pixels": 0,
        "iou_with_ai": 0.0,
        "center_distance_ratio": 0.0,
        "area_ratio": None,
        "thresholds": {
            "min_component_area": int(PERSPECTIVE_MIN_COMPONENT_AREA),
            "min_iou": float(PERSPECTIVE_MIN_IOU_THRESHOLD),
            "max_center_distance_ratio": float(PERSPECTIVE_MAX_CENTER_DISTANCE_RATIO),
            "min_area_ratio": float(PERSPECTIVE_MIN_AREA_RATIO),
            "max_area_ratio": float(PERSPECTIVE_MAX_AREA_RATIO),
            "padding_px": int(PERSPECTIVE_PADDING_PX),
            "morph_kernel_size": int(PERSPECTIVE_MORPH_KERNEL_SIZE),
        },
        "fallback_reason": None,
    }
    debug_imgs = {"meta": meta}

    ok_ai, msg_ai = bu.validate_pixel_bbox(ai_bbox, width, height, "perspective_ai_bbox")
    if not ok_ai:
        meta["fallback_reason"] = f"ai_bbox_invalid: {msg_ai}"
        return None, debug_imgs

    ax1, ay1, ax2, ay2 = [int(round(v)) for v in ai_bbox]
    pad_w = int(width * PERSPECTIVE_SEARCH_EXPAND_RATIO)
    pad_h = int(height * PERSPECTIVE_SEARCH_EXPAND_RATIO)
    limit_x1, limit_y1, limit_x2, limit_y2 = 0, 0, width, height
    if panel_bbox_px is not None:
        ok_panel, _ = bu.validate_pixel_bbox(
            panel_bbox_px, width, height, "perspective_panel_bbox"
        )
        if ok_panel:
            limit_x1, limit_y1, limit_x2, limit_y2 = (
                bu.pixel_bbox_to_int(panel_bbox_px)
            )
    roi_x1 = max(limit_x1, ax1 - pad_w)
    roi_y1 = max(limit_y1, ay1 - pad_h)
    roi_x2 = min(limit_x2, ax2 + pad_w)
    roi_y2 = min(limit_y2, ay2 + pad_h)

    roi = img_bgr[roi_y1:roi_y2, roi_x1:roi_x2].copy()
    rh, rw = roi.shape[:2]
    if roi.size == 0 or rw == 0 or rh == 0:
        meta["fallback_reason"] = "roi_empty"
        return None, debug_imgs

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Vectorized paper-edge mask, không lặp Python qua từng pixel.
    abs_x = np.arange(roi_x1, roi_x2, dtype=np.int32)[None, :]
    abs_y = np.arange(roi_y1, roi_y2, dtype=np.int32)[:, None]
    paper_mask = (
        (abs_x < 25)
        | (abs_x > width - 25)
        | (abs_y < 25)
        | (abs_y > height - 25)
    ).astype(np.uint8) * 255

    # Red dimension mask.
    r1 = cv2.inRange(
        hsv,
        (0, PERSPECTIVE_RED_MIN_SATURATION, PERSPECTIVE_RED_MIN_VALUE),
        (PERSPECTIVE_RED_LOW_HUE_MAX, 255, 255),
    )
    r2 = cv2.inRange(
        hsv,
        (
            PERSPECTIVE_RED_HIGH_HUE_MIN,
            PERSPECTIVE_RED_MIN_SATURATION,
            PERSPECTIVE_RED_MIN_VALUE,
        ),
        (180, 255, 255),
    )
    red_pixels = cv2.bitwise_or(r1, r2)
    red_mask = _red_annotation_mask(red_pixels, roi)
    meta["removed_red_pixels"] = int(cv2.countNonZero(red_mask))

    # Gray text/grid mask.
    gray_mask = (
        (hsv[:, :, 1] < PERSPECTIVE_GRAY_MAX_SATURATION)
        & (gray < PERSPECTIVE_GRAY_MAX_VALUE)
        & (gray > PERSPECTIVE_GRAY_MIN_VALUE)
    )
    gray_mask_img = gray_mask.astype(np.uint8) * 255

    text_grid_mask = np.zeros((rh, rw), dtype=np.uint8)
    cnts, _ = cv2.findContours(gray_mask_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        is_text = (ch < 32 and cw < 180 and area < 1200)
        is_h_line = (cw > 20 and ch <= 5)
        is_v_line = (ch > 20 and cw <= 5)
        if is_text or is_h_line or is_v_line:
            cv2.rectangle(text_grid_mask, (max(0, x - 2), max(0, y - 2)), (min(rw, x + cw + 2), min(rh, y + ch + 2)), 255, -1)
    meta["removed_text_grid_pixels"] = int(cv2.countNonZero(text_grid_mask))

    # Model candidate mask, bao phủ cả kim loại màu và bạc gần grayscale.
    model_pixels = ((hsv[:, :, 1] > 18) | (gray < 210)).astype(np.uint8) * 255
    model_mask = cv2.subtract(model_pixels, red_mask)
    model_mask = cv2.subtract(model_mask, text_grid_mask)
    model_mask = cv2.subtract(model_mask, paper_mask)

    kernel_size = max(3, int(PERSPECTIVE_MORPH_KERNEL_SIZE))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    model_mask = cv2.morphologyEx(model_mask, cv2.MORPH_OPEN, kernel)
    model_mask = cv2.morphologyEx(model_mask, cv2.MORPH_CLOSE, kernel)

    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        model_mask, connectivity=8
    )
    ai_area = max(1.0, bu.bbox_area(ai_bbox))
    ai_diag = max(1.0, bu.bbox_diagonal(ai_bbox))
    ai_center = bu.calculate_bbox_center(ai_bbox)
    candidates = []

    for label in range(1, component_count):
        cx, cy, cw, ch, area = [int(v) for v in stats[label]]
        if area < PERSPECTIVE_MIN_COMPONENT_AREA:
            continue

        component_bbox = [
            float(roi_x1 + cx),
            float(roi_y1 + cy),
            float(roi_x1 + cx + cw),
            float(roi_y1 + cy + ch),
        ]
        ix1 = max(component_bbox[0], ai_bbox[0])
        iy1 = max(component_bbox[1], ai_bbox[1])
        ix2 = min(component_bbox[2], ai_bbox[2])
        iy2 = min(component_bbox[3], ai_bbox[3])
        if ix1 >= ix2 or iy1 >= iy2:
            continue

        comp_center = (
            float(roi_x1 + centroids[label][0]),
            float(roi_y1 + centroids[label][1]),
        )
        center_distance = float(
            np.hypot(comp_center[0] - ai_center[0], comp_center[1] - ai_center[1])
        )
        center_ratio = center_distance / ai_diag
        area_ratio = bu.bbox_area(component_bbox) / ai_area
        iou = bu.bbox_iou(component_bbox, ai_bbox)
        if center_ratio > PERSPECTIVE_MAX_CENTER_DISTANCE_RATIO:
            continue
        if not (PERSPECTIVE_MIN_AREA_RATIO <= area_ratio <= PERSPECTIVE_MAX_AREA_RATIO):
            continue
        if iou < PERSPECTIVE_MIN_IOU_THRESHOLD:
            continue

        contains_ai_center = (
            component_bbox[0] <= ai_center[0] <= component_bbox[2]
            and component_bbox[1] <= ai_center[1] <= component_bbox[3]
        )
        score = iou - (0.25 * center_ratio) + (1.0 if contains_ai_center else 0.0)
        candidates.append(
            (score, label, component_bbox, iou, center_ratio, area_ratio)
        )

    if not candidates:
        meta["fallback_reason"] = "no_component_related_to_ai_bbox"
        debug_imgs.update({
            "perspective_red_mask": red_mask,
            "perspective_text_grid_mask": text_grid_mask,
            "perspective_model_candidate_mask": model_mask,
        })
        logger.info("PERSPECTIVE: Không tìm thấy component liên hệ bbox AI.")
        return None, debug_imgs

    # Một model phối cảnh có thể gồm nhiều mảng màu không nối nhau (ví dụ nửa
    # vàng và nửa hồng). Gộp mọi component đã vượt qua các gate liên hệ với bbox
    # AI; chỉ chọn một component sẽ làm crop mất một nửa vật thể.
    selected_labels = [item[1] for item in candidates]
    selected_bboxes = [item[2] for item in candidates]
    component_bbox = [
        min(box[0] for box in selected_bboxes),
        min(box[1] for box in selected_bboxes),
        max(box[2] for box in selected_bboxes),
        max(box[3] for box in selected_bboxes),
    ]
    selected_mask = np.isin(labels, selected_labels).astype(np.uint8) * 255
    selected_mask = cv2.subtract(selected_mask, red_mask)
    selected_mask = cv2.subtract(selected_mask, text_grid_mask)
    selected_mask = cv2.subtract(selected_mask, paper_mask)
    iou = bu.bbox_iou(component_bbox, ai_bbox)
    component_center = bu.calculate_bbox_center(component_bbox)
    center_ratio = float(
        np.hypot(
            component_center[0] - ai_center[0],
            component_center[1] - ai_center[1],
        )
        / ai_diag
    )
    area_ratio = bu.bbox_area(component_bbox) / ai_area
    cx = int(round(component_bbox[0] - roi_x1))
    cy = int(round(component_bbox[1] - roi_y1))
    cw = int(round(component_bbox[2] - component_bbox[0]))
    ch = int(round(component_bbox[3] - component_bbox[1]))

    # PERSPECTIVE cũng phải giữ đầy đủ mũi tên, đường dóng và số đo đỏ như sáu
    # view thường. Mở rộng bbox model tới toàn bộ annotation đỏ trong search ROI.
    red_y, red_x = np.where(red_mask > 0)
    if red_x.size > 0 and red_y.size > 0:
        content_x1 = min(cx, int(red_x.min()))
        content_y1 = min(cy, int(red_y.min()))
        content_x2 = max(cx + cw, int(red_x.max()) + 1)
        content_y2 = max(cy + ch, int(red_y.max()) + 1)
        cx, cy = content_x1, content_y1
        cw, ch = content_x2 - content_x1, content_y2 - content_y1
        meta["included_red_annotation_pixels"] = int(red_x.size)
    else:
        meta["included_red_annotation_pixels"] = 0

    pad = max(0, int(PERSPECTIVE_PADDING_PX))
    crop_x1 = max(0, cx - pad)
    crop_y1 = max(0, cy - pad)
    crop_x2 = min(rw, cx + cw + pad)
    crop_y2 = min(rh, cy + ch + pad)

    refined_full = [
        float(roi_x1 + crop_x1),
        float(roi_y1 + crop_y1),
        float(roi_x1 + crop_x2),
        float(roi_y1 + crop_y2),
    ]
    ok_candidate, msg_candidate = bu.validate_pixel_bbox(
        refined_full, width, height, "perspective_candidate_bbox"
    )
    if not ok_candidate:
        meta["candidate_bbox"] = refined_full
        meta["fallback_reason"] = f"candidate_bbox_invalid: {msg_candidate}"
        return None, debug_imgs

    meta.update({
        "success": True,
        "bbox": refined_full,
        "candidate_bbox": refined_full,
        "final_bbox": refined_full,
        "mask_available": True,
        "mask_applied": selected_mode == "masked_object",
        "selected_components": len(selected_labels),
        "iou_with_ai": float(iou),
        "center_distance_ratio": float(center_ratio),
        "area_ratio": float(area_ratio),
        "fallback_reason": None,
    })
    debug_imgs.update({
        "perspective_red_mask": red_mask,
        "perspective_text_grid_mask": text_grid_mask,
        "perspective_model_candidate_mask": model_mask,
        "perspective_selected_mask": selected_mask,
    })

    if selected_mode == "masked_object":
        crop_original = roi[crop_y1:crop_y2, crop_x1:crop_x2]
        crop_mask = selected_mask[crop_y1:crop_y2, crop_x1:crop_x2]
        masked_crop = np.full_like(crop_original, PERSPECTIVE_BACKGROUND_VALUE)
        masked_crop[crop_mask > 0] = crop_original[crop_mask > 0]
        debug_imgs["_masked_object_crop"] = masked_crop

    return refined_full, debug_imgs


# =============================================================================
# VẼ BOUNDING BOX
# =============================================================================

def draw_results_on_image(
    img_bgr: np.ndarray,
    panel_bbox_px: Optional[BBox],
    ai_obj_bbox_px: Optional[BBox],
    refined_obj_bbox_px: Optional[BBox],
    center_px: Optional[List[float]],
    target_view: str = "FRONT",
) -> np.ndarray:
    """
    Vẽ tất cả bounding box và tâm lên ảnh.
    """
    result = img_bgr.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX

    def draw_box(bbox, color, label):
        if bbox is None:
            return
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        cv2.rectangle(result, (x1, y1), (x2, y2), color, BOX_THICKNESS)
        (tw, th), _ = cv2.getTextSize(label, font, FONT_SCALE, FONT_THICKNESS)
        cv2.rectangle(result, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            result, label, (x1 + 2, y1 - 4),
            font, FONT_SCALE, (255, 255, 255), FONT_THICKNESS, cv2.LINE_AA
        )

    draw_box(panel_bbox_px, COLOR_PANEL, f"{target_view.upper()} Panel")
    draw_box(ai_obj_bbox_px, COLOR_AI_OBJECT, "AI Object")
    draw_box(refined_obj_bbox_px, COLOR_REFINED_OBJECT, "Refined Object")

    if center_px is not None:
        cx, cy = int(round(center_px[0])), int(round(center_px[1]))
        cv2.circle(result, (cx, cy), 6, COLOR_CENTER, -1)
        cv2.drawMarker(result, (cx, cy), COLOR_CENTER,
                       cv2.MARKER_CROSS, 20, 2)

    return result


# =============================================================================
# PIPELINE CHÍNH
# =============================================================================

def process_image(
    image_path: Path,
    ai_response: dict,
    model_name: str,
    coord_scale_type: str,
    enable_refine: bool = ENABLE_OPENCV_REFINE,
    target_view: str = "FRONT",
    save_json: bool = True,
    output_dir: Optional[Path] = None,
) -> dict:
    """
    Pipeline xử lý ảnh hoàn chỉnh.

    Trả về dict kết quả (cũng là nội dung JSON output).
    """
    start_time = time.time()
    stem = image_path.stem
    active_output_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    active_debug_dir = (
        active_output_dir / "debug"
        if output_dir is not None
        else DEBUG_DIR
    )
    output_base = active_output_dir / stem
    debug_base = active_debug_dir / stem

    # ---- Đọc ảnh ----
    width, height = read_image_size(image_path)
    logger.info(f"Kích thước ảnh: {width} x {height} px")
    img_bgr = load_cv2_image(image_path)

    # ---- Validate AI response trước khi chuyển pixel ----
    ok_val, val_errs = bu.validate_view_payload(ai_response)
    if not ok_val:
        err_msg = f"AI response không hợp lệ cho view '{target_view}': " + "; ".join(val_errs)
        logger.error(err_msg)
        raise ValueError(err_msg)

    # ---- Lấy tọa độ chuẩn hóa từ AI ----
    panel_norm = ai_response.get("panel_bbox", [])
    obj_norm = ai_response.get("object_bbox", [])
    center_norm = ai_response.get("object_center", [])

    # ---- Chuyển sang pixel ----
    scale = 1000.0
    panel_px = bu.normalized_bbox_to_pixel(panel_norm, width, height, scale)
    obj_px = bu.normalized_bbox_to_pixel(obj_norm, width, height, scale)
    center_px = bu.normalized_point_to_pixel(center_norm, width, height, scale)

    panel_px = bu.clamp_pixel_bbox(panel_px, width, height)
    obj_px = bu.clamp_pixel_bbox(obj_px, width, height)

    panel_int = bu.pixel_bbox_to_int(panel_px)
    obj_int = bu.pixel_bbox_to_int(obj_px)
    center_int = [int(round(center_px[0])), int(round(center_px[1]))]

    logger.info(f"Panel pixel (AI): {panel_int}")
    logger.info(f"Object pixel (AI): {obj_int}")
    logger.info(f"Center pixel: {center_int}")

    refine_warnings: List[str] = []

    # ---- OpenCV refine panel ----
    refined_panel_px = panel_px[:]
    opencv_panel_success = False
    opencv_debug_panel = {}

    if enable_refine and target_view.upper() != "PERSPECTIVE":
        refined, dbg = refine_panel_bbox_opencv(img_bgr, panel_px)
        opencv_debug_panel = dbg
        if refined is not None:
            ok_panel, msg_panel = bu.validate_pixel_bbox(refined, width, height, "refined_panel_bbox")
            if ok_panel:
                refined_panel_px = refined
                opencv_panel_success = True
                logger.info(f"Panel refined (OpenCV): {bu.pixel_bbox_to_int(refined_panel_px)}")
            else:
                logger.warning(f"Refined panel bbox không hợp lệ ({msg_panel}). Giữ bbox AI.")
                refined_panel_px = panel_px[:]
                if "meta" in opencv_debug_panel:
                    opencv_debug_panel["meta"]["success"] = False
                    opencv_debug_panel["meta"]["final_bbox"] = [float(v) for v in panel_px]
                    opencv_debug_panel["meta"]["fallback_reason"] = f"candidate_bbox_invalid: {msg_panel}"
                refine_warnings.append(f"Panel refine bị từ chối: {msg_panel}")
        else:
            logger.info("Panel refine không thành công, dùng bbox AI.")

    # Panel ở hàng cuối thường kết thúc sát đáy trang. Nếu AI đã đặt panel gần
    # đáy nhưng contour dừng tại mép search ROI, dùng đáy ảnh làm giới hạn tìm
    # kiếm; clean_panel_crop vẫn loại đường viền bảng nếu có.
    if enable_refine and target_view.upper() != "PERSPECTIVE":
        bottom_gap = max(0.0, float(height) - float(panel_px[3]))
        bottom_edge_snap = (
            bottom_gap <= float(height) * float(PANEL_BOTTOM_EDGE_SNAP_RATIO)
        )
        panel_before_edge_snap = [float(v) for v in refined_panel_px]
        if bottom_edge_snap:
            refined_panel_px = [
                float(refined_panel_px[0]),
                float(refined_panel_px[1]),
                float(refined_panel_px[2]),
                float(height),
            ]
        if "meta" in opencv_debug_panel:
            opencv_debug_panel["meta"]["pre_bottom_edge_snap_bbox"] = (
                panel_before_edge_snap
            )
            opencv_debug_panel["meta"]["bottom_edge_snap_ratio"] = float(
                PANEL_BOTTOM_EDGE_SNAP_RATIO
            )
            opencv_debug_panel["meta"]["bottom_edge_snap_applied"] = (
                bottom_edge_snap
            )
            opencv_debug_panel["meta"]["final_bbox"] = [
                float(v) for v in refined_panel_px
            ]
        if bottom_edge_snap:
            logger.info(
                "Panel bottom-edge snap: %s -> %s",
                bu.pixel_bbox_to_int(panel_before_edge_snap),
                bu.pixel_bbox_to_int(refined_panel_px),
            )

    # ---- Crop panel ----
    px1, py1, px2, py2 = bu.pixel_bbox_to_int(refined_panel_px)
    px1 = max(0, px1); py1 = max(0, py1)
    px2 = min(width, px2); py2 = min(height, py2)
    panel_crop_raw = img_bgr[py1:py2, px1:px2].copy()

    # ---- Clean panel crop ----
    panel_crop_clean = panel_crop_raw.copy()
    clean_panel_info = {}
    clean_px1, clean_py1 = px1, py1
    
    if panel_crop_raw.size > 0 and target_view.upper() != "PERSPECTIVE":
        panel_crop_clean, clean_panel_info = clean_panel_crop(panel_crop_raw)
        trim = clean_panel_info.get("trim", {"left": 0, "top": 0})
        clean_px1 = px1 + trim["left"]
        clean_py1 = py1 + trim["top"]

    # ---- Tọa độ object trong hệ clean panel ----
    ai_obj_in_clean_panel = [
        obj_px[0] - clean_px1,
        obj_px[1] - clean_py1,
        obj_px[2] - clean_px1,
        obj_px[3] - clean_py1,
    ]

    # ---- OpenCV refine object ----
    refined_obj_px = obj_px[:]
    opencv_obj_success = False
    opencv_debug_obj = {}

    if enable_refine:
        if target_view.upper() == "PERSPECTIVE":
            refined_obj_full, dbg2 = refine_perspective_object_opencv(
                img_bgr,
                obj_px,
                width,
                height,
                panel_bbox_px=panel_px,
            )
        elif panel_crop_clean.size > 0:
            refined_obj_full, dbg2 = refine_object_bbox_opencv(
                panel_crop_clean,
                ai_obj_in_clean_panel,
                (clean_px1, clean_py1),
                width, height,
            )
        else:
            refined_obj_full, dbg2 = None, {}

        opencv_debug_obj = dbg2
        if refined_obj_full is not None:
            ok_obj, msg_obj = bu.validate_pixel_bbox(refined_obj_full, width, height, "refined_object_bbox")
            wants_perspective_mask = (
                target_view.upper() == "PERSPECTIVE"
                and opencv_debug_obj.get("meta", {}).get("mode") == "masked_object"
            )
            masked_crop = opencv_debug_obj.get("_masked_object_crop")
            mask_ready = (
                isinstance(masked_crop, np.ndarray)
                and masked_crop.size > 0
            )
            if ok_obj and wants_perspective_mask and not mask_ready:
                ok_obj = False
                msg_obj = "perspective_mask_missing"
            if ok_obj:
                refined_obj_px = refined_obj_full
                opencv_obj_success = True
                logger.info(f"Object refined (OpenCV Trim): {bu.pixel_bbox_to_int(refined_obj_px)}")
            else:
                logger.warning(f"Refined object bbox không hợp lệ ({msg_obj}). Giữ bbox AI.")
                refined_obj_px = obj_px[:]
                if "meta" in opencv_debug_obj:
                    opencv_debug_obj["meta"]["success"] = False
                    opencv_debug_obj["meta"]["final_bbox"] = [float(v) for v in obj_px]
                    opencv_debug_obj["meta"]["fallback_reason"] = f"candidate_bbox_invalid: {msg_obj}"
                refine_warnings.append(f"Object refine bị từ chối: {msg_obj}")
        else:
            logger.info("Object trim không thành công, dùng bbox AI gốc.")

    # ---- Validate pixel bbox ----
    warnings: List[str] = list(refine_warnings)
    ok1, m1 = bu.validate_pixel_bbox(panel_px, width, height, "panel_bbox")
    ok2, m2 = bu.validate_pixel_bbox(obj_px, width, height, "object_bbox")
    if not ok1:
        warnings.append(m1)
    if not ok2:
        warnings.append(m2)

    ok_ref_panel, m_ref_p = bu.validate_pixel_bbox(refined_panel_px, width, height, "refined_panel_bbox")
    ok_ref_obj, m_ref_o = bu.validate_pixel_bbox(refined_obj_px, width, height, "refined_object_bbox")
    if not ok_ref_panel and ok_ref_panel != ok1:
        warnings.append(m_ref_p)
    if not ok_ref_obj and ok_ref_obj != ok2:
        warnings.append(m_ref_o)

    all_valid = ok1 and ok2

    # ---- Vẽ kết quả ----
    result_img = draw_results_on_image(
        img_bgr,
        refined_panel_px,
        obj_px,
        refined_obj_px if opencv_obj_success else None,
        center_px,
        target_view,
    )

    # ---- Crop object ----
    ro_x1, ro_y1, ro_x2, ro_y2 = bu.pixel_bbox_to_int(refined_obj_px)
    ro_x1 = max(0, ro_x1); ro_y1 = max(0, ro_y1)
    ro_x2 = min(width, ro_x2); ro_y2 = min(height, ro_y2)
    object_crop = img_bgr[ro_y1:ro_y2, ro_x1:ro_x2].copy()
    if (
        target_view.upper() == "PERSPECTIVE"
        and opencv_obj_success
        and opencv_debug_obj.get("meta", {}).get("mode") == "masked_object"
    ):
        masked_crop = opencv_debug_obj.get("_masked_object_crop")
        if isinstance(masked_crop, np.ndarray) and masked_crop.size > 0:
            object_crop = masked_crop.copy()
    # ---- Lưu ảnh ----
    output_base.parent.mkdir(parents=True, exist_ok=True)
    
    preview_dir = active_output_dir / ".preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    result_path = preview_dir / f"{stem}_{target_view.lower()}_result.jpg"
    panel_path = preview_dir / f"{stem}_{target_view.lower()}_panel.png"
    object_path = active_output_dir / f"{stem}_{target_view.lower()}_object.png"

    output_files = {
        "result_image": None,
        "panel_image": None,
        "object_image": None,
    }

    if save_cv2_image(result_img, result_path):
        output_files["result_image"] = str(result_path)
        logger.info(f"Đã lưu ảnh kết quả: {result_path.name}")
    else:
        logger.warning(f"Không lưu được ảnh kết quả: {result_path.name}")
        warnings.append(f"Không lưu được result_image: {result_path}")

    if panel_crop_clean.size > 0:
        if save_cv2_image(panel_crop_clean, panel_path):
            output_files["panel_image"] = str(panel_path)
        else:
            warnings.append(f"Không lưu được panel_image: {panel_path}")
    else:
        warnings.append("Panel crop rỗng; không lưu panel_image")

    if object_crop.size > 0:
        if save_cv2_image(object_crop, object_path):
            output_files["object_image"] = str(object_path)
        else:
            warnings.append(f"Không lưu được object_image: {object_path}")
    else:
        warnings.append("Object crop rỗng; không lưu object_image")

    # ---- Debug images ----
    if DEBUG_MODE:
        debug_base.mkdir(parents=True, exist_ok=True)
        for name, dimg in {**opencv_debug_panel, **opencv_debug_obj}.items():
            if dimg is not None and isinstance(dimg, np.ndarray) and dimg.size > 0:
                save_cv2_image(
                    dimg if len(dimg.shape) == 3 else cv2.cvtColor(dimg, cv2.COLOR_GRAY2BGR),
                    debug_base / f"{name}.jpg"
                )

    # ---- Xây dựng kết quả JSON ----
    elapsed = time.time() - start_time
    logger.info(f"Tổng thời gian xử lý: {elapsed:.2f}s")

    panel_thresholds = {
        "min_iou": float(MIN_IOU_THRESHOLD),
        "max_center_distance_ratio": float(MAX_CENTER_DISTANCE_RATIO),
        "prefilter_max_center_distance_ratio": float(PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO),
        "min_contour_area": int(PANEL_CONTOUR_MIN_AREA),
    }
    object_thresholds = {
        "min_iou": float(OBJECT_MIN_IOU_THRESHOLD),
        "max_center_distance_ratio": float(OBJECT_MAX_CENTER_DISTANCE_RATIO),
        "min_area_ratio": float(OBJECT_MIN_AREA_RATIO),
        "max_area_ratio": float(OBJECT_MAX_AREA_RATIO),
        "min_contour_area": int(OBJECT_MIN_CONTOUR_AREA),
        "search_margin_ratio": float(OBJECT_SEARCH_MARGIN_RATIO),
    }
    is_perspective = target_view.upper() == "PERSPECTIVE"
    panel_meta = _normalize_refine_meta(
        opencv_debug_panel.get("meta"),
        attempted=enable_refine and not is_perspective,
        success=opencv_panel_success,
        method="opencv" if enable_refine and not is_perspective else "none",
        ai_bbox=panel_px,
        final_bbox=refined_panel_px,
        thresholds=panel_thresholds,
        fallback_reason=(
            "disabled_by_config"
            if not enable_refine
            else "perspective_special_handling"
            if is_perspective
            else "no_matching_contour_found"
        ),
    )
    object_meta = _normalize_refine_meta(
        opencv_debug_obj.get("meta"),
        attempted=enable_refine,
        success=opencv_obj_success,
        method="perspective_opencv" if is_perspective and enable_refine else "opencv" if enable_refine else "none",
        ai_bbox=obj_px,
        final_bbox=refined_obj_px,
        thresholds={} if is_perspective else object_thresholds,
        fallback_reason="disabled_by_config" if not enable_refine else "no_refined_candidate",
    )

    result_json = {
        "source_image": str(image_path),
        "image_size": {"width": width, "height": height},
        "model": model_name,
        "coordinate_input_type": coord_scale_type,
        "processing_time_sec": round(elapsed, 2),
        "normalized": {
            "panel_bbox": panel_norm,
            "object_bbox": obj_norm,
            "object_center": center_norm,
        },
        "pixel": {
            "ai_panel_bbox": panel_int,
            "refined_panel_bbox": bu.pixel_bbox_to_int(refined_panel_px),
            "ai_object_bbox": obj_int,
            "refined_object_bbox": bu.pixel_bbox_to_int(refined_obj_px),
            "object_center": center_int,
        },
        "opencv": {
            "panel_refine_success": opencv_panel_success,
            "object_refine_success": opencv_obj_success,
            "panel_meta": panel_meta,
            "object_meta": object_meta,
        },
        "clean_panel": clean_panel_info,
        "output_files": output_files,
        "validation": {
            "valid": bool(all_valid and ok_ref_panel and ok_ref_obj and (object_crop.size > 0)),
            "warnings": warnings,
            "ai_bbox_valid": bool(ok1 and ok2),
            "refined_panel_bbox_valid": bool(ok_ref_panel),
            "refined_object_bbox_valid": bool(ok_ref_obj),
            "object_crop_valid": bool(object_crop.size > 0),
        },
    }

    if save_json:
        json_path = preview_dir / f"{stem}_{target_view.lower()}_result.json"
        result_json["output_files"]["json"] = str(json_path)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result_json, f, ensure_ascii=False, indent=2)
            if not json_path.is_file() or json_path.stat().st_size <= 0:
                raise OSError("JSON file không tồn tại hoặc rỗng sau khi ghi")
            logger.info(f"Đã lưu JSON: {json_path.name}")
        except (OSError, TypeError) as exc:
            result_json["output_files"].pop("json", None)
            warnings.append(f"Không lưu được JSON: {json_path} ({exc})")
            logger.error(f"Không lưu được JSON {json_path}: {exc}")

    return result_json
