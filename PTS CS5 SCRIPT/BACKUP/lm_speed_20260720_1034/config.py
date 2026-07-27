"""
config.py
Cấu hình toàn cục cho dự án Jewelry Front Detector.
Chỉnh sửa các giá trị tại đây để thay đổi hành vi ứng dụng.
"""

import os
from pathlib import Path

# =============================================================================
# ĐƯỜNG DẪN CƠ SỞ
# =============================================================================
BASE_DIR = Path(__file__).parent.resolve()
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Tạo thư mục nếu chưa tồn tại
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# LM STUDIO API
# =============================================================================
LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"
# Không hard-code tên model – người dùng nhập qua giao diện hoặc chỉnh tại đây
DEFAULT_MODEL: str = "llava-v1.5-7b"  # Thay bằng tên model đang load trong LM Studio

# =============================================================================
# THAM SỐ GỌI MODEL
# =============================================================================
TEMPERATURE: float = 0.1
MAX_TOKENS: int = 2000
REQUEST_TIMEOUT: int = 120       # giây – tăng nếu model phản hồi chậm
RETRY_COUNT: int = 2             # số lần retry khi gặp lỗi mạng
RETRY_DELAY: float = 2.0         # giây chờ giữa các lần retry

# =============================================================================
# OPENCV REFINE
# =============================================================================
ENABLE_OPENCV_REFINE: bool = True
# Mở rộng vùng tìm kiếm thêm x% so với bbox AI dự đoán
PANEL_SEARCH_EXPAND_RATIO: float = 0.08   # 8%
# IoU tối thiểu để chấp nhận bbox từ OpenCV so với bbox AI
MIN_IOU_THRESHOLD: float = 0.35
# Khoảng cách tâm tối đa (tỷ lệ so với đường chéo bbox) để chấp nhận bbox OpenCV
MAX_CENTER_DISTANCE_RATIO: float = 0.25
# Kích thước contour tối thiểu để không bị coi là noise (pixel^2)
MIN_CONTOUR_AREA: int = 500

# =============================================================================
# PHÁT HIỆN HỆ TỌA ĐỘ
# =============================================================================
# Ngưỡng để phát hiện model trả 0-100 thay vì 0-1000
COORD_SCALE_100_THRESHOLD: float = 100.0

# =============================================================================
# OUTPUT
# =============================================================================
OUTPUT_IMAGE_QUALITY: int = 95   # JPEG quality (1-100)

# =============================================================================
# DEBUG MODE
# =============================================================================
DEBUG_MODE: bool = False          # Bật True để lưu ảnh trung gian
DEBUG_DIR = OUTPUT_DIR / "debug"

# =============================================================================
# BOUNDING BOX COLORS (BGR cho OpenCV)
# =============================================================================
COLOR_PANEL = (0, 200, 0)        # Xanh lá – panel FRONT
COLOR_AI_OBJECT = (0, 140, 255)  # Cam     – object từ AI
COLOR_REFINED_OBJECT = (255, 80, 0)  # Xanh dương – object đã refine
COLOR_CENTER = (0, 0, 255)       # Đỏ     – tâm vật thể
BOX_THICKNESS: int = 2
FONT_SCALE: float = 0.6
FONT_THICKNESS: int = 2
