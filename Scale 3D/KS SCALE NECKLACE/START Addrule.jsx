/**
 * START Addrule.jsx - Script Launcher
 * Photoshop CS5+ — Gọi các script theo thứ tự
 * 
 * Script này sẽ tự động tìm và chạy các file theo thứ tự:
 * 1. 4.RuleAdd.jsx
 * 2. 5.Position Rule.jsx
 * 3. 6.Chain To Motif.jsx
 * 4. 7.Chain to Motif Phase 2 (Position).jsx
 * 
 * Lưu ý: Nếu brand trong Cache/state.txt là "NONE", script sẽ tự động dừng
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
        // 🔍 HELPERS
        // ====================================
        function trimString(str) {
            if (typeof str !== "string") str = String(str);
            return str.replace(/^\s+|\s+$/g, "");
        }

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

        function readBrandFromFile() {
            try {
                var scriptFolder = scriptFile.parent;
                var stateFile = getKSNecklaceStateFile(scriptFolder);
                if (!stateFile.exists) return null;
                stateFile.open("r");
                var content = stateFile.read();
                stateFile.close();
                if (typeof content !== "string") content = String(content);
                var lines = content.split(/\r?\n/);
                for (var i = 0; i < lines.length; i++) {
                    var line = trimString(lines[i] || "");
                    if (line && line.indexOf("brand=") === 0) {
                        return trimString(line.substring(6)).toUpperCase();
                    }
                }
                return null;
            } catch (e) { return null; }
        }

        // ====================================
        // 🚀 MAIN SCRIPT
        // ====================================
        try {
            var selectedBrand = readBrandFromFile();
            if (!selectedBrand || selectedBrand === "NONE") return;

            var scriptFolder = scriptFile.parent;

            // Tiến trình con cho Addrule
            var steps = ["Thêm Rules", "Căn chỉnh Rules", "Gắn Chain", "Hoàn thiện Chain"];
            if (typeof ProgressHelper !== "undefined") {
                ProgressHelper.create("Tiến trình Gắn Chain KS", steps);
            }

            // ==== 4.RuleAdd.jsx ====
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(0);
            var ruleAddScript = new File(scriptFolder.fsName + "/4.RuleAdd.jsx");
            if (ruleAddScript.exists) $.evalFile(ruleAddScript);
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(0);

            // ==== 5.Position Rule.jsx ====
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(1);
            var positionRuleScript = new File(scriptFolder.fsName + "/5.Position Rule.jsx");
            if (positionRuleScript.exists) $.evalFile(positionRuleScript);
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(1);

            // ==== 6.Chain To Motif.jsx ====
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(2);
            var chainToMotifScript = new File(scriptFolder.fsName + "/6.Chain To Motif.jsx");
            if (chainToMotifScript.exists) $.evalFile(chainToMotifScript);
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(2);

            // ==== 7.Chain to Motif Phase 2 (Position).jsx ====
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setActive(3);
            var chainToMotifPhase2Script = new File(scriptFolder.fsName + "/7.Chain to Motif Phase 2 (Position).jsx");
            if (chainToMotifPhase2Script.exists) $.evalFile(chainToMotifPhase2Script);
            if (typeof ProgressHelper !== "undefined") ProgressHelper.setDone(3);

            $.sleep(500);
            if (typeof ProgressHelper !== "undefined") ProgressHelper.close();

        } catch (e) {
            if (typeof ProgressHelper !== "undefined") ProgressHelper.close();
            alert("❌ LỖI Gắn Chain:\n" + e.message);
        } finally {
            app.bringToFront = originalBringToFront;
        }
    })();

