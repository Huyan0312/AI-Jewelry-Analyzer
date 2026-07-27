#target photoshop;

/**
 * START Hanger — Chạy thứ tự script 1 → 5
 * 1. Duplicate Layer 1
 * 2. Add Hanger Rules
 * 3. Position RULES
 * 4. Position Shape8 to Hanger
 * 5. AutoReplaceDrawing
 */

(function () {
    try {
        var scriptFile = new File($.fileName);
        var scriptFolder = scriptFile.parent;

        var steps = [
            "1.Duplicate Layer 1.jsx",
            "2.Add Hanger Rules.jsx",
            "3.Position RULES.jsx",
            "4.Position Shape8 to Hanger.jsx",
            "5. AutoReplaceDrawing.jsx"
        ];

        for (var i = 0; i < steps.length; i++) {
            var f = new File(scriptFolder.fsName + "/" + steps[i]);
            if (!f.exists) {
                alert("Không tìm thấy: " + steps[i]);
                return;
            }
            $.evalFile(f);
        }

    } catch (err) {
        alert("Lỗi START Hanger:\n\n" + err.message);
    }
})();
