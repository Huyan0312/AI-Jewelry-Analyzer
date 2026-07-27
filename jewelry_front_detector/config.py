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
INPUT_DIR = Path(os.environ.get("JEWELRY_INPUT_DIR", BASE_DIR / "input")).expanduser().resolve()
OUTPUT_DIR = Path(os.environ.get("JEWELRY_OUTPUT_DIR", BASE_DIR / "output")).expanduser().resolve()
LOGS_DIR = Path(os.environ.get("JEWELRY_LOGS_DIR", BASE_DIR / "logs")).expanduser().resolve()
AUTO_TEST_DIR = Path(
    os.environ.get("JEWELRY_AUTO_TEST_DIR", OUTPUT_DIR / "AutoTest")
).expanduser().resolve()
AUTO_TEST_RESULTS_DIR = Path(
    os.environ.get("JEWELRY_AUTO_TEST_RESULTS_DIR", OUTPUT_DIR / "AutoTest_Results")
).expanduser().resolve()

# Tao thu muc neu chua ton tai
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
TEMPERATURE: float = 0.0
MAX_TOKENS: int = 1500
REQUEST_TIMEOUT: int = 120       # giây – tăng nếu model phản hồi chậm
RETRY_COUNT: int = 2             # số lần retry khi gặp lỗi mạng
RETRY_DELAY: float = 2.0         # giây chờ giữa các lần retry

# Resize ảnh trước khi gửi LM Studio (giữ tỷ lệ). 
# Giữ 2048px theo yêu cầu người dùng để đảm bảo độ chuẩn xác tối đa khi đọc số đo nhỏ & 7 views
MAX_AI_SIZE: int = 2048
AI_JPEG_QUALITY: int = 90

# =============================================================================
# OPENCV REFINE
# =============================================================================
ENABLE_OPENCV_REFINE: bool = True
# Mở rộng vùng tìm kiếm thêm x% so với bbox AI dự đoán
PANEL_SEARCH_EXPAND_RATIO: float = 0.08   # 8%
# Nếu panel hàng cuối được AI đặt cách đáy ảnh không quá 8%, dùng luôn đáy ảnh
# làm biên tìm kiếm. Tránh contour panel dừng sớm và cắt vật thể sát mép trang.
PANEL_BOTTOM_EDGE_SNAP_RATIO: float = 0.08
# IoU tối thiểu để chấp nhận bbox từ OpenCV so với bbox AI
MIN_IOU_THRESHOLD: float = 0.35
# Khoảng cách tâm tối đa (tỷ lệ so với đường chéo bbox) để chấp nhận bbox OpenCV
MAX_CENTER_DISTANCE_RATIO: float = 0.25
PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO: float = 0.50

# Kích thước contour tối thiểu cho panel / object
PANEL_CONTOUR_MIN_AREA: int = 1000
OBJECT_MIN_CONTOUR_AREA: int = 50

# Tỷ lệ trim tối đa cho panel clean (18% mỗi chiều)
MAX_PANEL_TRIM_RATIO: float = 0.18
# Tỷ lệ nội dung tối thiểu giữ lại sau khi clean (85%)
CONTENT_RETAINED_MIN_RATIO: float = 0.85

# Object Refine Acceptance Gate thresholds
OBJECT_SEARCH_MARGIN_RATIO: float = 0.15
OBJECT_DILATION_KERNEL_SIZE: int = 25
OBJECT_PADDING_PX: int = 10
OBJECT_PADDING_RATIO: float = 0.02
# Bbox AI của LM Studio thường bao cả vùng đo nên object thật có thể chỉ chiếm
# khoảng 30% bbox. Các gate area/center vẫn chặn contour sai.
OBJECT_MIN_IOU_THRESHOLD: float = 0.30
OBJECT_MAX_CENTER_DISTANCE_RATIO: float = 0.25
OBJECT_MIN_AREA_RATIO: float = 0.30
OBJECT_MAX_AREA_RATIO: float = 2.50

# Perspective refine: "bbox_only" giữ pixel ảnh gốc, "masked_object" áp mask nền trắng
PERSPECTIVE_OUTPUT_MODE: str = "bbox_only"
PERSPECTIVE_SEARCH_EXPAND_RATIO: float = 0.08
PERSPECTIVE_MIN_COMPONENT_AREA: int = 200
PERSPECTIVE_MORPH_KERNEL_SIZE: int = 7
# Chi tiết chấu/đá ở rìa phối cảnh dễ bị mask bỏ sót vài pixel.
# Dùng biên an toàn lớn hơn view thường; bbox vẫn bị chặn trong panel tương ứng.
PERSPECTIVE_PADDING_PX: int = 16
PERSPECTIVE_MIN_IOU_THRESHOLD: float = 0.05
PERSPECTIVE_MAX_CENTER_DISTANCE_RATIO: float = 0.50
PERSPECTIVE_MIN_AREA_RATIO: float = 0.02
PERSPECTIVE_MAX_AREA_RATIO: float = 2.50
PERSPECTIVE_RED_MIN_SATURATION: int = 45
PERSPECTIVE_RED_MIN_VALUE: int = 45
PERSPECTIVE_RED_LOW_HUE_MAX: int = 8
PERSPECTIVE_RED_HIGH_HUE_MIN: int = 172
# Chỉ loại nét/nhãn kích thước màu đỏ mảnh. Không được loại các mảng vật thể
# màu đỏ/hồng (thường gặp ở ảnh render phối cảnh).
PERSPECTIVE_RED_ANNOTATION_MAX_THICKNESS: int = 8
PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_SIZE: int = 40
PERSPECTIVE_RED_ANNOTATION_MAX_GLYPH_AREA: int = 500
PERSPECTIVE_GRAY_MAX_SATURATION: int = 32
PERSPECTIVE_GRAY_MIN_VALUE: int = 30
PERSPECTIVE_GRAY_MAX_VALUE: int = 225
PERSPECTIVE_BACKGROUND_VALUE: int = 255

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
