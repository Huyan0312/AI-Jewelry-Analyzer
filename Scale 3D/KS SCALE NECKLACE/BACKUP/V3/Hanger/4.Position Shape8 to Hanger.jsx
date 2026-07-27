#target photoshop;

/**
 * 2. Position Shape8 to Hanger
 * Dời Shape 8 sát dưới Hangerchain, canh giữa (trục X), xích lên 10px.
 * Đọc Cache/state.txt dòng 4 (hanger=...). NONE thì thoát.
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

        var hangerchain = findLayerByName(doc, "Hangerchain");
        if (!hangerchain) {
            throw new Error("Không tìm thấy layer 'Hangerchain'.");
        }

        var shape8 = findLayerByName(doc, "Shape 8");
        if (!shape8) {
            throw new Error("Không tìm thấy layer 'Shape 8'.");
        }

        positionTopCenterToBottomCenter(shape8, hangerchain, -7); // xích lên 10px (âm = lên)
        shape8.remove(); // xoá Shape 8 sau khi position xong

    } catch (err) {
        alert("Lỗi Position Shape8 to Hanger:\n\n" + err.message);
    } finally {
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;
        try { app.playbackDisplayDialogs = DialogModes.ALL; } catch (e) { }
    }

    function readHangerFromState() {
        try {
            var scriptFile = new File($.fileName);
            var rootFolder = scriptFile.parent.parent;
            var statePath = rootFolder.fsName + "/Cache/state.txt";
            var f = new File(statePath);
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
        } catch (e) { }
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

    function positionTopCenterToBottomCenter(layerToMove, anchorLayer, gap) {
        var anchorBounds = anchorLayer.bounds;
        var anchorLeft = toPx(anchorBounds[0]);
        var anchorRight = toPx(anchorBounds[2]);
        var anchorBottom = toPx(anchorBounds[3]);
        var anchorCenterX = (anchorLeft + anchorRight) / 2;

        var moveBounds = layerToMove.bounds;
        var moveLeft = toPx(moveBounds[0]);
        var moveTop = toPx(moveBounds[1]);
        var moveRight = toPx(moveBounds[2]);
        var moveWidth = moveRight - moveLeft;

        var newTop = anchorBottom + (gap || 0);
        var newLeft = anchorCenterX - moveWidth / 2;
        var moveX = newLeft - moveLeft;
        var moveY = newTop - moveTop;

        doc.activeLayer = layerToMove;
        layerToMove.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
    }

    function toPx(val) {
        if (val == null) return 0;
        if (typeof val === "number") return val;
        try {
            return Number(UnitValue(val).as("px"));
        } catch (e) {
            return parseFloat(val) || 0;
        }
    }
})();
