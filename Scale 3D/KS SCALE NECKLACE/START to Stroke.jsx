/**
 * START to Stroke.jsx - Script Launcher (roi tai Create Stroke)
 * Photoshop CS5+ — Goi script theo thu tu, dung o buoc 4
 *
 * Pipeline:
 *  1. Scale (dialog + AI View + scale)
 *  2. Positioning (View 1-7)
 *  3. Create Stroke
 *  (dung o buoc 3 — khong phan nhanh Addrule / Hanger)
 */

#target photoshop

(function () {
    // ====================================
    // CHONG GIAT CUA SO (FOCUS JUMPING FIX)
    // ====================================
    var originalBringToFront = app.bringToFront;
    app.bringToFront = function () {};

    // ====================================
    // IMPORT PROGRESS HELPER
    // ====================================
    var scriptFile = new File($.fileName);
    var rootFolder = scriptFile.parent.parent.parent; // autoscale V2
    var helperFile = new File(rootFolder.fsName + "/ProgressHelper.jsx");
    if (helperFile.exists) {
        $.evalFile(helperFile);
    }

    // ====================================
    // HISTORY STATE OPTIMIZATION
    // ====================================
    var savedHistoryStates = app.preferences.maximumHistoryStates;
    app.preferences.maximumHistoryStates = 0;

    var startTime = new Date().getTime();

    try {
        var scriptFolder = scriptFile.parent;

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
        // KHOI TAO TIEN TRINH
        // ====================================
        var steps = [
            "Scale dung kich thuoc",
            "Positioning",
            "Create Stroke"
        ];

        if (typeof ProgressHelper !== "undefined") {
            ProgressHelper.create("KS Necklace — toi Create Stroke", steps);
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

        // ==== Kiem tra cache (check) — huy Dialog Scale thi dung ====
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

        $.global.autoscale_scriptSuccess = true;
        $.sleep(500);
        if (typeof ProgressHelper !== "undefined") ProgressHelper.close();

    } catch (e) {
        if (typeof ProgressHelper !== "undefined") ProgressHelper.close();
        alert("LOI khi chay START to Stroke:\n" + e.message);
    } finally {
        try { app.preferences.maximumHistoryStates = savedHistoryStates; } catch (e) { }
        app.bringToFront = originalBringToFront;
    }
})();
