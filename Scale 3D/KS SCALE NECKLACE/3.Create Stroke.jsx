#target photoshop;

// ===============================================
// KS TẠO STROKE - CS5 (NO MERGE VERSION - FOR NECKLACE)
// ===============================================
// WORKFLOW:
// 1. Chọn tất cả layer cần thiết (View 1-7)
// 2. Merge tạm thời để lấy kích thước tổng thể
// 3. Ctrl+Z (Undo) để giữ nguyên các layer riêng lẻ
// 4. Tạo stroke layer dựa trên kích thước đã lấy
// 5. Kết quả: Có stroke + các layer gốc riêng biệt để dễ chỉnh sửa
// ===============================================
// KHÁC BIỆT VỚI EARRINGS:
// - Necklace có workflow tương tự Ring
// - Script này TẠO STROKE RIÊNG, KHÔNG merge
// - Giữ nguyên các layer để linh hoạt chỉnh sửa
// ===============================================

// ===============================================
// CONTROL: BẬT/TẮT THÔNG BÁO
// ===============================================
var showAlerts = false;  // true = hiển thị alert, false = tắt alert

// ===== CÀI ĐẶT =====
var strokeWidth = 1;           // Độ dày viền (px)
var strokeColor = [0, 0, 0];   // Màu viền RGB (đen)
var strokePosition = 2;        // 1=Inside, 2=Center, 3=Outside
var mergeWithNewLayers = false; // true = merge với New 1, New 3, New 6 | false = CHỈ merge View 1-7

if (app.documents.length === 0) {
    if (showAlerts) alert("❌ Không có file nào đang mở.");
} else {
    var doc = app.activeDocument;
    var layer = doc.activeLayer;

    // ===== HELPER: Chọn layer theo tên =====
    function selectLayerByName(layerName, addToSelection) {
        try {
            var ref = new ActionReference();
            ref.putName(charIDToTypeID("Lyr "), layerName);
            var desc = new ActionDescriptor();
            desc.putReference(charIDToTypeID("null"), ref);
            
            if (addToSelection === true) {
                desc.putEnumerated(stringIDToTypeID("selectionModifier"), stringIDToTypeID("selectionModifierType"), stringIDToTypeID("addToSelection"));
            }
            
            executeAction(charIDToTypeID("slct"), desc, DialogModes.NO);
            return true;
        } catch (e) {
            return false;
        }
    }

    // ===== HELPER: Undo =====
    function undo() {
        try {
            executeAction(charIDToTypeID("undo"), undefined, DialogModes.NO);
            return true;
        } catch (e) {
            return false;
        }
    }

    try {
        var bounds = null;
        var mergedLayerCount = 0;

        // ===== WORKFLOW: MERGE TẠM → LẤY BOUNDS → UNDO =====
        // 1. Chọn CHỈ các layer cần thiết (View 1-7)
        var layersToMerge = ["View 1", "View 2", "View 3", "View 4", "View 5", "View 6", "View 7"];
        
        // Tùy chọn: Thêm New layers vào merge
        if (mergeWithNewLayers) {
            layersToMerge.push("New 1", "New 3", "New 6");
        }
        
        // Chọn từng layer theo tên (chỉ các layer trong danh sách)
        var firstLayerSelected = false;
        var selectedLayers = [];
        
        for (var i = 0; i < layersToMerge.length; i++) {
            var success = selectLayerByName(layersToMerge[i], firstLayerSelected);
            if (success) {
                if (!firstLayerSelected) firstLayerSelected = true;
                mergedLayerCount++;
                selectedLayers.push(layersToMerge[i]);
            }
        }
        
        if (!firstLayerSelected) {
            throw new Error("Không tìm thấy layer nào để tạo stroke");
        }
        
        // Debug: Hiển thị các layer đã chọn
        // alert("Đã chọn " + mergedLayerCount + " layers:\n" + selectedLayers.join(", "));
        
        // 2. Merge tạm thời (Ctrl+E)
        var descMerge = new ActionDescriptor();
        executeAction(charIDToTypeID("Mrg2"), descMerge, DialogModes.NO);
        
        // 3. Lấy bounds từ layer merged
        var mergedLayer = doc.activeLayer;
        bounds = mergedLayer.bounds; // [left, top, right, bottom]
        
        // 4. UNDO để quay lại trạng thái ban đầu (giữ nguyên các layer riêng lẻ)
        undo();

        // ===== LẤY BOUNDING BOX =====
        var margin = 15; // Chừa bờ 15px
        var left   = bounds[0].as("px") - margin;
        var top    = bounds[1].as("px") - margin;
        var right  = bounds[2].as("px") + margin;
        var bottom = bounds[3].as("px") + margin;

        // ===== TẠO LAYER MỚI ĐỂ VẼ KHUNG =====
        var boxLayer = doc.artLayers.add();
        boxLayer.name = "Bounding Box Stroke";
        boxLayer.kind = LayerKind.NORMAL;

        // ===== TẠO VÙNG CHỌN HÌNH CHỮ NHẬT BAO LAYER =====
        doc.selection.select([
            [left, top],
            [right, top],
            [right, bottom],
            [left, bottom]
        ]);

        // ===== VẼ STROKE DẠNG HỘP (CS5 Compatible) =====
        var color = new SolidColor();
        color.rgb.red = strokeColor[0];
        color.rgb.green = strokeColor[1];
        color.rgb.blue = strokeColor[2];
        var loc = strokePosition === 1 ? StrokeLocation.INSIDE :
                  strokePosition === 2 ? StrokeLocation.CENTER :
                                          StrokeLocation.OUTSIDE;
        doc.selection.stroke(color, strokeWidth, loc, ColorBlendMode.NORMAL, 100, false);

        // ===== BỎ CHỌN =====
        doc.selection.deselect();

        // ===== THÔNG BÁO KẾT QUẢ =====
        var message = "✅ Đã tạo stroke thành công!\n\n";
        message += "🔄 Workflow: Merge tạm thời (Necklace version)\n";
        message += "📦 Đã chọn: " + mergedLayerCount + " layer (View 1-7";
        if (mergeWithNewLayers) {
            message += " + New layers";
        }
        message += ")\n";
        message += "⚙️ Merge → Lấy bounds → Undo\n";
        message += "✨ Các layer gốc vẫn giữ nguyên để dễ chỉnh sửa!\n";
        message += "\n📏 Stroke: " + strokeWidth + "px, Margin: 15px";
        message += "\n⚙️ Cài đặt: mergeWithNewLayers = " + mergeWithNewLayers;
        
        if (showAlerts) alert(message);

    } catch (e) {
        if (showAlerts) alert("❌ Lỗi khi tạo stroke: " + e.message);
    }
}


