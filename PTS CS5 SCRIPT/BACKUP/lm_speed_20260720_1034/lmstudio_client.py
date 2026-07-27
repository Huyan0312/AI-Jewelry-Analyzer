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
    Tương thích với OpenAI vision message format.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file ảnh: {image_path}")

    mime = get_image_mime(image_path)
    with open(image_path, "rb") as f:
        raw = f.read()

    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{b64}"


# =============================================================================
# PARSE JSON AN TOÀN
# =============================================================================

def extract_json_safe(text: str) -> Optional[dict]:
    """
    Bóc JSON an toàn từ response của model.
    Xử lý các trường hợp:
    - JSON thuần túy
    - JSON bọc trong markdown ```json ... ```
    - JSON lẫn với văn bản thừa
    """
    if not text:
        return None

    # Thử parse trực tiếp trước
    text_stripped = text.strip()
    try:
        return json.loads(text_stripped)
    except json.JSONDecodeError:
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
            except json.JSONDecodeError:
                continue

    # Tìm JSON object đầu tiên trong text
    brace_start = text_stripped.find("{")
    brace_end = text_stripped.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        candidate = text_stripped[brace_start : brace_end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    logger.error(f"Không thể parse JSON từ response:\n{text[:500]}")
    return None


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

def send_image_to_model(
    image_path: Path,
    model: str,
    target_view: str = "FRONT",
    base_url: str = LMSTUDIO_BASE_URL,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
) -> Tuple[Optional[dict], str]:
    """
    Gửi ảnh tới model vision trong LM Studio.

    Trả về:
        (parsed_json: Optional[dict], raw_response: str)
        parsed_json là None nếu có lỗi.
    """
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    logger.info(f"Gửi ảnh '{image_path.name}' tới model '{model}' tại {endpoint}")

    # Encode ảnh
    try:
        data_url = encode_image_to_base64_url(image_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        return None, str(e)
    except Exception as e:
        logger.error(f"Lỗi encode ảnh: {e}")
        return None, f"Lỗi encode ảnh: {e}"

    # Xây dựng message theo chuẩn OpenAI vision
    user_prompt = get_user_prompt(target_view)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
                {
                    "type": "text",
                    "text": user_prompt,
                },
            ],
        },
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = ""
    for attempt in range(1, RETRY_COUNT + 2):
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
                logger.info("Model phản hồi thành công.")
                logger.debug(f"Response thô:\n{raw_content}")

                parsed = extract_json_safe(raw_content)
                if parsed is None:
                    logger.warning("Không parse được JSON từ response của model.")
                    return None, raw_content

                return parsed, raw_content

            elif resp.status_code == 400:
                err_body = resp.text
                if "vision" in err_body.lower() or "image" in err_body.lower():
                    last_error = (
                        f"Model '{model}' không hỗ trợ vision (xử lý ảnh). "
                        "Vui lòng load model vision như LLaVA, BakLLaVA, MiniCPM-V, v.v."
                    )
                else:
                    last_error = f"API trả lỗi 400: {err_body}"
                logger.error(last_error)
                return None, last_error

            elif resp.status_code == 404:
                last_error = (
                    f"Model '{model}' chưa được load trong LM Studio. "
                    "Vui lòng load model trước khi gửi request."
                )
                logger.error(last_error)
                return None, last_error

            elif resp.status_code == 503:
                last_error = "LM Studio server đang bận hoặc model chưa sẵn sàng (503)."
                logger.warning(f"{last_error} Thử lại sau {RETRY_DELAY}s...")

            else:
                last_error = f"API trả lỗi HTTP {resp.status_code}: {resp.text[:300]}"
                logger.error(last_error)
                return None, last_error

        except requests.exceptions.ConnectionError:
            last_error = (
                "Không thể kết nối đến LM Studio. "
                "Kiểm tra LM Studio đã bật Local Server chưa?"
            )
            logger.error(last_error)

        except requests.exceptions.Timeout:
            last_error = (
                f"Request timeout sau {REQUEST_TIMEOUT}s. "
                "Model xử lý quá lâu. Thử tăng timeout trong config.py."
            )
            logger.warning(last_error)

        except requests.exceptions.RequestException as e:
            last_error = f"Lỗi network: {e}"
            logger.error(last_error)

        except Exception as e:
            last_error = f"Lỗi không xác định: {e}"
            logger.error(last_error)
            return None, last_error

        # Chờ trước khi retry
        if attempt <= RETRY_COUNT:
            logger.info(f"Chờ {RETRY_DELAY}s trước lần thử {attempt + 1}...")
            time.sleep(RETRY_DELAY)

    return None, last_error

def send_image_to_model_all_views(
    image_path: Path,
    model: str,
    base_url: str = LMSTUDIO_BASE_URL,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
    retry_count: Optional[int] = None,
) -> Tuple[Optional[List[dict]], str]:
    """
    Gửi ảnh tới model vision trong LM Studio để lấy TẤT CẢ 7 view cùng lúc.

    Trả về:
        (parsed_json_list: Optional[List[dict]], raw_response: str)
    """
    from prompts import get_all_views_user_prompt
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    logger.info(f"Gửi ảnh '{image_path.name}' tới model '{model}' để phân tích ALL VIEWS")

    t_all = time.perf_counter()
    try:
        t0 = time.perf_counter()
        data_url = encode_image_to_base64_url(image_path)
        enc_ms = (time.perf_counter() - t0) * 1000
        # data URL ~ "data:mime;base64," + payload
        b64_len = max(0, len(data_url) - data_url.find(",") - 1) if "," in data_url else len(data_url)
        logger.info(f"[TIMING] base64 encode: {enc_ms:.0f}ms | ~{b64_len // 1024} KB b64")
    except Exception as e:
        logger.error(f"Lỗi encode ảnh: {e}")
        return None, f"Lỗi encode ảnh: {e}"

    user_prompt = get_all_views_user_prompt()
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

    last_error = ""
    max_attempts = RETRY_COUNT if retry_count is None else retry_count
    for attempt in range(1, max_attempts + 2):
        try:
            logger.info(f"Đang gửi request ALL VIEWS (lần {attempt})...")
            t0 = time.perf_counter()
            resp = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT, headers={"Content-Type": "application/json"})
            http_ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[TIMING] LM Studio HTTP: {http_ms:.0f}ms | status={resp.status_code}")
            if resp.status_code == 200:
                t0 = time.perf_counter()
                result = resp.json()
                raw_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = extract_json_safe(raw_content)
                parse_ms = (time.perf_counter() - t0) * 1000
                logger.info(f"[TIMING] parse JSON response: {parse_ms:.0f}ms")
                total_ms = (time.perf_counter() - t_all) * 1000
                logger.info(f"[TIMING] ALL VIEWS (encode+HTTP+parse): {total_ms:.0f}ms")
                if parsed is None or not isinstance(parsed, list):
                    logger.warning("Không parse được JSON array từ response của model.")
                    return None, raw_content
                return parsed, raw_content
            else:
                last_error = f"API trả lỗi {resp.status_code}: {resp.text[:300]}"
                logger.error(last_error)
        except Exception as e:
            last_error = f"Lỗi: {e}"
            logger.error(last_error)

        if attempt <= max_attempts:
            time.sleep(RETRY_DELAY)

    return None, last_error
