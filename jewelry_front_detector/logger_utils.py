"""
logger_utils.py
Tiện ích logging cho toàn bộ dự án.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from config import LOGS_DIR, DEBUG_MODE


def get_logger(name: str = "jewelry_detector") -> logging.Logger:
    """
    Tạo hoặc lấy logger đã cấu hình.
    - Ghi ra file Debug/<name>_YYYY-MM-DD.log (tap trung Debug folder)
    - Ghi ra console
    """
    logger = logging.getLogger(name)

    # Tránh thêm handler trùng nếu logger đã tồn tại
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

    # ---- File handler — ten file: <tool>_YYYY-MM-DD.log ----
    log_file = LOGS_DIR / f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)

    # ---- Console handler ----
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def log_separator(logger: logging.Logger, title: str = "") -> None:
    """Ghi dòng phân cách để dễ đọc log."""
    line = "=" * 60
    if title:
        logger.info(f"{line}\n  {title}\n{line}")
    else:
        logger.info(line)


def log_dict(logger: logging.Logger, label: str, data: dict) -> None:
    """Ghi dict ra log theo định dạng dễ đọc."""
    import json
    try:
        formatted = json.dumps(data, ensure_ascii=False, indent=2)
        logger.debug(f"{label}:\n{formatted}")
    except Exception:
        logger.debug(f"{label}: {data}")
