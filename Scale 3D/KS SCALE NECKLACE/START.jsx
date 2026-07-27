/**
 * START.jsx - Script Launcher
 * Photoshop CS5+ — Goi script theo thu tu
 *
 * Pipeline:
 *  1. Scale
 *  2. Positioning
 *  3. Create Stroke
 *  4. Phan nhanh: Addrule (4-8) / Hanger
 */

#target photoshop

    (function () {
    // ====================================
    // 🚀 CHỐNG GIẬT CỬA SỔ (FOCUS JUMPING FIX)
    // ====================================
    var originalBringToFront = app.bringToFront;
    app.bringToFront = function () {};

    // ====================================
    // 🚀 IMPORT PROGRESS HELPER
    // ====================================
    var scriptFile = new File($.fileName);
    var rootFolder = scriptFile.parent.parent.parent; // autoscale V2
    var helperFile = new File(rootFolder.fsName + "/ProgressHelper.jsx");
    if (helperFile.exists) {
        $.evalFile(helperFile);
    }

    // ====================================
    // 🚀 HISTORY STATE OPTIMIZATION
    // ====================================
    var savedHistoryStates = app.preferences.maximumHistoryStates;
    app.preferences.maximumHistoryStates = 0; // Tắt history hoàn toàn

    // Bắt đầu tính thời gian
    var startTime = new Date().getTime();

    try {
        // Lấy đường dẫn của script hiện tại
        var scriptFolder = scriptFile.parent;

        // ... (helpers remain same) ...
        function getCacheUserKey() {
            if (typeof $.autoscaleCacheKey !== "undefined" && $.autoscaleCacheKey) return $.autoscaleCacheKey;
            var key = "default";
            try {
                var path = Folder.userData.fsName;
                var parts = path.split(/[\\\/]/);
                for (var i = 0; i < parts.length; i++) {
                    if (parts[i].toLowerCase() === "users" && parts[i + 1]) {
                        key = parts[i + 1].replace(/[^a-zA-Z0-9_-]/g, "_");
                        if (!key) key = "default";
                        break;
                    }
                }
            } catch (e) {}
            $.autoscaleCacheKey = key;
            return key;
        }

        function getKSNecklaceCacheRoot(sf) {
            var cacheFolder = new Folder(sf.fsName + "/Cache");
            if (!cacheFolder.exists) cacheFolder.create();
            return cacheFolder;
        }

        function copyKSNecklaceStateFile(srcFile, destFile) {
            try {
                if (!srcFile.exists) return;
                if (!srcFile.open("r")) return;
                var text = srcFile.read();
                srcFile.close();
                destFile.open("w");
                destFile.write(text);
                destFile.close();
            } catch (e) {}
        }

        function migrateLegacyKSNecklaceStateIfNeeded(cacheRoot, userFolder) {
            try {
                var userState = new File(userFolder.fsName + "/state.txt");
                if (userState.exists) return;
                var rootState = new File(cacheRoot.fsName + "/state.txt");
                if (!rootState.exists) return;
                copyKSNecklaceStateFile(rootState, userState);
            } catch (e) {}
        }

        function getKSNecklaceUserCacheFolder(sf) {
            var cacheRoot = getKSNecklaceCacheRoot(sf);
            var key = getCacheUserKey();
            var userFolder = new Folder(cacheRoot.fsName + "/User_" + key);
            if (!userFolder.exists) userFolder.create();
            migrateLegacyKSNecklaceStateIfNeeded(cacheRoot, userFolder);
            return userFolder;
        }

        function getKSNecklaceStateFile(sf) {
            return new File(getKSNecklaceUserCacheFolder(sf).fsName + "/state.txt");
        }

        // ====================================
        // 🚀 KHỞI TẠO TIẾN TRÌNH
        // ====================================
        var steps = [
            "Scale dung kich thuoc",
            "Positioning",
            "Create Stroke",
            "Phan nhanh quy trinh"
        ];
        
        if (typeof ProgressHelper !== "undefined") {
            ProgressHelper.create("Tien trinh KS Necklace Scale", steps);
        }

        // ====================================
        // QUEUE AI NGAY KHI BAM NUT (truoc Scale)
        // ====================================
        var projectRoot = scriptFolder.parent.parent;
        var AI_AUTODETECT_TEST = projectRoot.fsName + "\\AI_AutoDetect test.jsx";
        try {
            if (app.documents.length > 0) {
                var aiEarly = new File(AI_AUTODETECT_TEST);
                if (aiEarly.exists) {
                    $.global.ksScaleSilentAI = true;
                    $.global.ksAIPhase = "queue";
                    $.global.ksAIQueued = false;
                    try {
                        $.evalFile(aiEarly);
                    } finally {
                        $.global.ksAIPhase = "";
                    }
                }
            }
        } catch (aiEarlyErr) {
            $.global.ksAIQueued = false;
        }

        // ==== BUOC 1: Goi 1.Scale.jsx ====
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(0);
        var scaleScript = new File(scriptFolder.fsName + "/1.Scale.jsx");
        if (!scaleScript.exists) throw new Error("Khong tim thay file '1.Scale.jsx'");
        $.evalFile(scaleScript);
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(0);

        // ==== Kiem tra cache (check) ====
        var cacheFile = getKSNecklaceStateFile(scriptFolder);
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
            if (typeof ProgressHelper !== "undefined") ProgressHelper.close();
            return;
        }

        // ==== 2.Positioning.jsx ====
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(1);
        var positioningScript = new File(scriptFolder.fsName + "/2.Positioning.jsx");
        if (!positioningScript.exists) throw new Error("Khong tim thay file '2.Positioning.jsx'");
        $.evalFile(positioningScript);
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(1);

        // ==== 3.Create Stroke.jsx ====
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(2);
        var strokeScript = new File(scriptFolder.fsName + "/3.Create Stroke.jsx");
        if (!strokeScript.exists) throw new Error("Khong tim thay file '3.Create Stroke.jsx'");
        $.evalFile(strokeScript);
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(2);

        // ==== Doc hanger tu state de phan nhanh ====
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(3);
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
            // Hanger NONE
            var startAddruleScript = new File(scriptFolder.fsName + "/START Addrule.jsx");
            if (startAddruleScript.exists) $.evalFile(startAddruleScript);

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
                var autoReplaceScript = new File(scriptFolder.fsName + "/8. AutoReplaceDrawing.jsx");
                if (autoReplaceScript.exists) $.evalFile(autoReplaceScript);
            }
        } else {
            // Có chọn hanger
            var ruleAddScript = new File(scriptFolder.fsName + "/4.RuleAdd.jsx");
            if (ruleAddScript.exists) $.evalFile(ruleAddScript);

            var positionRuleScript = new File(scriptFolder.fsName + "/5.Position Rule.jsx");
            if (positionRuleScript.exists) $.evalFile(positionRuleScript);

            var startHangerScript = new File(scriptFolder.fsName + "/Hanger/START Hanger.jsx");
            if (startHangerScript.exists) $.evalFile(startHangerScript);
        }
        if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(3);

        $.global.autoscale_scriptSuccess = true;
        $.sleep(500);
        if (typeof ProgressHelper !== "undefined") ProgressHelper.close();

    } catch (e) {
        if (typeof ProgressHelper !== "undefined") ProgressHelper.close();
        alert("❌ LỖI khi chạy script:\n" + e.message);
    } finally {
        if (typeof $.global.ksStatusWin !== "undefined" && $.global.ksStatusWin) {
            try { $.global.ksStatusWin.close(); } catch (eCloseWin) {}
            $.global.ksStatusWin = null;
        }
        try { app.preferences.maximumHistoryStates = savedHistoryStates; } catch (e) { }
        app.bringToFront = originalBringToFront;
    }
})();
