"""
gui.py
Giao diện PySide6 cho Jewelry Front Detector.
Sử dụng QThread để tránh treo giao diện khi gọi API.
"""

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

# Qt 6 đã hỗ trợ High-DPI mặc định. Các biến này giúp Windows 150%
# giữ kích thước theo logical pixel và tránh làm tròn scale gây lệch bố cục.
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
from typing import Optional

from PySide6.QtCore import (
    Qt, QThread, Signal, QObject, QSize, QTimer, QSettings
)
from PySide6.QtGui import (
    QPixmap, QFont, QColor, QPalette, QIcon, QImage
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTextEdit, QFileDialog, QProgressBar, QSplitter,
    QGroupBox, QScrollArea, QStatusBar, QMessageBox,
    QSizePolicy, QFrame, QGridLayout, QComboBox, QTabWidget
)

import numpy as np

from config import (
    LMSTUDIO_BASE_URL, DEFAULT_MODEL, OUTPUT_DIR, AUTO_TEST_DIR,
    ENABLE_OPENCV_REFINE, DEBUG_MODE,
)
from logger_utils import get_logger

logger = get_logger("jewelry_detector.gui")


# =============================================================================
# WORKER THREAD
# =============================================================================

class AnalysisWorker(QObject):
    """Worker chạy trong QThread – gọi API và xử lý ảnh."""

    progress = Signal(str)          # message tiến trình
    finished = Signal(dict)         # kết quả JSON
    error = Signal(str)             # thông báo lỗi

    def __init__(self, image_path: Path, model_name: str, base_url: str, target_view: str = "FRONT"):
        super().__init__()
        self.image_path = image_path
        self.model_name = model_name
        self.base_url = base_url
        self.target_view = target_view

    def run(self):
        try:
            import time
            start_time = time.time()
            import lmstudio_client as lm
            import image_processor as ip
            import bbox_utils as bu
            from config import ENABLE_OPENCV_REFINE
            from logger_utils import log_separator

            log_separator(logger, f"Phân tích: {self.image_path.name}")

            self.progress.emit(f"🤖 Đang gửi ảnh tới model '{self.model_name}'...")
            res = lm.send_image_to_model(
                self.image_path, model=self.model_name, base_url=self.base_url, target_view=self.target_view
            )

            if res.get("error") or not res.get("parsed_json"):
                self.error.emit(f"Lỗi: {res.get('error') or 'Không nhận được kết quả hợp lệ từ model.'}\n\nChi tiết:\n{res.get('raw_response', '')}")
                return

            parsed_json = res["parsed_json"]
            raw_response = res.get("raw_response", "")

            self.progress.emit("✅ Model phản hồi thành công. Đang xử lý ảnh...")
            
            scale_type, multiplier = bu.detect_coordinate_scale(parsed_json)
            if multiplier != 1.0:
                parsed_json = bu.rescale_response_coords(parsed_json, multiplier)
                
            result = ip.process_image(
                self.image_path,
                parsed_json,
                self.model_name,
                scale_type,
                enable_refine=ENABLE_OPENCV_REFINE,
                target_view=self.target_view
            )

            elapsed = time.time() - start_time
            self.progress.emit(f"⏱️ Thời gian xử lý: {elapsed:.2f} giây")
            from result_contract import nonempty_file
            single_success = bool(
                result.get("validation", {}).get("valid")
                and nonempty_file(result.get("output_files", {}).get("object_image"))
            )
            result["status"] = "SUCCESS" if single_success else "FAILED"
            self.progress.emit("✅ Hoàn tất!" if single_success else "⚠️ Hoàn tất nhưng output chưa hợp lệ.")
            result["_raw_response"] = raw_response
            self.finished.emit(result)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Worker lỗi: {tb}")
            self.error.emit(f"Lỗi không mong đợi:\n{e}\n\nChi tiết:\n{tb}")

class AnalysisAllViewsWorker(QObject):
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, image_path: Path, model_name: str, base_url: str):
        super().__init__()
        self.image_path = image_path
        self.model_name = model_name
        self.base_url = base_url

    def run(self):
        try:
            import time
            start_time = time.time()
            import lmstudio_client as lm
            import image_processor as ip
            import bbox_utils as bu
            from result_contract import build_all_views_result
            from config import ENABLE_OPENCV_REFINE
            from logger_utils import log_separator

            log_separator(logger, f"Phân tích ALL VIEWS: {self.image_path.name}")

            self.progress.emit("📐 Đang đọc kích thước ảnh gốc...")
            width, height = ip.read_image_size(self.image_path)
            
            self.progress.emit(f"🤖 Đang gửi ảnh tới model '{self.model_name}' (1 Lần duy nhất)...")
            res = lm.send_image_to_model_all_views(
                self.image_path, model=self.model_name, base_url=self.base_url
            )

            parsed_json_list = res.get("views")
            raw_response = res.get("raw_response", "")
            sheet = res.get("sheet", {})

            if res.get("error") or not parsed_json_list:
                self.error.emit(f"Lỗi: {res.get('error') or 'Không nhận được danh sách kết quả hợp lệ.'}\n\nChi tiết:\n{raw_response}")
                return
                
            self.progress.emit(f"✅ Model phản hồi. Đang xử lý {len(parsed_json_list)} views...")
            
            all_results = []
            for item in parsed_json_list:
                view_name = item.get("view", "UNKNOWN")
                self.progress.emit(f"✂️ Đang cắt {view_name}...")
                try:
                    scale_type, multiplier = bu.detect_coordinate_scale(item)
                    if multiplier != 1.0:
                        item = bu.rescale_response_coords(item, multiplier)

                    result = ip.process_image(
                        self.image_path,
                        item,
                        self.model_name,
                        scale_type,
                        enable_refine=ENABLE_OPENCV_REFINE,
                        target_view=view_name,
                        save_json=False
                    )
                    result["view_name"] = view_name
                    all_results.append(result)
                except Exception as view_error:
                    logger.error(f"View {view_name} xử lý thất bại: {view_error}")
                    all_results.append({
                        "view_name": view_name,
                        "error": str(view_error),
                        "output_files": {},
                        "validation": {
                            "valid": False,
                            "warnings": [str(view_error)],
                        },
                    })
                
            elapsed = time.time() - start_time
            self.progress.emit(f"⏱️ Tổng thời gian xử lý toàn bộ: {elapsed:.2f} giây")
            all_views_result = build_all_views_result(
                sheet=sheet,
                views=all_results,
                raw_response=raw_response,
            )
            all_views_result["image_size"] = {"width": width, "height": height}
            if all_views_result["status"] == "SUCCESS":
                self.progress.emit("✅ Hoàn thành đủ và lưu thành công 7 views!")
            else:
                val = all_views_result["validation"]
                self.progress.emit(
                    "⚠️ Kết quả chưa đầy đủ: "
                    f"received={val['views_received']}/7, saved={val['views_saved']}/7"
                )
            self.finished.emit(all_views_result)
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.error.emit(f"Lỗi không mong đợi:\n{e}\n\nChi tiết:\n{tb}")

class ConnectionWorker(QObject):
    """Worker kiểm tra kết nối LM Studio."""
    # Phát ra (ok, message, danh_sach_model)
    finished = Signal(bool, str, list)

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url

    def run(self):
        from lmstudio_client import check_connection
        ok, msg, models = check_connection(self.base_url)
        self.finished.emit(ok, msg, models)


# =============================================================================
# WIDGET HIỂN THỊ ẢNH
# =============================================================================

class ImageViewer(QLabel):
    """Label hiển thị ảnh với tự động scale."""

    def __init__(self, placeholder: str = "Chưa có ảnh", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self._pixmap_original: Optional[QPixmap] = None
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(160, 110)
        self.setStyleSheet("""
            QLabel {
                background: #f8fafc;
                border: 2px dashed #b7c6d8;
                border-radius: 10px;
                color: #64748b;
                font-size: 13px;
            }
        """)
        self.setText(placeholder)

    def set_image_path(self, path: str) -> None:
        px = QPixmap(path)
        if px.isNull():
            self.setText(f"Không tải được ảnh:\n{path}")
            return
        self._pixmap_original = px
        self._update_display()

    def set_cv2_image(self, bgr_array: np.ndarray) -> None:
        """Hiển thị ảnh từ numpy BGR array."""
        import cv2
        rgb = cv2.cvtColor(bgr_array, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * c, QImage.Format_RGB888)
        px = QPixmap.fromImage(qimg)
        self._pixmap_original = px
        self._update_display()

    def _update_display(self) -> None:
        if self._pixmap_original:
            orig_size = self._pixmap_original.size()
            target_size = self.size()
            
            # Không upscale quá kích thước thật của ảnh để tránh mờ
            if target_size.width() > orig_size.width() and target_size.height() > orig_size.height():
                target_size = orig_size
                
            scaled = self._pixmap_original.scaled(
                target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()


# =============================================================================
# MAIN WINDOW
# =============================================================================

class MainWindow(QMainWindow):
    """Cửa sổ chính tối ưu cho màn 2K và Windows scaling 150%."""

    # 2560x1440 ở Windows scale 150% tương đương khoảng 1707x960 logical px.
    # Các giá trị dưới đây đủ rộng nhưng vẫn chừa taskbar và viền cửa sổ.
    DEFAULT_WINDOW_WIDTH = 1500
    DEFAULT_WINDOW_HEIGHT = 840

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jewelry View Detector - LM Studio Vision")
        self.setMinimumSize(1080, 680)

        self._image_path: Optional[str] = None
        self._worker_thread: Optional[QThread] = None
        self.worker: Optional[AnalysisWorker] = None
        self._conn_thread: Optional[QThread] = None
        self._conn_worker: Optional[ConnectionWorker] = None
        self._result_data: Optional[dict] = None

        self._apply_light_theme()
        self._build_ui()
        self._load_settings()
        self._restore_window_state()
        self.statusBar().showMessage("Sẵn sàng.")

    # ------------------------------------------------------------------
    # THEME
    # ------------------------------------------------------------------
    def _apply_light_theme(self):
        """Giao diện sáng dịu, tối ưu độ tương phản cho bản vẽ trang sức."""
        app = QApplication.instance()
        if app is None:
            return

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f3f6fa"))
        palette.setColor(QPalette.WindowText, QColor("#1f2937"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#eef3f8"))
        palette.setColor(QPalette.Text, QColor("#1f2937"))
        palette.setColor(QPalette.Button, QColor("#ffffff"))
        palette.setColor(QPalette.ButtonText, QColor("#1f2937"))
        palette.setColor(QPalette.Highlight, QColor("#2563eb"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor("#1f2937"))
        app.setPalette(palette)

        app.setStyleSheet("""
            * {
                font-family: "Segoe UI", "Segoe UI Emoji", sans-serif;
                font-size: 13px;
            }
            QMainWindow, QWidget {
                background-color: #f3f6fa;
                color: #1f2937;
            }
            QWidget#headerBar {
                background: #ffffff;
                border: 1px solid #d8e1ec;
                border-radius: 12px;
            }
            QLabel#appTitle {
                color: #173b70;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#appSubtitle, QLabel#mutedLabel {
                color: #64748b;
                font-size: 11px;
            }
            QLabel#sectionHint {
                color: #64748b;
                font-size: 12px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d8e1ec;
                border-radius: 10px;
                margin-top: 13px;
                padding: 9px;
                padding-top: 13px;
                font-weight: 650;
                color: #1d4ed8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                background: #f3f6fa;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 8px;
                color: #1f2937;
                selection-background-color: #bfdbfe;
                selection-color: #172554;
            }
            QLineEdit:hover, QComboBox:hover, QTextEdit:hover {
                border-color: #94a3b8;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #3b82f6;
            }
            QLineEdit[readOnly="true"] {
                color: #64748b;
                background: #f8fafc;
            }
            QComboBox {
                min-height: 22px;
                padding-right: 24px;
            }
            QComboBox::drop-down {
                border: 0;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #1f2937;
                border: 1px solid #cbd5e1;
                selection-background-color: #dbeafe;
                selection-color: #1e3a8a;
                outline: 0;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 7px 12px;
                min-height: 20px;
                color: #334155;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #eff6ff;
                border-color: #60a5fa;
                color: #1d4ed8;
            }
            QPushButton:pressed {
                background: #dbeafe;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background: #f1f5f9;
                border-color: #e2e8f0;
            }
            QPushButton#btnPrimary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #3b82f6);
                border-color: #2563eb;
                color: #ffffff;
                font-weight: 700;
                padding: 8px 18px;
            }
            QPushButton#btnPrimary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1d4ed8, stop:1 #2563eb);
                border-color: #1d4ed8;
                color: #ffffff;
            }
            QPushButton#btnConnect {
                background: #eaf3ff;
                border-color: #93c5fd;
                color: #1d4ed8;
            }
            QPushButton#btnConnect:hover {
                background: #dbeafe;
                border-color: #60a5fa;
            }
            QPushButton#btnQuiet {
                background: #f8fafc;
            }
            QPushButton#btnQuiet:hover {
                background: #eff6ff;
            }
            QProgressBar {
                min-height: 17px;
                max-height: 17px;
                border: 1px solid #bfdbfe;
                border-radius: 7px;
                text-align: center;
                background: #eaf2fb;
                color: #1e3a8a;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #38bdf8);
                border-radius: 6px;
            }
            QSplitter::handle {
                background: #dce5ef;
            }
            QSplitter::handle:hover {
                background: #60a5fa;
            }
            QSplitter::handle:horizontal {
                width: 6px;
                margin: 3px 1px;
                border-radius: 3px;
            }
            QSplitter::handle:vertical {
                height: 6px;
                margin: 1px 3px;
                border-radius: 3px;
            }
            QTabWidget::pane {
                border: 1px solid #d8e1ec;
                border-radius: 9px;
                top: -1px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #eaf0f7;
                color: #64748b;
                border: 1px solid #d8e1ec;
                padding: 7px 14px;
                margin-right: 3px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:hover {
                color: #1d4ed8;
                background: #eff6ff;
            }
            QTabBar::tab:selected {
                color: #1d4ed8;
                background: #ffffff;
                border-bottom-color: #ffffff;
                font-weight: 650;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #edf2f7;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #b8c5d4;
                border-radius: 5px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar:horizontal {
                background: #edf2f7;
                height: 10px;
            }
            QScrollBar::handle:horizontal {
                background: #b8c5d4;
                border-radius: 5px;
                min-width: 28px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0;
                height: 0;
            }
            QStatusBar {
                background: #ffffff;
                border-top: 1px solid #d8e1ec;
                color: #64748b;
            }
            QToolTip {
                color: #1f2937;
                background: #ffffff;
                border: 1px solid #93c5fd;
                padding: 5px;
            }
            QMessageBox {
                background: #ffffff;
            }
        """)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(9)

        # Header gọn: các thao tác thường dùng luôn nằm trên cùng.
        header = QWidget()
        header.setObjectName("headerBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 9, 10, 9)
        header_layout.setSpacing(9)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("💎 Jewelry View Detector")
        title.setObjectName("appTitle")
        subtitle = QLabel("Tách view bản vẽ bằng LM Studio Vision")
        subtitle.setObjectName("appSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)

        header_layout.addWidget(QLabel("View:"))
        self.combo_view = QComboBox()
        self.combo_view.addItems([
            "FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "BACK", "PERSPECTIVE"
        ])
        self.combo_view.setMinimumWidth(135)
        self.combo_view.currentTextChanged.connect(self._on_view_changed)
        header_layout.addWidget(self.combo_view)

        self.btn_choose = QPushButton("📁 Chọn ảnh")
        self.btn_choose.clicked.connect(self._on_choose_image)
        header_layout.addWidget(self.btn_choose)

        self.btn_open_output = QPushButton("📂 Output")
        self.btn_open_output.setObjectName("btnQuiet")
        self.btn_open_output.clicked.connect(self._on_open_output)
        header_layout.addWidget(self.btn_open_output)

        self.btn_analyze = QPushButton("🚀 Phân tích FRONT")
        self.btn_analyze.setObjectName("btnPrimary")
        self.btn_analyze.setMinimumWidth(150)
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self._on_analyze)
        header_layout.addWidget(self.btn_analyze)

        self.btn_analyze_all = QPushButton("⚡ Phân tích All Views")
        self.btn_analyze_all.setObjectName("btnPrimary")
        self.btn_analyze_all.setMinimumWidth(160)
        self.btn_analyze_all.setEnabled(False)
        self.btn_analyze_all.clicked.connect(self._on_analyze_all)
        header_layout.addWidget(self.btn_analyze_all)
        root.addWidget(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # Splitter chính: settings trái, workspace phải.
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)
        root.addWidget(self.main_splitter, 1)

        self.main_splitter.addWidget(self._build_left_panel())
        self.main_splitter.addWidget(self._build_workspace())
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([330, 1140])

    def _build_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(295)
        scroll.setMaximumWidth(430)

        content = QWidget()
        content.setMinimumWidth(275)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(8)

        # Input image
        grp_img = QGroupBox("Ảnh đầu vào")
        img_layout = QVBoxLayout(grp_img)
        img_layout.setContentsMargins(9, 12, 9, 9)
        img_layout.setSpacing(6)
        self.lbl_path = QLineEdit("Chưa chọn ảnh")
        self.lbl_path.setReadOnly(True)
        self.lbl_path.setToolTip("Đường dẫn ảnh đang được phân tích")
        img_hint = QLabel("Hỗ trợ JPG, JPEG, PNG và WEBP")
        img_hint.setObjectName("mutedLabel")
        img_layout.addWidget(self.lbl_path)
        img_layout.addWidget(img_hint)
        layout.addWidget(grp_img)

        # LM Studio config
        grp_api = QGroupBox("Cấu hình LM Studio")
        api_layout = QGridLayout(grp_api)
        api_layout.setContentsMargins(9, 12, 9, 9)
        api_layout.setHorizontalSpacing(8)
        api_layout.setVerticalSpacing(7)
        api_layout.setColumnStretch(1, 1)

        api_layout.addWidget(QLabel("Base URL"), 0, 0)
        self.inp_url = QLineEdit(LMSTUDIO_BASE_URL)
        self.inp_url.setPlaceholderText("http://127.0.0.1:1234/v1")
        api_layout.addWidget(self.inp_url, 0, 1)

        api_layout.addWidget(QLabel("Model"), 1, 0)
        self.inp_model = QLineEdit(DEFAULT_MODEL)
        self.inp_model.setPlaceholderText("Tên model đang load")
        api_layout.addWidget(self.inp_model, 1, 1)

        self.btn_connect = QPushButton("🔌 Kiểm tra kết nối")
        self.btn_connect.setObjectName("btnConnect")
        self.btn_connect.clicked.connect(self._on_check_connection)
        api_layout.addWidget(self.btn_connect, 2, 0, 1, 2)

        self.lbl_connect_status = QLabel("Chưa kiểm tra kết nối")
        self.lbl_connect_status.setObjectName("mutedLabel")
        self.lbl_connect_status.setWordWrap(True)
        api_layout.addWidget(self.lbl_connect_status, 3, 0, 1, 2)
        layout.addWidget(grp_api)

        # Tabs thay cho hai khung xếp dọc gây tràn chiều cao.
        self.info_tabs = QTabWidget()
        self.info_tabs.setDocumentMode(True)
        self.info_tabs.setMinimumHeight(220)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Tiến trình xử lý sẽ xuất hiện tại đây...")
        self.txt_log.setLineWrapMode(QTextEdit.WidgetWidth)

        self.txt_json = QTextEdit()
        self.txt_json.setReadOnly(True)
        self.txt_json.setPlaceholderText("JSON kết quả sẽ xuất hiện tại đây...")
        self.txt_json.setLineWrapMode(QTextEdit.NoWrap)

        self.info_tabs.addTab(self.txt_log, "📋 Tiến trình")
        self.info_tabs.addTab(self.txt_json, "{ } JSON")
        layout.addWidget(self.info_tabs, 1)

        note = QLabel(
            "Mẹo: kéo thanh chia ở giữa để tăng vùng xem ảnh. "
            "Vị trí sẽ được tự động lưu."
        )
        note.setObjectName("sectionHint")
        note.setWordWrap(True)
        layout.addWidget(note)

        scroll.setWidget(content)
        return scroll

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.workspace_splitter = QSplitter(Qt.Vertical)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(6)
        layout.addWidget(self.workspace_splitter)

        # Hàng trên: ảnh gốc và ảnh có bounding box.
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        self.preview_splitter = QSplitter(Qt.Horizontal)
        self.preview_splitter.setChildrenCollapsible(False)
        self.preview_splitter.setHandleWidth(6)
        top_layout.addWidget(self.preview_splitter)

        grp_orig = QGroupBox("Ảnh gốc")
        orig_layout = QVBoxLayout(grp_orig)
        orig_layout.setContentsMargins(8, 12, 8, 8)
        self.viewer_original = ImageViewer("Chưa chọn ảnh")
        orig_layout.addWidget(self.viewer_original)
        self.preview_splitter.addWidget(grp_orig)

        grp_result = QGroupBox("Kết quả + Bounding Box")
        result_layout = QVBoxLayout(grp_result)
        result_layout.setContentsMargins(8, 12, 8, 8)
        self.viewer_result = ImageViewer("Chưa có kết quả")
        result_layout.addWidget(self.viewer_result)
        self.preview_splitter.addWidget(grp_result)
        self.preview_splitter.setSizes([680, 680])

        # Hàng dưới: crop; không khóa cứng 220 px như phiên bản cũ.
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        self.crop_splitter = QSplitter(Qt.Horizontal)
        self.crop_splitter.setChildrenCollapsible(False)
        self.crop_splitter.setHandleWidth(6)
        bottom_layout.addWidget(self.crop_splitter)

        grp_panel = QGroupBox("Panel Crop")
        panel_layout = QVBoxLayout(grp_panel)
        panel_layout.setContentsMargins(8, 12, 8, 8)
        panel_layout.setSpacing(6)
        self.viewer_panel = ImageViewer("Chưa có panel crop")
        panel_layout.addWidget(self.viewer_panel, 1)

        self.txt_ai_result = QTextEdit()
        self.txt_ai_result.setReadOnly(True)
        self.txt_ai_result.setMinimumHeight(52)
        self.txt_ai_result.setMaximumHeight(76)
        self.txt_ai_result.setPlaceholderText("AI kiểm tra crop sẽ hiển thị tại đây...")
        self.txt_ai_result.setStyleSheet("""
            QTextEdit {
                color: #8a5a00;
                font-weight: 650;
                background: #fff8df;
                border: 1px solid #e5bd55;
                border-radius: 7px;
                padding: 5px 7px;
            }
        """)
        panel_layout.addWidget(self.txt_ai_result)
        self.crop_splitter.addWidget(grp_panel)

        grp_obj = QGroupBox("Object Crop")
        object_layout = QVBoxLayout(grp_obj)
        object_layout.setContentsMargins(8, 12, 8, 8)
        self.viewer_object = ImageViewer("Chưa có object crop")
        object_layout.addWidget(self.viewer_object)
        self.crop_splitter.addWidget(grp_obj)
        self.crop_splitter.setSizes([680, 680])

        self.workspace_splitter.addWidget(top)
        self.workspace_splitter.addWidget(bottom)
        self.workspace_splitter.setStretchFactor(0, 7)
        self.workspace_splitter.setStretchFactor(1, 3)
        self.workspace_splitter.setSizes([650, 320])
        return workspace

    # ------------------------------------------------------------------
    # WINDOW STATE
    # ------------------------------------------------------------------
    def _restore_window_state(self):
        settings = QSettings("JewelryAI", "FrontDetector")
        geometry = settings.value("ui/geometry")

        restored = bool(geometry and self.restoreGeometry(geometry))
        if not restored:
            screen = QApplication.primaryScreen()
            if screen:
                available = screen.availableGeometry()
                width = min(self.DEFAULT_WINDOW_WIDTH, int(available.width() * 0.90))
                height = min(self.DEFAULT_WINDOW_HEIGHT, int(available.height() * 0.90))
                width = max(width, self.minimumWidth())
                height = max(height, self.minimumHeight())
                self.resize(width, height)
                frame = self.frameGeometry()
                frame.moveCenter(available.center())
                self.move(frame.topLeft())
            else:
                self.resize(self.DEFAULT_WINDOW_WIDTH, self.DEFAULT_WINDOW_HEIGHT)

        splitter_map = {
            "ui/main_splitter": self.main_splitter,
            "ui/workspace_splitter": self.workspace_splitter,
            "ui/preview_splitter": self.preview_splitter,
            "ui/crop_splitter": self.crop_splitter,
        }
        for key, splitter in splitter_map.items():
            state = settings.value(key)
            if state:
                splitter.restoreState(state)

        # Geometry cũ có thể được lưu từ scale 100% hoặc từ màn hình khác.
        # Chuẩn hóa sau khi Qt đã gán screen để cửa sổ không tràn khỏi màn 2K/150%.
        QTimer.singleShot(0, self._fit_window_to_current_screen)

    def _fit_window_to_current_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        max_width = max(self.minimumWidth(), int(available.width() * 0.96))
        max_height = max(self.minimumHeight(), int(available.height() * 0.96))

        new_width = min(self.width(), max_width)
        new_height = min(self.height(), max_height)
        if new_width != self.width() or new_height != self.height():
            self.resize(new_width, new_height)

        frame = self.frameGeometry()
        visible = frame.intersected(available)
        mostly_offscreen = (
            visible.width() < min(240, frame.width())
            or visible.height() < min(160, frame.height())
        )
        if mostly_offscreen or not available.contains(frame.center()):
            frame.moveCenter(available.center())
            self.move(frame.topLeft())

    def _save_window_state(self):
        settings = QSettings("JewelryAI", "FrontDetector")
        settings.setValue("ui/geometry", self.saveGeometry())
        settings.setValue("ui/main_splitter", self.main_splitter.saveState())
        settings.setValue("ui/workspace_splitter", self.workspace_splitter.saveState())
        settings.setValue("ui/preview_splitter", self.preview_splitter.saveState())
        settings.setValue("ui/crop_splitter", self.crop_splitter.saveState())
        settings.sync()

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------
    def _on_choose_image(self):
        initial_dir = AUTO_TEST_DIR if AUTO_TEST_DIR.is_dir() else OUTPUT_DIR
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh bản vẽ trang sức",
            str(initial_dir),
            "Ảnh (*.jpg *.jpeg *.png *.webp);;Tất cả tệp (*)"
        )
        if not path:
            return

        self._image_path = path
        self.lbl_path.setText(path)
        self.lbl_path.setToolTip(path)
        self.viewer_original.set_image_path(path)
        self.btn_analyze.setEnabled(True)
        self.btn_analyze_all.setEnabled(True)
        self._log(f"📁 Đã chọn ảnh: {Path(path).name}")

    def _on_view_changed(self, text):
        self.btn_analyze.setText(f"🚀 Phân tích {text}")

    def _on_check_connection(self):
        url = self.inp_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Thiếu URL", "Vui lòng nhập LM Studio Base URL.")
            return
        if self._conn_thread and self._conn_thread.isRunning():
            return

        self.btn_connect.setEnabled(False)
        self.lbl_connect_status.setText("⏳ Đang kiểm tra kết nối...")
        self.lbl_connect_status.setStyleSheet("color: #64748b;")

        self._conn_thread = QThread(self)
        self._conn_worker = ConnectionWorker(url)
        self._conn_worker.moveToThread(self._conn_thread)
        self._conn_thread.started.connect(self._conn_worker.run)
        self._conn_worker.finished.connect(self._on_connection_result)
        self._conn_worker.finished.connect(self._conn_thread.quit)
        self._conn_worker.finished.connect(self._conn_worker.deleteLater)
        self._conn_thread.finished.connect(self._on_connection_thread_finished)
        self._conn_thread.finished.connect(self._conn_thread.deleteLater)
        self._conn_thread.start()

    def _on_connection_thread_finished(self):
        self._conn_worker = None
        self._conn_thread = None

    def _on_connection_result(self, ok: bool, msg: str, models: list):
        self.btn_connect.setEnabled(True)
        if ok:
            self.lbl_connect_status.setText(f"✅ {msg}")
            self.lbl_connect_status.setStyleSheet("color: #15803d; font-weight: 600;")
            if models:
                self.inp_model.setText(models[0])
                self._log(f"✅ Đã đồng bộ model: {models[0]}")
                if len(models) > 1:
                    self._log(f"ℹ️ Các model khác đang load: {', '.join(models[1:])}")
        else:
            self.lbl_connect_status.setText(f"❌ {msg}")
            self.lbl_connect_status.setStyleSheet("color: #dc2626; font-weight: 600;")

    def _on_analyze(self):
        if not self._image_path:
            QMessageBox.warning(self, "Chưa chọn ảnh", "Vui lòng chọn ảnh trước.")
            return
        if self._worker_thread and self._worker_thread.isRunning():
            return

        model = self.inp_model.text().strip()
        url = self.inp_url.text().strip()
        if not model:
            QMessageBox.warning(self, "Thiếu model", "Vui lòng nhập tên model.")
            return
        if not url:
            QMessageBox.warning(self, "Thiếu URL", "Vui lòng nhập LM Studio Base URL.")
            return

        self._set_processing(True)
        self.txt_log.clear()
        self.txt_json.clear()
        self.txt_ai_result.clear()
        self.info_tabs.setCurrentWidget(self.txt_log)
        self._log(f"🚀 Bắt đầu phân tích {self.combo_view.currentText()}...")

        self._worker_thread = QThread(self)
        self.worker = AnalysisWorker(
            Path(self._image_path),
            model,
            url,
            target_view=self.combo_view.currentText(),
        )
        self.worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._log)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.finished.connect(self._worker_thread.quit)
        self.worker.error.connect(self._worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self._worker_thread.finished.connect(self._on_analysis_thread_finished)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def _on_analysis_thread_finished(self):
        self.worker = None
        self._worker_thread = None

    def _on_analyze_all(self):
        if not self._image_path:
            QMessageBox.warning(self, "Chưa chọn ảnh", "Vui lòng chọn ảnh trước.")
            return
        if self._worker_thread and self._worker_thread.isRunning():
            return

        model = self.inp_model.text().strip()
        url = self.inp_url.text().strip()
        if not model or not url:
            QMessageBox.warning(self, "Thiếu cấu hình", "Vui lòng nhập model và URL.")
            return

        self._set_processing(True)
        self.txt_log.clear()
        self.txt_json.clear()
        self.txt_ai_result.clear()
        self.info_tabs.setCurrentWidget(self.txt_log)
        self._log("⚡ Bắt đầu phân tích Tất cả Views...")

        self._worker_thread = QThread(self)
        self.worker = AnalysisAllViewsWorker(Path(self._image_path), model, url)
        self.worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._log)
        self.worker.finished.connect(self._on_analyze_all_done)
        self.worker.error.connect(self._on_analysis_error)
        
        self.worker.finished.connect(self._worker_thread.quit)
        self.worker.error.connect(self._worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self._worker_thread.finished.connect(self._on_analysis_thread_finished)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def _on_analyze_all_done(self, all_views_result):
        self._set_processing(False)
        
        import image_processor as ip
        from result_contract import save_json_with_self_path
        from config import OUTPUT_DIR
        
        try:
            all_results = all_views_result.get("views", [])
            img_bgr = ip.load_cv2_image(Path(self._image_path))
            
            for res in all_results:
                view_name = res.get("view_name", "UNKNOWN")
                pixel_info = res.get("pixel", {})
                
                panel_px = pixel_info.get("refined_panel_bbox")
                if not panel_px:
                    panel_px = pixel_info.get("ai_panel_bbox")
                    
                obj_px = pixel_info.get("refined_object_bbox")
                if not obj_px:
                    obj_px = pixel_info.get("ai_object_bbox")
                
                img_bgr = ip.draw_results_on_image(
                    img_bgr,
                    panel_bbox_px=panel_px,
                    # Preview tổng chỉ hiển thị bbox cuối. Trước đây bbox
                    # refined bị truyền nhầm vào ô AI nên luôn có khung cam
                    # "AI Object", trông như kết quả còn phạm số đo đỏ.
                    ai_obj_bbox_px=None,
                    refined_obj_bbox_px=obj_px,
                    center_px=None,
                    target_view=view_name
                )
            
            preview_dir = OUTPUT_DIR / ".preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            output_path = preview_dir / f"{Path(self._image_path).stem}_all_views.jpg"
            if ip.save_cv2_image(img_bgr, output_path):
                all_views_result.setdefault("output_files", {})["preview_image"] = str(output_path)
            
            master_json_path = OUTPUT_DIR / f"{Path(self._image_path).stem}_all_views_result.json"
            if not save_json_with_self_path(all_views_result, master_json_path, "json"):
                all_views_result["status"] = "PARTIAL" if all_results else "FAILED"
                all_views_result["validation"]["valid"] = False
                all_views_result["validation"].setdefault("errors", []).append(
                    "Không lưu được master JSON"
                )

            preview_path = all_views_result.get("output_files", {}).get("preview_image")
            if preview_path:
                self.viewer_result.set_image_path(preview_path)

            status = all_views_result.get("status", "FAILED")
            validation = all_views_result.get("validation", {})
            if status == "SUCCESS":
                self.statusBar().showMessage("✅ Đã xử lý và lưu đủ 7 views!")
            else:
                self.statusBar().showMessage(
                    f"⚠️ {status}: nhận {validation.get('views_received', 0)}/7, "
                    f"lưu {validation.get('views_saved', 0)}/7 views"
                )
            self._log(
                f"Trạng thái {status}: received={validation.get('views_received', 0)}/7, "
                f"saved={validation.get('views_saved', 0)}/7"
            )
            self.txt_json.setPlainText(json.dumps(all_views_result, ensure_ascii=False, indent=2))
            self.info_tabs.setCurrentWidget(self.txt_json)
        except Exception as e:
            self._on_analysis_error(f"Lỗi khi hiển thị kết quả: {e}")

    def _on_analysis_done(self, result: dict):
        self._set_processing(False)
        self._result_data = result

        display = {key: value for key, value in result.items() if key != "_raw_response"}
        self.txt_json.setPlainText(json.dumps(display, ensure_ascii=False, indent=2))

        files = result.get("output_files", {})
        result_img = files.get("result_image")
        panel_img = files.get("panel_image")
        object_img = files.get("object_image")

        if result_img and Path(result_img).exists():
            self.viewer_result.set_image_path(result_img)
        if panel_img and Path(panel_img).exists():
            self.viewer_panel.set_image_path(panel_img)
        if object_img and Path(object_img).exists():
            self.viewer_object.set_image_path(object_img)

        ai_feedback = result.get("ai_validation_result")
        if ai_feedback:
            self.txt_ai_result.setPlainText(f"AI RESULT: {ai_feedback}")

        validation = result.get("validation", {})
        valid = (
            result.get("status") == "SUCCESS"
            and validation.get("valid", False)
        )
        warnings = validation.get("warnings", [])
        if valid:
            self.statusBar().showMessage("✅ Phân tích hoàn thành thành công!")
        else:
            short_warning = "; ".join(warnings[:2]) if warnings else "Có cảnh báo chưa xác định"
            self.statusBar().showMessage(f"⚠️ Hoàn thành: {short_warning}")
            if warnings:
                self._log(f"⚠️ Cảnh báo:\n{chr(10).join(warnings)}")

        processing_time = result.get("processing_time_sec", 0)
        self._log(f"⏱️ Thời gian xử lý: {processing_time:.2f}s")
        self.info_tabs.setCurrentWidget(self.txt_json)

    def _on_analysis_error(self, msg: str):
        self._set_processing(False)
        self.info_tabs.setCurrentWidget(self.txt_log)
        self._log(f"❌ Lỗi:\n{msg}")
        self.statusBar().showMessage("❌ Phân tích thất bại.")
        QMessageBox.critical(self, "Lỗi phân tích", msg)

    def _on_open_output(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(OUTPUT_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(OUTPUT_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Không mở được thư mục",
                f"Không thể mở thư mục output:\n{OUTPUT_DIR}\n\n{exc}",
            )

    def _set_processing(self, active: bool):
        self.btn_analyze.setEnabled(not active and bool(self._image_path))
        self.btn_analyze_all.setEnabled(not active and bool(self._image_path))
        self.btn_choose.setEnabled(not active)
        self.btn_connect.setEnabled(not active)
        self.combo_view.setEnabled(not active)
        self.inp_url.setEnabled(not active)
        self.inp_model.setEnabled(not active)
        self.progress_bar.setVisible(active)
        if active:
            self.statusBar().showMessage("⏳ Đang xử lý...")

    def _log(self, msg: str):
        self.txt_log.append(msg)
        scrollbar = self.txt_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------
    def _load_settings(self):
        settings = QSettings("JewelryAI", "FrontDetector")
        url = str(settings.value("lmstudio/base_url", "") or "").strip()
        model = str(settings.value("lmstudio/model", "") or "").strip()
        target_view = str(settings.value("target_view", "FRONT") or "FRONT")

        if url:
            self.inp_url.setText(url)
        if model:
            self.inp_model.setText(model)
        if self.combo_view.findText(target_view) >= 0:
            self.combo_view.setCurrentText(target_view)

    def _save_settings(self):
        settings = QSettings("JewelryAI", "FrontDetector")
        settings.setValue("lmstudio/base_url", self.inp_url.text().strip())
        settings.setValue("lmstudio/model", self.inp_model.text().strip())
        settings.setValue("target_view", self.combo_view.currentText())
        settings.sync()

    def closeEvent(self, event):
        analysis_running = self._worker_thread and self._worker_thread.isRunning()
        connection_running = self._conn_thread and self._conn_thread.isRunning()
        if analysis_running or connection_running:
            QMessageBox.information(
                self,
                "Đang xử lý",
                "Ứng dụng vẫn đang xử lý dữ liệu. Hãy chờ tác vụ hoàn tất rồi đóng cửa sổ.",
            )
            event.ignore()
            return

        self._save_settings()
        self._save_window_state()
        super().closeEvent(event)
