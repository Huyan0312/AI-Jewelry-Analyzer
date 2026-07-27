"""
dimension_crop.py  (STANDALONE - chua gan vao pipeline)

Muc dich:
    Cho 1 anh ban ve trang suc + 1 gia tri kich thuoc cu the (vd "6.5"),
    tool se:
      1. Nho LM Studio Vision AI tim dung duong kich thuoc do
         (so + mui ten + doan ma no do).
      2. Crop VUNG VAT THE ma kich thuoc do dang do (object_segment_bbox),
         khong phai ca vat the.
      3. Luu anh crop + anh annotated de kiem tra bang mat.

Cach dung:
    python dimension_crop.py <duong_dan_anh> <gia_tri_kich_thuoc> [tuy chon]

Vi du:
    python dimension_crop.py output/889524-A.jpg 6.5
    python dimension_crop.py output/889524-A.jpg 11.40 --view FRONT --pad 12

Yeu cau: LM Studio dang chay + da load 1 model vision (vd qwen3-vl).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import requests

import bbox_utils as bu
from config import LMSTUDIO_BASE_URL, REQUEST_TIMEOUT
from image_processor import load_cv2_image, save_cv2_image, read_image_size
from lmstudio_client import (
    encode_image_to_base64_url,
    extract_json_safe,
    get_loaded_models,
)
from logger_utils import get_logger

logger = get_logger("dimension_crop")

OUTPUT_DIR = Path(__file__).parent / "output" / ".preview"


# =============================================================================
# PROMPT CHUYEN BIET
# =============================================================================

def build_prompt(dimension_value: str, view: Optional[str]) -> str:
    view_hint = ""
    if view:
        view_hint = (
            f"\nThe target dimension is located inside the {view.upper()} view panel. "
            f"If the same number appears in several views, choose the one in {view.upper()}."
        )

    return f"""You are analyzing a technical jewelry drawing that contains several views
(FRONT, LEFT, RIGHT, TOP, BOTTOM, BACK, PERSPECTIVE). Each view has red dimension
lines (arrows) with measurement numbers such as 11.40, 3.60, 0.50.

TASK: Find the specific dimension measurement with value "{dimension_value}".{view_hint}

A dimension consists of:
- A measurement number (red text), e.g. "{dimension_value}".
- A dimension line with an arrowhead at EACH END. The two arrowheads touch the
  two extreme edges of the jewelry part being measured.

CRITICAL RULES about the dimension_line:
- The dimension_line MUST connect the TWO ARROWHEADS (the measured span), NOT
  the number text.
- If this dimension measures WIDTH (horizontal), the two arrowheads are on the
  LEFT edge and RIGHT edge of the part. The line is roughly horizontal:
  x1 < x2 and y1 == y2.
- If this dimension measures HEIGHT (vertical), the two arrowheads are on the
  TOP edge and BOTTOM edge of the part. The line is roughly vertical:
  y1 < y2 and x1 == x2.
- HEIGHT numbers are usually ROTATED 90 degrees and placed on the LEFT or RIGHT
  side of the view. If the number "{dimension_value}" looks rotated/vertical,
  it is a VERTICAL (height) dimension: return a vertical dimension_line that goes
  from the TOP of the jewelry part down to the BOTTOM of that part.
- Do NOT draw the line from the jewelry to the number label.

Return coordinates normalized 0..1000 relative to the WHOLE original image
(top-left = [0,0], bottom-right = [1000,1000], bbox format [x1,y1,x2,y2]):

- found: true/false (whether you found the number "{dimension_value}").
- view: which view it belongs to (FRONT/LEFT/.../PERSPECTIVE).
- orientation: "vertical" if it measures height (top-to-bottom), "horizontal"
  if it measures width (left-to-right).
- text_bbox: tight bbox around the measurement number "{dimension_value}".
- dimension_line: [x1,y1,x2,y2] connecting the two arrowheads (the measured span).
- object_segment_bbox: tight bbox of the PART OF THE JEWELRY OBJECT that this
  dimension is measuring, aligned with the two arrowheads. Exclude the number
  text and empty white space.

Return ONLY valid JSON, no markdown, no explanation:

{{
  "found": true,
  "view": "FRONT",
  "value": "{dimension_value}",
  "orientation": "vertical",
  "text_bbox": [x1, y1, x2, y2],
  "dimension_line": [x1, y1, x2, y2],
  "object_segment_bbox": [x1, y1, x2, y2]
}}"""


# =============================================================================
# GOI AI
# =============================================================================

def query_dimension(image_path: Path, dimension_value: str, model: str,
                    view: Optional[str]) -> Optional[dict]:
    data_url = encode_image_to_base64_url(image_path)
    prompt = build_prompt(dimension_value, view)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 500,
    }

    endpoint = f"{LMSTUDIO_BASE_URL.rstrip('/')}/chat/completions"
    logger.info(f"Gui request tim kich thuoc '{dimension_value}' toi model '{model}'...")
    resp = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT,
                         headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = extract_json_safe(raw)
    if parsed is None:
        logger.error(f"Khong parse duoc JSON. Raw:\n{raw[:400]}")
    return parsed


# =============================================================================
# OPENCV: BAM SAT VAT THE (KIM LOAI VANG) THEO CHIEU DO
# =============================================================================

def _gold_object_mask(img_bgr: np.ndarray) -> np.ndarray:
    """Mask cua phan kim loai vang (than mon trang suc). Bo qua nen trang, net do."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # Vang/nau (hue ~10-45) voi do bao hoa & sang du lon
    gold = cv2.inRange(hsv, (10, 40, 40), (45, 255, 255))
    # Chi lam sach nhieu nho, KHONG no khung (giu bien sat vat the)
    gold = cv2.morphologyEx(gold, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    return gold


def _red_mask(img_bgr: np.ndarray) -> np.ndarray:
    """Mask cac net do (duong kich thuoc, mui ten, so do)."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    r1 = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
    r2 = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
    return cv2.bitwise_or(r1, r2)


def measure_red_span(img_bgr: np.ndarray,
                     search_box: Tuple[int, int, int, int],
                     orientation: str) -> Optional[Tuple[int, int, int]]:
    """
    Do chinh xac doan cua DUONG KICH THUOC MAU DO trong vung tim.
    Tra ve (span_min, span_max, perp_center) theo chieu do, hoac None.
      - horizontal: (x_min, x_max, y_center) cua duong do dai nhat.
      - vertical:   (y_min, y_max, x_center).
    """
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = search_box
    x1 = max(0, int(x1)); y1 = max(0, int(y1))
    x2 = min(w, int(x2)); y2 = min(h, int(y2))
    if x2 - x1 < 5 or y2 - y1 < 5:
        return None

    red = _red_mask(img_bgr)[y1:y2, x1:x2]
    rh, rw = red.shape[:2]

    if orientation == "horizontal":
        klen = max(15, int(rw * 0.25))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (klen, 1))
        lines = cv2.morphologyEx(red, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_len = 0
        for c in contours:
            bx, by, bw, bh = cv2.boundingRect(c)
            if bw > best_len:
                best_len = bw
                best = (bx, by, bw, bh)
        if best is None:
            return None
        bx, by, bw, bh = best
        return (x1 + bx, x1 + bx + bw, y1 + by + bh // 2)

    else:  # vertical
        klen = max(15, int(rh * 0.25))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, klen))
        lines = cv2.morphologyEx(red, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_len = 0
        for c in contours:
            bx, by, bw, bh = cv2.boundingRect(c)
            if bh > best_len:
                best_len = bh
                best = (bx, by, bw, bh)
        if best is None:
            return None
        bx, by, bw, bh = best
        return (y1 + by, y1 + by + bh, x1 + bx + bw // 2)


def refine_with_measured_span(mask: np.ndarray, orientation: str,
                              span_min: int, span_max: int,
                              perp_hint: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Chieu do: GIU DUNG span (span_min..span_max) de khung trung khit duong do.
    Chieu vuong goc: lay bien that cua kim loai (grow + tighten).
    """
    h, w = mask.shape[:2]
    if span_max - span_min < 3:
        return None

    if orientation == "horizontal":
        x1 = max(0, span_min); x2 = min(w, span_max)
        band = mask[:, x1:x2]
        span = x2 - x1
        flags = (band.sum(axis=1) / 255.0) > (0.08 * span)
        gap_tol = max(20, int(span * 0.35))
        run = _grow_object_run(flags, perp_hint, gap_tol)
        if run is None:
            return None
        top, bot = run
        # Chieu vuong goc siet theo vang; chieu do GIU nguyen span do
        tight = _tighten_to_gold(mask, x1, top, x2, bot)
        if tight is None:
            return (x1, top, x2, bot)
        return (x1, tight[1], x2, tight[3])

    else:  # vertical
        y1 = max(0, span_min); y2 = min(h, span_max)
        band = mask[y1:y2, :]
        span = y2 - y1
        flags = (band.sum(axis=0) / 255.0) > (0.08 * span)
        gap_tol = max(20, int(span * 0.35))
        run = _grow_object_run(flags, perp_hint, gap_tol)
        if run is None:
            return None
        left, right = run
        tight = _tighten_to_gold(mask, left, y1, right, y2)
        if tight is None:
            return (left, y1, right, y2)
        return (tight[0], y1, tight[2], y2)


def _grow_object_run(flags: np.ndarray, anchor: int,
                     gap_tol: int = 30) -> Optional[Tuple[int, int]]:
    """
    Tu diem 'anchor', tim hat giong (pixel vat the gan nhat) roi lan ra 2 phia,
    bo qua cac khe nho trong vat the (<= gap_tol) nhung dung o khe lon
    (khoang trang giua cac view). Tra ve (start, end) inclusive.
    """
    idx = np.where(flags)[0]
    if idx.size == 0:
        return None
    seed = int(idx[np.argmin(np.abs(idx - anchor))])
    n = len(flags)

    top = seed
    gap = 0
    i = seed
    while i >= 0:
        if flags[i]:
            top = i
            gap = 0
        else:
            gap += 1
            if gap > gap_tol:
                break
        i -= 1

    bot = seed
    gap = 0
    i = seed
    while i < n:
        if flags[i]:
            bot = i
            gap = 0
        else:
            gap += 1
            if gap > gap_tol:
                break
        i += 1

    return top, bot


def refine_segment_with_object(
    img_bgr: np.ndarray,
    line_px: Tuple[int, int, int, int],
    orientation: str,
) -> Optional[Tuple[int, int, int, int]]:
    """
    Dung mask kim loai vang de bam sat vat the theo chieu do:
      - Chieu do (theo mui ten): giu nguyen doan giua 2 mui ten.
      - Chieu vuong goc: lay bien that cua kim loai.
    """
    h, w = img_bgr.shape[:2]
    lx1, ly1, lx2, ly2 = line_px
    lx1, lx2 = sorted((int(lx1), int(lx2)))
    ly1, ly2 = sorted((int(ly1), int(ly2)))
    lx1 = max(0, lx1); lx2 = min(w, lx2)
    ly1 = max(0, ly1); ly2 = min(h, ly2)

    mask = _gold_object_mask(img_bgr)

    if orientation == "horizontal":
        if lx2 - lx1 < 3:
            return None
        band = mask[:, lx1:lx2]
        span = lx2 - lx1
        row_gold = band.sum(axis=1) / 255.0
        flags = row_gold > (0.08 * span)   # >=8% chieu rong la co kim loai
        anchor = (ly1 + ly2) // 2
        gap_tol = max(20, int(span * 0.35))
        run = _grow_object_run(flags, anchor, gap_tol)
        if run is None:
            return None
        top, bot = run
        # Siet ve bien kim loai that trong vung [lx1,lx2] x [top,bot]
        return _tighten_to_gold(mask, lx1, top, lx2, bot)

    else:  # vertical
        if ly2 - ly1 < 3:
            return None
        band = mask[ly1:ly2, :]
        span = ly2 - ly1
        col_gold = band.sum(axis=0) / 255.0
        flags = col_gold > (0.08 * span)
        anchor = (lx1 + lx2) // 2
        gap_tol = max(20, int(span * 0.35))
        run = _grow_object_run(flags, anchor, gap_tol)
        if run is None:
            return None
        left, right = run
        return _tighten_to_gold(mask, left, ly1, right, ly2)


def _tighten_to_gold(mask: np.ndarray, x1: int, y1: int, x2: int, y2: int,
                     min_pixels: int = 20) -> Optional[Tuple[int, int, int, int]]:
    """Siet khung ve dung bounding box cua kim loai vang ben trong vung cho."""
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(mask.shape[1], x2); y2 = min(mask.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return None
    region = mask[y1:y2, x1:x2]
    ys, xs = np.where(region > 0)
    if xs.size < min_pixels:
        return None
    gx1 = x1 + int(xs.min())
    gx2 = x1 + int(xs.max()) + 1
    gy1 = y1 + int(ys.min())
    gy2 = y1 + int(ys.max()) + 1
    return (gx1, gy1, gx2, gy2)


# =============================================================================
# XU LY + CROP
# =============================================================================

def _arrow_usable(line_px, orientation: str, w: int, h: int) -> bool:
    """Mui ten co dung duoc cho huong do khong (du dai + dung chieu)."""
    if not line_px:
        return False
    x1, y1, x2, y2 = line_px
    xspan = abs(x2 - x1)
    yspan = abs(y2 - y1)
    if orientation == "horizontal":
        return xspan > yspan and xspan >= 0.03 * w
    else:
        return yspan > xspan and yspan >= 0.03 * h


def _expand_bbox(box, ratio, w, h):
    x1, y1, x2, y2 = box
    dw = int((x2 - x1) * ratio)
    dh = int((y2 - y1) * ratio)
    return (max(0, x1 - dw), max(0, y1 - dh),
            min(w, x2 + dw), min(h, y2 + dh))


def _union_box(a, b):
    """Gop 2 bbox (bo qua cai None). Tra ve None neu ca hai None."""
    boxes = [x for x in (a, b) if x is not None]
    if not boxes:
        return None
    x1 = min(x[0] for x in boxes)
    y1 = min(x[1] for x in boxes)
    x2 = max(x[2] for x in boxes)
    y2 = max(x[3] for x in boxes)
    return (x1, y1, x2, y2)


def _infer_orientation(result: dict, w: int, h: int) -> Optional[str]:
    """
    Suy huong do tu hinh hoc:
      - So do chieu cao thuong bi xoay 90 do -> text_bbox cao hon rong.
      - Neu khong ro, dua vao ty le duong mui ten.
    """
    text = result.get("text_bbox")
    if isinstance(text, (list, tuple)) and len(text) == 4:
        tw = (text[2] - text[0]) / 1000.0 * w
        th = (text[3] - text[1]) / 1000.0 * h
        if th > tw * 1.3:
            return "vertical"
        if tw > th * 1.3:
            return "horizontal"

    line = result.get("dimension_line")
    if isinstance(line, (list, tuple)) and len(line) == 4:
        lw = abs(line[2] - line[0]) / 1000.0 * w
        lh = abs(line[3] - line[1]) / 1000.0 * h
        if lh > lw * 1.3:
            return "vertical"
        if lw > lh * 1.3:
            return "horizontal"
    return None


def resolve_model(model_arg: Optional[str]) -> str:
    if model_arg:
        return model_arg
    models = get_loaded_models(LMSTUDIO_BASE_URL)
    if not models:
        raise RuntimeError(
            "LM Studio chua load model nao (hoac chua bat Local Server). "
            "Vui long mo LM Studio va load 1 model vision."
        )
    logger.info(f"Tu dong dung model dang load: {models[0]}")
    return models[0]


def crop_by_dimension(image_path: Path, dimension_value: str,
                      model_arg: Optional[str] = None,
                      view: Optional[str] = None,
                      pad: int = 0) -> Optional[dict]:
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Khong tim thay anh: {image_path}")

    width, height = read_image_size(image_path)
    logger.info(f"Anh: {image_path.name} ({width}x{height})")

    model = resolve_model(model_arg)
    result = query_dimension(image_path, dimension_value, model, view)

    if not result or not result.get("found"):
        logger.error(f"Khong tim thay kich thuoc '{dimension_value}' trong anh.")
        return None

    orientation = str(result.get("orientation", "horizontal")).lower()
    if orientation not in ("horizontal", "vertical"):
        orientation = "horizontal"

    img = load_cv2_image(image_path)

    # Chuyen duong kich thuoc (mui ten) sang pixel
    line_norm = result.get("dimension_line", [])
    line_px = None
    if isinstance(line_norm, (list, tuple)) and len(line_norm) == 4:
        lp = bu.clamp_pixel_bbox(
            bu.normalized_bbox_to_pixel(line_norm, width, height), width, height
        )
        line_px = tuple(bu.pixel_bbox_to_int(lp))

    # Tu suy huong tu hinh hoc: uu tien so xoay (text cao hon rong) va mui ten
    inferred = _infer_orientation(result, width, height)
    if inferred and inferred != orientation:
        logger.info(f"Ghi de orientation AI: '{orientation}' -> '{inferred}' (theo hinh hoc)")
        orientation = inferred

    mask = _gold_object_mask(img)

    # --- Vung tim: gop duong AI + chu so, noi rong de chua duong do that ---
    text_px = None
    text_norm = result.get("text_bbox")
    if isinstance(text_norm, (list, tuple)) and len(text_norm) == 4:
        tp = bu.clamp_pixel_bbox(
            bu.normalized_bbox_to_pixel(text_norm, width, height), width, height
        )
        text_px = tuple(bu.pixel_bbox_to_int(tp))

    seg_hint_px = None
    seg_hint_norm = result.get("object_segment_bbox")
    if isinstance(seg_hint_norm, (list, tuple)) and len(seg_hint_norm) == 4:
        shp = bu.clamp_pixel_bbox(
            bu.normalized_bbox_to_pixel(seg_hint_norm, width, height), width, height
        )
        seg_hint_px = tuple(bu.pixel_bbox_to_int(shp))

    # Vung tim gom ca segment cua AI de phu du chieu do (nhat la kich thuoc doc)
    search_box = _union_box(_union_box(line_px, text_px), seg_hint_px)
    seg_px_int = None
    method = None

    # --- Uu tien 1: DO DUONG DO MAU DO THAT (trung khit line kich thuoc) ---
    if search_box is not None:
        sb = _expand_bbox(search_box, 0.8, width, height)
        red = measure_red_span(img, sb, orientation)
        if red is not None:
            span_min, span_max, perp = red
            seg_px_int = refine_with_measured_span(mask, orientation,
                                                   span_min, span_max, perp)
            if seg_px_int is not None:
                method = "red_line"

    # --- Uu tien 2: mui ten AI neu dung duoc cho huong do ---
    if seg_px_int is None and _arrow_usable(line_px, orientation, width, height):
        seg_px_int = refine_segment_with_object(img, line_px, orientation)
        if seg_px_int is not None:
            method = "opencv_arrow"

    if seg_px_int is None:
        logger.info("Khong dung duoc duong do/mui ten -> dung object_segment cua AI.")

    # --- Neu chua co: dung object_segment_bbox cua AI roi siet ve vang ---
    if seg_px_int is None:
        seg_norm = result.get("object_segment_bbox", [])
        if isinstance(seg_norm, (list, tuple)) and len(seg_norm) == 4:
            seg_px = bu.clamp_pixel_bbox(
                bu.normalized_bbox_to_pixel(seg_norm, width, height), width, height
            )
            ex1, ey1, ex2, ey2 = _expand_bbox(bu.pixel_bbox_to_int(seg_px),
                                              0.08, width, height)
            seg_px_int = _tighten_to_gold(mask, ex1, ey1, ex2, ey2)
            method = "opencv_segment"

    # --- Fallback cuoi: dung nguyen segment AI ---
    if seg_px_int is None:
        seg_norm = result.get("object_segment_bbox", [])
        if not isinstance(seg_norm, (list, tuple)) or len(seg_norm) != 4:
            logger.error("Khong bam duoc vat the va AI cung khong tra segment hop le.")
            return None
        seg_px = bu.clamp_pixel_bbox(
            bu.normalized_bbox_to_pixel(seg_norm, width, height), width, height
        )
        seg_px_int = tuple(bu.pixel_bbox_to_int(seg_px))
        method = "ai_fallback"
        logger.warning("OpenCV khong bam duoc kim loai, dung segment cua AI.")

    sx1, sy1, sx2, sy2 = seg_px_int
    sx1 = max(0, sx1 - pad); sy1 = max(0, sy1 - pad)
    sx2 = min(width, sx2 + pad); sy2 = min(height, sy2 + pad)

    if sx2 <= sx1 or sy2 <= sy1:
        logger.error(f"Vung crop rong: [{sx1},{sy1},{sx2},{sy2}]")
        return None

    crop = img[sy1:sy2, sx1:sx2].copy()

    # Anh annotated: ve segment cuoi + text_bbox + line
    annotated = img.copy()
    cv2.rectangle(annotated, (sx1, sy1), (sx2, sy2), (255, 80, 0), 2)
    cv2.putText(annotated, f"dim {dimension_value}", (sx1, max(0, sy1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 80, 0), 2, cv2.LINE_AA)
    _draw_norm_box(annotated, result.get("text_bbox"), width, height,
                   (0, 0, 255), None)
    _draw_norm_line(annotated, result.get("dimension_line"), width, height,
                    (0, 220, 255))

    # Luu
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_val = dimension_value.replace(".", "_")
    crop_path = OUTPUT_DIR / f"{image_path.stem}_dim_{safe_val}_crop.png"
    annot_path = OUTPUT_DIR / f"{image_path.stem}_dim_{safe_val}_annotated.jpg"

    save_cv2_image(crop, crop_path)
    save_cv2_image(annotated, annot_path)

    logger.info(f"View: {result.get('view')} | orientation: {orientation} | method: {method}")
    logger.info(f"Crop pixel: [{sx1},{sy1},{sx2},{sy2}]  size={sx2-sx1}x{sy2-sy1}")
    logger.info(f"Da luu crop:      {crop_path}")
    logger.info(f"Da luu annotated: {annot_path}")

    return {
        "value": dimension_value,
        "view": result.get("view"),
        "orientation": orientation,
        "method": method,
        "crop_bbox_px": [sx1, sy1, sx2, sy2],
        "crop_path": str(crop_path),
        "annotated_path": str(annot_path),
        "raw_ai": result,
    }


def _draw_norm_box(img, box_norm, w, h, color, label):
    if not isinstance(box_norm, (list, tuple)) or len(box_norm) != 4:
        return
    px = bu.pixel_bbox_to_int(
        bu.clamp_pixel_bbox(bu.normalized_bbox_to_pixel(box_norm, w, h), w, h)
    )
    cv2.rectangle(img, (px[0], px[1]), (px[2], px[3]), color, 2)
    if label:
        cv2.putText(img, label, (px[0], max(0, px[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)


def _draw_norm_line(img, line_norm, w, h, color):
    if not isinstance(line_norm, (list, tuple)) or len(line_norm) != 4:
        return
    x1 = int(round(line_norm[0] / 1000.0 * w))
    y1 = int(round(line_norm[1] / 1000.0 * h))
    x2 = int(round(line_norm[2] / 1000.0 * w))
    y2 = int(round(line_norm[3] / 1000.0 * h))
    cv2.arrowedLine(img, (x1, y1), (x2, y2), color, 2, tipLength=0.03)
    cv2.arrowedLine(img, (x2, y2), (x1, y1), color, 2, tipLength=0.03)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Crop vung vat the theo 1 kich thuoc cu the (dung LM Studio Vision AI)."
    )
    parser.add_argument("image", help="Duong dan anh ban ve trang suc")
    parser.add_argument("dimension", help="Gia tri kich thuoc can tim, vd 6.5 hoac 11.40")
    parser.add_argument("--view", default="FRONT",
                        help="Gioi han trong 1 view (mac dinh FRONT)")
    parser.add_argument("--model", default=None,
                        help="Ten model LM Studio (mac dinh: tu lay model dang load)")
    parser.add_argument("--pad", type=int, default=0,
                        help="So pixel padding them quanh vung crop (mac dinh 0 = sat khit)")
    args = parser.parse_args()

    try:
        result = crop_by_dimension(
            args.image, args.dimension,
            model_arg=args.model, view=args.view, pad=args.pad,
        )
    except Exception as e:
        logger.error(f"Loi: {e}")
        sys.exit(1)

    if result is None:
        sys.exit(2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
