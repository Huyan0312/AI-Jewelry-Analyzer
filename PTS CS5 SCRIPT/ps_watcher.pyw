"""
ps_watcher.pyw
==============================================================
Chạy ngầm dưới dạng System Tray Icon.
Được tự động kích hoạt bởi Photoshop Script (START.jsx / START Auto.jsx).

Quy trình:
  1. Khi Photoshop Script kích hoạt -> ps_watcher.pyw chạy.
  2. Bật headless_detector.py NGAY LẬP TỨC.
  3. Kiểm tra & load model qwen/qwen3-vl-4b vào LM Studio.
  4. Theo dõi ứng dụng Photoshop mỗi 5s.
  5. Khi Photoshop tắt -> Tự động dừng detector & đóng watcher.
"""

import sys
import os
import json
import time
import threading
import subprocess
import datetime
import logging
from pathlib import Path

try:
    import pystray
    from pystray import MenuItem as item, Menu
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import tkinter as tk
    import tkinter.messagebox as mb
    root = tk.Tk()
    root.withdraw()
    mb.showerror(
        "Thiếu thư viện",
        "Vui lòng cài đặt:\n  pip install pystray pillow psutil requests"
    )
    sys.exit(1)

try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests as _req
except ImportError:
    _req = None

# ---------------------------------------------------------------
# Đường dẫn
# ---------------------------------------------------------------
BASE_DIR    = Path(__file__).parent.resolve()
DETECTOR_PY = BASE_DIR / "headless_detector.py"
CACHE_DIR   = BASE_DIR / "cache"
STATUS_FILE = CACHE_DIR / "launcher_status.json"
LOG_FILE    = BASE_DIR / "Debug" / "ps_watcher.log"
ICON_PNG    = BASE_DIR / "app_icon.png"
PYTHON_EXE  = sys.executable

LMSTUDIO_URL = "http://localhost:1234"
TARGET_MODEL = "qwen/qwen3-vl-4b"

PS_NAMES = {"photoshop.exe", "adobe photoshop.exe"}

# ---------------------------------------------------------------
# Logging
# ---------------------------------------------------------------
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")]
)
log = logging.getLogger("ps_watcher")


# ---------------------------------------------------------------
# Icon builder
# ---------------------------------------------------------------
def _make_icon(state: str = "idle") -> Image.Image:
    base_img = None
    if ICON_PNG.exists():
        try:
            base_img = Image.open(ICON_PNG).convert("RGBA")
        except Exception:
            base_img = None

    if base_img is None:
        size = 64
        base_img = Image.new("RGBA", (size, size), (25, 30, 40, 255))
        draw = ImageDraw.Draw(base_img)
        draw.ellipse([4, 4, 60, 60], fill=(25, 30, 40), outline=(245, 197, 24), width=3)

    img = base_img.resize((64, 64), Image.LANCZOS)
    draw = ImageDraw.Draw(img)

    # Chấm tròn báo trạng thái ở góc dưới phải
    palette = {
        "idle":    "#888888",
        "loading": "#f5c518",
        "running": "#2ecc71",
        "warning": "#e67e22",
        "error":   "#e74c3c",
    }
    dot_color = palette.get(state, "#888888")
    draw.ellipse([64 - 22, 64 - 22, 64 - 2, 64 - 2], fill=dot_color, outline="white", width=2)

    return img.resize((32, 32), Image.LANCZOS)


# ---------------------------------------------------------------
# LM Studio helpers
# ---------------------------------------------------------------
def _lm_is_up() -> bool:
    if _req is None:
        return False
    try:
        r = _req.get(f"{LMSTUDIO_URL}/v1/models", timeout=4)
        return r.status_code == 200
    except Exception:
        return False


def _lm_loaded_models() -> list:
    if _req is None:
        return []
    try:
        # Kiểm tra qua API v0 trước (chỉ lấy models có state == 'loaded')
        r = _req.get(f"{LMSTUDIO_URL}/api/v0/models", timeout=5)
        if r.status_code == 200:
            return [m.get("id", "") for m in r.json().get("data", []) if m.get("state") == "loaded"]
    except Exception:
        pass
    try:
        r = _req.get(f"{LMSTUDIO_URL}/v1/models", timeout=5)
        if r.status_code == 200:
            return [m.get("id", "") for m in r.json().get("data", [])]
    except Exception:
        pass
    return []


def _lm_load(model_id: str) -> bool:
    if _req is None:
        return False
    try:
        # Gọi v1/chat/completions dummy để kích hoạt LM Studio JIT load model vào VRAM
        r = _req.post(
            f"{LMSTUDIO_URL}/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            },
            timeout=45,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning(f"_lm_load error: {e}")
        return False


def ensure_model_loaded(model_id: str, status_cb=None) -> bool:
    def cb(msg):
        log.info(msg)
        if status_cb:
            status_cb(msg)
    cb(f"Kiểm tra LM Studio tại {LMSTUDIO_URL} ...")
    if not _lm_is_up():
        cb("LM Studio chưa chạy -- bỏ qua load model.")
        return False
    loaded = _lm_loaded_models()
    cb(f"Models đang load trong VRAM: {loaded or '(none)'}")
    for m in loaded:
        if model_id.lower() in m.lower() or m.lower() in model_id.lower():
            cb(f"Model '{m}' đã sẵn sàng trong VRAM.")
            return True
    cb(f"Đang kích hoạt load model '{model_id}' vào LM Studio ...")
    ok = _lm_load(model_id)
    cb("Model đã load thành công!" if ok else "Cần load model thủ công trong LM Studio.")
    return ok


# ---------------------------------------------------------------
# Photoshop helper
# ---------------------------------------------------------------
def is_photoshop_running() -> bool:
    if psutil:
        try:
            for p in psutil.process_iter(["name"]):
                n = (p.info["name"] or "").lower()
                if n in PS_NAMES:
                    return True
            return False
        except Exception:
            pass
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Photoshop.exe", "/NH"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True, errors="replace"
        )
        return "Photoshop.exe" in out
    except Exception:
        return False


# ---------------------------------------------------------------
# Detector process manager
# ---------------------------------------------------------------
def _write_status(running: bool):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({"launcher_active": True, "detector_running": running}, f)
    except Exception:
        pass


class DetectorManager:
    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def _kill_stale_detector(self):
        """Kill bất kỳ process headless_detector.py nào đang chạy ngầm"""
        if psutil is not None:
            for proc in psutil.process_iter():
                try:
                    cmdline = " ".join(proc.cmdline() or []).lower()
                    if "headless_detector.py" in cmdline:
                        if self._proc and proc.pid == self._proc.pid:
                            continue
                        log.info(f"[Detector] Kill instance headless_detector cũ PID {proc.pid}")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except Exception:
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
                    pass

        # Xóa lock file cũ nếu còn
        lock_file = BASE_DIR / ".detector.lock"
        if lock_file.exists():
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass

    def start(self) -> bool:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                log.info("Detector đã đang chạy.")
                return True
            if not DETECTOR_PY.exists():
                log.error(f"Không tìm thấy: {DETECTOR_PY}")
                return False

            # Kill instance cũ đang giữ lock (nếu có)
            self._kill_stale_detector()

            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUNBUFFERED"] = "1"
                self._proc = subprocess.Popen(
                    [PYTHON_EXE, str(DETECTOR_PY)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    env=env, cwd=str(BASE_DIR),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                log.info(f"[Detector] Khởi động -- PID {self._proc.pid}")
                threading.Thread(target=self._read_out, daemon=True).start()

                # Chờ 0.5s rồi kiểm tra process có còn sống không
                time.sleep(0.5)
                if self._proc.poll() is not None:
                    log.error("[Detector] Process thoát ngay sau khi khởi động!")
                    return False

                return True
            except Exception as e:
                log.error(f"[Detector] Lỗi: {e}")
                return False

    def stop(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=3)
                log.info("[Detector] Đã dừng.")
            self._proc = None
            _write_status(False)

    def _read_out(self):
        proc = self._proc
        if proc and proc.stdout:
            for line in proc.stdout:
                s = line.rstrip()
                if s:
                    log.info(f"[DET] {s}")
            proc.wait()
            _write_status(False)
            log.info("[Detector] Process kết thúc.")


# ---------------------------------------------------------------
# Main tray application
# ---------------------------------------------------------------
class PSWatcherApp:
    PS_INTERVAL = 5   # giây poll PS

    def __init__(self):
        self._det       = DetectorManager()
        self._icon      = None
        self._state     = "idle"
        self._stxt      = "Khởi động..."
        self._stop      = threading.Event()
        self._ps_ok     = False

    # --- state update ---
    def _set(self, state: str, msg: str = ""):
        self._state = state
        if msg:
            self._stxt = msg
            log.info(f"[{state.upper()}] {msg}")
        if self._icon:
            try:
                self._icon.icon  = _make_icon(state)
                self._icon.title = "Jewelry AI Detector | " + self._stxt[:60]
            except Exception:
                pass

    # --- startup ---
    def _startup(self):
        # 1. Bật Detector process NGAY LẬP TỨC
        self._set("loading", "Đang khởi động Detector ...")
        ok = self._det.start()

        if ok:
            _write_status(True)
            self._set("running", "Detector đang chạy -- kiểm tra model...")
        else:
            self._set("warning", "Detector chưa khởi động được")
            return

        # 2. Kiểm tra & load model ở nền
        ensure_model_loaded(TARGET_MODEL, status_cb=lambda m: self._set("running", m))
        self._set("running", "Detector đang chạy -- model sẵn sàng")

    # --- watch loop ---
    def _watch(self):
        for _ in range(60):
            if self._stop.is_set():
                return
            if self._state in ("running", "warning", "error"):
                break
            time.sleep(1)

        log.info(f"[Watcher] Bắt đầu theo dõi Photoshop (mỗi {self.PS_INTERVAL}s)")
        self._ps_ok = is_photoshop_running()

        _restart_fails = 0
        _MAX_RESTART = 3

        while not self._stop.is_set():
            self._stop.wait(self.PS_INTERVAL)
            if self._stop.is_set():
                break

            ps_now = is_photoshop_running()

            # Photoshop vừa tắt -> Tắt toàn bộ
            if self._ps_ok and not ps_now:
                log.info("[Watcher] Photoshop đã tắt -- dừng toàn bộ.")
                self._set("idle", "Photoshop đã tắt -- đang dừng ...")
                self._shutdown()
                return

            if ps_now and self._det.is_running():
                self._set("running", "Đang chạy -- Photoshop mở")
                _restart_fails = 0  # reset khi detector chạy ổn
            elif ps_now and not self._det.is_running():
                if _restart_fails >= _MAX_RESTART:
                    self._set("error", f"Detector lỗi liên tục ({_MAX_RESTART} lần) -- cần khởi lại thủ công")
                else:
                    _restart_fails += 1
                    log.warning(f"[Watcher] Detector dừng -- thử lại lần {_restart_fails}/{_MAX_RESTART}")
                    self._set("warning", f"Detector ngừng -- thử lại {_restart_fails}/{_MAX_RESTART} ...")
                    self._det.start()

            self._ps_ok = ps_now

    # --- shutdown ---
    def _shutdown(self):
        self._stop.set()
        self._det.stop()
        try:
            if STATUS_FILE.exists():
                STATUS_FILE.unlink()
        except Exception:
            pass
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        log.info("[PSWatcher] Đã thoát.")

    # --- menu callbacks ---
    def _on_open_log(self, icon, it):
        try:
            os.startfile(str(LOG_FILE))
        except Exception as e:
            log.error(f"Mở log thất bại: {e}")

    def _on_restart(self, icon, it):
        def _do():
            self._set("loading", "Đang khởi lại Detector ...")
            self._det.stop()
            time.sleep(1)
            ok = self._det.start()
            self._set("running" if ok else "error",
                      "Detector đã khởi lại" if ok else "Khởi lại thất bại")
        threading.Thread(target=_do, daemon=True).start()

    def _on_reload(self, icon, it):
        threading.Thread(target=self._startup, daemon=True).start()

    def _on_quit(self, icon, it):
        log.info("[Menu] Người dùng thoát.")
        self._shutdown()

    def _status_fn(self, _item=None):
        det = "Running" if self._det.is_running() else "Stopped"
        ps  = "Open" if self._ps_ok else "Closed"
        return f"Detector: {det}  |  PS: {ps}"

    # --- run ---
    def run(self):
        log.info("=" * 56)
        log.info(f"PS Watcher -- {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
        log.info(f"Python  : {PYTHON_EXE}")
        log.info(f"Base    : {BASE_DIR}")
        log.info(f"Model   : {TARGET_MODEL}")
        log.info(f"Icon    : {ICON_PNG}")
        log.info("=" * 56)

        menu = Menu(
            item(self._status_fn,          lambda *a: None, enabled=False),
            Menu.SEPARATOR,
            item("Khởi lại Detector",      self._on_restart),
            item("Reload Model LM Studio", self._on_reload),
            item("Mở File Log",            self._on_open_log),
            Menu.SEPARATOR,
            item("Thoát",                  self._on_quit),
        )

        self._icon = pystray.Icon(
            name="ps_watcher",
            icon=_make_icon("idle"),
            title="Jewelry AI Detector -- Đang chạy...",
            menu=menu,
        )

        threading.Thread(target=self._startup, daemon=True).start()
        threading.Thread(target=self._watch,   daemon=True).start()

        self._icon.run()


if __name__ == "__main__":
    # --- Single-instance lock cho ps_watcher ---
    _WATCHER_LOCK = BASE_DIR / ".watcher.lock"
    try:
        _watcher_lock_fh = open(_WATCHER_LOCK, "w")
        import msvcrt
        msvcrt.locking(_watcher_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
        _watcher_lock_fh.write(str(os.getpid()))
        _watcher_lock_fh.flush()
    except (OSError, IOError):
        # Đã có instance khác đang chạy -> thoát im lặng
        log.info("ps_watcher đã đang chạy (instance khác). Thoát.")
        sys.exit(0)

    app = PSWatcherApp()
    app.run()
