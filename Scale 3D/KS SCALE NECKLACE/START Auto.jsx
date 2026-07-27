/**
 * START Auto.jsx - Script Launcher Tự Động Hoàn Toàn (Auto Mode)
 * Photoshop CS5+
 *
 * Workflow:
 *  - Tự động chạy toàn bộ quy trình từ AI Detection (đã nhận dạng H và W, Drawing, Metal, Brand)
 *  - Tự động Scale, Positioning, Create Stroke, RuleAdd / Hanger mà KHÔNG CẦN BẤM DIALOG CHỌN TAY.
 *
 * Thiết kế mô-đun:
 *  - File này độc lập và ủy quyền trực tiếp cho START.jsx thông qua $.evalFile().
 *  - Mọi chỉnh sửa ở 1.Scale.jsx, 2.Positioning.jsx, START.jsx... về sau đều được áp dụng tự động.
 */

#target photoshop

(function () {
    // Kích hoạt cờ Global chạy tự động không hiện Dialog
    $.global.ksScaleAuto = true;
    $.global.ksScaleSilentAI = true;

    try {
        var scriptFile = new File($.fileName);
        var scriptFolder = scriptFile.parent;
        var mainStartScript = new File(scriptFolder.fsName + "/START.jsx");

        if (!mainStartScript.exists) {
            throw new Error("Không tìm thấy file 'START.jsx' tại:\n" + mainStartScript.fsName);
        }

        // Thực thi quy trình START.jsx gốc
        $.evalFile(mainStartScript);
    } catch (e) {
        alert("❌ LỖI trong quy trình Auto Start:\n" + e.message);
    } finally {
        // Tắt cờ tự động sau khi kết thúc hoặc gặp lỗi
        $.global.ksScaleAuto = false;
        $.global.ksScaleSilentAI = false;
    }
})();
