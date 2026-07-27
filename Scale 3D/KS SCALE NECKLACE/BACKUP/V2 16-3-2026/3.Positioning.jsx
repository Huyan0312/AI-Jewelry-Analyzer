/**
 * KS SCALE NECKLACE - PHASE 3: POSITIONING (NECKLACE LAYOUT)
 * Photoshop CS5+ — Positioning layers theo necklace layout
 * 
 * Workflow:
 * 1. Layer 2 sát trái Layer 1
 * 2. Layer 3 sát trên Layer 1 + canh giữa
 * 3. Layer 6 sát phải Layer 1 + canh giữa ngang
 * 4. Layer 7 sát dưới Layer 1 + canh giữa
 * 5. Layer 5 sát phải Layer 6 + canh giữa
 * 6. Layer 4 sát phải Layer 5 + canh giữa
 * 
 * Layout:
 *        [Layer 3]
 * [Layer 2] [Layer 1] [Layer 6] [Layer 5] [Layer 4]
 *        [Layer 7]
 */

#target photoshop

// ====================================
// 🎛️ CONFIGURATION FLAGS
// ====================================
var CONFIG = {
    showAlerts: false                 // Hiển thị alert cuối cùng
};

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

        // ===============================================
        // PHASE 4: POSITIONING LAYERS (NECKLACE LAYOUT)
        // ===============================================

        // Chuyển về MILLIMETERS cho positioning
        app.preferences.rulerUnits = Units.MM;

        var positionResult = { success: false, message: "" };

        // Tìm các layer cần thiết
        function findLayers() {
            var layer1 = null, layer2 = null, layer3 = null,
                layer4 = null, layer5 = null, layer6 = null, layer7 = null;

            for (var i = 0; i < doc.layers.length; i++) {
                var name = doc.layers[i].name.toLowerCase();
                if ((name.indexOf("layer 1") >= 0 || name.indexOf("layer1") >= 0) && !layer1) {
                    layer1 = doc.layers[i];
                }
                if ((name.indexOf("layer 2") >= 0 || name.indexOf("layer2") >= 0) && !layer2) {
                    layer2 = doc.layers[i];
                }
                if ((name.indexOf("layer 3") >= 0 || name.indexOf("layer3") >= 0) && !layer3) {
                    layer3 = doc.layers[i];
                }
                if ((name.indexOf("layer 4") >= 0 || name.indexOf("layer4") >= 0) && !layer4) {
                    layer4 = doc.layers[i];
                }
                if ((name.indexOf("layer 5") >= 0 || name.indexOf("layer5") >= 0) && !layer5) {
                    layer5 = doc.layers[i];
                }
                if ((name.indexOf("layer 6") >= 0 || name.indexOf("layer6") >= 0) && !layer6) {
                    layer6 = doc.layers[i];
                }
                if ((name.indexOf("layer 7") >= 0 || name.indexOf("layer7") >= 0) && !layer7) {
                    layer7 = doc.layers[i];
                }
            }

            if (!layer1 || !layer2 || !layer3 || !layer4 || !layer5 || !layer6 || !layer7) {
                throw new Error("Không tìm đủ Layer 1-7");
            }

            return {
                layer1: layer1, layer2: layer2, layer3: layer3,
                layer4: layer4, layer5: layer5, layer6: layer6, layer7: layer7
            };
        }

        // Layer 2 sát trái Layer 1
        function snapLayer2ToLeftOfLayer1(layer1, layer2) {
            var bounds1 = layer1.bounds;
            var bounds2 = layer2.bounds;
            var left1 = parseFloat(bounds1[0]);
            var left2 = parseFloat(bounds2[0]);
            var right2 = parseFloat(bounds2[2]);
            var width2 = right2 - left2;
            var newX = left1 - width2;
            var moveX = newX - left2;
            doc.activeLayer = layer2;
            layer2.translate(UnitValue(moveX, "mm"), UnitValue(0, "mm"));
        }

        // Layer 6 sát phải Layer 1 + canh giữa ngang
        function snapLayer6ToRightOfLayer1(layer1, layer6) {
            var bounds1 = layer1.bounds;
            var bounds6 = layer6.bounds;
            var right1 = parseFloat(bounds1[2]);
            var top1 = parseFloat(bounds1[1]);
            var bottom1 = parseFloat(bounds1[3]);
            var centerY1 = top1 + (bottom1 - top1) / 2;
            var left6 = parseFloat(bounds6[0]);
            var top6 = parseFloat(bounds6[1]);
            var bottom6 = parseFloat(bounds6[3]);
            var height6 = bottom6 - top6;
            var newX = right1;
            var newY = centerY1 - height6 / 2;
            var moveX = newX - left6;
            var moveY = newY - top6;
            doc.activeLayer = layer6;
            layer6.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 7 sát dưới Layer 1 + canh giữa
        function snapLayer7BelowLayer1(layer1, layer7) {
            var bounds1 = layer1.bounds;
            var bounds7 = layer7.bounds;
            var left1 = parseFloat(bounds1[0]);
            var right1 = parseFloat(bounds1[2]);
            var bottom1 = parseFloat(bounds1[3]);
            var centerX1 = left1 + (right1 - left1) / 2;
            var left7 = parseFloat(bounds7[0]);
            var top7 = parseFloat(bounds7[1]);
            var right7 = parseFloat(bounds7[2]);
            var width7 = right7 - left7;
            var newX = centerX1 - width7 / 2;
            var newY = bottom1;
            var moveX = newX - left7;
            var moveY = newY - top7;
            doc.activeLayer = layer7;
            layer7.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 3 sát trên Layer 1 + canh giữa
        function snapLayer3AboveLayer1(layer1, layer3) {
            var bounds1 = layer1.bounds;
            var bounds3 = layer3.bounds;
            var left1 = bounds1[0].as("mm");
            var top1 = bounds1[1].as("mm");
            var right1 = bounds1[2].as("mm");
            var left3 = bounds3[0].as("mm");
            var top3 = bounds3[1].as("mm");
            var right3 = bounds3[2].as("mm");
            var bottom3 = bounds3[3].as("mm");
            var width3 = right3 - left3;
            var height3 = bottom3 - top3;
            var centerX1 = left1 + (right1 - left1) / 2;
            var newX = centerX1 - width3 / 2;
            var newY = top1 - height3;
            var moveX = newX - left3;
            var moveY = newY - top3;
            doc.activeLayer = layer3;
            layer3.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 5 sát phải Layer 6 + canh giữa
        function snapLayer5ToRightOfLayer6(layer6, layer5) {
            var bounds6 = layer6.bounds;
            var bounds5 = layer5.bounds;
            var right6 = bounds6[2].as("mm");
            var top6 = bounds6[1].as("mm");
            var bottom6 = bounds6[3].as("mm");
            var centerY6 = top6 + (bottom6 - top6) / 2;
            var left5 = bounds5[0].as("mm");
            var top5 = bounds5[1].as("mm");
            var bottom5 = bounds5[3].as("mm");
            var height5 = bottom5 - top5;
            var newX = right6;
            var newY = centerY6 - height5 / 2;
            var moveX = newX - left5;
            var moveY = newY - top5;
            doc.activeLayer = layer5;
            layer5.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 4 sát phải Layer 5 + canh giữa
        function snapLayer4ToRightOfLayer5(layer5, layer4) {
            var bounds5 = layer5.bounds;
            var bounds4 = layer4.bounds;
            var right5 = bounds5[2].as("mm");
            var top5 = bounds5[1].as("mm");
            var bottom5 = bounds5[3].as("mm");
            var centerY5 = top5 + (bottom5 - top5) / 2;
            var left4 = bounds4[0].as("mm");
            var top4 = bounds4[1].as("mm");
            var bottom4 = bounds4[3].as("mm");
            var height4 = bottom4 - top4;
            var newX = right5;
            var newY = centerY5 - height4 / 2;
            var moveX = newX - left4;
            var moveY = newY - top4;
            doc.activeLayer = layer4;
            layer4.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Thực thi positioning
        var layers = findLayers();
        snapLayer2ToLeftOfLayer1(layers.layer1, layers.layer2);
        snapLayer3AboveLayer1(layers.layer1, layers.layer3);
        snapLayer6ToRightOfLayer1(layers.layer1, layers.layer6);
        snapLayer7BelowLayer1(layers.layer1, layers.layer7);
        snapLayer5ToRightOfLayer6(layers.layer6, layers.layer5);
        snapLayer4ToRightOfLayer5(layers.layer5, layers.layer4);

        positionResult.success = true;
        positionResult.message = "Positioning thành công cho 7 layers (Necklace layout)";

        // Tính thời gian thực thi
        var endTime = new Date().getTime();
        var executionTime = (endTime - startTime) / 1000;

        // Thông báo kết quả
        if (CONFIG.showAlerts) {
            var message = "✅ HOÀN THÀNH PHASE 4 - POSITIONING!\n\n";
            message += "📋 Layout Necklace:\n";
            message += "   • Layer 2 → Sát trái Layer 1\n";
            message += "   • Layer 3 → Sát trên Layer 1 + Canh giữa\n";
            message += "   • Layer 6 → Sát phải Layer 1 + Canh giữa ngang\n";
            message += "   • Layer 7 → Sát dưới Layer 1 + Canh giữa\n";
            message += "   • Layer 5 → Sát phải Layer 6 + Canh giữa\n";
            message += "   • Layer 4 → Sát phải Layer 5 + Canh giữa\n";
            message += "\n⏱️ Thời gian: " + executionTime.toFixed(2) + " giây\n";
            message += "\n🎉 HOÀN THÀNH TẤT CẢ PHASES!";
            alert(message);
        }

    } catch (e) {
        positionResult.success = false;
        positionResult.message = "Lỗi positioning: " + e.message;
        if (CONFIG.showAlerts) alert("❌ LỖI PHASE 4: " + e.message);
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

        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;

        try {
            app.playbackDisplayDialogs = DialogModes.ALL;
        } catch (e) { }
    }
})();

