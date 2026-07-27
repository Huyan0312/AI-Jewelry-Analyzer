"""
bbox_utils.py
Tất cả hàm xử lý bounding box: quy đổi, validate, tính toán.
"""

import math
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger("jewelry_detector.bbox")


# =============================================================================
# KIỂU DỮ LIỆU VÀ KHAI BÁO
# =============================================================================
BBox = List[float]          # [x1, y1, x2, y2]
Point = List[float]         # [x, y]

STANDARD_VIEWS = {"FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "BACK", "PERSPECTIVE"}


# =============================================================================
# VALIDATE
# =============================================================================

def validate_pixel_bbox(bbox: BBox, width: int, height: int, name: str = "bbox") -> Tuple[bool, str]:
    """
    Kiểm tra bbox trong hệ pixel.
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False, f"{name}: phải có đúng 4 phần tử"

    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return False, f"{name}: chứa giá trị không hợp lệ"

    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        return False, (
            f"{name}: bbox [{x1},{y1},{x2},{y2}] vượt ngoài ảnh [{width}x{height}]"
        )

    if x1 >= x2 or y1 >= y2:
        return False, f"{name}: x1>=x2 hoặc y1>=y2, bbox không hợp lệ"

    return True, ""


def validate_normalized_bbox(bbox: BBox, name: str = "bbox", scale: float = 1000.0) -> Tuple[bool, str]:
    """
    Kiểm tra bbox trong hệ chuẩn hóa (chứa 4 số thực hữu hạn, x1 < x2, y1 < y2, 0 <= coord <= scale).
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False, f"{name}: phải có đúng 4 phần tử"

    try:
        coords = []
        for v in bbox:
            if v is None:
                return False, f"{name}: chứa giá trị None"
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                return False, f"{name}: chứa giá trị NaN hoặc Infinity"
            coords.append(val)
        x1, y1, x2, y2 = coords
    except (TypeError, ValueError):
        return False, f"{name}: chứa giá trị không phải số"

    if any(v < 0 or v > scale for v in coords):
        return False, f"{name}: tọa độ phải nằm trong [0, {scale}] ([{x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}])"

    if x1 >= x2 or y1 >= y2:
        return False, f"{name}: x1 >= x2 hoặc y1 >= y2 ([{x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}])"

    return True, ""


def validate_normalized_point(point: Point, name: str = "point", scale: float = 1000.0) -> Tuple[bool, str]:
    """
    Kiểm tra point trong hệ chuẩn hóa (chứa 2 số thực hữu hạn, 0 <= coord <= scale).
    """
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        return False, f"{name}: phải có đúng 2 phần tử"

    try:
        coords = []
        for v in point:
            if v is None:
                return False, f"{name}: chứa giá trị None"
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                return False, f"{name}: chứa giá trị NaN hoặc Infinity"
            coords.append(val)
    except (TypeError, ValueError):
        return False, f"{name}: chứa giá trị không phải số"

    if any(v < 0 or v > scale for v in coords):
        return False, f"{name}: tọa độ phải nằm trong [0, {scale}] ([{coords[0]:.1f}, {coords[1]:.1f}])"

    return True, ""


def validate_view_payload(view_dict: dict, tolerance: float = 0.01) -> Tuple[bool, List[str]]:
    """
    Kiểm tra chi tiết 1 vùng view_dict:
    - Tên view thuộc STANDARD_VIEWS
    - coordinate_scale thuộc {100.0, 1000.0}
    - panel_bbox, object_bbox, object_center hợp lệ trong scale đó
    - object_bbox nằm trong panel_bbox (cho phép sai số tolerance)
    - object_center nằm trong object_bbox
    """
    errors = []
    if not isinstance(view_dict, dict):
        return False, ["view_payload: phải là dictionary"]

    vname = str(view_dict.get("view", "")).upper()
    if not vname or vname not in STANDARD_VIEWS:
        errors.append(f"view: Tên view '{view_dict.get('view')}' không hợp lệ. Phải thuộc {sorted(list(STANDARD_VIEWS))}")

    # Scale check
    raw_scale = view_dict.get("coordinate_scale", 1000)
    try:
        scale = float(raw_scale)
    except (TypeError, ValueError):
        errors.append(f"coordinate_scale: '{raw_scale}' không phải số")
        scale = 1000.0

    if scale not in (100.0, 1000.0):
        errors.append(f"coordinate_scale: {scale} không hợp lệ, chỉ chấp nhận 100 hoặc 1000")

    # Bbox checks
    panel = view_dict.get("panel_bbox")
    ok_p, err_p = validate_normalized_bbox(panel, "panel_bbox", scale=scale)
    if not ok_p:
        errors.append(err_p)

    obj = view_dict.get("object_bbox")
    ok_o, err_o = validate_normalized_bbox(obj, "object_bbox", scale=scale)
    if not ok_o:
        errors.append(err_o)

    center = view_dict.get("object_center")
    ok_c, err_c = validate_normalized_point(center, "object_center", scale=scale)
    if not ok_c:
        errors.append(err_c)

    # Containment checks if bboxes valid
    if ok_p and ok_o:
        px1, py1, px2, py2 = [float(v) for v in panel]
        ox1, oy1, ox2, oy2 = [float(v) for v in obj]
        pw = max(1.0, px2 - px1)
        ph = max(1.0, py2 - py1)
        tol_x = pw * tolerance
        tol_y = ph * tolerance

        if ox1 < px1 - tol_x or oy1 < py1 - tol_y or ox2 > px2 + tol_x or oy2 > py2 + tol_y:
            errors.append(
                f"object_bbox [{ox1:.1f}, {oy1:.1f}, {ox2:.1f}, {oy2:.1f}] vượt ngoài panel_bbox [{px1:.1f}, {py1:.1f}, {px2:.1f}, {py2:.1f}]"
            )

    if ok_o and ok_c:
        ox1, oy1, ox2, oy2 = [float(v) for v in obj]
        cx, cy = [float(v) for v in center]
        if cx < ox1 or cx > ox2 or cy < oy1 or cy > oy2:
            errors.append(
                f"object_center [{cx:.1f}, {cy:.1f}] nằm ngoài object_bbox [{ox1:.1f}, {oy1:.1f}, {ox2:.1f}, {oy2:.1f}]"
            )

    return len(errors) == 0, errors


def validate_all_views_schema(views_list: List[dict]) -> Tuple[bool, List[str], set]:
    """
    Kiểm tra danh sách 7 view trong all-views payload.
    Trả về (is_valid, error_list, found_views_set).
    """
    errors = []
    if not isinstance(views_list, list):
        return False, ["all_views: payload phải là danh sách (list)"], set()

    found_views = set()
    for idx, item in enumerate(views_list):
        if not isinstance(item, dict):
            errors.append(f"item[{idx}]: Không phải dictionary")
            continue

        raw_v = item.get("view")
        if not raw_v:
            errors.append(f"item[{idx}]: Thiếu trường 'view'")
            continue

        vname = str(raw_v).upper()
        if vname not in STANDARD_VIEWS:
            errors.append(f"item[{idx}]: Tên view lạ '{raw_v}'. Phải thuộc {sorted(list(STANDARD_VIEWS))}")
            continue

        if vname in found_views:
            errors.append(f"Trùng lặp view '{vname}' trong payload")
        else:
            found_views.add(vname)

        ok_v, errs_v = validate_view_payload(item)
        if not ok_v:
            for e in errs_v:
                errors.append(f"[{vname}] {e}")

    missing_views = STANDARD_VIEWS - found_views
    if missing_views:
        errors.append(f"Thiếu các view: {sorted(list(missing_views))}")

    return len(errors) == 0, errors, found_views


# =============================================================================
# CHUYỂN ĐỔI TỌA ĐỘ
# =============================================================================

def normalized_bbox_to_pixel(
    bbox: BBox,
    image_width: int,
    image_height: int,
    scale: float = 1000.0,
) -> BBox:
    """
    Chuyển bbox chuẩn hóa (0–scale) sang tọa độ pixel.
    pixel_x = normalized_x / scale * image_width
    """
    x1, y1, x2, y2 = bbox
    return [
        x1 / scale * image_width,
        y1 / scale * image_height,
        x2 / scale * image_width,
        y2 / scale * image_height,
    ]


def normalized_point_to_pixel(
    point: Point,
    image_width: int,
    image_height: int,
    scale: float = 1000.0,
) -> Point:
    """
    Chuyển điểm chuẩn hóa sang tọa độ pixel.
    """
    cx, cy = point
    return [cx / scale * image_width, cy / scale * image_height]


def pixel_bbox_to_int(bbox: BBox) -> List[int]:
    """Chuyển bbox float sang int (làm tròn về phía trong để an toàn)."""
    x1, y1, x2, y2 = bbox
    return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]


# =============================================================================
# PHÁT HIỆN HỆ TỌA ĐỘ 0-100 vs 0-1000
# =============================================================================

def detect_coordinate_scale(data: dict) -> Tuple[str, float]:
    """
    Phát hiện model trả tọa độ 0-100 hay 0-1000.

    Trả về:
        (scale_type, multiplier)
        scale_type: "normalized_0_1000" hoặc "normalized_0_100"
        multiplier: hệ số nhân để về 0-1000 (1.0 hoặc 10.0)
    """
    exp_scale = data.get("coordinate_scale")
    if exp_scale is not None:
        try:
            s_val = float(exp_scale)
            if s_val == 100.0:
                return "normalized_0_100", 10.0
            elif s_val == 1000.0:
                return "normalized_0_1000", 1.0
        except (TypeError, ValueError):
            pass

    all_values: List[float] = []
    for key in ("panel_bbox", "object_bbox", "object_center"):
        val = data.get(key, [])
        if isinstance(val, (list, tuple)):
            for v in val:
                if v is not None:
                    try:
                        f_v = float(v)
                        if not math.isnan(f_v) and not math.isinf(f_v):
                            all_values.append(f_v)
                    except (TypeError, ValueError):
                        pass

    if not all_values:
        return "normalized_0_1000", 1.0

    max_val = max(all_values)

    if max_val <= 100.0 and min(all_values) >= 0:
        panel = data.get("panel_bbox", [])
        if isinstance(panel, (list, tuple)) and len(panel) == 4:
            try:
                x1, y1, x2, y2 = [float(v) for v in panel]
                w = (x2 - x1) * 10
                h = (y2 - y1) * 10
                if w > 50 and h > 50:
                    logger.warning(
                        "⚠️  Phát hiện model có thể trả tọa độ hệ 0–100 thay vì 0–1000. "
                        f"Giá trị max = {max_val:.1f}. Tự động nhân 10 để chuyển sang 0–1000."
                    )
                    return "normalized_0_100", 10.0
            except (TypeError, ValueError):
                pass

    return "normalized_0_1000", 1.0


def rescale_response_coords(data: dict, multiplier: float) -> dict:
    """
    Nhân tất cả tọa độ trong response với multiplier.
    Khi multiplier khác 1.0 (ví dụ 10.0), tự động cập nhật coordinate_scale thành 1000.
    Không mutate dictionary đầu vào.
    Báo lỗi rõ ràng nếu có giá trị không chuyển được sang float.
    """
    if not isinstance(data, dict):
        raise ValueError("data phải là dictionary")

    result = dict(data)

    if multiplier == 1.0:
        return result

    for key in ("panel_bbox", "object_bbox", "object_center"):
        val = result.get(key)
        if isinstance(val, (list, tuple)):
            new_coords = []
            for v in val:
                if v is None:
                    raise ValueError(f"Tọa độ trong {key} chứa giá trị None")
                try:
                    f_v = float(v)
                    if math.isnan(f_v) or math.isinf(f_v):
                        raise ValueError(f"Tọa độ trong {key} chứa giá trị NaN hoặc Infinity")
                    new_coords.append(f_v * multiplier)
                except (TypeError, ValueError) as e:
                    raise ValueError(f"Không thể chuyển đổi tọa độ trong {key} ('{v}') sang float: {e}")
            result[key] = new_coords

    result["coordinate_scale"] = 1000
    return result


# =============================================================================
# TÍNH TOÁN HÌNH HỌC
# =============================================================================

def calculate_bbox_center(bbox: BBox) -> Point:
    """Tính tâm của bbox."""
    x1, y1, x2, y2 = bbox
    return [(x1 + x2) / 2.0, (y1 + y2) / 2.0]


def clamp_bbox(bbox: BBox, min_val: float = 0.0, max_val: float = 1000.0) -> BBox:
    """Clamp tọa độ bbox vào khoảng [min_val, max_val]."""
    x1, y1, x2, y2 = bbox
    x1 = max(min_val, min(max_val, x1))
    y1 = max(min_val, min(max_val, y1))
    x2 = max(min_val, min(max_val, x2))
    y2 = max(min_val, min(max_val, y2))
    return [x1, y1, x2, y2]


def clamp_pixel_bbox(bbox: BBox, width: int, height: int) -> BBox:
    """Clamp bbox pixel vào kích thước ảnh."""
    x1, y1, x2, y2 = bbox
    x1 = max(0.0, min(float(width), x1))
    y1 = max(0.0, min(float(height), y1))
    x2 = max(0.0, min(float(width), x2))
    y2 = max(0.0, min(float(height), y2))
    return [x1, y1, x2, y2]


def bbox_iou(boxA: BBox, boxB: BBox) -> float:
    """
    Tính Intersection over Union (IoU) giữa hai bbox.
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = inter_w * inter_h

    if inter_area == 0:
        return 0.0

    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    union_area = areaA + areaB - inter_area

    return inter_area / union_area if union_area > 0 else 0.0


def bbox_area(bbox: BBox) -> float:
    """Tính diện tích bbox."""
    x1, y1, x2, y2 = bbox
    return max(0.0, (x2 - x1) * (y2 - y1))


def center_distance(bbox_a: BBox, bbox_b: BBox) -> float:
    """Tính khoảng cách Euclidean giữa hai tâm bbox."""
    cx_a, cy_a = calculate_bbox_center(bbox_a)
    cx_b, cy_b = calculate_bbox_center(bbox_b)
    return math.sqrt((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2)


def bbox_diagonal(bbox: BBox) -> float:
    """Tính đường chéo của bbox."""
    x1, y1, x2, y2 = bbox
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def expand_bbox(bbox: BBox, ratio: float, max_val: float = 1000.0) -> BBox:
    """
    Mở rộng bbox theo tỷ lệ ratio (ví dụ 0.08 = +8% mỗi chiều).
    Giữ trong giới hạn [0, max_val].
    """
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1
    dx = w * ratio / 2
    dy = h * ratio / 2
    return clamp_bbox(
        [x1 - dx, y1 - dy, x2 + dx, y2 + dy],
        0.0, max_val
    )


def expand_pixel_bbox(bbox: BBox, ratio: float, width: int, height: int) -> List[int]:
    """Mở rộng pixel bbox và clamp vào kích thước ảnh, trả về int."""
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1
    dx = w * ratio / 2
    dy = h * ratio / 2
    expanded = clamp_pixel_bbox(
        [x1 - dx, y1 - dy, x2 + dx, y2 + dy],
        width, height
    )
    return pixel_bbox_to_int(expanded)
