/**
 * START.jsx - Script Launcher
 * Photoshop CS5+ — Gọi các script theo thứ tự
 * 
 * Script này sẽ tự động tìm và chạy các file theo thứ tự:
 * 1. 1.Scale.jsx
 * 2. 2.Rasterize.jsx
 * 3. 3.Positioning.jsx
 * 4. 4.Create Stroke.jsx
 * 5. START Addrule.jsx
 * 6. 9. AutoReplaceDrawing.jsx (chỉ chạy nếu có file Drawing.txt trong folder DATA)
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

            // ==== BƯỚC 5: Gọi START Addrule.jsx ====
            var startAddruleScript = new File(scriptFolder.fsName + "/START Addrule.jsx");
            if (!startAddruleScript.exists) {
                alert("❌ Không tìm thấy file 'START Addrule.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(startAddruleScript);

            // ==== BƯỚC 6: Gọi 9. AutoReplaceDrawing.jsx (chỉ nếu có file Drawing.txt và brand không phải NONE) ====
            var dataFolder = new Folder(scriptFolder.fsName + "/DATA");
            var drawingFile = new File(dataFolder.fsName + "/Drawing.txt");

            // Hàm trim() tự viết cho Photoshop CS5
            function trimString(str) {
                if (typeof str !== "string") {
                    str = String(str);
                }
                return str.replace(/^\s+|\s+$/g, "");
            }

            // Đọc brand từ mode_info.txt để kiểm tra
            var shouldRunScript9 = false;
            if (dataFolder.exists && drawingFile.exists) {
                try {
                    var modeInfoFile = new File(dataFolder.fsName + "/mode_info.txt");
                    if (modeInfoFile.exists) {
                        modeInfoFile.open("r");
                        var content = modeInfoFile.read();
                        modeInfoFile.close();

                        if (typeof content !== "string") {
                            content = String(content);
                        }

                        // Parse brand từ dòng "brand=..."
                        var lines = content.split(/\r?\n/);
                        var brandName = "NONE";
                        for (var i = 0; i < lines.length; i++) {
                            var line = trimString(lines[i] || "");
                            if (line && line.indexOf("brand=") === 0) {
                                brandName = trimString(line.substring(6));
                                break;
                            }
                        }

                        // Chỉ chạy script nếu brand không phải "NONE"
                        if (brandName.toUpperCase() !== "NONE") {
                            shouldRunScript9 = true;
                        }
                    } else {
                        // Nếu không có file mode_info.txt, vẫn chạy script (fallback)
                        shouldRunScript9 = true;
                    }
                } catch (e) {
                    // Nếu có lỗi khi đọc, bỏ qua (không chạy script)
                }
            }

            // Chỉ chạy script nếu đã kiểm tra và được phép
            if (shouldRunScript9) {
                var autoReplaceScript = new File(scriptFolder.fsName + "/9. AutoReplaceDrawing.jsx");
                if (autoReplaceScript.exists) {
                    $.evalFile(autoReplaceScript);
                }
                // Nếu không tìm thấy script thì bỏ qua (không báo lỗi)
            }
            // Nếu brand là NONE hoặc không có file Drawing.txt thì bỏ qua (không báo lỗi)

            // ====================================
            // 📊 THÔNG BÁO HOÀN THÀNH
            // ====================================

            // Tính thời gian hoàn thành
            var endTime = new Date().getTime();
            var totalSeconds = ((endTime - startTime) / 1000).toFixed(2);

            // Hàm trim() tự viết cho Photoshop CS5
            function trimString(str) {
                if (typeof str !== "string") {
                    str = String(str);
                }
                return str.replace(/^\s+|\s+$/g, "");
            }

            // Đọc brand từ mode_info.txt
            var brandName = "NONE";
            try {
                if (dataFolder.exists) {
                    var modeInfoFile = new File(dataFolder.fsName + "/mode_info.txt");
                    if (modeInfoFile.exists) {
                        modeInfoFile.open("r");
                        var content = modeInfoFile.read();
                        modeInfoFile.close();

                        if (typeof content !== "string") {
                            content = String(content);
                        }

                        // Parse brand từ dòng "brand=..."
                        var lines = content.split(/\r?\n/);
                        for (var i = 0; i < lines.length; i++) {
                            var line = trimString(lines[i] || "");
                            if (line && line.indexOf("brand=") === 0) {
                                brandName = trimString(line.substring(6));
                                break;
                            }
                        }
                    }
                }
            } catch (e) {
                // Nếu không đọc được, giữ giá trị mặc định "NONE"
            }

            // Đọc Drawing từ Drawing.txt
            var drawingValue = "không có";
            try {
                if (dataFolder.exists && drawingFile.exists) {
                    drawingFile.open("r");
                    var drawingContent = drawingFile.read();
                    drawingFile.close();

                    if (typeof drawingContent !== "string") {
                        drawingContent = String(drawingContent);
                    }

                    // Loại bỏ ký tự xuống dòng
                    drawingContent = drawingContent.replace(/\r?\n$/, "");
                    drawingContent = drawingContent.replace(/\r$/, "");

                    if (drawingContent && drawingContent.length > 0) {
                        drawingValue = drawingContent;
                    }
                }
            } catch (e) {
                // Nếu không đọc được, giữ giá trị mặc định "không có"
            }

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
