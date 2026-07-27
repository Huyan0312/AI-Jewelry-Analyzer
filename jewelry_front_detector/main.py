"""
main.py
Điểm khởi chạy chính của ứng dụng Jewelry FRONT Detector.
"""

import sys
import os

# Đảm bảo Python tìm đúng module trong thư mục dự án
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from gui import MainWindow
from logger_utils import get_logger

logger = get_logger("jewelry_detector.main")


def main():
    logger.info("=" * 60)
    logger.info("Khởi động Jewelry FRONT Detector")
    logger.info("=" * 60)

    # Bật High DPI scaling trước khi tạo QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Jewelry FRONT Detector")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("JewelryAI")

    # Font mặc định
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    logger.info("Giao diện đã khởi động.")
    exit_code = app.exec()
    logger.info(f"Ứng dụng kết thúc với mã: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
