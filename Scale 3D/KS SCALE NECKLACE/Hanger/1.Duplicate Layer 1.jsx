#target photoshop;

/**
 * 4. Duplicate Layer 1
 * Photoshop CS5+ — Nhân bản layer "View 1", đặt tên "View 1 copy", rồi link với Shape 1.
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

        var layer1 = findLayerByName(doc, "View 1");
        if (!layer1) {
            throw new Error("Không tìm thấy layer 'View 1'.");
        }

        var dup = layer1.duplicate();
        dup.name = "View 1 copy";

        var shape8 = findLayerByName(doc, "Shape 1");
        if (!shape8) {
            throw new Error("Không tìm thấy layer 'Shape 1'.");
        }
        linkLayers(["View 1 copy", "Shape 1"]);

    } catch (err) {
        alert("Lỗi Duplicate View 1:\n\n" + err.message);
    } finally {
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;
        try { app.playbackDisplayDialogs = DialogModes.ALL; } catch (e) { }
    }

    function linkLayers(layerNames) {
        try {
            var doc = app.activeDocument;
            var layersToLink = [];
            for (var i = 0; i < layerNames.length; i++) {
                var layer = findLayerByName(doc, layerNames[i]);
                if (layer) layersToLink.push(layer);
            }
            if (layersToLink.length === 0) return false;

            var ref1 = new ActionReference();
            ref1.putName(charIDToTypeID("Lyr "), layersToLink[0].name);
            var desc1 = new ActionDescriptor();
            desc1.putReference(charIDToTypeID("null"), ref1);
            executeAction(charIDToTypeID("slct"), desc1, DialogModes.NO);

            for (var j = 1; j < layersToLink.length; j++) {
                var ref2 = new ActionReference();
                ref2.putName(charIDToTypeID("Lyr "), layersToLink[j].name);
                var desc2 = new ActionDescriptor();
                desc2.putReference(charIDToTypeID("null"), ref2);
                desc2.putEnumerated(stringIDToTypeID("selectionModifier"), stringIDToTypeID("selectionModifierType"), stringIDToTypeID("addToSelection"));
                executeAction(charIDToTypeID("slct"), desc2, DialogModes.NO);
            }

            var ref3 = new ActionReference();
            ref3.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            var desc3 = new ActionDescriptor();
            desc3.putReference(charIDToTypeID("null"), ref3);
            executeAction(stringIDToTypeID("linkSelectedLayers"), desc3, DialogModes.NO);
            return true;
        } catch (e) {
            return false;
        }
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
})();
