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

    function readHangerFromState(rootFolder) {
        try {
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
