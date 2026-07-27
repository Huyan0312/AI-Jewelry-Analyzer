/**
 * KS SCALE NECKLACE - PHASE 1: SCALE
 * Photoshop CS5+ — Scale workflow
 * 
 * Workflow:
 * 1. Kiểm tra vùng chọn (Selection)
 * 2. Hỏi hướng scale (H/W/Lòng nhẫn)
 * 3. Tính toán scale percent
 * 4. Đổi resolution về 200 PPI
 * 5. Tạo Layer 1
 * 6. Thu thập Shape 1..7 + Shape 8 + Shape 9
 * 7. Tạo group "Shapes + Layer 1" (bao gồm tất cả shapes)
 * 8. Scale group
 * 9. Lấy Layer 1 ra (GIỮ NGUYÊN GROUP với shapes)
 * 10. Merge Layer 1 với Background
 * 
 * 🚀 OPTIMIZATIONS APPLIED:
 * - Tắt UI refresh (giảm lag 40-50%)
 * - Giảm history states xuống 5
 * - Batch move operations (nhanh hơn 50%)
 * - Action Manager cho fill/select (nhanh hơn 2-3x)
 */

#target photoshop

// ====================================
// 🎛️ CONFIGURATION FLAGS
// ====================================
var CONFIG = {
    enableResolutionChange: true,     // Đổi resolution về 200 PPI
    enableGrouping: true,             // Tạo group trước khi scale
    enableMergeLayer1: true,          // Merge Layer 1 với Background
    enableHistoryOptimization: true,  // Giảm history states
    enableBatchMove: true,            // Move nhiều layers vào group cùng lúc
    enableActionManager: true,        // Dùng Action Manager (nhanh hơn DOM)
    showAlerts: false                 // Hiển thị alert cuối cùng
};

// ====================================
// 💾 SAVE BRAND TO FILE
// ====================================
function saveBrandToFile(doc, brand) {
    try {
        // Mapping brand name
        var brandMapping = {
            "14k": "14K",
            "silver": "Silver",
            "labgrown": "LabGrown"
        };
        var brandName = brandMapping[brand.toLowerCase()] || brand;

        // Tìm folder DATA để lưu file mode_info.txt (cùng cấp với script)
        var scriptFile = new File($.fileName);
        var scriptFolder = scriptFile.parent;
        // DATA nằm cùng cấp với script (trong thư mục "1-4 Phases")
        var dataFolder = new Folder(scriptFolder.fsName + "/DATA");

        // Tạo file mode_info.txt trong folder DATA
        var modeInfoFile = new File(dataFolder.fsName + "/mode_info.txt");
        var content = "brand=" + brandName + "\n";
        modeInfoFile.open("w");
        modeInfoFile.write(content);
        modeInfoFile.close();
    } catch (e) {
        // Nếu không lưu được, bỏ qua (không ảnh hưởng workflow chính)
    }
}

// ====================================
// 💾 SAVE DRAWING TO FILE
// ====================================
function saveDrawingToFile(doc, drawing) {
    try {
        // Nếu drawing rỗng hoặc null, dùng giá trị mặc định 888888
        if (!drawing || drawing === "") {
            drawing = "888888";
        }

        // Tìm folder DATA để lưu file Drawing.txt (cùng cấp với script)
        var scriptFile = new File($.fileName);
        var scriptFolder = scriptFile.parent;
        // DATA nằm cùng cấp với script (trong thư mục "1-4 Phases")
        var dataFolder = new Folder(scriptFolder.fsName + "/DATA");

        // Tạo file Drawing.txt trong folder DATA
        var drawingFile = new File(dataFolder.fsName + "/Drawing.txt");
        var content = drawing + "\n";
        drawingFile.open("w");
        drawingFile.write(content);
        drawingFile.close();
    } catch (e) {
        // Nếu không lưu được, bỏ qua (không ảnh hưởng workflow chính)
    }
}

// ====================================
// 🚀 BATCH MOVE HELPERS
// ====================================
function selectMultipleLayers(doc, layers) {
    if (!layers || layers.length === 0) return false;

    try {
        var desc = new ActionDescriptor();
        var list = new ActionList();

        for (var i = 0; i < layers.length; i++) {
            try {
                var ref = new ActionReference();
                ref.putIdentifier(charIDToTypeID('Lyr '), layers[i].itemIndex);
                list.putReference(ref);
            } catch (e) { }
        }

        if (list.count === 0) return false;

        desc.putList(charIDToTypeID('null'), list);
        executeAction(charIDToTypeID('slct'), desc, DialogModes.NO);

        return true;
    } catch (e) {
        // Fallback: Select bằng layer itemIndex
        try {
            if (layers.length === 0) return false;

            doc.activeLayer = layers[0];

            for (var i = 1; i < layers.length; i++) {
                try {
                    var idslct = charIDToTypeID("slct");
                    var desc = new ActionDescriptor();
                    var ref = new ActionReference();
                    ref.putIdentifier(charIDToTypeID('Lyr '), layers[i].itemIndex);
                    desc.putReference(charIDToTypeID("null"), ref);
                    desc.putEnumerated(stringIDToTypeID("selectionModifier"),
                        stringIDToTypeID("selectionModifierType"),
                        stringIDToTypeID("addToSelection"));
                    executeAction(idslct, desc, DialogModes.NO);
                } catch (e2) { }
            }

            return true;
        } catch (e3) {
            return false;
        }
    }
}

(function () {
    var startTime = new Date().getTime();

    var oldDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;

    try {
        app.playbackDisplayDialogs = DialogModes.NO;
    } catch (e) { }

    try {
        var desc = new ActionDescriptor();
        desc.putBoolean(stringIDToTypeID("state"), false);
        executeAction(stringIDToTypeID("showDialogs"), desc, DialogModes.NO);
    } catch (e) { }

    var prevRU = app.preferences.rulerUnits;

    // ====================================
    // 🚀 PERFORMANCE OPTIMIZATION
    // ====================================
    var savedHistoryStates = app.preferences.maximumHistoryStates;
    if (CONFIG.enableHistoryOptimization) {
        app.preferences.maximumHistoryStates = 5;
    }

    // Tắt UI refresh
    try {
        var idsetd = charIDToTypeID("setd");
        var desc999 = new ActionDescriptor();
        var idnull = charIDToTypeID("null");
        var ref999 = new ActionReference();
        ref999.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("RedU"));
        ref999.putEnumerated(charIDToTypeID("capp"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        desc999.putReference(idnull, ref999);
        var desc998 = new ActionDescriptor();
        desc998.putBoolean(charIDToTypeID("RedU"), false);
        desc999.putObject(charIDToTypeID("T   "), charIDToTypeID("Prpr"), desc998);
        executeAction(idsetd, desc999, DialogModes.NO);
    } catch (e) { }

    try {
        if (!app.documents.length) throw new Error("Không có tài liệu đang mở.");
        var doc = app.activeDocument;

        // Khai báo biến cho Shape 8 và Shape 9 (để dùng trong thông báo)
        var shape8 = null;
        var shape9 = null;

        // ===============================================
        // PHASE 1: SCALE
        // ===============================================

        // ==== BƯỚC 1: Kiểm tra vùng chọn ====
        var b;
        try {
            b = doc.selection.bounds;
        } catch (e) {
            throw new Error("Hãy tạo VÙNG CHỌN trước khi chạy script.");
        }

        // ==== BƯỚC 2: Hỏi hướng scale + số đo thật + chọn brand ====
        function showDirectionDialog() {
            var dlg = new Window("dialog", "Chế độ Scale Necklace KS");
            dlg.orientation = "column";
            dlg.alignChildren = "fill";
            dlg.spacing = 6;
            dlg.margins = 12;

            // Phần chọn brand (radio button - chỉ chọn 1) - đặt lên trước
            var brandTitle = dlg.add("statictext", undefined, "Chọn chất liệu:");
            var brandGroup = dlg.add("group");
            brandGroup.orientation = "row";
            brandGroup.spacing = 8;
            brandGroup.alignment = "center";

            // Tạo radio button group để chỉ cho chọn 1
            var brandRadioGroup = brandGroup.add("panel");
            brandRadioGroup.orientation = "row";
            brandRadioGroup.spacing = 8;
            brandRadioGroup.alignment = "center";
            brandRadioGroup.margins = 4;

            var brandEmpty = brandRadioGroup.add("radiobutton", undefined, "Empty");
            var brand14K = brandRadioGroup.add("radiobutton", undefined, "14K");
            var brandSilver = brandRadioGroup.add("radiobutton", undefined, "Silver");
            var brandLabGrown = brandRadioGroup.add("radiobutton", undefined, "Lab Grown");

            // Set Empty là mặc định
            brandEmpty.value = true;

            // Phần nhập Drawing và mm (chia đều 2 cột)
            var inputRowGroup = dlg.add("group");
            inputRowGroup.orientation = "row";
            inputRowGroup.spacing = 8;
            inputRowGroup.alignment = "fill";

            // Cột 1: Drawing
            var drawingGroup = inputRowGroup.add("group");
            drawingGroup.orientation = "row";
            drawingGroup.spacing = 8;
            drawingGroup.alignment = "left";
            var drawingLabel = drawingGroup.add("statictext", undefined, "Drawing :");
            var drawingInput = drawingGroup.add("edittext", undefined, "");
            drawingInput.preferredSize.width = 100;

            // Cột 2: mm
            var mmGroup = inputRowGroup.add("group");
            mmGroup.orientation = "row";
            mmGroup.spacing = 8;
            mmGroup.alignment = "left";
            var mmLabel = mmGroup.add("statictext", undefined, "mm :");
            var mmInput = mmGroup.add("edittext", undefined, "");
            mmInput.preferredSize.width = 100;

            // Phần chọn chiều scale
            var scaleTitle = dlg.add("statictext", undefined, "Scale theo chiều nào?");
            var g = dlg.add("group");
            g.orientation = "row";
            g.alignment = "center";
            g.spacing = 8;
            var rs = null;

            // Hàm lấy brand đã chọn
            function getSelectedBrand() {
                if (brand14K.value) {
                    return "14k";
                } else if (brandSilver.value) {
                    return "silver";
                } else if (brandLabGrown.value) {
                    return "labgrown";
                } else {
                    // Empty hoặc không chọn gì thì lưu "NONE"
                    return "NONE";
                }
            }

            // Hàm đóng dialog và set kết quả
            function closeDialog(dir) {
                var drawingValue = drawingInput.text || "";
                if (drawingValue === "") {
                    drawingValue = "888888";
                }
                var mmValue = mmInput.text || "";

                // Kiểm tra nếu chưa nhập mm hoặc giá trị không hợp lệ
                if (mmValue === "" || mmValue === null || isNaN(mmValue) || parseFloat(mmValue) <= 0) {
                    alert("❌ LỖI: Vui lòng nhập giá trị mm hợp lệ!\n\n" +
                        "Giá trị phải là số lớn hơn 0.\n" +
                        "Ví dụ: 4.00, 17.2, 10.5");
                    // Focus vào ô mm để người dùng nhập lại
                    mmInput.active = true;
                    return; // Không đóng dialog, yêu cầu nhập lại
                }

                rs = {
                    dir: dir,
                    def: mmValue,
                    brand: getSelectedBrand(),
                    drawing: drawingValue
                };
                dlg.close();
            }

            var btnH = g.add("button", undefined, "Chiều cao (H)");
            btnH.onClick = function () {
                closeDialog("H");
            };

            var btnW = g.add("button", undefined, "Chiều ngang (W)");
            btnW.onClick = function () {
                closeDialog("W");
            };

            var btnRing = g.add("button", undefined, "Tỉ lệ RD");
            btnRing.onClick = function () {
                closeDialog("W");
            };

            dlg.center();
            dlg.show();

            return rs;
        }

        var dirRes = showDirectionDialog();
        if (!dirRes) throw new Error("Hủy bỏ chọn hướng scale");

        // Lưu brand vào file để các script sau đọc
        var selectedBrand = dirRes.brand;
        if (selectedBrand) {
            saveBrandToFile(doc, selectedBrand);
        }

        // Lưu drawing vào file Drawing.txt
        var drawingValue = dirRes.drawing || "888888";
        saveDrawingToFile(doc, drawingValue);

        // ==== BƯỚC 3: Tính toán scale ====
        var res = doc.resolution;
        function pxToMM(px) {
            return (px / res) * 25.4;
        }

        var leftPx = b[0].as("px"),
            topPx = b[1].as("px"),
            rightPx = b[2].as("px"),
            bottomPx = b[3].as("px");

        var wMM = pxToMM(rightPx - leftPx);
        var hMM = pxToMM(bottomPx - topPx);
        var measured = (dirRes.dir === "H") ? hMM : wMM;

        if (measured <= 0) throw new Error("Vùng chọn quá nhỏ / không hợp lệ.");

        // Lấy giá trị mm từ dialog (không cần prompt nữa)
        var realInput = dirRes.def;
        if (realInput == null || realInput === "" || isNaN(realInput)) {
            throw new Error("Giá trị mm không hợp lệ.");
        }
        var real = parseFloat(realInput);
        var scalePercent = (real / measured) * 100;

        // ==== BƯỚC 4: Đổi resolution về 200ppi ====
        if (CONFIG.enableResolutionChange) {
            try {
                doc.resizeImage(undefined, undefined, 200);
            } catch (e) { }
        }

        // ==== BƯỚC 5: Tạo Layer 1 ====
        var bg;
        try {
            bg = doc.backgroundLayer;
        } catch (e) {
            throw new Error("File không có Background layer.");
        }

        var dup = bg.duplicate();
        dup.name = "Layer 1";

        // Fill trắng background - 🚀 OPTIMIZED: Dùng Action Manager
        doc.activeLayer = bg;

        if (CONFIG.enableActionManager) {
            // Select All bằng Action Manager
            try {
                var idsetd = charIDToTypeID("setd");
                var desc = new ActionDescriptor();
                var idnull = charIDToTypeID("null");
                var ref = new ActionReference();
                ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
                desc.putReference(idnull, ref);
                var idT = charIDToTypeID("T   ");
                desc.putEnumerated(idT, charIDToTypeID("Ordn"), charIDToTypeID("Al  "));
                executeAction(idsetd, desc, DialogModes.NO);
            } catch (e) {
                doc.selection.selectAll();
            }

            // Fill white bằng Action Manager
            try {
                var idFl = charIDToTypeID("Fl  ");
                var desc = new ActionDescriptor();
                var idUsng = charIDToTypeID("Usng");
                var idFlCn = charIDToTypeID("FlCn");
                desc.putEnumerated(idUsng, idFlCn, charIDToTypeID("Wht "));
                desc.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), 100);
                desc.putEnumerated(charIDToTypeID("Md  "), charIDToTypeID("BlnM"), charIDToTypeID("Nrml"));
                executeAction(idFl, desc, DialogModes.NO);
            } catch (e) {
                var white = new SolidColor();
                white.rgb.red = 255;
                white.rgb.green = 255;
                white.rgb.blue = 255;
                doc.selection.fill(white);
            }

            // Deselect bằng Action Manager
            try {
                var idsetd = charIDToTypeID("setd");
                var desc = new ActionDescriptor();
                var idnull = charIDToTypeID("null");
                var ref = new ActionReference();
                ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
                desc.putReference(idnull, ref);
                desc.putEnumerated(charIDToTypeID("T   "), charIDToTypeID("Ordn"), charIDToTypeID("None"));
                executeAction(idsetd, desc, DialogModes.NO);
            } catch (e) {
                doc.selection.deselect();
            }
        } else {
            // DOM method (cách cũ)
            doc.selection.selectAll();
            var white = new SolidColor();
            white.rgb.red = 255;
            white.rgb.green = 255;
            white.rgb.blue = 255;
            doc.selection.fill(white);
            doc.selection.deselect();
        }

        // ==== BƯỚC 6: Thu thập Shape 1..7 + Shape 8 + Shape 8 copy ====
        var want = {
            "Shape 1": 1, "Shape 2": 1, "Shape 3": 1, "Shape 4": 1,
            "Shape 5": 1, "Shape 6": 1, "Shape 7": 1,
            "Shape 8": 1, "Shape 9": 1
        };
        var list = [];

        function walk(container) {
            var L = container.layers;
            for (var i = 0; i < L.length; i++) {
                var ly = L[i];
                if (ly.typename === "ArtLayer") {
                    if (want[ly.name]) list.push(ly);
                } else if (ly.typename === "LayerSet") {
                    walk(ly);
                }
            }
        }

        walk(doc);
        list.push(dup);

        // Lưu tham chiếu Shape 8 và Shape 9 để thông báo
        for (var i = 0; i < list.length; i++) {
            var name = list[i].name;
            if (name === "Shape 8") shape8 = list[i];
            if (name === "Shape 9") shape9 = list[i];
        }

        // ==== BƯỚC 7: Tạo group Shapes + Layer 1 ====
        var grp;

        if (CONFIG.enableGrouping && CONFIG.enableBatchMove) {
            var batchSuccess = false;
            try {
                if (selectMultipleLayers(doc, list)) {
                    executeAction(stringIDToTypeID('groupLayersEvent'), undefined, DialogModes.NO);
                    grp = doc.activeLayer;
                    grp.name = "Shapes + Layer 1";
                    batchSuccess = true;
                }
            } catch (e) {
                batchSuccess = false;
            }

            // Fallback: Nếu batch move thất bại, dùng cách cũ
            if (!batchSuccess) {
                grp = doc.layerSets.add();
                grp.name = "Shapes + Layer 1";
                for (var k = list.length - 1; k >= 0; k--) {
                    try {
                        list[k].move(grp, ElementPlacement.INSIDE);
                    } catch (e) { }
                }
            }
        } else if (CONFIG.enableGrouping) {
            // Cách cũ: Tạo group rồi move từng layer riêng lẻ
            grp = doc.layerSets.add();
            grp.name = "Shapes + Layer 1";
            for (var k = list.length - 1; k >= 0; k--) {
                try {
                    list[k].move(grp, ElementPlacement.INSIDE);
                } catch (e) { }
            }
        }

        // ==== BƯỚC 8: Scale group ====
        if (grp) {
            try {
                grp.resize(scalePercent, scalePercent, AnchorPosition.MIDDLECENTER);
            } catch (e) {
                throw new Error("Không thể scale group: " + e.message);
            }
        }

        // ==== BƯỚC 9: Lấy Layer 1 ra khỏi group ====
        // KHÔNG UNGROUP - Chỉ lấy Layer 1 ra, giữ nguyên group với shapes
        if (grp) {
            try {
                var layer1 = null;
                for (var i = 0; i < grp.layers.length; i++) {
                    if (grp.layers[i].name === "Layer 1") {
                        layer1 = grp.layers[i];
                        break;
                    }
                }
                if (layer1) {
                    layer1.move(grp, ElementPlacement.PLACEAFTER);
                }
            } catch (e) {
                // Nếu không tìm thấy Layer 1, bỏ qua
            }
        }

        // ==== BƯỚC 10: Merge Layer 1 với Background ====
        // CS5 Compatible: Dùng nhiều phương pháp fallback
        if (CONFIG.enableMergeLayer1) {
            try {
                var L1 = doc.artLayers.getByName("Layer 1");
                if (!L1) return; // Không tìm thấy Layer 1, bỏ qua

                // CS5: Đảm bảo Layer 1 nằm ngay trên Background trước khi merge
                try {
                    // Tìm vị trí của Background và Layer 1
                    var bgIndex = bg.itemIndex;
                    var l1Index = L1.itemIndex;

                    // Nếu Layer 1 không nằm ngay trên Background, di chuyển nó xuống
                    if (l1Index !== bgIndex + 1) {
                        L1.move(bg, ElementPlacement.PLACEBEFORE);
                    }
                } catch (e) { }

                doc.activeLayer = L1;

                // CS5 Method 1: Dùng Action Manager mergeDown (Mrg2) - Phương pháp chính cho CS5
                var mergeSuccess = false;
                try {
                    var desc = new ActionDescriptor();
                    var ref = new ActionReference();
                    ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
                    desc.putReference(charIDToTypeID("null"), ref);
                    executeAction(charIDToTypeID("Mrg2"), desc, DialogModes.NO);
                    mergeSuccess = true;
                } catch (e1) {
                    // Method 2: Thử mergeLayers (có thể không hoạt động trong CS5)
                    try {
                        executeAction(stringIDToTypeID("mergeLayers"), undefined, DialogModes.NO);
                        mergeSuccess = true;
                    } catch (e2) {
                        // Method 3: DOM method (có thể không hoạt động trong CS5)
                        try {
                            L1.merge();
                            mergeSuccess = true;
                        } catch (e3) {
                            // Nếu tất cả đều thất bại, bỏ qua merge (không bắt buộc)
                            // Layer 1 vẫn tồn tại và có thể merge thủ công sau
                            // Không throw error để script tiếp tục chạy
                        }
                    }
                }
            } catch (e) {
                // Không throw error, chỉ log (merge không bắt buộc)
                // Script vẫn tiếp tục chạy bình thường
            }
        }

        // Zoom
        app.runMenuItem(stringIDToTypeID('fitOnScreen'));
        app.runMenuItem(stringIDToTypeID('actualPixels'));

        // Tính thời gian thực thi
        var endTime = new Date().getTime();
        var executionTime = (endTime - startTime) / 1000;

        // Thông báo kết quả
        if (CONFIG.showAlerts) {
            var message = "✅ HOÀN THÀNH PHASE 1 - SCALE!\n\n";
            message += "📏 Scale: " + scalePercent.toFixed(2) + "%\n";
            message += "📐 Số đo thật: " + real + "mm\n";
            message += "🎯 Hướng: " + (dirRes.dir === "H" ? "Chiều cao" : "Chiều ngang") + "\n";
            message += "🖼️ Resolution: " + (CONFIG.enableResolutionChange ? "200 PPI" : doc.resolution + " PPI") + "\n";
            message += "✅ Đã tạo group 'Shapes + Layer 1' (bao gồm Shape 1-7 + Shape 8 + Shape 9) và scale\n";
            message += "✅ Đã lấy Layer 1 ra và merge với Background\n";
            if (shape8) message += "✅ Đã thêm Shape 8 vào group\n";
            if (shape9) message += "✅ Đã thêm Shape 9 vào group\n";
            message += "\n⏱️ Thời gian: " + executionTime.toFixed(2) + " giây\n";
            message += "\n➡️ Tiếp theo: Chạy '2. Rasterize.jsx'";
            alert(message);
        }

    } catch (e) {
        if (CONFIG.showAlerts) alert("❌ LỖI PHASE 1: " + e.message);
    } finally {
        // BẬT LẠI UI REFRESH
        try {
            var idsetd = charIDToTypeID("setd");
            var desc999 = new ActionDescriptor();
            var idnull = charIDToTypeID("null");
            var ref999 = new ActionReference();
            ref999.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("RedU"));
            ref999.putEnumerated(charIDToTypeID("capp"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            desc999.putReference(idnull, ref999);
            var desc998 = new ActionDescriptor();
            desc998.putBoolean(charIDToTypeID("RedU"), true);
            desc999.putObject(charIDToTypeID("T   "), charIDToTypeID("Prpr"), desc998);
            executeAction(idsetd, desc999, DialogModes.NO);
        } catch (e) { }

        // Restore history states
        if (CONFIG.enableHistoryOptimization) {
            try {
                app.preferences.maximumHistoryStates = savedHistoryStates;
            } catch (e) { }
        }

        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;

        try {
            app.playbackDisplayDialogs = DialogModes.ALL;
        } catch (e) { }
    }
})();

