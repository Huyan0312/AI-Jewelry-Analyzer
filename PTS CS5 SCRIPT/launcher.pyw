"""
launcher.py - UI don gian de start/stop headless_detector.
"""
import sys
import os
import json
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QPlainTextEdit, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

BASE_DIR      = Path(__file__).parent.resolve()
DETECTOR_PY   = BASE_DIR / "headless_detector.py"
INPUT_DIR     = BASE_DIR / "input"
OUTPUT_DIR    = BASE_DIR / "output"
CACHE_DIR     = BASE_DIR / "cache"
LOCK_FILE     = BASE_DIR / ".detector.lock"
STATUS_FILE   = CACHE_DIR / "launcher_status.json"
PYTHON_EXE    = sys.executable   # dung chinh Python dang chay launcher nay


# ─────────────────────────────────────────────
# Worker: doc stdout cua subprocess va emit log
# ─────────────────────────────────────────────
class DetectorWorker(QThread):
    log   = Signal(str)
    stopped = Signal()

    def __init__(self):
        super().__init__()
        self._proc = None

    def run(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        self._proc = subprocess.Popen(
            [PYTHON_EXE, str(DETECTOR_PY)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in self._proc.stdout:
            self.log.emit(line.rstrip())
        self._proc.wait()
        self.stopped.emit()

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=3)


# ─────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────
class LauncherWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Detector – Launcher")
        self.setFixedSize(480, 380)
        self._worker = None
        self._starting = False
        
        # Tao thu muc cache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._set_status_json(False)

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_status)
        self._timer.start(1000)

    def _set_status_json(self, is_running):
        try:
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump({"launcher_active": True, "detector_running": is_running}, f)
        except Exception:
            pass

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(16, 16, 16, 16)

        # ── Tieu de ──
        title = QLabel("🔍 AI View Detector")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main.addWidget(title)

        # ── Trang thai ──
        self.lbl_status = QLabel("● Chua chay")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setFont(QFont("Segoe UI", 10))
        self.lbl_status.setStyleSheet("color: #888;")
        main.addWidget(self.lbl_status)

        # ── Separator ──
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #ddd;")
        main.addWidget(sep)

        # ── Thu muc theo doi ──
        info = QLabel(f"📂 Input:  {INPUT_DIR}\n📤 Output: {OUTPUT_DIR}")
        info.setFont(QFont("Consolas", 8))
        info.setStyleSheet("color: #555;")
        main.addWidget(info)

        # ── Log ──
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 8))
        self.log_box.setStyleSheet(
            "background:#1e1e1e; color:#d4d4d4; border-radius:6px; padding:6px;"
        )
        main.addWidget(self.log_box)

        # ── Nut ──
        btn_row = QHBoxLayout()

        self.btn_start = QPushButton("▶  Start Detector")
        self.btn_start.setFixedHeight(38)
        self.btn_start.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_start.setStyleSheet(
            "QPushButton { background:#27ae60; color:white; border-radius:8px; }"
            "QPushButton:hover { background:#2ecc71; }"
            "QPushButton:disabled { background:#555; color:#999; }"
        )
        self.btn_start.clicked.connect(self._start)
        btn_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setFixedHeight(38)
        self.btn_stop.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(
            "QPushButton { background:#c0392b; color:white; border-radius:8px; }"
            "QPushButton:hover { background:#e74c3c; }"
            "QPushButton:disabled { background:#555; color:#999; }"
        )
        self.btn_stop.clicked.connect(self._stop)
        btn_row.addWidget(self.btn_stop)

        main.addLayout(btn_row)

    # ── Logic ──
    def _start(self):
        if self._starting or (self._worker and self._worker.isRunning()):
            return
        if LOCK_FILE.exists() and not self._cleanup_stale_detector():
            self._append_log("Detector khac dang chay. Chi can 1 instance.")
            return

        self._starting = True
        self.btn_start.setEnabled(False)
        try:
            self.log_box.clear()
            self._worker = DetectorWorker()
            self._worker.log.connect(self._append_log)
            self._worker.stopped.connect(self._on_stopped)
            self._worker.start()
            self.btn_stop.setEnabled(True)
            self.lbl_status.setText("● Dang chay")
            self.lbl_status.setStyleSheet("color: #27ae60; font-weight:bold;")
            self._append_log("=== Detector started ===")
            self._set_status_json(True)
        finally:
            self._starting = False

    def _cleanup_stale_detector(self):
        """Xoa lock cu neu process da chet. Tra ve False neu detector khac van dang chay."""
        lock = BASE_DIR / ".detector.lock"
        if not lock.exists():
            return True
        try:
            pid = int(lock.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            return False
        except ProcessLookupError:
            pass
        except (ValueError, PermissionError, OSError):
            pass
        try:
            lock.unlink()
        except OSError:
            pass
        return True

    def _stop(self):
        if self._worker:
            self._worker.stop()
        self.btn_stop.setEnabled(False)
        self._set_status_json(False)

    def _on_stopped(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("● Da dung")
        self.lbl_status.setStyleSheet("color: #e74c3c; font-weight:bold;")
        self._append_log("=== Detector stopped ===")
        self._set_status_json(False)

    def _append_log(self, text: str):
        self.log_box.appendPlainText(text)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

    def _update_status(self):
        try:
            waiting = sum(
                1 for f in INPUT_DIR.iterdir()
                if f.is_file() and (
                    f.name.endswith(".job.json")
                    or (
                        f.suffix.lower() in (".jpg", ".jpeg", ".png")
                        and not f.name.startswith("_")
                    )
                )
            )
            if self._worker and self._worker.isRunning() and waiting > 0:
                self.lbl_status.setText(f"● Dang xu ly ({waiting} anh trong hang)...")
        except Exception:
            pass

    def closeEvent(self, event):
        self._stop()
        try:
            if STATUS_FILE.exists():
                STATUS_FILE.unlink()
        except Exception:
            pass
        event.accept()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = LauncherWindow()
    win.show()
    sys.exit(app.exec())
