/**
 * KS SCALE NECKLACE - PHASE 3: POSITIONING (NECKLACE LAYOUT)
 * Photoshop CS5+ — Positioning layers theo necklace layout
 *
 * Workflow (ten layer: View 1..7 — sau 1.Scale):
 * 1. View 2 sat trai View 1
 * 2. View 3 sat tren View 1 + canh giua
 * 3. View 6 sat phai View 1 + canh giua ngang
 * 4. View 7 sat duoi View 1 + canh giua
 * 5. View 5 sat phai View 6 + canh giua
 * 6. View 4 sat phai View 5 + canh giua
 *
 * Layout:
 *        [View 3]
 * [View 2] [View 1] [View 6] [View 5] [View 4]
 *        [View 7]
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

        // Tim View 1..7 — dệ quy vào LayerSet để tìm cả khi AI tạo View trong group
        function findLayers() {
            var layer1 = null, layer2 = null, layer3 = null,
                layer4 = null, layer5 = null, layer6 = null, layer7 = null;

            function matchView(name, n) {
                return name === ("view " + n) || name === ("view" + n);
            }

            // Đệ quy để tìm trong cả LayerSet (group)
            function walkLayers(container) {
                for (var i = 0; i < container.layers.length; i++) {
                    var l = container.layers[i];
                    var name = l.name.toLowerCase();
                    if (matchView(name, 1) && !layer1) layer1 = l;
                    if (matchView(name, 2) && !layer2) layer2 = l;
                    if (matchView(name, 3) && !layer3) layer3 = l;
                    if (matchView(name, 4) && !layer4) layer4 = l;
                    if (matchView(name, 5) && !layer5) layer5 = l;
                    if (matchView(name, 6) && !layer6) layer6 = l;
                    if (matchView(name, 7) && !layer7) layer7 = l;
                    // Đệ quy vào LayerSet (group)
                    if (l.typename === "LayerSet") {
                        walkLayers(l);
                    }
                }
            }

            walkLayers(doc);

            var found = 0;
            if (layer1) found++;
            if (layer2) found++;
            if (layer3) found++;
            if (layer4) found++;
            if (layer5) found++;
            if (layer6) found++;
            if (layer7) found++;

            if (found < 1) {
                throw new Error("Khong tim thay bat ky View nao trong tai lieu.");
            }
            if (found < 7) {
                // Chi canh bao, khong dung lai — positioning nhung view co san
                if (CONFIG.showAlerts) {
                    alert("Chi tim thay " + found + "/7 View. Positioning nhung view co san.");
                }
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
            var left6 = parseFloat(bounds6[0]);
            var top1 = parseFloat(bounds1[1]);
            var bottom1 = parseFloat(bounds1[3]);
            var top6 = parseFloat(bounds6[1]);
            var bottom6 = parseFloat(bounds6[3]);
            var height1 = bottom1 - top1;
            var height6 = bottom6 - top6;
            var newX = right1;
            var moveX = newX - left6;
            var centerY1 = top1 + height1 / 2;
            var centerY6 = top6 + height6 / 2;
            var moveY = centerY1 - centerY6;
            doc.activeLayer = layer6;
            layer6.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 3 sát trên Layer 1 + canh giữa
        function snapLayer3AboveLayer1(layer1, layer3) {
            var bounds1 = layer1.bounds;
            var bounds3 = layer3.bounds;
            var top1 = parseFloat(bounds1[1]);
            var left1 = parseFloat(bounds1[0]);
            var right1 = parseFloat(bounds1[2]);
            var top3 = parseFloat(bounds3[1]);
            var bottom3 = parseFloat(bounds3[3]);
            var left3 = parseFloat(bounds3[0]);
            var right3 = parseFloat(bounds3[2]);
            var height3 = bottom3 - top3;
            var width1 = right1 - left1;
            var width3 = right3 - left3;
            var newY = top1 - height3;
            var moveY = newY - top3;
            var centerX1 = left1 + width1 / 2;
            var centerX3 = left3 + width3 / 2;
            var moveX = centerX1 - centerX3;
            doc.activeLayer = layer3;
            layer3.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 7 sát dưới Layer 1 + canh giữa
        function snapLayer7BelowLayer1(layer1, layer7) {
            var bounds1 = layer1.bounds;
            var bounds7 = layer7.bounds;
            var bottom1 = parseFloat(bounds1[3]);
            var left1 = parseFloat(bounds1[0]);
            var right1 = parseFloat(bounds1[2]);
            var top7 = parseFloat(bounds7[1]);
            var left7 = parseFloat(bounds7[0]);
            var right7 = parseFloat(bounds7[2]);
            var width1 = right1 - left1;
            var width7 = right7 - left7;
            var newY = bottom1;
            var moveY = newY - top7;
            var centerX1 = left1 + width1 / 2;
            var centerX7 = left7 + width7 / 2;
            var moveX = centerX1 - centerX7;
            doc.activeLayer = layer7;
            layer7.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 5 sát phải Layer 6 + canh giữa
        function snapLayer5ToRightOfLayer6(layer6, layer5) {
            var bounds6 = layer6.bounds;
            var bounds5 = layer5.bounds;
            var right6 = parseFloat(bounds6[2]);
            var left5 = parseFloat(bounds5[0]);
            var top6 = parseFloat(bounds6[1]);
            var bottom6 = parseFloat(bounds6[3]);
            var top5 = parseFloat(bounds5[1]);
            var bottom5 = parseFloat(bounds5[3]);
            var height6 = bottom6 - top6;
            var height5 = bottom5 - top5;
            var newX = right6;
            var moveX = newX - left5;
            var centerY6 = top6 + height6 / 2;
            var centerY5 = top5 + height5 / 2;
            var moveY = centerY6 - centerY5;
            doc.activeLayer = layer5;
            layer5.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        // Layer 4 sát phải Layer 5 + canh giữa
        function snapLayer4ToRightOfLayer5(layer5, layer4) {
            var bounds5 = layer5.bounds;
            var bounds4 = layer4.bounds;
            var right5 = parseFloat(bounds5[2]);
            var left4 = parseFloat(bounds4[0]);
            var top5 = parseFloat(bounds5[1]);
            var bottom5 = parseFloat(bounds5[3]);
            var top4 = parseFloat(bounds4[1]);
            var bottom4 = parseFloat(bounds4[3]);
            var height5 = bottom5 - top5;
            var height4 = bottom4 - top4;
            var newX = right5;
            var moveX = newX - left4;
            var centerY5 = top5 + height5 / 2;
            var centerY4 = top4 + height4 / 2;
            var moveY = centerY5 - centerY4;
            doc.activeLayer = layer4;
            layer4.translate(UnitValue(moveX, "mm"), UnitValue(moveY, "mm"));
        }

        var layers = findLayers();

        // Chi positioning nhung view ton tai — bo qua neu null
        if (layers.layer1 && layers.layer2) snapLayer2ToLeftOfLayer1(layers.layer1, layers.layer2);
        if (layers.layer1 && layers.layer3) snapLayer3AboveLayer1(layers.layer1, layers.layer3);
        if (layers.layer1 && layers.layer6) snapLayer6ToRightOfLayer1(layers.layer1, layers.layer6);
        if (layers.layer1 && layers.layer7) snapLayer7BelowLayer1(layers.layer1, layers.layer7);
        if (layers.layer6 && layers.layer5) snapLayer5ToRightOfLayer6(layers.layer6, layers.layer5);
        if (layers.layer5 && layers.layer4) snapLayer4ToRightOfLayer5(layers.layer5, layers.layer4);

        positionResult.success = true;
        positionResult.message = "Positioning thanh cong.";

        var endTime = new Date().getTime();
        var executionTime = (endTime - startTime) / 1000;

        if (CONFIG.showAlerts) {
            var message = "✅ HOÀN THÀNH POSITIONING!\n\n";
            message += positionResult.message + "\n\n";
            message += "   View 2 -> Sat trai View 1\n";
            message += "   View 3 -> Sat tren View 1 + Canh giua\n";
            message += "   View 6 -> Sat phai View 1 + Canh giua ngang\n";
            message += "   View 7 -> Sat duoi View 1 + Canh giua\n";
            message += "   View 5 -> Sat phai View 6 + Canh giua\n";
            message += "   View 4 -> Sat phai View 5 + Canh giua\n";
            message += "\n⏱️ Thời gian: " + executionTime.toFixed(2) + " giây\n";
            alert(message);
        }

    } catch (e) {
        if (CONFIG.showAlerts) alert("❌ LỖI POSITIONING: " + e.message);
        else alert("Loi Positioning: " + e.message);
    } finally {
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

        app.preferences.rulerUnits = prevRU;
        app.displayDialogs = oldDialogs;
    }
})();
