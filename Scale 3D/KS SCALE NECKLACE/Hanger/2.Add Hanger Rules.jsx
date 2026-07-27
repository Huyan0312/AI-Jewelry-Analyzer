#target photoshop;

/**
 * Add Hanger Rules
 * Photoshop CS5+ — Place 2 layer theo hanger đọc từ Cache/state.txt dòng 4.
 *
 * Đọc Cache/state.txt dòng 4 (hanger=...) → ví dụ ANV070X350X200
 * Place 2 file từ DATA/Hanger/:
 *   1. ANV070X350X200RULES (file) → layer name: Ruleshanger
 *   2. ANV070X350X200       (file) → layer name: Hangerchain
 * Nếu hanger=NONE hoặc rỗng thì thoát không làm gì.
 */

(function () {
    var supportedExtensions = /\.(png|psd|tif|tiff|jpg|jpeg|bmp)$/i;
    var oldDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;
    try { app.playbackDisplayDialogs = DialogModes.NO; } catch (e) { }
    var prevRU = app.preferences.rulerUnits;

    try {
        if (!app.documents.length) throw new Error("Không có tài liệu đang mở.");
        var doc = app.activeDocument;
        app.preferences.rulerUnits = Units.PIXELS;

        var scriptFile = new File($.fileName);
        var scriptFolder = scriptFile.parent;   // Hanger/
        var rootFolder = scriptFolder.parent;   // KS SCALE NECKLACE
        var hangerName = readHangerFromState(rootFolder);
        if (!hangerName || hangerName.toUpperCase() === "NONE") {
            return;
        }

        var hangerFolder = new Folder(rootFolder.fsName + "/DATA/Hanger");
        if (!hangerFolder.exists) {
            throw new Error("Không tìm thấy folder DATA/Hanger tại: " + hangerFolder.fsName);
        }

        var toPlace = [
            { baseName: hangerName + "RULES", layerName: "Ruleshanger" },
            { baseName: hangerName, layerName: "Hangerchain" }
        ];

        for (var i = 0; i < toPlace.length; i++) {
            var info = toPlace[i];
            var file = findFileByBaseName(hangerFolder, info.baseName);
            if (!file) {
                throw new Error("Không tìm thấy file '" + info.baseName + "' trong DATA/Hanger (đuôi: png, psd, tif, jpg, bmp).");
            }
            var placedLayer = placeFile(file);
            if (!placedLayer) {
                throw new Error("Không thể place file '" + file.fsName + "'.");
            }
            placedLayer.name = info.layerName;
        }

    } catch (err) {
        alert("Lỗi Add Hanger Rules:\n\n" + err.message);
    } finally {
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;
        try { app.playbackDisplayDialogs = DialogModes.ALL; } catch (e) { }
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

    function readHangerFromState(rootFolder) {
        try {
            var f = getKSNecklaceStateFile(rootFolder);
            if (!f.exists) return "";
            f.open("r");
            var content = f.read();
            f.close();
            if (!content) return "";
            var lines = content.split(/\r?\n/);
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i].replace(/^\s+|\s+$/g, "");
                if (line.indexOf("hanger=") === 0) {
                    return line.substring(7).replace(/^\s+|\s+$/g, "");
                }
            }
        } catch (e) {}
        return "";
    }

    function findFileByBaseName(folder, baseName) {
        var list = folder.getFiles();
        if (!list) return null;
        var targetLower = baseName.toLowerCase();
        for (var i = 0; i < list.length; i++) {
            var f = list[i];
            if (!(f instanceof File)) continue;
            var name = f.name;
            var base = name.replace(/\.[^\.]+$/, "").toLowerCase();
            if (base === targetLower && supportedExtensions.test(name)) {
                return f;
            }
        }
        return null;
    }

    function placeFile(file) {
        try {
            var desc = new ActionDescriptor();
            desc.putPath(charIDToTypeID("null"), file);
            desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
            executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);
            return app.activeDocument.activeLayer;
        } catch (e) {
            return null;
        }
    }
})();
