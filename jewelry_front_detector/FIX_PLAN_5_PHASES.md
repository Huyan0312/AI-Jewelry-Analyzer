# KẾ HOẠCH SỬA PIPELINE THEO 5 PHẦN CÓ THỂ KIỂM THỬ ĐỘC LẬP

## 1. Mục tiêu và nguyên tắc thực hiện

Tài liệu này chia toàn bộ phần cần sửa của pipeline:

```text
GUI/CLI → LM Studio API → parse JSON → chuẩn hóa bbox
→ OpenCV refine panel/object/PERSPECTIVE → crop 7 views → lưu output
```

thành 5 phần theo đúng thứ tự phụ thuộc. Sau khi hoàn thành mỗi phần phải chạy được bộ test tương ứng và đạt tiêu chí nghiệm thu trước khi chuyển sang phần tiếp theo.

Nguyên tắc chung:

- Không dùng output cũ làm bằng chứng duy nhất; mỗi phần phải có test tự động hoặc kiểm tra đầu ra mới.
- Không gọi LM Studio trong unit test. HTTP phải được mock để test ổn định.
- Test tích hợp LM Studio là nhóm riêng, chỉ chạy khi server và vision model đã sẵn sàng.
- Mọi fallback phải được thể hiện trong kết quả bằng `success`, `method` hoặc `fallback_reason`; không được fallback âm thầm.
- Không báo thành công nếu thiếu view, crop rỗng hoặc file output không tồn tại.
- Không dùng các tuyên bố như “chính xác 100%” nếu chưa có bộ dữ liệu gán nhãn và số đo định lượng.

Thư mục test đề xuất:

```text
tests/
├── fixtures/
│   ├── api_responses/
│   └── images/
├── test_lmstudio_payload.py
├── test_response_schema.py
├── test_bbox_utils.py
├── test_standard_refine.py
├── test_perspective_refine.py
├── test_process_image.py
└── test_gui_workers.py
```

Có thể dùng `unittest` và `unittest.mock` của Python để không phát sinh dependency mới. Nếu chọn `pytest`, phải thêm nó vào dependency dành cho development.

---

## PHẦN 1 — ỔN ĐỊNH LM STUDIO API, RESIZE ẢNH VÀ PARSE JSON

### Mục tiêu

Đảm bảo request gửi tới LM Studio có kích thước ảnh đúng cấu hình, parse response có retry hợp lý và trả về một cấu trúc rõ ràng gồm metadata, danh sách view và thông tin lỗi.

### File và hàm cần sửa

- `lmstudio_client.py`
  - `encode_image_to_base64_url()`
  - `prepare_image_data_url_for_lm()`
  - `extract_json_safe()`
  - `normalize_all_views_payload()`
  - `send_image_to_model()`
  - `send_image_to_model_all_views()`
- `config.py`
  - `MAX_AI_SIZE`
  - `AI_JPEG_QUALITY`
  - `RETRY_COUNT`
  - `RETRY_DELAY`
  - `REQUEST_TIMEOUT`
- `prompts.py`
  - Đồng bộ schema JSON mà code thực sự chấp nhận.

### Công việc cần làm

1. Dùng `prepare_image_data_url_for_lm()` trong cả single-view và all-views.
2. Bảo đảm cạnh dài ảnh gửi đi không vượt `MAX_AI_SIZE`, giữ đúng tỷ lệ.
3. Trả metadata encode trong kết quả hoặc log:
   - Kích thước ảnh gốc.
   - Kích thước ảnh gửi.
   - Có resize hay không.
   - Số byte JPEG/base64.
4. Tách rõ các loại lỗi:
   - Encode/file.
   - Connection/timeout.
   - HTTP status.
   - Response body không đúng chuẩn OpenAI-compatible.
   - JSON parse lỗi.
   - JSON đúng cú pháp nhưng sai schema.
5. Cho phép retry khi HTTP 200 nhưng JSON parse/schema lỗi, không chỉ retry lỗi mạng.
6. Không dùng `send_image_to_model_all_views.last_sheet` làm kênh truyền metadata.
7. Trả về một cấu trúc rõ ràng, ví dụ:

```json
{
  "sheet": {
    "drawing_number": null,
    "metal": null,
    "brand": "NONE",
    "metal_weight": null
  },
  "views": [],
  "raw_response": "",
  "request_meta": {},
  "error": null
}
```

8. Không loại bỏ hậu tố drawing number nếu nghiệp vụ cần phân biệt `889486 A`, `889486 B+F`, `889524-A`. Nếu vẫn chuẩn hóa về cụm số, phải lưu cả `drawing_number_raw`.

### Test sau khi code xong

#### Unit test

- Ảnh nhỏ hơn 2048 px không bị resize.
- Ảnh lớn hơn 2048 px được resize đúng tỷ lệ và không ghi file tạm.
- PNG/RGBA được chuyển sang JPEG RGB hợp lệ.
- Parse được:
  - JSON object thuần.
  - JSON array thuần.
  - Markdown `json` code fence.
  - Code fence không ghi ngôn ngữ.
  - JSON có text bao quanh.
- Response rỗng hoặc JSON hỏng trả lỗi parse, không ném exception ra ngoài.
- Mock HTTP 200 + JSON hỏng hai lần, lần ba hợp lệ: xác nhận retry đúng số lần.
- Mock 400, 404, 503, timeout và connection error: xác nhận error type/message.
- Xác nhận metadata không còn phụ thuộc vào function attribute `last_sheet`.

#### Test tích hợp tùy chọn

```powershell
python -m unittest tests.test_lmstudio_payload tests.test_response_schema -v
```

Khi LM Studio đang chạy, gửi một fixture và xác nhận:

- Endpoint đúng `/v1/chat/completions`.
- Response được parse.
- Có `sheet`, `views`, `request_meta`.

### Tiêu chí nghiệm thu phần 1

- Tất cả unit test phần 1 pass.
- `MAX_AI_SIZE` và `AI_JPEG_QUALITY` thực sự có caller trong pipeline.
- JSON lỗi được retry theo cấu hình.
- Metadata được trả bằng dữ liệu return chính thức.
- Không còn đường truyền dữ liệu qua `last_sheet`.

---

## PHẦN 2 — VALIDATE SCHEMA 7 VIEWS VÀ CHUẨN HÓA BBOX AN TOÀN

### Mục tiêu

Ngăn input AI thiếu/sai bbox đi vào OpenCV; xác nhận đúng bảy view duy nhất và chuyển tọa độ sang pixel mà không nhân hệ số sai âm thầm.

### File và hàm cần sửa

- `bbox_utils.py`
  - `validate_pixel_bbox()`
  - `detect_coordinate_scale()`
  - `rescale_response_coords()`
  - `normalized_bbox_to_pixel()`
  - `normalized_point_to_pixel()`
  - Thêm validator cho bbox/point chuẩn hóa.
- `lmstudio_client.py`
  - `normalize_all_views_payload()`
- `prompts.py`
  - Schema và trường `coordinate_scale`.
- `image_processor.py`
  - `process_image()` tại đoạn nhận AI response.

### Công việc cần làm

1. Khai báo tập view chuẩn:

```text
FRONT, LEFT, RIGHT, TOP, BOTTOM, BACK, PERSPECTIVE
```

2. Chuẩn hóa tên view về uppercase.
3. Từ chối hoặc đánh dấu lỗi khi:
   - Thiếu view.
   - Trùng view.
   - Có view lạ.
   - `panel_bbox` hoặc `object_bbox` không có đúng 4 số hữu hạn.
   - `object_center` không có đúng 2 số hữu hạn.
   - `x1 >= x2` hoặc `y1 >= y2`.
   - Object không nằm trong panel, có xét tolerance rõ ràng.
   - Center không nằm trong object.
4. Validate dữ liệu chuẩn hóa trước khi unpack và trước khi clamp.
5. Không dùng clamp để che lỗi input. Lưu riêng:
   - Bbox AI raw.
   - Bbox sau chuẩn hóa scale.
   - Bbox pixel/clamped.
6. Ưu tiên yêu cầu model trả trường:

```json
"coordinate_scale": 1000
```

7. Chỉ dùng heuristic 0–100/0–1000 khi thiếu trường scale, đồng thời ghi:

```json
{
  "coordinate_scale_source": "explicit|heuristic|fallback",
  "coordinate_scale_warning": null
}
```

8. Nếu không xác định scale đáng tin cậy, dừng view đó thay vì tự nhân 10 âm thầm.

### Test sau khi code xong

#### Unit test

- Payload đủ đúng bảy view được chấp nhận bất kể thứ tự.
- Thiếu `BACK` bị reject và báo đúng tên view thiếu.
- Hai `FRONT` bị reject là duplicate.
- View `SIDE` bị reject.
- Bbox có 3 hoặc 5 phần tử bị reject trước OpenCV.
- Bbox chứa string không chuyển được, `NaN`, `Infinity` bị reject.
- Bbox đảo chiều bị reject.
- Object nằm ngoài panel bị reject hoặc warning theo tolerance đã định.
- Center ngoài object bị reject hoặc warning.
- `coordinate_scale=100` nhân đúng 10.
- `coordinate_scale=1000` không nhân.
- Bbox hệ 0–1000 nằm ở góc trên-trái không bị nhầm thành hệ 0–100 khi có scale explicit.
- Heuristic không chắc chắn phải trả warning/error có cấu trúc.
- Tọa độ âm hoặc lớn hơn scale được phát hiện trước clamp.

Lệnh test:

```powershell
python -m unittest tests.test_response_schema tests.test_bbox_utils -v
```

### Tiêu chí nghiệm thu phần 2

- Không còn lỗi unpack do bbox thiếu/sai kiểu.
- Chỉ payload có đúng bảy view duy nhất mới được coi là all-views thành công.
- Scale explicit được ưu tiên.
- Raw input sai không bị clamp rồi báo là hợp lệ.
- Mỗi validation error xác định được view và field gây lỗi.

---

## PHẦN 3 — HOÀN THIỆN OPENCV CHO 6 VIEW THƯỜNG VÀ FALLBACK

### Mục tiêu

Làm cho panel refine, clean panel và object refine của sáu view thường có cấu hình thống nhất, có giới hạn an toàn và có thể đo được việc refine tốt hơn hay tệ hơn bbox AI.

### File và hàm cần sửa

- `image_processor.py`
  - `_find_table_borders()`
  - `refine_panel_bbox_opencv()`
  - `clean_panel_crop()`
  - `refine_object_bbox_opencv()`
  - `process_image()`
- `config.py`
  - `MIN_CONTOUR_AREA`
  - `MIN_IOU_THRESHOLD`
  - `MAX_CENTER_DISTANCE_RATIO`
  - Các threshold đang hard-code.

### Công việc cần làm

1. Thay các số hard-code `1000`, `200`, `25×25`, `12`, `0.18` bằng config có tên rõ ràng khi cần tuning.
2. Dùng `MIN_CONTOUR_AREA` thực sự hoặc xóa biến này.
3. Đồng bộ điều kiện khoảng cách tâm với tài liệu và config; không dùng `* 2` mà không giải thích.
4. Ghi đầy đủ thông tin refine:

```json
{
  "attempted": true,
  "success": true,
  "method": "opencv",
  "ai_bbox": [],
  "candidate_bbox": [],
  "final_bbox": [],
  "iou_with_ai": 0.0,
  "center_distance_ratio": 0.0,
  "fallback_reason": null
}
```

5. Validate bbox OpenCV trước khi chấp nhận:
   - Nằm trong ảnh.
   - Diện tích không quá nhỏ.
   - Không tăng/giảm bất thường so với AI.
   - Không cắt mất object theo content mask.
6. Với clean panel:
   - Không đánh dấu success nếu trim đều bằng 0.
   - Giữ bảo vệ `content_retained_ratio >= 0.85`.
   - Trả fallback reason cho crop nhỏ, mất nội dung hoặc không thấy line.
7. Với object refine:
   - Không gom contour ở xa chỉ vì chạm vùng tìm kiếm mở rộng.
   - Kiểm soát dilation theo kích thước ROI hoặc config.
   - Không xóa nhầm chi tiết object ở vùng trên.
8. Nếu refine thất bại, fallback về bbox AI hợp lệ và ghi rõ lý do.

### Test sau khi code xong

Chuẩn bị fixture nhỏ cho từng tình huống:

- Panel có bốn đường bảng rõ.
- Panel chỉ có hai đường biên.
- Panel không có đường bảng.
- Panel sát mép ảnh.
- Object có đường kích thước đỏ/xanh.
- Object có label ở góc trên.
- Crop trắng/rỗng.
- Object sát mép panel.

#### Unit/integration OpenCV

- Panel rõ: refine thành công, IoU với bbox kỳ vọng đạt ngưỡng.
- Không có line: fallback đúng bbox AI và có `fallback_reason`.
- Clean panel không làm mất quá 15% content.
- Không có line sát mép: crop giữ nguyên và không báo trim giả.
- Object refine trả bbox hợp lệ, không rỗng.
- Dilation không kéo label ở xa vào bbox cuối.
- Bbox OpenCV bất thường bị từ chối.
- Khi `ENABLE_OPENCV_REFINE=False`, output bbox bằng bbox AI và `attempted=false`.

Lệnh test:

```powershell
python -m unittest tests.test_standard_refine tests.test_process_image -v
```

### Tiêu chí nghiệm thu phần 3

- Sáu view thường đều đi qua cùng một contract refine/fallback.
- Không còn config import nhưng không được sử dụng.
- Fixture không có panel/object không làm pipeline crash.
- Mọi fallback có lý do cụ thể.
- Crop cuối luôn có bbox hợp lệ và kích thước lớn hơn 0.

---

## PHẦN 4 — HOÀN THIỆN THUẬT TOÁN RIÊNG CHO PERSPECTIVE

### Mục tiêu

Giữ `PERSPECTIVE` là nhánh riêng nhưng làm rõ và thực hiện đúng một trong hai chế độ:

1. `bbox_only`: chỉ tìm bbox sạch hơn rồi crop ảnh gốc.
2. `masked_object`: áp mask lên ảnh để thật sự loại nền/chữ/đường đỏ.

Không được gọi kết quả là “spotless” nếu chỉ chạy `bbox_only`.

### File và hàm cần sửa

- `image_processor.py`
  - `refine_perspective_object_opencv()`
  - `process_image()`
  - Có thể thêm `apply_perspective_mask()`.
- `config.py`
  - Threshold HSV/gray.
  - Diện tích contour.
  - Padding.
  - Chế độ output PERSPECTIVE.
- `PROJECT_WORKFLOW.md`
- `CODE_LOGIC.md`

### Công việc cần làm

1. Vector hóa `paper_mask`, không lặp Python qua từng pixel.
2. Giới hạn contour candidate theo quan hệ với bbox AI:
   - Giao với bbox AI.
   - Khoảng cách tâm.
   - Tỷ lệ diện tích.
   - Có thể ưu tiên component chứa tâm AI.
3. Không `vstack` tất cả contour hợp lệ một cách vô điều kiện.
4. Phân biệt mask:
   - Red dimension mask.
   - Gray text/grid mask.
   - Model candidate mask.
5. Thêm morphology và connected-component filtering có tham số.
6. Trả về:

```json
{
  "mode": "bbox_only|masked_object",
  "bbox": [],
  "mask_available": true,
  "selected_components": 1,
  "removed_red_pixels": 0,
  "removed_text_grid_pixels": 0,
  "fallback_reason": null
}
```

7. Nếu chọn `masked_object`:
   - Áp mask vào crop.
   - Nền đầu ra phải là trắng hoặc alpha theo config.
   - Lưu mask debug khi debug mode bật.
8. Nếu mask thất bại:
   - Fallback về bbox AI.
   - Không gọi output là cleaned/masked.
9. Không chạy panel refine/clean chung cho PERSPECTIVE trừ khi có yêu cầu thiết kế mới.

### Test sau khi code xong

Chuẩn bị fixture:

- Mô hình 3D màu vàng.
- Mô hình bạc gần grayscale.
- Có chữ `PERSPECTIVE` gần object.
- Có đường kích thước đỏ cắt ngang ROI.
- Có đường bảng sát object.
- Có hai component màu; chỉ một component giao bbox AI.
- Object sát mép giấy.
- ROI không có component hợp lệ.

#### Test bắt buộc

- Xác nhận `process_image()` gọi hàm PERSPECTIVE riêng, không gọi `refine_object_bbox_opencv()`.
- Component ngoài bbox AI không kéo bbox cuối ra xa.
- Đường đỏ không được chọn làm component object.
- Chữ/grid không kéo bbox cuối.
- Model bạc vẫn được nhận hoặc fallback rõ ràng.
- Không có contour: dùng bbox AI và ghi reason.
- `bbox_only`: ảnh crop là vùng ảnh gốc và tài liệu không gọi là tách nền.
- `masked_object`: pixel thuộc red/text mask được thay nền; test bằng đếm pixel.
- Bbox/mask không vượt kích thước ảnh.
- Thời gian xử lý fixture nằm dưới ngưỡng đã chọn, ví dụ 500 ms cho ROI test chuẩn.

Lệnh test:

```powershell
python -m unittest tests.test_perspective_refine -v
```

### Tiêu chí nghiệm thu phần 4

- PERSPECTIVE vẫn có call path riêng.
- Output khai báo đúng `bbox_only` hoặc `masked_object`.
- Không còn tuyên bố tách nền nếu mask không được áp lên ảnh.
- Không còn vòng lặp Python theo từng pixel cho paper mask.
- Các artifact ngoài object không làm bbox phình bất thường trong fixture test.

---

## PHẦN 5 — HOÀN THIỆN GUI/CLI, OUTPUT, BATCH SUMMARY VÀ TÀI LIỆU

### Mục tiêu

Đảm bảo GUI và CLI chỉ báo thành công khi pipeline thật sự hoàn tất, output JSON khớp file trên đĩa, metadata không bị mất và tài liệu phản ánh đúng code.

### File và hàm cần sửa

- `gui.py`
  - `AnalysisWorker.run()`
  - `AnalysisAllViewsWorker.run()`
  - `_on_analysis_done()`
  - `_on_analyze_all_done()`
- `run_auto_test.py`
  - `run_batch_test()`
  - `clean_old_results()`
- `image_processor.py`
  - `save_cv2_image()`
  - `process_image()`
- `config.py`
  - Các đường dẫn hard-code.
- `PROJECT_WORKFLOW.md`
- `CODE_LOGIC.md`
- `DEPENDENCIES.md`
- `README.md`

### Công việc cần làm

1. GUI all-views nhận một result object gồm:
   - `sheet`.
   - `views`.
   - `validation`.
   - `raw_response` hoặc debug reference.
2. GUI hiển thị số view thực tế, metadata và fallback của từng view.
3. Không hiện “đã cắt 7 views” nếu thiếu view hoặc có crop lỗi.
4. Ghi master JSON sau khi đã thêm tất cả `output_files`, bao gồm chính path JSON.
5. Chỉ đưa path vào `output_files` khi file đã được lưu thành công.
6. Sau mỗi lần lưu, xác nhận file tồn tại và kích thước lớn hơn 0.
7. Batch summary phải chứa:

```json
{
  "image": "",
  "status": "SUCCESS|PARTIAL|FAILED",
  "sheet": {},
  "views_expected": 7,
  "views_received": 7,
  "views_saved": 7,
  "validation": {},
  "views": [
    {
      "view": "FRONT",
      "ai_bbox": [],
      "final_bbox": [],
      "refine_success": true,
      "fallback_reason": null,
      "crop_size": [],
      "crop_file": ""
    }
  ]
}
```

8. Không đánh dấu `SUCCESS` nếu:
   - Thiếu một trong bảy view.
   - Crop rỗng.
   - File không tồn tại.
   - Validation nghiêm trọng thất bại.
9. Thay path tuyệt đối hard-code bằng path dựa trên `BASE_DIR` hoặc config/environment.
10. Giữ việc xóa kết quả batch là thao tác rõ ràng:
    - Thêm `--clean` hoặc xác nhận scope trước khi xóa.
    - Không xóa ngoài `RESULTS_DIR` đã resolve/validate.
11. Đồng bộ bốn file tài liệu với hành vi thật:
    - Resize.
    - Retry.
    - Schema.
    - PERSPECTIVE mode.
    - Metadata.
    - Fallback.
    - Output GUI khác batch.
12. Ghi rõ `dimension_crop.py` là standalone hoặc tích hợp chính thức; không để trạng thái mơ hồ.

### Test sau khi code xong

#### Unit test GUI/worker

- Mock client trả đủ bảy view: worker phát `finished`, không phát `error`.
- Mock thiếu một view: worker trả `PARTIAL/FAILED`, GUI không báo thành công.
- Metadata parsed xuất hiện trong result GUI.
- Một crop lỗi không làm sáu kết quả tốt bị mất, nhưng batch không được báo `SUCCESS`.

#### Test output

- Single-view JSON trên đĩa có `output_files.json`.
- Mọi path khai báo đều tồn tại.
- Không khai báo `panel_image` hoặc `object_image` nếu không lưu được.
- Master all-views JSON có đúng bảy view duy nhất.
- Batch summary giữ được drawing number, metal, brand và metal weight.
- Test đường dẫn trong thư mục có Unicode và khoảng trắng.

#### Test end-to-end không gọi LM Studio

Dùng response fixture hợp lệ và ảnh fixture:

```text
fixture JSON → validate → scale → process 7 views → save → summary
```

Xác nhận:

- 7 object crop được tạo.
- Mỗi crop có width/height lớn hơn 0.
- JSON và file ảnh khớp nhau.
- Có đúng một nhánh PERSPECTIVE.
- Metadata không null nếu fixture có metadata.

#### Test tích hợp thật với LM Studio

Chỉ chạy khi server/model sẵn sàng:

```powershell
python -m unittest discover -s tests -v
python run_auto_test.py
```

Sau batch, kiểm tra tự động:

- `SUCCESS = tổng số ảnh` hoặc liệt kê rõ ảnh `PARTIAL/FAILED`.
- Mỗi ảnh thành công có đúng 7 crop.
- Không có crop path bị thiếu.
- Metadata trong log và summary khớp nhau.
- Không có view duplicate/unknown.

### Tiêu chí nghiệm thu phần 5

- GUI, single-view và batch dùng chung contract kết quả.
- Summary không còn mất metadata.
- Status phản ánh đúng kết quả thực tế.
- JSON trên đĩa không thiếu path của chính nó.
- Không còn đường dẫn workspace hard-code.
- Tài liệu không còn mô tả khác code.

---

## 3. Thứ tự triển khai và cổng kiểm thử

Không nên làm năm phần song song vì contract đầu ra của phần trước là đầu vào của phần sau.

| Thứ tự | Phần | Phụ thuộc | Cổng để chuyển bước |
|---:|---|---|---|
| 1 | API, resize, parse | Không | Unit test HTTP/parse/resize pass |
| 2 | Schema và bbox | Phần 1 | Test đủ 7 view và bbox invalid pass |
| 3 | Sáu view thường | Phần 2 | Fixture panel/object/fallback pass |
| 4 | PERSPECTIVE | Phần 2, có thể dùng contract phần 3 | Test bbox/mask/fallback pass |
| 5 | GUI/CLI/output/docs | Phần 1–4 | E2E fixture và batch thật pass |

Sau mỗi phần:

```powershell
python -m unittest discover -s tests -v
```

Chỉ merge/chuyển phần khi:

- Test mới của phần đó pass.
- Test các phần trước vẫn pass.
- Không phát sinh warning/error không có chủ đích.
- Output contract đã được cập nhật trong test fixture.

---

## 4. Định nghĩa hoàn tất chung

Toàn bộ kế hoạch được coi là hoàn tất khi:

- API dùng resize/config thật.
- Parse lỗi có retry và error type rõ ràng.
- Payload được enforce đúng bảy view.
- Bbox được validate trước chuyển đổi/clamp.
- Sáu view thường có refine/fallback kiểm thử được.
- PERSPECTIVE có chế độ rõ ràng và không tuyên bố vượt quá kết quả thật.
- GUI/CLI không báo success giả.
- Metadata không bị mất.
- Mọi output path khớp file tồn tại.
- Batch summary phân biệt `SUCCESS`, `PARTIAL`, `FAILED`.
- Tất cả test tự động pass.
- `PROJECT_WORKFLOW.md`, `CODE_LOGIC.md`, `DEPENDENCIES.md` và `README.md` khớp code thực tế.
