# 💎 Jewelry FRONT Detector

Ứng dụng phân tích bản vẽ kỹ thuật trang sức sử dụng **LM Studio Vision AI** kết hợp **OpenCV**.

Tự động xác định vị trí panel FRONT và vật thể trang sức trong bản vẽ, vẽ bounding box và lưu kết quả.

---

## 📋 Yêu cầu hệ thống

- **Windows 10/11** (64-bit)
- **Python 3.11+**
- **LM Studio** đã cài đặt và có model Vision
- RAM tối thiểu 8 GB (khuyến nghị 16 GB+ nếu chạy model lớn)

---

## 🚀 Cài đặt

### 1. Cài Python

Tải Python 3.11 hoặc mới hơn từ https://python.org

> ⚠️ Tích chọn **"Add Python to PATH"** khi cài đặt.

Kiểm tra:
```powershell
python --version
```

---

### 2. Tạo môi trường ảo

Mở PowerShell, điều hướng vào thư mục dự án:

```powershell
cd jewelry_front_detector
python -m venv .venv
.venv\Scripts\activate
```

> Sau khi kích hoạt, prompt sẽ hiện `(.venv)` ở đầu dòng.

---

### 3. Cài thư viện

```powershell
pip install -r requirements.txt
```

Các thư viện được cài:
| Thư viện | Mục đích |
|---|---|
| `opencv-python` | Xử lý ảnh, tinh chỉnh bounding box |
| `Pillow` | Đọc kích thước ảnh gốc |
| `requests` | Gọi LM Studio API |
| `PySide6` | Giao diện đồ họa |
| `numpy` | Xử lý ma trận ảnh |

---

### 4. Cài đặt LM Studio

1. Tải LM Studio từ https://lmstudio.ai
2. Cài đặt và mở ứng dụng.
3. Vào tab **Discover** → Tìm model vision (ví dụ: `LLaVA`, `BakLLaVA`, `MiniCPM-V`, `llava-v1.5-7b`).
4. Tải model về máy.

---

### 5. Load model Vision trong LM Studio

1. Vào tab **Chat** → Click **Load Model** → Chọn model vision vừa tải.
2. Chờ model load xong (thanh progress bar đầy).

---

### 6. Bật Local Server

1. Vào tab **Local Server** (biểu tượng `</>` bên trái).
2. Click nút **Start Server**.
3. Server sẽ chạy tại: `http://localhost:1234`

---

### 7. Kiểm tra endpoint

Mở trình duyệt, truy cập:
```
http://localhost:1234/v1/models
```

Nếu thấy JSON danh sách models → Server đang hoạt động.

---

### 8. Chạy ứng dụng

```powershell
python main.py
```

---

## 🖥️ Hướng dẫn sử dụng giao diện

### Bước 1 – Cấu hình

| Trường | Mô tả |
|---|---|
| **Base URL** | Giữ nguyên `http://localhost:1234/v1` hoặc thay đổi nếu dùng port khác |
| **Model** | Nhập chính xác tên model đang load trong LM Studio (xem ở tab Local Server) |

Click **"🔌 Kiểm tra kết nối"** để xác nhận server hoạt động.

### Bước 2 – Chọn ảnh

Click **"📁 Chọn ảnh"** → Chọn file ảnh bản vẽ kỹ thuật trang sức.

Hỗ trợ: `.jpg`, `.jpeg`, `.png`, `.webp`

### Bước 3 – Phân tích

Click **"🚀 Phân tích FRONT"** cho một view hoặc phân tích all-views. GUI chỉ
báo thành công khi crop thực sự được lưu và validation hợp lệ.

### Bước 4 – Đọc kết quả

Sau khi hoàn thành:
- **Ảnh kết quả**: Xem bounding box được vẽ lên ảnh.
- **JSON**: Xem tọa độ chi tiết.
- **Thư mục output**: Click "📂 Mở thư mục Output".

---

## 📦 Kết quả đầu ra

```
output/
├── <tên_ảnh>_<view>_object.png
├── .preview/
│   ├── <tên_ảnh>_<view>_result.jpg
│   ├── <tên_ảnh>_<view>_panel.png
│   └── <tên_ảnh>_<view>_result.json
└── AutoTest_Results/
    └── batch_summary.json
```

### Ý nghĩa màu bounding box

| Màu | Ý nghĩa |
|---|---|
| 🟩 Xanh lá | Panel FRONT (đã tinh chỉnh OpenCV) |
| 🟠 Cam | Vật thể theo AI |
| 🔵 Xanh dương | Vật thể đã tinh chỉnh OpenCV |
| 🔴 Đỏ | Tâm vật thể |

### Cấu trúc file JSON

```json
{
  "source_image": "đường dẫn ảnh gốc",
  "image_size": { "width": 1820, "height": 1212 },
  "model": "tên model",
  "coordinate_input_type": "normalized_0_1000_full_image",
  "normalized": {
    "panel_bbox": [x1, y1, x2, y2],
    "object_bbox": [x1, y1, x2, y2],
    "object_center": [cx, cy]
  },
  "pixel": {
    "ai_panel_bbox": [x1, y1, x2, y2],
    "refined_panel_bbox": [x1, y1, x2, y2],
    "ai_object_bbox": [x1, y1, x2, y2],
    "refined_object_bbox": [x1, y1, x2, y2],
    "object_center": [cx, cy]
  },
  "validation": {
    "valid": true,
    "warnings": []
  },
  "output_files": {
    "result_image": "...",
    "panel_image": "...",
    "object_image": "...",
    "json": "..."
  }
}
```

---

## ⚙️ Cấu hình nâng cao (config.py)

```python
ENABLE_OPENCV_REFINE = True      # Bật/tắt tinh chỉnh OpenCV
DEBUG_MODE = False               # True để lưu ảnh debug trung gian
REQUEST_TIMEOUT = 120            # Giây chờ model phản hồi
RETRY_COUNT = 2                  # Số lần retry khi lỗi
TEMPERATURE = 0.0                # Độ ngẫu nhiên của model
MAX_TOKENS = 1500                # Token tối đa
PERSPECTIVE_OUTPUT_MODE = "bbox_only"  # hoặc "masked_object"
```

Các path có thể override bằng biến môi trường:

```text
JEWELRY_INPUT_DIR
JEWELRY_OUTPUT_DIR
JEWELRY_LOGS_DIR
JEWELRY_AUTO_TEST_DIR
JEWELRY_AUTO_TEST_RESULTS_DIR
JEWELRY_PROJECT_DIR
```

## Batch AutoTest

```powershell
python run_auto_test.py
python run_auto_test.py --clean
```

Mặc định không xóa kết quả cũ. `--clean` chỉ dọn thư mục kết quả đã được
resolve và kiểm tra scope. Summary phân biệt `SUCCESS`, `PARTIAL`, `FAILED` và
giữ sheet metadata cùng số view expected/received/saved.

`dimension_crop.py` là tiện ích standalone, chưa thuộc call path GUI/batch chính.

---

## 🐛 Các lỗi thường gặp

### ❌ "Không thể kết nối đến LM Studio"
**Nguyên nhân**: LM Studio chưa bật Local Server.  
**Giải pháp**: Mở LM Studio → Tab Local Server → Click **Start Server**.

### ❌ "Model chưa được load"
**Nguyên nhân**: Server đang chạy nhưng chưa load model vào bộ nhớ.  
**Giải pháp**: Trong LM Studio → Tab Chat → Load model.

### ❌ "Model không hỗ trợ vision"
**Nguyên nhân**: Model hiện tại không xử lý được ảnh (không phải vision model).  
**Giải pháp**: Load model có khả năng vision như LLaVA, BakLLaVA, MiniCPM-V.

### ❌ "Không parse được JSON từ response"
**Nguyên nhân**: Model trả lời bằng văn bản thay vì JSON thuần.  
**Giải pháp**: Chương trình sẽ tự cố gắng bóc JSON. Nếu vẫn thất bại, thử model khác hoặc giảm `TEMPERATURE` về `0.05`.

### ❌ Ứng dụng bị treo
**Nguyên nhân**: Model xử lý lâu.  
**Giải pháp**: Tăng `REQUEST_TIMEOUT` trong `config.py`. Đây là hoạt động bình thường với model lớn.

### ❌ Bounding box sai vị trí
**Nguyên nhân**: Model trả tọa độ hệ 0-100 thay vì 0-1000.  
**Giải pháp**: Chương trình tự phát hiện và log cảnh báo. Kiểm tra file log trong thư mục `logs/`.

---

## 📁 Cấu trúc dự án

```
jewelry_front_detector/
├── main.py              # Điểm khởi chạy
├── gui.py               # Giao diện PySide6
├── lmstudio_client.py   # Giao tiếp LM Studio API
├── image_processor.py   # Xử lý ảnh + OpenCV
├── bbox_utils.py        # Tiện ích bounding box
├── config.py            # Cấu hình
├── prompts.py           # System/User prompt
├── logger_utils.py      # Logging
├── requirements.txt     # Thư viện
├── README.md
├── input/               # Thư mục ảnh đầu vào (tùy chọn)
├── output/              # Ảnh và JSON kết quả
└── logs/                # File log theo ngày
```

---

## 📝 Log

Log được lưu tự động tại `logs/YYYY-MM-DD.log`.

Bật `DEBUG_MODE = True` trong `config.py` để lưu thêm ảnh trung gian tại `output/debug/<tên_ảnh>/`.

---

## 📄 License

MIT License – Sử dụng tự do cho mục đích cá nhân và thương mại.
