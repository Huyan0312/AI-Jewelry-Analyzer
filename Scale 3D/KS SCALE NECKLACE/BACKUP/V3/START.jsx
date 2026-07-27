/**
 * START.jsx - Script Launcher
 * Photoshop CS5+ — Gọi các script theo thứ tự
 *
 * Sau bước 4 (Create Stroke), đọc Cache/state.txt dòng 4 (hanger=...):
 * - Nếu hanger = NONE: chạy START Addrule (5,6,7,8) rồi 9. AutoReplaceDrawing (nếu brand khác NONE).
 * - Nếu có chọn hanger: chạy 5.RuleAdd, 6.Position Rule, rồi Hanger/START Hanger (1→5, gồm 5. AutoReplaceDrawing).
 *
 * Trước đó luôn: 1.Scale → 2.Rasterize → 3.Positioning → 4.Create Stroke.
 */

#target photoshop

    (function () {
        // Bắt đầu tính thời gian
        var startTime = new Date().getTime();

        try {
            // Lấy đường dẫn của script hiện tại
            var scriptFile = new File($.fileName);
            var scriptFolder = scriptFile.parent;

            // ==== BƯỚC 1: Gọi 1.Scale.jsx ====
            var scaleScript = new File(scriptFolder.fsName + "/1.Scale.jsx");
            if (!scaleScript.exists) {
                alert("❌ Không tìm thấy file '1.Scale.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(scaleScript);

            // ==== Kiểm tra cache (check) ====
            var cacheFile = new File(scriptFolder.fsName + "/Cache/state.txt");
            var checkStatus = "false";
            if (cacheFile.exists) {
                try {
                    cacheFile.open("r");
                    var cacheContent = cacheFile.read();
                    cacheFile.close();
                    var lines = (cacheContent || "").replace(/\r/g, "").split("\n");
                    for (var ci = 0; ci < lines.length; ci++) {
                        var ln = lines[ci];
                        if (ln.indexOf("check=") === 0) {
                            checkStatus = ln.substring(6).replace(/^\s+|\s+$/g, "");
                            break;
                        }
                    }
                } catch (e) {}
            }
            if (checkStatus !== "true") {
                return;
            }

            // ==== BƯỚC 2: Gọi 2.Rasterize.jsx ====
            var rasterizeScript = new File(scriptFolder.fsName + "/2.Rasterize.jsx");
            if (!rasterizeScript.exists) {
                alert("❌ Không tìm thấy file '2.Rasterize.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(rasterizeScript);

            // ==== BƯỚC 3: Gọi 3.Positioning.jsx ====
            var positioningScript = new File(scriptFolder.fsName + "/3.Positioning.jsx");
            if (!positioningScript.exists) {
                alert("❌ Không tìm thấy file '3.Positioning.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(positioningScript);

            // ==== BƯỚC 4: Gọi 4.Create Stroke.jsx ====
            var strokeScript = new File(scriptFolder.fsName + "/4.Create Stroke.jsx");
            if (!strokeScript.exists) {
                alert("❌ Không tìm thấy file '4.Create Stroke.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(strokeScript);

            // ==== Đọc hanger từ state (dòng 4) để phân nhánh ====
            var hangerValue = "NONE";
            if (cacheFile.exists) {
                try {
                    cacheFile.open("r");
                    var stateContent = cacheFile.read();
                    cacheFile.close();
                    var stateLines = (stateContent || "").replace(/\r/g, "").split("\n");
                    for (var hi = 0; hi < stateLines.length; hi++) {
                        if (stateLines[hi].indexOf("hanger=") === 0) {
                            hangerValue = stateLines[hi].substring(7).replace(/^\s+|\s+$/g, "") || "NONE";
                            break;
                        }
                    }
                } catch (e) {}
            }

            if (!hangerValue || hangerValue.toUpperCase() === "NONE") {
                // Hanger NONE: chạy như cũ — START Addrule (5,6,7,8) rồi 9. AutoReplaceDrawing nếu brand khác NONE
                var startAddruleScript = new File(scriptFolder.fsName + "/START Addrule.jsx");
                if (!startAddruleScript.exists) {
                    alert("❌ Không tìm thấy file 'START Addrule.jsx' trong thư mục:\n" + scriptFolder.fsName);
                    return;
                }
                $.evalFile(startAddruleScript);

                var shouldRunScript9 = false;
                if (cacheFile.exists) {
                    try {
                        cacheFile.open("r");
                        var content9 = cacheFile.read();
                        cacheFile.close();
                        var lines9 = (content9 || "").replace(/\r/g, "").split("\n");
                        var brandName9 = "NONE";
                        for (var i9 = 0; i9 < lines9.length; i9++) {
                            if (lines9[i9].indexOf("brand=") === 0) {
                                brandName9 = lines9[i9].substring(6).replace(/^\s+|\s+$/g, "");
                                break;
                            }
                        }
                        if (brandName9.toUpperCase() !== "NONE") shouldRunScript9 = true;
                    } catch (e) {}
                }
                if (shouldRunScript9) {
                    var autoReplaceScript = new File(scriptFolder.fsName + "/9. AutoReplaceDrawing.jsx");
                    if (autoReplaceScript.exists) $.evalFile(autoReplaceScript);
                }
            } else {
                // Có chọn hanger: chạy tới bước 6 (5.RuleAdd + 6.Position Rule) rồi START Hanger
                var ruleAddScript = new File(scriptFolder.fsName + "/5.RuleAdd.jsx");
                if (!ruleAddScript.exists) {
                    alert("❌ Không tìm thấy file '5.RuleAdd.jsx' trong thư mục:\n" + scriptFolder.fsName);
                    return;
                }
                $.evalFile(ruleAddScript);

                var positionRuleScript = new File(scriptFolder.fsName + "/6.Position Rule.jsx");
                if (!positionRuleScript.exists) {
                    alert("❌ Không tìm thấy file '6.Position Rule.jsx' trong thư mục:\n" + scriptFolder.fsName);
                    return;
                }
                $.evalFile(positionRuleScript);

                var startHangerScript = new File(scriptFolder.fsName + "/Hanger/START Hanger.jsx");
                if (!startHangerScript.exists) {
                    alert("❌ Không tìm thấy file 'Hanger/START Hanger.jsx'.");
                    return;
                }
                $.evalFile(startHangerScript);
            }

            // ====================================
            // 📊 THÔNG BÁO HOÀN THÀNH
            // ====================================

            // Tính thời gian hoàn thành
            var endTime = new Date().getTime();
            var totalSeconds = ((endTime - startTime) / 1000).toFixed(2);

            // Đọc brand và drawing từ Cache/state.txt
            var brandName = "NONE";
            var drawingValue = "không có";
            try {
                var stateFile = new File(scriptFolder.fsName + "/Cache/state.txt");
                if (stateFile.exists) {
                    stateFile.open("r");
                    var stateContent = stateFile.read();
                    stateFile.close();
                    var stateLines = (stateContent || "").replace(/\r/g, "").split("\n");
                    for (var si = 0; si < stateLines.length; si++) {
                        var sl = stateLines[si];
                        if (sl.indexOf("brand=") === 0) brandName = sl.substring(6).replace(/^\s+|\s+$/g, "");
                        if (sl.indexOf("drawing=") === 0) drawingValue = sl.substring(8).replace(/^\s+|\s+$/g, "") || "không có";
                    }
                }
            } catch (e) {}

            // Hiển thị thông báo hoàn thành
            var message = "✅ ĐÃ HOÀN THÀNH SCALE KS NECKLACE!\n\n";
            message += "🏷️ Loại chất liệu: " + brandName + "\n";
            message += "📝 Số Drawing: " + drawingValue + "\n";
            message += "⏱️ Tổng thời gian: " + totalSeconds + " giây";

            alert(message);

        } catch (e) {
            alert("❌ LỖI khi chạy script:\n" + e.message);
        }
    })();
