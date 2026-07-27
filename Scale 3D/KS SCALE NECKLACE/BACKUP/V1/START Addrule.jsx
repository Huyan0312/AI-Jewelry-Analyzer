/**
 * START Addrule.jsx - Script Launcher
 * Photoshop CS5+ — Gọi các script theo thứ tự
 * 
 * Script này sẽ tự động tìm và chạy các file theo thứ tự:
 * 1. 5.RuleAdd.jsx
 * 2. 6.Position Rule.jsx
 * 3. 7.Chain To Motif.jsx
 * 4. 8.Chain to Motif Plase 2 (Position).jsx
 * 
 * Lưu ý: Nếu brand trong mode_info.txt là "NONE", script sẽ tự động dừng
 */

#target photoshop

    (function () {
        // ====================================
        // 🔍 HELPER: Đọc brand từ file
        // ====================================
        function trimString(str) {
            if (typeof str !== "string") {
                str = String(str);
            }
            return str.replace(/^\s+|\s+$/g, "");
        }

        function readBrandFromFile() {
            try {
                // Tìm folder DATA để đọc file mode_info.txt (cùng cấp với script)
                var scriptFile = new File($.fileName);
                var scriptFolder = scriptFile.parent;
                var dataFolder = new Folder(scriptFolder.fsName + "/DATA");

                if (!dataFolder.exists) {
                    throw new Error("Không tìm thấy folder DATA tại: " + dataFolder.fsName);
                }

                var modeInfoFile = new File(dataFolder.fsName + "/mode_info.txt");
                if (!modeInfoFile.exists) {
                    throw new Error("Không tìm thấy file mode_info.txt tại: " + modeInfoFile.fsName);
                }

                // Đọc nội dung file
                modeInfoFile.open("r");
                var content = modeInfoFile.read();
                modeInfoFile.close();

                // Đảm bảo content là string
                if (typeof content !== "string") {
                    content = String(content);
                }

                // Parse brand từ dòng "brand=..."
                var lines = content.split(/\r?\n/);
                for (var i = 0; i < lines.length; i++) {
                    var line = trimString(lines[i] || "");
                    if (line && line.indexOf("brand=") === 0) {
                        var brandName = trimString(line.substring(6));
                        return brandName.toUpperCase();
                    }
                }

                return null;
            } catch (e) {
                throw new Error("Lỗi khi đọc file mode_info.txt: " + e.message);
            }
        }

        // ====================================
        // 🚀 MAIN SCRIPT
        // ====================================
        try {
            // ==== KIỂM TRA BRAND TRƯỚC KHI CHẠY ====
            var selectedBrand;
            try {
                selectedBrand = readBrandFromFile();
            } catch (readError) {
                alert("❌ Lỗi đọc file mode_info.txt:\n\n" + readError.message + "\n\nHãy đảm bảo đã chạy script '1.Scale.jsx' trước.");
                return;
            }

            // Nếu brand là "NONE" thì tự động tắt script, không chạy
            if (!selectedBrand || selectedBrand === "NONE") {
                return; // Dừng script, không làm gì cả
            }

            // Lấy đường dẫn của script hiện tại
            var scriptFile = new File($.fileName);
            var scriptFolder = scriptFile.parent;

            // ==== BƯỚC 1: Gọi 5.RuleAdd.jsx ====
            var ruleAddScript = new File(scriptFolder.fsName + "/5.RuleAdd.jsx");
            if (!ruleAddScript.exists) {
                alert("❌ Không tìm thấy file '5.RuleAdd.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(ruleAddScript);

            // ==== BƯỚC 2: Gọi 6.Position Rule.jsx ====
            var positionRuleScript = new File(scriptFolder.fsName + "/6.Position Rule.jsx");
            if (!positionRuleScript.exists) {
                alert("❌ Không tìm thấy file '6.Position Rule.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(positionRuleScript);

            // ==== BƯỚC 3: Gọi 7.Chain To Motif.jsx ====
            var chainToMotifScript = new File(scriptFolder.fsName + "/7.Chain To Motif.jsx");
            if (!chainToMotifScript.exists) {
                alert("❌ Không tìm thấy file '7.Chain To Motif.jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(chainToMotifScript);

            // ==== BƯỚC 4: Gọi 8.Chain to Motif Plase 2 (Position).jsx ====
            var chainToMotifPhase2Script = new File(scriptFolder.fsName + "/8.Chain to Motif Plase 2 (Position).jsx");
            if (!chainToMotifPhase2Script.exists) {
                alert("❌ Không tìm thấy file '8.Chain to Motif Plase 2 (Position).jsx' trong thư mục:\n" + scriptFolder.fsName);
                return;
            }
            $.evalFile(chainToMotifPhase2Script);

        } catch (e) {
            alert("❌ LỖI khi chạy script:\n" + e.message);
        }
    })();

