"""
lmstudio_client.py
Giao tiếp với LM Studio local API theo chuẩn OpenAI-compatible.
"""

import base64
import json
import re
import time
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple

import requests

from config import (
    LMSTUDIO_BASE_URL,
    TEMPERATURE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    RETRY_COUNT,
    RETRY_DELAY,
    DEFAULT_MODEL,
    MAX_AI_SIZE,
    AI_JPEG_QUALITY,
)
from prompts import SYSTEM_PROMPT, get_user_prompt
from logger_utils import get_logger

logger = get_logger("jewelry_detector.lmstudio")


# =============================================================================
# MIME TYPE
# =============================================================================

def get_image_mime(path: Path) -> str:
    """Xác định MIME type đúng theo phần mở rộng."""
    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/jpeg")


# =============================================================================
# ĐỌC VÀ ENCODE ẢNH
# =============================================================================

def encode_image_to_base64_url(image_path: Path) -> str:
    """
    Đọc ảnh từ đĩa và chuyển sang base64 data URL.
    Sử dụng prepare_image_data_url_for_lm để bảo đảm giới hạn MAX_AI_SIZE và AI_JPEG_QUALITY.
    """
    data_url, _ = prepare_image_data_url_for_lm(image_path)
    return data_url


def prepare_image_data_url_for_lm(
    image_path: Path,
    max_size: int = MAX_AI_SIZE,
    jpeg_quality: int = AI_JPEG_QUALITY,
) -> Tuple[str, dict]:
    """
    Resize (nếu cần) + JPEG + base64 trong RAM — không ghi file tạm lên đĩa.

    Trả về:
        (data_url, meta) với meta: orig_w, orig_h, send_w, send_h, resized, jpeg_bytes, b64_kb, resize_ms, encode_ms
    """
    from io import BytesIO
    from PIL import Image, ImageOps

    if not image_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file ảnh: {image_path}")

    meta = {
        "orig_w": 0,
        "orig_h": 0,
        "send_w": 0,
        "send_h": 0,
        "jpeg_bytes": 0,
        "b64_kb": 0,
        "resized": False,
        "resize_ms": 0.0,
        "encode_ms": 0.0,
    }

    t0 = time.perf_counter()
    with Image.open(image_path) as im:
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass

        im = im.convert("RGB")
        ow, oh = im.size
        meta["orig_w"], meta["orig_h"] = ow, oh
        nw, nh = ow, oh
        if max(ow, oh) > max_size:
            scale = max_size / float(max(ow, oh))
            nw, nh = int(round(ow * scale)), int(round(oh * scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            meta["resized"] = True
        meta["send_w"], meta["send_h"] = nw, nh

        buf = BytesIO()
        im.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        jpeg_bytes = buf.getvalue()

    meta["resize_ms"] = (time.perf_counter() - t0) * 1000
    meta["jpeg_bytes"] = len(jpeg_bytes)

    t1 = time.perf_counter()
    b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"
    meta["encode_ms"] = (time.perf_counter() - t1) * 1000
    meta["b64_kb"] = len(b64) // 1024
    return data_url, meta


# =============================================================================
# PARSE JSON AN TOÀN
# =============================================================================

def extract_json_safe(text: str):
    """
    Bóc JSON an toàn từ response của model.
    Xử lý các trường hợp:
    - JSON thuần túy (object hoặc array)
    - JSON bọc trong markdown ```json ... ```
    - JSON lẫn với văn bản thừa
    """
    if not text:
        return None

    # Thử parse trực tiếp trước
    text_stripped = text.strip()
    try:
        return json.loads(text_stripped)
    except Exception:
        pass

    # Loại bỏ markdown code fence ```json ... ``` hoặc ``` ... ```
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
        r"`([\s\S]*?)`",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_stripped, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                continue

    # Ưu tiên object {..} (format mới: sheet + views), rồi mới array [..]
    brace_start = text_stripped.find("{")
    brace_end = text_stripped.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        candidate = text_stripped[brace_start : brace_end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    bracket_start = text_stripped.find("[")
    bracket_end = text_stripped.rfind("]")
    if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
        candidate = text_stripped[bracket_start : bracket_end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    logger.error(f"Không thể parse JSON từ response:\n{text[:500]}")
    return None


def _normalize_drawing_number(raw) -> Tuple[Optional[str], Optional[str]]:
    """
    Trả về (drawing_number, drawing_number_raw).
    Lưu giữ cả cụm số chính lẫn nguyên bản hậu tố (ví dụ: '889486 A').
    """
    if raw is None:
        return None, None
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", "n/a"):
        return None, None

    raw_val = s
    m = re.match(r"^(\d{4,})", s)
    if m:
        return m.group(1), raw_val
    m2 = re.search(r"(\d{5,})", s)
    num_val = m2.group(1) if m2 else s
    return num_val, raw_val


def _normalize_brand_metal(metal, brand) -> Tuple[Optional[str], str]:
    """Trả về (metal, brand) chuẩn: metal in {14K,925,None}, brand in {14k,silver,NONE}."""
    metal_s = None if metal is None else str(metal).strip()
    brand_s = None if brand is None else str(brand).strip().lower().replace(" ", "")

    if metal_s:
        mlow = metal_s.lower().replace(" ", "")
        if "925" in mlow or mlow in ("silver", "sterling"):
            return "925", "silver"
        if "14k" in mlow or mlow in ("14", "gold"):
            return "14K", "14k"

    if brand_s:
        if brand_s in ("silver", "925"):
            return "925", "silver"
        if brand_s in ("14k", "14"):
            return "14K", "14k"
        if brand_s in ("none", "null", "empty"):
            return None, "NONE"

    return None, "NONE"


def normalize_all_views_payload(parsed) -> Tuple[Optional[List[dict]], dict]:
    """
    Chấp nhận:
      - list view (format cũ)
      - object { drawing_number, metal, brand, metal_weight, coordinate_scale, views: [...] } (format mới)
    Trả về (views_list, sheet_dict).
    """
    from bbox_utils import validate_all_views_schema

    sheet = {
        "drawing_number": None,
        "drawing_number_raw": None,
        "metal": None,
        "brand": "NONE",
        "metal_weight": None,
        "coordinate_scale": None,
        "validation_errors": [],
    }
    if parsed is None:
        return None, sheet

    views = None
    if isinstance(parsed, list):
        views = [v for v in parsed if isinstance(v, dict) and v.get("view")]
    elif isinstance(parsed, dict):
        raw_dn = parsed.get("drawing_number") or parsed.get("drawing") or parsed.get("Drawing")
        num_dn, raw_dn_val = _normalize_drawing_number(raw_dn)
        sheet["drawing_number"] = num_dn
        sheet["drawing_number_raw"] = raw_dn_val

        metal_n, brand_n = _normalize_brand_metal(parsed.get("metal"), parsed.get("brand"))
        sheet["metal"] = metal_n
        sheet["brand"] = brand_n

        mw = parsed.get("metal_weight") or parsed.get("metalWeight")
        if mw is not None and str(mw).strip().lower() not in ("null", "none", "---", "--"):
            sheet["metal_weight"] = str(mw).strip()

        if parsed.get("coordinate_scale") is not None:
            try:
                sheet["coordinate_scale"] = float(parsed["coordinate_scale"])
            except (TypeError, ValueError):
                pass

        raw_views = parsed.get("views") or parsed.get("Views") or parsed.get("all_views")
        if isinstance(raw_views, list):
            views = [v for v in raw_views if isinstance(v, dict) and v.get("view")]
        elif parsed.get("view") and parsed.get("object_bbox"):
            views = [parsed]

    if not views:
        sheet["validation_errors"].append("Không tìm thấy dữ liệu views")
        return None, sheet

    # Upper case view names & attach coordinate_scale
    for item in views:
        if isinstance(item, dict) and "view" in item:
            item["view"] = str(item["view"]).upper()
            if sheet["coordinate_scale"] is not None and "coordinate_scale" not in item:
                item["coordinate_scale"] = sheet["coordinate_scale"]

    # Validate 7-views schema
    is_valid, err_list, _ = validate_all_views_schema(views)
    if not is_valid:
        sheet["validation_errors"].extend(err_list)
        logger.warning(f"Validation schema 7 views có lỗi/cảnh báo: {err_list}")

    return views, sheet


# =============================================================================
# LẤY DANH SÁCH MODEL ĐANG LOAD
# =============================================================================

def get_loaded_models(base_url: str, timeout: int = 5) -> List[str]:
    """
    Lấy danh sách tên model đang được load trong LM Studio.
    Trả về list rỗng nếu lỗi.
    """
    try:
        url = f"{base_url.rstrip('/')}/models"
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", [])
            return [m.get("id", "") for m in models if m.get("id")]
    except Exception:
        pass
    return []


# =============================================================================
# KIỂM TRA KẾT NỐI
# =============================================================================

def check_connection(base_url: str) -> Tuple[bool, str, List[str]]:
    """
    Kiểm tra LM Studio server có đang chạy không.
    Trả về (success: bool, message: str, model_names: List[str]).
    model_names chứa danh sách model đang load (dùng để tự điền vào giao diện).
    """
    try:
        model_names = get_loaded_models(base_url)
        if model_names:
            msg = f"Kết nối thành công. Models đang load: {', '.join(model_names)}"
            return True, msg, model_names
        else:
            # Thử GET /models một lần nữa để phân biệt "server chạy nhưng không có model" vs lỗi
            url = f"{base_url.rstrip('/')}/models"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return True, "Kết nối thành công nhưng chưa có model nào được load.", []
            else:
                return False, f"Server phản hồi HTTP {resp.status_code}", []
    except requests.exceptions.ConnectionError:
        return False, (
            "Không thể kết nối đến LM Studio. "
            "Vui lòng kiểm tra:\n"
            "  1. LM Studio đã được mở chưa?\n"
            "  2. Local Server đã được bật chưa (nút Start Server)?\n"
            f"  3. URL có đúng không? Đang dùng: {base_url}"
        ), []
    except requests.exceptions.Timeout:
        return False, f"Timeout khi kết nối tới {base_url}", []
    except Exception as e:
        return False, f"Lỗi không xác định: {e}", []


# =============================================================================
# GỬI ẢNH TỚI MODEL
# =============================================================================

# =============================================================================
# GỬI ẢNH TỚI MODEL
# =============================================================================

def send_image_to_model(
    image_path: Path,
    model: str,
    target_view: str = "FRONT",
    base_url: str = LMSTUDIO_BASE_URL,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
    retry_count: Optional[int] = None,
) -> dict:
    """
    Gửi ảnh tới model vision trong LM Studio để phân tích 1 view.

    Trả về dictionary cấu trúc:
    {
        "sheet": dict,
        "views": Optional[List[dict]],
        "parsed_json": Optional[dict],
        "raw_response": str,
        "request_meta": dict,
        "validation": dict,
        "error": Optional[str],
        "error_type": Optional[str],
    }
    """
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    logger.info(f"Gửi ảnh '{image_path.name}' tới model '{model}' tại {endpoint}")

    res_dict = {
        "sheet": {
            "drawing_number": None,
            "drawing_number_raw": None,
            "metal": None,
            "brand": "NONE",
            "metal_weight": None,
            "coordinate_scale": None,
            "validation_errors": [],
        },
        "views": None,
        "parsed_json": None,
        "raw_response": "",
        "request_meta": {},
        "validation": {"valid": False, "errors": []},
        "error": None,
        "error_type": None,
    }

    try:
        data_url, meta = prepare_image_data_url_for_lm(image_path)
        res_dict["request_meta"] = meta
    except FileNotFoundError as e:
        err_msg = str(e)
        logger.error(err_msg)
        res_dict["error"] = err_msg
        res_dict["error_type"] = "EncodeError"
        return res_dict
    except Exception as e:
        err_msg = f"Lỗi encode ảnh: {e}"
        logger.error(err_msg)
        res_dict["error"] = err_msg
        res_dict["error_type"] = "EncodeError"
        return res_dict

    user_prompt = get_user_prompt(target_view)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": user_prompt},
            ],
        },
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    max_attempts = RETRY_COUNT if retry_count is None else retry_count
    for attempt in range(1, max_attempts + 2):
        try:
            logger.info(f"Đang gửi request (lần {attempt})...")
            resp = requests.post(
                endpoint,
                json=payload,
                timeout=REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )

            if resp.status_code == 200:
                result = resp.json()
                raw_content = (
                    result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                res_dict["raw_response"] = raw_content
                logger.info("Model phản hồi thành công.")

                parsed = extract_json_safe(raw_content)
                if parsed is None or not isinstance(parsed, dict):
                    logger.warning(f"Lần {attempt}: Không parse được JSON dictionary từ response.")
                    res_dict["error"] = "Không parse được JSON dictionary từ response của model"
                    res_dict["error_type"] = "JSONParseError"
                    res_dict["validation"] = {"valid": False, "errors": ["Response không phải JSON dictionary"]}
                    if attempt <= max_attempts:
                        time.sleep(RETRY_DELAY)
                        continue
                    return res_dict

                res_dict["parsed_json"] = parsed
                parsed["view"] = str(parsed.get("view", "")).upper()

                from bbox_utils import validate_view_payload
                ok_val, schema_errs = validate_view_payload(parsed)
                if parsed.get("view") != target_view.upper():
                    schema_errs.append(f"Model trả view {parsed.get('view')}, nhưng yêu cầu {target_view.upper()}")

                if not ok_val or schema_errs:
                    logger.warning(f"Lần {attempt}: Single-view response không đạt schema validation: {schema_errs}")
                    res_dict["error"] = "; ".join(schema_errs)
                    res_dict["error_type"] = "SchemaValidationError"
                    res_dict["validation"] = {"valid": False, "errors": schema_errs}
                    res_dict["parsed_json"] = None
                    res_dict["views"] = None
                    if attempt <= max_attempts:
                        time.sleep(RETRY_DELAY)
                        continue
                    return res_dict

                res_dict["views"] = [parsed]
                res_dict["validation"] = {"valid": True, "errors": []}
                res_dict["error"] = None
                res_dict["error_type"] = None
                return res_dict

            elif resp.status_code == 400:
                err_body = resp.text
                if "vision" in err_body.lower() or "image" in err_body.lower():
                    msg = f"Model '{model}' không hỗ trợ vision (xử lý ảnh)."
                else:
                    msg = f"API trả lỗi 400: {err_body}"
                logger.error(msg)
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text
                return res_dict

            elif resp.status_code == 404:
                msg = f"Model '{model}' chưa được load trong LM Studio."
                logger.error(msg)
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text
                return res_dict

            elif resp.status_code == 503:
                msg = "LM Studio server đang bận hoặc model chưa sẵn sàng (503)."
                logger.warning(f"{msg} Thử lại sau {RETRY_DELAY}s...")
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text

            else:
                msg = f"API trả lỗi HTTP {resp.status_code}: {resp.text[:300]}"
                logger.error(msg)
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text
                return res_dict

        except requests.exceptions.ConnectionError:
            msg = "Không thể kết nối đến LM Studio. Kiểm tra LM Studio đã bật Local Server chưa?"
            logger.error(msg)
            res_dict["error"] = msg
            res_dict["error_type"] = "ConnectionError"
            return res_dict

        except requests.exceptions.Timeout:
            msg = f"Request timeout sau {REQUEST_TIMEOUT}s."
            logger.warning(msg)
            res_dict["error"] = msg
            res_dict["error_type"] = "TimeoutError"

        except Exception as e:
            msg = f"Lỗi không xác định: {e}"
            logger.error(msg)
            res_dict["error"] = msg
            res_dict["error_type"] = "OpenAIResponseError"
            return res_dict

        if attempt <= max_attempts:
            logger.info(f"Chờ {RETRY_DELAY}s trước lần thử {attempt + 1}...")
            time.sleep(RETRY_DELAY)

    return res_dict

def send_image_to_model_all_views(
    image_path: Optional[Path] = None,
    model: str = "",
    base_url: str = LMSTUDIO_BASE_URL,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
    retry_count: Optional[int] = None,
    data_url: Optional[str] = None,
) -> dict:
    """
    Gửi ảnh tới model vision trong LM Studio để lấy TẤT CẢ 7 view cùng lúc.

    Trả về dictionary cấu trúc:
    {
        "sheet": sheet_dict,
        "views": Optional[List[dict]],
        "parsed_json": Optional[dict],
        "raw_response": str,
        "request_meta": dict,
        "validation": dict,
        "error": Optional[str],
        "error_type": Optional[str],
    }
    """
    from prompts import get_all_views_user_prompt
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    label = image_path.name if image_path else "in-memory"
    logger.info(f"Gửi ảnh '{label}' tới model '{model}' để phân tích ALL VIEWS")

    res_dict = {
        "sheet": {
            "drawing_number": None,
            "drawing_number_raw": None,
            "metal": None,
            "brand": "NONE",
            "metal_weight": None,
            "coordinate_scale": None,
            "validation_errors": [],
        },
        "views": None,
        "parsed_json": None,
        "raw_response": "",
        "request_meta": {},
        "validation": {"valid": False, "errors": []},
        "error": None,
        "error_type": None,
    }

    t_all = time.perf_counter()
    try:
        if data_url:
            used_url = data_url
            b64_len = max(0, len(used_url) - used_url.find(",") - 1) if "," in used_url else len(used_url)
            res_dict["request_meta"] = {"b64_kb": b64_len // 1024, "prebuilt": True}
        elif image_path is not None:
            used_url, meta = prepare_image_data_url_for_lm(image_path)
            res_dict["request_meta"] = meta
        else:
            res_dict["error"] = "Thiếu image_path hoặc data_url"
            res_dict["error_type"] = "EncodeError"
            return res_dict
    except Exception as e:
        err_msg = f"Lỗi encode ảnh: {e}"
        logger.error(err_msg)
        res_dict["error"] = err_msg
        res_dict["error_type"] = "EncodeError"
        return res_dict

    user_prompt = get_all_views_user_prompt()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": used_url}},
                {"type": "text", "text": user_prompt},
            ],
        },
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    max_attempts = RETRY_COUNT if retry_count is None else retry_count
    for attempt in range(1, max_attempts + 2):
        try:
            logger.info(f"Đang gửi request ALL VIEWS (lần {attempt})...")
            t0 = time.perf_counter()
            resp = requests.post(
                endpoint,
                json=payload,
                timeout=REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
            http_ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[TIMING] LM Studio HTTP: {http_ms:.0f}ms | status={resp.status_code}")

            if resp.status_code == 200:
                t0 = time.perf_counter()
                result = resp.json()
                raw_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                res_dict["raw_response"] = raw_content

                parsed = extract_json_safe(raw_content)
                res_dict["parsed_json"] = parsed

                views, sheet = normalize_all_views_payload(parsed)
                res_dict["sheet"] = sheet
                val_errors = sheet.get("validation_errors", [])

                parse_ms = (time.perf_counter() - t0) * 1000
                logger.info(f"[TIMING] parse JSON response: {parse_ms:.0f}ms")
                total_ms = (time.perf_counter() - t_all) * 1000
                logger.info(f"[TIMING] ALL VIEWS (encode+HTTP+parse): {total_ms:.0f}ms")

                if views is None:
                    logger.warning(f"Lần {attempt}: Không parse được views từ response của model.")
                    res_dict["error"] = "Không parse được views từ response của model"
                    res_dict["error_type"] = "JSONParseError"
                    res_dict["validation"] = {"valid": False, "errors": ["Không parse được views"]}
                    if attempt <= max_attempts:
                        time.sleep(RETRY_DELAY)
                        continue
                    return res_dict

                if val_errors:
                    logger.warning(f"Lần {attempt}: All-views response vi phạm schema validation: {val_errors}")
                    res_dict["views"] = None
                    res_dict["error"] = "; ".join(val_errors)
                    res_dict["error_type"] = "SchemaValidationError"
                    res_dict["validation"] = {"valid": False, "errors": val_errors}
                    if attempt <= max_attempts:
                        time.sleep(RETRY_DELAY)
                        continue
                    return res_dict

                res_dict["views"] = views
                res_dict["validation"] = {"valid": True, "errors": []}
                res_dict["error"] = None
                res_dict["error_type"] = None
                logger.info(
                    f"Sheet meta: drawing={sheet.get('drawing_number')} ({sheet.get('drawing_number_raw')}) "
                    f"metal={sheet.get('metal')} brand={sheet.get('brand')} "
                    f"weight={sheet.get('metal_weight')} | views={len(views)}"
                )
                return res_dict

            elif resp.status_code == 400:
                err_body = resp.text
                msg = f"API trả lỗi 400: {err_body}"
                logger.error(msg)
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text
                return res_dict

            elif resp.status_code == 404:
                msg = f"Model '{model}' chưa được load trong LM Studio."
                logger.error(msg)
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text
                return res_dict

            elif resp.status_code == 503:
                msg = "LM Studio server đang bận hoặc model chưa sẵn sàng (503)."
                logger.warning(f"{msg} Thử lại sau {RETRY_DELAY}s...")
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text

            else:
                msg = f"API trả lỗi HTTP {resp.status_code}: {resp.text[:300]}"
                logger.error(msg)
                res_dict["error"] = msg
                res_dict["error_type"] = "HTTPStatusError"
                res_dict["raw_response"] = resp.text
                return res_dict

        except requests.exceptions.ConnectionError:
            msg = "Không thể kết nối đến LM Studio. Kiểm tra LM Studio đã bật Local Server chưa?"
            logger.error(msg)
            res_dict["error"] = msg
            res_dict["error_type"] = "ConnectionError"
            return res_dict

        except requests.exceptions.Timeout:
            msg = f"Request timeout sau {REQUEST_TIMEOUT}s."
            logger.warning(msg)
            res_dict["error"] = msg
            res_dict["error_type"] = "TimeoutError"

        except Exception as e:
            msg = f"Lỗi không xác định: {e}"
            logger.error(msg)
            res_dict["error"] = msg
            res_dict["error_type"] = "OpenAIResponseError"
            return res_dict

        if attempt <= max_attempts:
            logger.info(f"Chờ {RETRY_DELAY}s trước lần thử {attempt + 1}...")
            time.sleep(RETRY_DELAY)

    return res_dict


# =============================================================================
# LẦN 2: ĐỌC H/W/RD TỪ CROP FRONT VIEW
# =============================================================================

DIMENSION_SYSTEM_PROMPT = (
    "You are a technical drawing dimension reader for jewelry. "
    "Return valid JSON only. No markdown, no explanation."
)

DIMENSION_USER_PROMPT = (
    "This is a CROPPED portion of a jewelry technical drawing.\n"
    "Find dimension lines and numbers (in RED, BLUE, BLACK, or inside yellow boxes) and measure them.\n\n"
    "RULES — follow carefully:\n"
    "1. Read the dimension number associated with the dimension arrows in the crop.\n"
    "2. CRITICAL PREFERENCE: If a number is inside a YELLOW HIGHLIGHT BOX (e.g. 1.35, 1.55) or BLUE text next to the arrows, it is the PRIMARY target dimension. ALWAYS extract this yellow-highlighted/blue number (e.g. 1.35) instead of neighboring red numbers (like 11.20).\n"
    "3. Determine direction:\n"
    "   - Arrows pointing UP <-> DOWN = HEIGHT (front_height_mm)\n"
    "   - Arrows pointing LEFT <-> RIGHT = WIDTH (front_width_mm)\n"
    "4. Return valid JSON only.\n\n"
    "Return ONLY this JSON:\n"
    '{"front_width_mm": <number or 0>, "front_height_mm": <number or 0>, '
    '"scale_direction": "<H|W>", "confidence": "<high|medium|low>"}'
)

# Prompt chuyen biet: user chon CHIEU CAO (H)
DIMENSION_H_PROMPT = (
    "This is a cropped portion of a jewelry technical drawing.\n"
    "The user selected a region and wants to scale by HEIGHT (front_height_mm).\n\n"
    "YOUR TASK:\n"
    "1. Find the dimension number attached to the selection arrows.\n"
    "2. CRITICAL PREFERENCE: If a number is inside a YELLOW HIGHLIGHT BOX (e.g. 1.35) or BLUE text, ALWAYS PREFER this target number over neighboring red numbers (like 11.20).\n"
    "3. Assign this target number (e.g. 1.35) to front_height_mm, set front_width_mm = 0, scale_direction = 'H'.\n\n"
    "Return ONLY this JSON:\n"
    '{"front_width_mm": 0, "front_height_mm": <number>, "scale_direction": "H", "confidence": "<high|medium|low>"}'
)

# Prompt chuyen biet: user chon CHIEU NGANG (W)
DIMENSION_W_PROMPT = (
    "This is a cropped portion of a jewelry technical drawing.\n"
    "The user selected a region and wants to scale by WIDTH (front_width_mm).\n\n"
    "YOUR TASK:\n"
    "1. Find the dimension number attached to the selection arrows.\n"
    "2. CRITICAL PREFERENCE: If a number is inside a YELLOW HIGHLIGHT BOX (e.g. 1.35, 1.55) or BLUE text, ALWAYS PREFER this target number over neighboring red numbers (like 11.20).\n"
    "3. Assign this target number (e.g. 1.35) to front_width_mm, set front_height_mm = 0, scale_direction = 'W'.\n\n"
    "Return ONLY this JSON:\n"
    '{"front_width_mm": <number>, "front_height_mm": 0, "scale_direction": "W", "confidence": "<high|medium|low>"}'
)


def send_image_to_model_dimensions(
    image_path: Optional[Path] = None,
    model: str = "",
    base_url: str = LMSTUDIO_BASE_URL,
    data_url: Optional[str] = None,
    retry_count: int = 1,
    expected_direction: str = "",   # "H" / "W" / "" (tu selection aspect ratio)
) -> Optional[dict]:
    """
    AI lần 2: Gửi ảnh crop FRONT view → đọc front_width_mm, front_height_mm, scale_direction.

    expected_direction: nếu set, dùng prompt chuyên biệt chỉ đọc chiều đó.
    Nhận image_path hoặc data_url (PIL Image crop trong RAM).
    Trả về dict hoặc None nếu thất bại.
    """
    # base_url da co /v1 (vd: http://localhost:1234/v1) nen dung /chat/completions
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    label = image_path.name if image_path else "in-memory-crop"
    logger.info(f"[DIMENSION] Gui crop '{label}' toi model '{model}' de doc H/W/RD...")

    t0 = time.perf_counter()
    try:
        if data_url:
            used_url = data_url
        elif image_path is not None:
            used_url = encode_image_to_base64_url(image_path)
        else:
            logger.error("[DIMENSION] Thieu image_path hoac data_url")
            return None
    except Exception as e:
        logger.error(f"[DIMENSION] Loi encode anh crop: {e}")
        return None

    enc_ms = (time.perf_counter() - t0) * 1000
    logger.info(f"[DIMENSION][TIMING] encode: {enc_ms:.0f}ms")

    # Chon prompt phu hop voi expected_direction
    if expected_direction == "H":
        active_prompt = DIMENSION_H_PROMPT
        logger.info(f"[DIMENSION] Dung prompt H-only (selection dung, aspect ratio cao)")
    elif expected_direction == "W":
        active_prompt = DIMENSION_W_PROMPT
        logger.info(f"[DIMENSION] Dung prompt W-only (selection ngang, aspect ratio rong)")
    else:
        active_prompt = DIMENSION_USER_PROMPT
        logger.info(f"[DIMENSION] Dung prompt tong quat (khong ro direction tu selection)")

    messages = [
        {"role": "system", "content": DIMENSION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": used_url}},
                {"type": "text", "text": active_prompt},
            ],
        },
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,   # Luon chon so chinh xac, khong creative
        "max_tokens": 200,    # Chi can 1 JSON ngan
    }

    for attempt in range(1, retry_count + 2):
        try:
            t1 = time.perf_counter()
            resp = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT,
                                 headers={"Content-Type": "application/json"})
            http_ms = (time.perf_counter() - t1) * 1000
            logger.info(f"[DIMENSION][TIMING] HTTP lần {attempt}: {http_ms:.0f}ms | status={resp.status_code}")

            if resp.status_code == 200:
                msg = resp.json().get("choices", [{}])[0].get("message", {})
                # Qwen3 thinking mode: content="" nhung output nam trong reasoning_content
                raw_content = msg.get("content", "") or ""
                if not raw_content.strip():
                    # Fallback: doc reasoning_content (Qwen3 /think mode)
                    raw_content = msg.get("reasoning_content", "") or ""
                    if raw_content.strip():
                        logger.info("[DIMENSION] Doc tu reasoning_content (Qwen3 thinking mode)")

                # Log 300 ky tu dau de debug neu can
                logger.debug(f"[DIMENSION] raw_content[:300]: {raw_content[:300]}")
                if not raw_content.strip():
                    logger.warning("[DIMENSION] content va reasoning_content deu rong. Raw resp keys: "
                                   + str(list(resp.json().get('choices',[{}])[0].get('message',{}).keys())))

                parsed = extract_json_safe(raw_content)
                if not parsed or not isinstance(parsed, dict):
                    logger.warning(f"[DIMENSION] Khong parse duoc JSON: {raw_content[:300]}")
                    continue

                # Validate cac truong can thiet
                w = parsed.get("front_width_mm")
                h = parsed.get("front_height_mm")
                d = parsed.get("scale_direction", "").upper()
                conf = parsed.get("confidence", "medium")

                if w is None or h is None:
                    logger.warning(f"[DIMENSION] Thieu front_width_mm / front_height_mm: {parsed}")
                    continue

                # Suy ra direction tu vung user chon:
                # - W=0, H>0 → user chi chon vung H → direction = H (chac chan)
                # - H=0, W>0 → user chi chon vung W → direction = W (chac chan)
                # - Ca hai > 0 → dung AI judgment hoac so sanh
                fW, fH = float(w), float(h)
                if fW == 0 and fH > 0:
                    d = "H"
                    logger.info(f"[DIMENSION] W=0 H={fH} → direction suy ra: H")
                elif fH == 0 and fW > 0:
                    d = "W"
                    logger.info(f"[DIMENSION] H=0 W={fW} → direction suy ra: W")
                elif d not in ("H", "W"):
                    d = "H" if fH > fW else "W"
                    logger.info(f"[DIMENSION] scale_direction tu tinh lai: {d}")


                result = {
                    "front_width_mm":  round(float(w), 2),
                    "front_height_mm": round(float(h), 2),
                    "scale_direction": d,
                    "confidence":      conf,
                }
                total_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    f"[DIMENSION] OK: W={result['front_width_mm']} H={result['front_height_mm']} "
                    f"dir={d} conf={conf} | total={total_ms:.0f}ms"
                )
                return result

            else:
                logger.error(f"[DIMENSION] API loi {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            logger.error(f"[DIMENSION] Loi lan {attempt}: {e}")

        if attempt <= retry_count:
            time.sleep(RETRY_DELAY)

    logger.error(f"[DIMENSION] That bai sau {retry_count + 1} lan thu.")
    return None
