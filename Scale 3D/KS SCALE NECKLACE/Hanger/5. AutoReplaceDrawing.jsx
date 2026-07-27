#target photoshop;

/**
 * 5. AutoReplaceDrawing (Hanger) — Gọi 8. AutoReplaceDrawing.jsx ở thư mục gốc
 * Đọc drawing từ Cache/state.txt và sửa layer Chainrules (cùng logic với 9.).
 */

(function () {
    try {
        var scriptFile = new File($.fileName);
        var rootFolder = scriptFile.parent.parent; // KS SCALE NECKLACE
        var mainScript = new File(rootFolder.fsName + "/8. AutoReplaceDrawing.jsx");
        if (!mainScript.exists) {
            alert("Không tìm thấy 8. AutoReplaceDrawing.jsx tại:\n" + mainScript.fsName);
            return;
        }
        $.evalFile(mainScript);
    } catch (err) {
        alert("Lỗi 5. AutoReplaceDrawing:\n\n" + err.message);
    }
})();
