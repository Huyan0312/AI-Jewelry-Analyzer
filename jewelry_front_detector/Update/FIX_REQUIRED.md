# CÁC HẠNG MỤC CẦN SỬA ĐỂ HOÀN TẤT PHASE 3

## 1. Phạm vi

Chỉ sửa Phase 3:

```text
OpenCV refine panel → clean panel → refine object
```

cho sáu view thường:

```text
FRONT, LEFT, RIGHT, TOP, BOTTOM, BACK
```

Chưa tối ưu hoặc thay đổi thuật toán riêng của `PERSPECTIVE` trong đợt này.

Các file cần đọc trước khi sửa:

- `jewelry_front_detector/FIX_PLAN_5_PHASES.md`
- `jewelry_front_detector/image_processor.py`
- `jewelry_front_detector/config.py`
- `jewelry_front_detector/tests/test_standard_refine.py`
- `jewelry_front_detector/tests/test_process_image.py`
- `jewelry_front_detector/Update/UPDATE_PHASE_1_2.md`

Kết quả audit hiện tại:

- 8/8 test Phase 3 hiện có đang pass.
- Tuy nhiên Phase 3 chưa đạt Definition of Done.
- Test `test_process_image.py` đang ghi ba file thật vào output production.
- Object refine chưa có acceptance gate để từ chối candidate bất thường.
- `MIN_CONTOUR_AREA` vẫn là cấu hình chết.
- Điều kiện center distance của panel vẫn dùng `MAX_CENTER_DISTANCE_RATIO * 2`, không khớp config/tài liệu.
- Refined bbox chưa được validate trước khi crop và lưu.
- Fixture test hiện tại chưa bao phủ các fallback và artifact quan trọng.

---

## 2. P0 — Cô lập test `process_image` khỏi output production

### File cần sửa

```text
jewelry_front_detector/tests/test_process_image.py
```

### Lỗi hiện tại

Test tạo ảnh input trong `TemporaryDirectory`, nhưng không patch:

```python
image_processor.OUTPUT_DIR
image_processor.DEBUG_DIR
```

Khi chạy test, code đã ghi file thật:

```text
jewelry_front_detector/output/sample_img_front_object.png
jewelry_front_detector/output/.preview/sample_img_front_panel.png
jewelry_front_detector/output/.preview/sample_img_front_result.jpg
```

### Yêu cầu sửa

Trong `setUp()` tạo:

```python
self.output_dir = self.temp_dir_path / "output"
self.debug_dir = self.output_dir / "debug"
```

Patch trong từng test hoặc dùng patcher ở `setUp()`:

```python
patch.object(ip, "OUTPUT_DIR", self.output_dir)
patch.object(ip, "DEBUG_DIR", self.debug_dir)
```

Yêu cầu:

- Không ghi file nào vào `jewelry_front_detector/output`.
- Không xóa hoặc ghi đè output thật của người dùng.
- Test phải xác nhận các file test được tạo bên trong temporary output.
- Temporary output phải được cleanup sau test.

Ba file `sample_img*` hiện có chỉ được xóa sau khi xác nhận đúng là artifact do test tạo. Không xóa bất kỳ output nào khác.

### Test nghiệm thu

- Chụp danh sách `sample_img*` trong production output trước và sau test; không được phát sinh file mới.
- File result/panel/object tồn tại trong temporary output.
- Chạy test hai lần liên tiếp không làm bẩn workspace.

---

## 3. P0 — Thêm acceptance gate cho object refine

### File cần sửa

```text
jewelry_front_detector/image_processor.py
jewelry_front_detector/config.py
```

### Hàm liên quan

```python
refine_object_bbox_opencv()
```

### Lỗi hiện tại

Object refine hiện:

1. Lấy mọi contour chỉ cần giao với vùng tìm kiếm mở rộng.
2. Hợp nhất toàn bộ contour đó.
3. Thêm padding.
4. Luôn đặt:

```python
meta["success"] = True
```

Không có bước từ chối candidate dựa trên:

- IoU với bbox AI.
- Khoảng cách tâm.
- Tỷ lệ diện tích candidate/AI.
- Candidate quá lớn hoặc quá nhỏ.
- Candidate bị kéo bởi label/noise ở xa.

Mặc dù metadata có `iou_with_ai` và `center_distance_ratio`, hai giá trị này chỉ được ghi lại, không được dùng để quyết định chấp nhận.

### Yêu cầu sửa

Thêm config có tên rõ ràng, ví dụ:

```python
OBJECT_MIN_IOU_THRESHOLD
OBJECT_MAX_CENTER_DISTANCE_RATIO
OBJECT_MIN_AREA_RATIO
OBJECT_MAX_AREA_RATIO
OBJECT_MIN_CONTOUR_AREA
```

Sau khi tính `refined_full`, kiểm tra:

1. Refined bbox hợp lệ trong kích thước ảnh.
2. IoU không thấp hơn ngưỡng.
3. Center distance ratio không vượt ngưỡng.
4. Diện tích candidate không quá nhỏ/lớn so với AI bbox.
5. Candidate không bị kéo ra ngoài panel hoặc ảnh.

Nếu vi phạm:

```python
meta["success"] = False
meta["final_bbox"] = ai_full
meta["fallback_reason"] = "..."
return None, debug_imgs
```

Fallback reason phải phân biệt được tối thiểu:

```text
no_intersecting_contour_with_ai_bbox
iou_below_threshold
center_distance_above_threshold
area_ratio_below_threshold
area_ratio_above_threshold
candidate_bbox_invalid
candidate_outside_panel
```

Không hard-code cùng một fallback reason cho mọi trường hợp.

### Lọc contour

Không nên nhận mọi contour chỉ vì có một pixel giao vùng search.

Mỗi contour candidate cần được lọc bằng một hoặc nhiều điều kiện:

- Diện tích contour tối thiểu.
- Tỷ lệ phần giao với search region.
- Khoảng cách tới tâm bbox AI.
- Component có liên hệ với vùng AI gốc, không chỉ vùng margin.

Không để chữ hoặc noise ở xa kéo bbox cuối phình ra.

### Test nghiệm thu

Thêm fixture:

1. Object hợp lệ trong bbox AI → refine success.
2. Object và label/noise ở xa → noise không kéo bbox cuối.
3. Candidate quá lớn → fallback `area_ratio_above_threshold`.
4. Candidate quá nhỏ → fallback `area_ratio_below_threshold` hoặc no-content.
5. Candidate lệch tâm → fallback center-distance.
6. Candidate IoU thấp → fallback IoU.
7. Candidate sát mép panel → bbox vẫn hợp lệ.
8. Bảng trắng → fallback AI.

---

## 4. P0 — Validate refined bbox trước khi crop và lưu

### File cần sửa

```text
jewelry_front_detector/image_processor.py
```

### Hàm liên quan

```python
process_image()
refine_panel_bbox_opencv()
refine_object_bbox_opencv()
```

### Lỗi hiện tại

`process_image()` chỉ validate:

```python
panel_px
obj_px
```

tức bbox AI sau chuyển pixel.

Code chưa validate:

```python
refined_panel_px
refined_obj_px
```

trước khi:

- Vẽ preview.
- Crop object.
- Lưu ảnh.
- Đặt `object_refine_success=True`.

### Yêu cầu sửa

Sau mỗi refine thành công:

```python
ok, message = bu.validate_pixel_bbox(
    candidate_bbox,
    width,
    height,
    "refined_object_bbox",
)
```

Nếu invalid:

- Không được dùng candidate.
- Fallback về bbox AI.
- Đặt success false.
- Ghi `fallback_reason="candidate_bbox_invalid: ..."` vào metadata.

Tương tự với refined panel.

Trước crop cuối phải xác nhận:

```text
x1 < x2
y1 < y2
width > 0
height > 0
bbox nằm trong ảnh
```

Nếu crop vẫn rỗng:

- Không báo success.
- Không khai báo output file như đã lưu.
- Trả lỗi/fallback có cấu trúc.

### Validation result

`result_json["validation"]` phải phản ánh bbox cuối, không chỉ bbox AI.

Nên có:

```json
{
  "valid": true,
  "warnings": [],
  "ai_bbox_valid": true,
  "refined_panel_bbox_valid": true,
  "refined_object_bbox_valid": true,
  "object_crop_valid": true
}
```

### Test nghiệm thu

- Mock panel refine trả bbox ngoài ảnh → fallback AI.
- Mock object refine trả bbox đảo chiều → fallback AI.
- Mock object refine trả bbox zero-area → fallback AI.
- Crop cuối rỗng không được ghi file.
- Validation báo đúng bbox nào thất bại.

---

## 5. P1 — Dùng hoặc loại bỏ `MIN_CONTOUR_AREA`

### File cần sửa

```text
jewelry_front_detector/config.py
jewelry_front_detector/image_processor.py
```

### Lỗi hiện tại

`MIN_CONTOUR_AREA` được import nhưng không được dùng trong object refine.

Object contour hiện chỉ bị bỏ qua khi:

```python
if w < 5 and h < 5:
    continue
```

Đây không phải kiểm tra diện tích contour và có thể nhận noise dài/mỏng hoặc contour rỗng bất thường.

### Yêu cầu sửa

Chọn một trong hai:

1. Dùng `MIN_CONTOUR_AREA` thực sự trong object refine:

```python
if cv2.contourArea(c) < MIN_CONTOUR_AREA:
    continue
```

2. Nếu panel và object cần threshold khác nhau, thay bằng:

```python
PANEL_CONTOUR_MIN_AREA
OBJECT_CONTOUR_MIN_AREA
```

và xóa `MIN_CONTOUR_AREA`.

Không để config được import nhưng không có tác dụng.

Threshold nên cân nhắc theo kích thước ROI hoặc có tỷ lệ tương đối, vì `500 px²` không tương đương giữa ảnh 500 px và ảnh 4K.

### Test nghiệm thu

- Noise nhỏ hơn threshold bị bỏ qua.
- Object thật lớn hơn threshold được giữ.
- Thay config trong test làm thay đổi hành vi tương ứng.

---

## 6. P1 — Đồng bộ center-distance threshold của panel

### File cần sửa

```text
jewelry_front_detector/image_processor.py
jewelry_front_detector/config.py
jewelry_front_detector/CODE_LOGIC.md
jewelry_front_detector/PROJECT_WORKFLOW.md
```

### Lỗi hiện tại

Config khai báo:

```python
MAX_CENTER_DISTANCE_RATIO = 0.25
```

nhưng panel pre-filter dùng:

```python
if dist_ratio > MAX_CENTER_DISTANCE_RATIO * 2:
```

tức ngưỡng thực tế là `0.50`.

### Yêu cầu sửa

Không nhân `* 2` âm thầm.

Chọn một trong hai:

1. Dùng đúng `MAX_CENTER_DISTANCE_RATIO`.
2. Tạo config riêng có tên rõ:

```python
PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO
PANEL_ACCEPT_MAX_CENTER_DISTANCE_RATIO
```

Nếu dùng pre-filter rộng hơn acceptance gate, phải có acceptance gate cuối với threshold chính thức.

Metadata phải ghi threshold và giá trị đo được để debug.

### Test nghiệm thu

- Candidate trong threshold → có thể được chấp nhận.
- Candidate nằm giữa 0.25 và 0.50 → hành vi đúng theo config mới, không phụ thuộc phép nhân ẩn.
- Candidate vượt threshold → fallback center-distance.

---

## 7. P1 — Làm rõ và hoàn thiện metadata refine/fallback

### File cần sửa

```text
jewelry_front_detector/image_processor.py
```

### Yêu cầu

Cả panel và object meta phải dùng cùng contract:

```json
{
  "attempted": true,
  "success": false,
  "method": "opencv",
  "ai_bbox": [],
  "candidate_bbox": null,
  "final_bbox": [],
  "iou_with_ai": 0.0,
  "center_distance_ratio": 0.0,
  "area_ratio": null,
  "thresholds": {},
  "fallback_reason": null
}
```

Quy tắc:

- `final_bbox` luôn là bbox thực sự được pipeline dùng.
- Khi fallback, `final_bbox` phải bằng bbox AI.
- `candidate_bbox` giữ candidate OpenCV bị từ chối để debug.
- `success=True` chỉ khi candidate vượt qua tất cả acceptance gate.
- `attempted=False` khi refine bị disable.
- `method="none"` khi không attempt.
- Không tạo metadata mặc định với fallback reason không đúng nguyên nhân.

Hiện `process_image()` tự dựng metadata mặc định chung như:

```text
no_matching_contour_found
no_intersecting_contour_with_ai_bbox
```

ngay cả khi nguyên nhân thật có thể là panel crop rỗng hoặc candidate invalid. Cần truyền nguyên nhân thật từ nhánh xử lý.

### Test nghiệm thu

- Disabled refine có `attempted=False`, `method="none"`.
- Không content có đúng reason.
- Low IoU có đúng reason và giữ candidate.
- Candidate invalid có đúng reason.
- `final_bbox` luôn khớp `pixel.refined_*_bbox`.

---

## 8. P1 — Rà lại `clean_panel_crop`

### File cần sửa

```text
jewelry_front_detector/image_processor.py
jewelry_front_detector/tests/test_standard_refine.py
```

### Các điểm cần hoàn thiện

1. Test crop quá nhỏ.
2. Test line ở cả bốn mép.
3. Test object sát mép để bảo đảm không bị cắt.
4. Test fallback khi `content_retained_ratio < 0.85`.
5. Test không có line → giữ nguyên crop, success false.
6. Test trim không vượt `MAX_PANEL_TRIM_RATIO`.

Nhánh:

```python
if new_w < w * 0.5 or new_h < h * 0.5
```

hiện gần như không thể xảy ra khi mỗi cạnh chỉ được trim tối đa 18%, vì kích thước nhỏ nhất còn khoảng 64%. Cần:

- Xóa nhánh chết, hoặc
- Điều chỉnh điều kiện theo giới hạn thực tế có ý nghĩa.

Không cần thay đổi thuật toán nếu test chứng minh hành vi hiện tại đúng, nhưng tài liệu và code phải thống nhất.

---

## 9. P1 — Bổ sung fixture cho sáu view thường

### File cần sửa

```text
jewelry_front_detector/tests/test_standard_refine.py
jewelry_front_detector/tests/test_process_image.py
```

### Fixture bắt buộc

- Panel đủ bốn đường biên.
- Panel chỉ có hai đường biên.
- Panel không có đường bảng.
- Panel sát mép ảnh.
- Panel crop nhỏ hơn 50 px.
- Object có label ở vùng trên.
- Object có đường kích thước đỏ/xanh.
- Object sát mép panel.
- Object kèm noise ở xa.
- Crop trắng/rỗng.

### Assertions cần có

- Bbox cuối hợp lệ.
- Crop cuối không rỗng.
- Fallback trả đúng bbox AI.
- Fallback reason đúng nguyên nhân.
- Content retained không dưới ngưỡng.
- Refine disabled không gọi các hàm OpenCV refine.
- Sáu tên view thường đều đi qua nhánh standard, không đi qua `refine_perspective_object_opencv()`.

Test không cần tạo sáu ảnh giống nhau; có thể parameterize/subTest theo tên view.

---

## 10. P1 — Làm test `process_image` thực sự kiểm tra refine

### Lỗi hiện tại

Fixture `test_process_image_success` chỉ là ảnh xám trơn. OpenCV panel/object refine đều fallback, nhưng test vẫn có tên `success` và chỉ kiểm tra result có key.

### Yêu cầu sửa

Tách thành:

1. `test_process_image_fallback_on_blank_image`
2. `test_process_image_standard_refine_success`
3. `test_process_image_disabled_refine`
4. `test_process_image_invalid_refined_candidate_falls_back`

Fixture refine success phải vẽ panel/object thật bằng OpenCV và xác nhận:

```python
res["opencv"]["panel_refine_success"] is True
res["opencv"]["object_refine_success"] is True
res["opencv"]["panel_meta"]["success"] is True
res["opencv"]["object_meta"]["success"] is True
```

Không chỉ kiểm tra key tồn tại.

---

## 11. Chạy kiểm thử

Chạy riêng Phase 3:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONIOENCODING = "utf-8"
python -m unittest tests.test_standard_refine tests.test_process_image -v
```

Sau đó chạy regression toàn bộ:

```powershell
python -m unittest discover -s tests -v
```

Điều kiện đạt:

- Tất cả test pass.
- Không gọi LM Studio thật.
- Không ghi output test vào production.
- Không có logging traceback.
- `MIN_CONTOUR_AREA` không còn là config chết.
- Panel và object đều có acceptance gate rõ ràng.
- Refined bbox được validate trước crop.
- Mọi fallback có reason đúng nguyên nhân.
- `final_bbox` trong metadata khớp bbox pipeline thực sự sử dụng.

---

## 12. Cập nhật báo cáo Phase 3

Sau khi sửa và test đạt, tạo:

```text
jewelry_front_detector/Update/UPDATE_PHASE_3.md
```

Báo cáo phải ghi:

- File/hàm đã sửa.
- Threshold/config được thêm hoặc xóa.
- Contract metadata cuối.
- Danh sách fixture test.
- Số test thực tế.
- Kết quả test Phase 3 và regression toàn bộ.
- Xác nhận không HTTP thật.
- Xác nhận không output production.
- Không ghi “100%” nếu acceptance gate hoặc test isolation chưa đạt.

---

## 13. Definition of Done Phase 3

Phase 3 chỉ hoàn tất khi:

- Sáu view thường dùng đúng nhánh standard.
- Panel refine có acceptance gate theo IoU và center distance.
- Object refine có acceptance gate theo IoU, center distance và area ratio.
- Contour noise nhỏ/xa không kéo bbox cuối.
- Clean panel không cắt mất quá 15% nội dung.
- Candidate invalid fallback về bbox AI.
- Refined bbox được validate trước crop.
- Crop cuối hợp lệ và không rỗng.
- Refine disabled không attempt OpenCV.
- Mọi fallback có reason chính xác.
- Metadata phản ánh đúng bbox cuối.
- Config OpenCV đều có caller thực tế.
- Unit test dùng temporary output.
- Tất cả test Phase 3 và regression pass.
- Không phát sinh file test trong production output.

---

## 14. Kết quả kiểm tra lại sau `UPDATE_PHASE_3.md`

Trạng thái kiểm tra thực tế:

- Regression hiện tại: `49/49 PASS`.
- Không phát sinh file mới trong production `output/` khi chạy test.
- Tuy nhiên Phase 3 **chưa đạt 100% Definition of Done**.
- Không được giữ tuyên bố hoàn thành 100% trong `UPDATE_PHASE_3.md` cho tới khi toàn bộ các mục dưới đây được sửa và có test chứng minh.

### P0 — Sửa panel center-distance gate và config chết

File:

```text
jewelry_front_detector/config.py
jewelry_front_detector/image_processor.py
jewelry_front_detector/tests/test_standard_refine.py
```

Lỗi hiện tại:

```python
PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO = 0.50
```

đã được khai báo và import, nhưng `refine_panel_bbox_opencv()` vẫn dùng:

```python
if dist_ratio > MAX_CENTER_DISTANCE_RATIO * 2:
```

Ngoài ra panel chỉ kiểm tra center distance ở pre-filter; acceptance gate cuối mới chỉ kiểm tra IoU.

Yêu cầu sửa:

1. Thay phép nhân ẩn bằng config có tên rõ:

   ```python
   if dist_ratio > PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO:
   ```

2. Bổ sung threshold riêng cho acceptance gate cuối, ví dụ:

   ```python
   PANEL_ACCEPT_MAX_CENTER_DISTANCE_RATIO
   ```

3. Sau khi chọn `refined_abs`, phải kiểm tra cả:

   - `final_iou >= MIN_IOU_THRESHOLD`
   - `final_center_distance_ratio <= PANEL_ACCEPT_MAX_CENTER_DISTANCE_RATIO`

4. Nếu center distance không đạt:

   ```python
   meta["success"] = False
   meta["final_bbox"] = ai_panel_bbox_px
   meta["fallback_reason"] = "center_distance_above_threshold (...)"
   return None, debug_imgs
   ```

Test bắt buộc:

- Candidate trong acceptance threshold được chấp nhận.
- Candidate nằm giữa acceptance threshold và pre-filter threshold bị fallback.
- Candidate vượt pre-filter threshold bị loại.
- Patch từng config threshold trong test phải làm thay đổi hành vi tương ứng.

### P0 — Đồng bộ metadata với bbox pipeline thực sự sử dụng

File:

```text
jewelry_front_detector/image_processor.py
jewelry_front_detector/tests/test_process_image.py
```

Lỗi hiện tại:

- Metadata chưa có `thresholds`.
- Panel metadata chưa có `area_ratio`.
- Khi `process_image()` từ chối refined candidate invalid, code đổi bbox pipeline về AI nhưng chưa bảo đảm cập nhật đầy đủ:
  - `success`
  - `candidate_bbox`
  - `final_bbox`
  - `fallback_reason`
- Metadata mặc định trong `process_image()` vẫn tự gán lý do chung, có thể không phản ánh nguyên nhân thực tế.

Yêu cầu sửa:

1. Panel và object phải dùng cùng contract tối thiểu:

   ```json
   {
     "attempted": true,
     "success": false,
     "method": "opencv",
     "ai_bbox": [],
     "candidate_bbox": null,
     "final_bbox": [],
     "iou_with_ai": 0.0,
     "center_distance_ratio": 0.0,
     "area_ratio": null,
     "thresholds": {},
     "fallback_reason": null
   }
   ```

2. Mỗi hàm refine phải tự trả metadata đúng nguyên nhân. Hạn chế tạo fallback reason giả trong `process_image()`.

3. Khi post-validation từ chối candidate:

   ```python
   meta["success"] = False
   meta["candidate_bbox"] = candidate
   meta["final_bbox"] = ai_bbox
   meta["fallback_reason"] = f"candidate_bbox_invalid: {message}"
   ```

4. Trước khi trả kết quả phải bảo đảm:

   ```text
   panel_meta.final_bbox == pixel.refined_panel_bbox
   object_meta.final_bbox == pixel.refined_object_bbox
   ```

5. Bbox trong metadata nên được chuẩn hóa cùng kiểu số với bbox trong `pixel`, tránh một bên float và một bên int gây sai contract.

Test bắt buộc:

- Mock panel candidate ngoài ảnh.
- Mock object candidate ngoài ảnh.
- Candidate đảo chiều.
- Candidate zero-area.
- Mỗi trường hợp phải assert `success`, `candidate_bbox`, `final_bbox`, `fallback_reason`.
- Assert `final_bbox` metadata khớp bbox trong `pixel`.

### P0 — Hoàn thiện contour filtering và test chống noise

File:

```text
jewelry_front_detector/image_processor.py
jewelry_front_detector/tests/test_standard_refine.py
```

Lỗi hiện tại:

Object refine đã lọc `OBJECT_MIN_CONTOUR_AREA`, nhưng vẫn hợp nhất mọi contour chỉ cần giao vùng search mở rộng. Acceptance gate có thể fallback toàn bộ candidate thay vì loại riêng contour noise.

Yêu cầu sửa:

- Ngoài diện tích tối thiểu, contour phải có quan hệ đủ mạnh với bbox AI gốc, ví dụ một hoặc nhiều điều kiện:
  - Giao trực tiếp bbox AI gốc.
  - Tỷ lệ diện tích giao tối thiểu.
  - Khoảng cách tâm contour tới bbox AI.
  - Connected component liên hệ với content nằm trong bbox AI.
- Label hoặc noise ở xa chỉ giao phần margin không được kéo phình bbox cuối.
- Không chỉ dựa vào gate cuối để fallback toàn bộ object hợp lệ.

Test bắt buộc:

- Object hợp lệ cộng noise nhỏ ở xa.
- Object hợp lệ cộng label lớn ở vùng margin.
- Object cộng đường kích thước đỏ/xanh.
- Xác nhận refine vẫn success và bbox cuối không bao gồm noise/label.
- Thay `OBJECT_MIN_CONTOUR_AREA` trong test phải chứng minh config có tác dụng.

### P1 — Hoàn thiện test acceptance gate của object

Các test hiện có mới chứng minh:

- Success cơ bản.
- Không có content.
- Area ratio quá lớn.
- Area ratio quá nhỏ.

Cần bổ sung:

- `iou_below_threshold`.
- `center_distance_above_threshold`.
- `candidate_outside_panel`.
- Candidate sát mép panel nhưng vẫn hợp lệ.
- Bbox candidate invalid.
- Noise không làm thay đổi bbox.

Mỗi test phải kiểm tra:

```text
refined result
attempted
success
candidate_bbox
final_bbox
fallback_reason
iou_with_ai
center_distance_ratio
area_ratio
thresholds
```

### P1 — Hoàn thiện test `clean_panel_crop`

Các test còn thiếu:

- Crop nhỏ hơn `50 px`.
- Đường bảng ở cả bốn mép.
- Chỉ có hai đường biên.
- Object sát từng mép.
- Trim không vượt `MAX_PANEL_TRIM_RATIO`.
- Fallback khi `content_retained_ratio < CONTENT_RETAINED_MIN_RATIO`.
- Ảnh trắng/rỗng.

Nhánh hiện tại:

```python
if new_w < w * 0.5 or new_h < h * 0.5:
```

gần như không thể chạy tới khi mỗi cạnh chỉ được trim tối đa 18%. Phải:

- Xóa nhánh chết; hoặc
- Thay bằng điều kiện có thể xảy ra và có test tương ứng.

### P1 — Chứng minh sáu view thường dùng đúng nhánh standard

File:

```text
jewelry_front_detector/tests/test_process_image.py
```

Hiện integration test chỉ chạy `FRONT`.

Phải thêm `subTest` hoặc parameterized test cho:

```text
FRONT
LEFT
RIGHT
TOP
BOTTOM
BACK
```

Với từng view, assert:

- `refine_panel_bbox_opencv()` được gọi.
- `clean_panel_crop()` được gọi.
- `refine_object_bbox_opencv()` được gọi.
- `refine_perspective_object_opencv()` không được gọi.

Thêm test riêng `PERSPECTIVE` để assert điều ngược lại:

- Không gọi panel standard refine.
- Không gọi clean panel standard.
- Không gọi object standard refine.
- Có gọi `refine_perspective_object_opencv()`.

### P1 — Hoàn thiện validation và output contract

File:

```text
jewelry_front_detector/image_processor.py
jewelry_front_detector/tests/test_process_image.py
```

Yêu cầu:

1. `validation.valid` phải kết hợp rõ:

   ```text
   ai_bbox_valid
   refined_panel_bbox_valid
   refined_object_bbox_valid
   object_crop_valid
   ```

2. Khi candidate refined invalid nhưng fallback AI thành công:

   - Kết quả cuối có thể `valid=True`.
   - `warnings` vẫn phải ghi candidate refine đã bị từ chối.
   - Metadata phải giữ đúng candidate và reason.

3. Không khai báo output như đã tồn tại nếu không lưu được:

   - `panel_image` phải là `null` hoặc không có key nếu panel crop không được lưu.
   - `object_image` phải là `null` hoặc không có key nếu object crop rỗng.
   - Chỉ khai báo JSON sau khi JSON được ghi thành công.

4. Kiểm tra giá trị trả về của `save_cv2_image()` nếu hàm có trạng thái thành công/thất bại; không log “đã lưu” khi thao tác lưu thất bại.

Test bắt buộc:

- Crop object rỗng không được khai báo file object đã lưu.
- Panel crop rỗng không được khai báo file panel đã lưu.
- Save thất bại không được báo output thành công.
- Fallback candidate invalid có warning nhưng bbox cuối hợp lệ.

### P1 — Đồng bộ tài liệu và báo cáo

File:

```text
jewelry_front_detector/CODE_LOGIC.md
jewelry_front_detector/PROJECT_WORKFLOW.md
jewelry_front_detector/Update/UPDATE_PHASE_3.md
```

Sau khi code và test đạt:

- Ghi đúng hai mức threshold panel: pre-filter và final acceptance.
- Ghi đầy đủ object acceptance gate và contour filter.
- Ghi metadata contract cuối.
- Liệt kê chính xác fixture/test đã thêm.
- Cập nhật số test từ kết quả chạy mới.
- Không tuyên bố “noise ở xa không kéo bbox” nếu chưa có fixture test tương ứng.
- Không tuyên bố `final_bbox` khớp 100% nếu chưa có assertion cho cả success và fallback.

### Lệnh nghiệm thu bắt buộc

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONIOENCODING = "utf-8"
python -m unittest tests.test_standard_refine tests.test_process_image -v
python -m unittest discover -s tests -v
```

Ngoài việc test pass, phải kiểm tra snapshot production output trước/sau:

```text
Số file mới trong jewelry_front_detector/output = 0
```

Chỉ đánh dấu Phase 3 hoàn thành khi toàn bộ mục P0/P1 trên có code caller thực tế và test nghiệm thu tương ứng.
