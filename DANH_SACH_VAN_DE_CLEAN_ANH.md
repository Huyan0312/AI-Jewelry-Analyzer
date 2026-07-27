# 📌 BÁO CÁO PHÂN TÍCH VẤN ĐỀ CLEAN ẢNH XUẤT RA (DANH_SACH_VAN_DE_CLEAN_ANH.md)

Tài liệu này tổng hợp chi tiết **vấn đề thực tế của các ảnh output xuất ra** tại thư mục `E:\CODE\SciptAuto=AI\AI Super\AI PTS\Scale 3D\KS` theo yêu cầu kiểm tra.

---

## 🎯 1. MỤC TIÊU MONG MUỐN CỦA ĐẦU RA (OUTPUT GOAL)
Ảnh xuất ra của từng góc nhìn (View) **chỉ được phép có 2 thành phần**:
1. **Mô hình trang sức chính (Jewelry Object)**.
2. **Các đường kẻ mũi tên & số đo kích thước màu đỏ (Red dimension lines & numbers)**.
3. **KHÔNG** được chứa bất kỳ chữ nhãn view, viền kẻ bảng hay ký tự đen/xám nào khác.

---

## 🔍 2. KẾT QUẢ KIỂM TRA THỰC TẾ TRÊN CÁC ẢNH OUTPUT (CURRENT ISSUES)

Sau khi kiểm tra trực tiếp các ảnh trong thư mục `Scale 3D\KS`:

### ❌ Vấn đề 1: Chữ nhãn View bị dính vào góc trên bên trái của ảnh crop
* **Hiện trạng**: Trên các ảnh như:
  * `DF27.COMP017.12_DI_07072026_front_object.png`: Dính nguyên chữ màu xám **`FRONT`** ở góc trên bên trái.
  * `DF27.COMP017.12_DI_07072026_back_object.png`: Dính chữ **`ACK`** (phần bị cắt của từ `BACK`) ở góc trên bên trái.
  * `DF27.COMP017.12_DI_07072026_left_object.png`: Dính chữ **`EFT`** (phần bị cắt của từ `LEFT`) ở góc trên bên trái.
  * `DF27.COMP017.12_DI_07072026_bottom_object.png`: Dính nguyên chữ **`BOTTOM`** ở góc trên bên trái.
* **Nguyên nhân**: Khi thực hiện crop khung vật thể (`object_crop`), thuật toán lấy trực tiếp mảng pixel gốc của ảnh (`img_bgr[ro_y1:ro_y2, ro_x1:ro_x2]`). Vì vậy, chữ nhãn tên View nằm ở góc trên của khung kẻ bảng vẫn xuất hiện trên ảnh đầu ra.

### ❌ Vấn đề 2: Viền đen/xám của khung bảng kẻ (Table Grid Lines) bị dính sát mép ảnh
* **Hiện trạng**: Một số ảnh crop 2D vẫn bị lem nét kẻ khung ô bảng đen/xám chạy dọc sát 4 mép viền ngoài của ảnh.
* **Nguyên nhân**: Bounding box của AI hoặc OpenCV mở rộng lề đệm (padding) chạm vào các đường kẻ ngang/dọc của ô bảng xung quanh.

---

## 🛠️ 3. ĐỀ XUẤT GIẢI PHÁP KỸ THUẬT (PROPOSED SOLUTIONS)

Để đạt đúng mục tiêu **chỉ giữ lại Vật thể + Mũi tên đỏ**:

1. **Phân loại màu bằng HSV**:
   * **Bảo vệ màu đỏ**: Tạo mask lọc tất cả các điểm ảnh màu đỏ ($H \in [0, 15] \cup [160, 180]$, $S > 35$, $V > 35$) đại diện cho mũi tên và số đo kích thước.
   * **Bảo vệ màu vật thể**: Các điểm ảnh có màu sắc/độ bão hòa của trang sức (vàng, bạc, đá quý cyan...).

2. **Lọc và xóa chữ nhãn/nét xám đen**:
   * Xác định các đường nét đơn sắc xám/đen ($S < 55, V < 230$) nằm ở vùng trên-trái ($y < 35\%$ chiều cao crop).
   * Đè màu trắng `(255, 255, 255)` lên các vùng chữ nhãn này để làm sạch hoàn toàn nền ảnh.
   * Tự động xóa các đường kẻ ngang/dọc đen/xám sát 4 biên ảnh crop.
