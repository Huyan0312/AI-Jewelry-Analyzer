# 📦 DANH SÁCH THƯ VIỆN & DEPENDENCIES

Tài liệu này tổng hợp toàn bộ các thư viện được sử dụng trong dự án **Jewelry Front Detector**, bao gồm mục đích sử dụng, phiên bản và hướng dẫn cài đặt.

---

## 1. THƯ VIỆN BÊN THỨ BA (EXTERNAL PACKAGES)

Các thư viện này được cài đặt thông qua `pip` và được khai báo trong `requirements.txt`:

```text
opencv-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
requests>=2.31.0
PySide6>=6.5.0
```

### 📋 Chi tiết từng thư viện:

| Tên Thư Viện | Module Trong Code | Mục Đích & Vai Trò Trong Dự Án |
| :--- | :--- | :--- |
| **`opencv-python`** | `import cv2` | **Core Vision Engine**: Dùng để xử lý ảnh số - Canny Edge Detection (dò khung bảng), Adaptive Thresholding (phân ngưỡng thích nghi), HSV Color Filtering (lọc màu đỏ/vàng/đá quý), Morphology Dilation/Erosion (giãn/co nét), Find Contours (tìm chu vi vật thể), vẽ Bounding Box màu và Encode ảnh output. |
| **`numpy`** | `import numpy as np` | **Toán Học & Ma Trận Điểm Ảnh**: Thực hiện phép toán vector/mask, tạo paper mask vector hóa và hỗ trợ connected-components filtering. |
| **`Pillow`** | `from PIL import Image` | **Đọc Ảnh An Toàn**: Đọc kích thước thật `(width, height)` của file ảnh nhanh chóng mà không làm xáo trộn dữ liệu màu hay chiếm dụng nhiều RAM. |
| **`requests`** | `import requests` | **HTTP REST API Client**: Gửi HTTP POST JSON payload (chứa ảnh Base64 & Prompts) sang server local LM Studio API endpoint (`http://localhost:1234/v1/chat/completions`) và kiểm tra danh sách model (`/v1/models`). |
| **`PySide6`** | `from PySide6...` | **Giao Diện Desktop (GUI)**: Cung cấp giao diện ứng dụng Qt6 đẹp mắt, đa luồng bất đồng bộ (`QThread`, `Signal`) để không treo giao diện khi gọi AI, tự động co giãn màn hình High-DPI 2K/4K và xem preview 7 views. |

---

## 2. THƯ VIỆN CHUẨN CỦA PYTHON (BUILT-IN MODULES)

Các module có sẵn trong Python chuẩn (không cần cài thêm):

| Module | Vai Trò Trong Dự Án |
| :--- | :--- |
| **`json`** | Chuyển đổi phản hồi AI, master result và `batch_summary.json`. |
| **`os` & `sys`** | Cấu hình mã hóa Console UTF-8 trên Windows, đọc biến môi trường Qt High-DPI Scaling (`QT_ENABLE_HIGHDPI_SCALING`). |
| **`pathlib.Path`** | Thao tác đường dẫn thư mục và file an toàn, tương thích tuyệt đối giữa Windows và Linux (`/` vs `\`). |
| **`time` & `datetime`** | Tính toán thời gian thực thi từng bước (Timing benchmark) và ghi mốc thời gian ISO UTC chuẩn. |
| **`base64`** | Mã hóa file ảnh binary thành chuỗi Base64 Data URL (`data:image/jpeg;base64,...`) để nhúng vào JSON payload gửi Vision AI. |
| **`re` (Regex)** | Lọc và trích xuất dữ liệu JSON từ phản hồi Markdown của AI (xử lý trường hợp AI trả về text có bao bằng ` ```json `). |
| **`shutil`** | Dọn nội dung `AutoTest_Results` khi người dùng chủ động truyền `--clean`. |
| **`argparse`** | Cung cấp CLI batch an toàn với cờ `--clean`. |
| **`typing`** | Khai báo kiểu dữ liệu (`List`, `Tuple`, `Optional`, `dict`) giúp mã nguồn rõ ràng, dễ bảo trì. |
| **`traceback`** | Bắt và định dạng chi tiết lỗi ngoại lệ (Stack Trace) khi xử lý đa luồng hoặc gọi API. |

---

## 🛠️ HƯỚNG DẪN CÀI ĐẶT MÔI TRƯỜNG

Mở Terminal tại thư mục dự án và chạy lệnh:

```bash
pip install -r requirements.txt
```
