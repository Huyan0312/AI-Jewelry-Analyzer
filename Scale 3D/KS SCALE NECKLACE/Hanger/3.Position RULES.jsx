#target photoshop;

/**
 * Position RULES — Canh Hangerchain và Ruleshanger (bỏ Shape 1)
 * Photoshop CS5+ — Chỉ dời 2 layer hanger theo neo:
 *
 * - Hangerchain: sát dưới CHAINRULES, canh giữa (top-center Hangerchain = bottom-center CHAINRULES + gap)
 * - Ruleshanger: canh giữa, sát dưới Bounding Box Stroke (top-center Ruleshanger = bottom-center Bounding Box Stroke + gap)
 *
 * Đọc Cache/state.txt dòng 4 (hanger=...) — nếu NONE thì thoát.
 */

(function () {
    var oldDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;
    try { app.playbackDisplayDialogs = DialogModes.NO; } catch (e) { }

    var prevRU = app.preferences.rulerUnits;

    try {
        if (!app.documents.length) throw new Error("Không có tài liệu đang mở.");
        var doc = app.activeDocument;
        app.preferences.rulerUnits = Units.PIXELS;

        var hangerName = readHangerFromState();
        if (!hangerName || hangerName.toUpperCase() === "NONE") {
            return;
        }

        var chainRules = findLayerByName(doc, "CHAINRULES");
        if (!chainRules) {
            throw new Error("Không tìm thấy layer 'CHAINRULES'.");
        }
        var hangerchain = findLayerByName(doc, "Hangerchain");
        if (!hangerchain) {
            throw new Error("Không tìm thấy layer 'Hangerchain' (add bởi Add Hanger Rules.jsx).");
        }
        positionTopCenterToBottomCenter(hangerchain, chainRules, 5); // Hangerchain sát dưới CHAINRULES, canh giữa

        var boundingBox = findLayerByName(doc, "Bounding Box Stroke");
        if (!boundingBox) {
            throw new Error("Không tìm thấy layer 'Bounding Box Stroke'.");
        }
        var ruleshanger = findLayerByName(doc, "Ruleshanger");
        if (!ruleshanger) {
            throw new Error("Không tìm thấy layer 'Ruleshanger' (add bởi Add Hanger Rules.jsx).");
        }
        positionTopCenterToBottomCenter(ruleshanger, boundingBox, 5); // Ruleshanger sát dưới Bounding Box Stroke, canh giữa

    } catch (err) {
        alert("Lỗi Position RULES:\n\n" + err.message);
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

    /** Đọc hanger=... từ Cache/User_{key}/state.txt */
    function readHangerFromState() {
        try {
            var scriptFile = new File($.fileName);
            var scriptFolder = scriptFile.parent;           // Hanger/
            var rootFolder = scriptFolder.parent;           // KS SCALE NECKLACE
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

    function findLayerByName(root, nameToFind) {
        var target = null;
        var nameLower = nameToFind.toLowerCase();
        for (var i = 0; i < root.layers.length; i++) {
            var layer = root.layers[i];
            var lname = layer.name.toLowerCase();
            if (lname === nameLower) return layer;
            if (!target && lname.indexOf(nameLower) >= 0) target = layer;
            if (layer.typename === "LayerSet") {
                var child = findLayerByName(layer, nameToFind);
                if (child) {
                    if (child.name.toLowerCase() === nameLower) return child;
                    if (!target) target = child;
                }
            }
        }
        return target;
    }

    /**
     * Dời layerToMove sao cho top-center của nó trùng với bottom-center của anchorLayer + gap (canh giữa, sát dưới).
     * gap: khoảng cách px (dương = layer nằm dưới anchor).
     */
    function positionTopCenterToBottomCenter(layerToMove, anchorLayer, gap) {
        var anchorBounds = anchorLayer.bounds;
        var anchorLeft = parseFloat(anchorBounds[0]);
        var anchorTop = parseFloat(anchorBounds[1]);
        var anchorRight = parseFloat(anchorBounds[2]);
        var anchorBottom = parseFloat(anchorBounds[3]);
        var anchorCenterX = (anchorLeft + anchorRight) / 2;
        var anchorBottomY = anchorBottom;

        var moveBounds = layerToMove.bounds;
        var moveLeft = parseFloat(moveBounds[0]);
        var moveTop = parseFloat(moveBounds[1]);
        var moveRight = parseFloat(moveBounds[2]);
        var moveBottom = parseFloat(moveBounds[3]);
        var moveWidth = moveRight - moveLeft;
        var moveHeight = moveBottom - moveTop;

        // Vị trí mới: top-center(layerToMove) = (anchorCenterX, anchorBottomY + gap)
        var newTop = anchorBottomY + (gap || 0);
        var newLeft = anchorCenterX - moveWidth / 2;

        var moveX = newLeft - moveLeft;
        var moveY = newTop - moveTop;

        doc.activeLayer = layerToMove;
        layerToMove.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
    }
})();
