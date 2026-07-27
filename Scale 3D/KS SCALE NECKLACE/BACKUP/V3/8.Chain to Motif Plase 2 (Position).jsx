#target photoshop;

/**
 * KS SCALE NECKLACE - PHASE 5.4: CHAIN TO MOTIF PHASE 2 (POSITION)
 * Photoshop CS5+ — Link Layer 1 copy và CHAIN copy, position CHAIN copy
 * 
 * Workflow:
 * - Tìm Layer 1 copy và CHAIN copy
 * - Link 2 layers lại với nhau
 * - Position CHAIN copy: canh giữa X và sát dưới CHAINRULES
 * - Unlink 2 layers sau khi di chuyển xong
 */

(function () {
    var oldDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;
    try { app.playbackDisplayDialogs = DialogModes.NO; } catch (e) { }

    var prevRU = app.preferences.rulerUnits;

    try {
        if (!app.documents.length) throw new Error("Không có tài liệu đang mở.");
        var doc = app.activeDocument;

        // Đổi ruler units mà không mở dialog
        try {
            // Đảm bảo dialogs đã tắt trước khi đổi preferences
            app.displayDialogs = DialogModes.NO;
            app.preferences.rulerUnits = Units.PIXELS;
        } catch (e) {
            // Nếu không đổi được, bỏ qua (không ảnh hưởng workflow)
        }

        // Tìm layer Layer 1 copy
        var layer1Copy = findLayerByName(doc, "Layer 1 copy");
        if (!layer1Copy) {
            throw new Error("Không tìm thấy layer 'Layer 1 copy'.");
        }

        // Tìm layer CHAIN copy
        var chainCopy = findLayerByName(doc, "CHAIN copy");
        if (!chainCopy) {
            throw new Error("Không tìm thấy layer 'CHAIN copy'.");
        }

        // Link Layer 1 copy với CHAIN copy
        linkLayers([layer1Copy.name, chainCopy.name]);

        // Tìm layer CHAINRULES và position CHAIN copy
        var chainRulesLayer = findLayerByName(doc, "CHAINRULES");
        if (chainRulesLayer) {
            // Position CHAIN copy: canh giữa X và sát dưới CHAINRULES
            // Vì đã link, Layer 1 copy sẽ di chuyển theo
            positionChainCopyBelowChainRules(chainCopy, chainRulesLayer);
        }

        // Sau khi di chuyển xong, unlink 2 layers
        unlinkLayers([layer1Copy.name, chainCopy.name]);

    } catch (err) {
        app.displayDialogs = DialogModes.ALL;
        alert("Lỗi Chain to Motif Phase 2:\n\n" + err.message);
    } finally {
        // Restore ruler units mà không mở dialog
        try {
            // Đảm bảo dialogs đã tắt trước khi restore preferences
            app.displayDialogs = DialogModes.NO;
            app.preferences.rulerUnits = prevRU;
        } catch (e) {
            // Nếu không restore được, bỏ qua
        }
        app.displayDialogs = oldDialogs;
        try { app.playbackDisplayDialogs = DialogModes.ALL; } catch (e) { }
    }

    function findLayerByName(root, nameLower) {
        var target = null;
        for (var i = 0; i < root.layers.length; i++) {
            var layer = root.layers[i];
            var lname = layer.name.toLowerCase();
            if (lname === nameLower.toLowerCase()) return layer;
            if (!target && lname.indexOf(nameLower.toLowerCase()) >= 0) target = layer;
            if (layer.typename === "LayerSet") {
                var child = findLayerByName(layer, nameLower);
                if (child) {
                    if (child.name.toLowerCase() === nameLower.toLowerCase()) return child;
                    if (!target) target = child;
                }
            }
        }
        return target;
    }

    function linkLayers(layerNames) {
        try {
            var doc = app.activeDocument;
            var layersToLink = [];

            // Tìm các layer theo tên
            for (var i = 0; i < layerNames.length; i++) {
                var layer = findLayerByName(doc, layerNames[i]);
                if (layer) {
                    layersToLink.push(layer);
                }
            }

            if (layersToLink.length === 0) {
                return false;
            }

            // Select tất cả các layer cần link
            var desc1 = new ActionDescriptor();
            var ref1 = new ActionReference();

            // Select layer đầu tiên
            ref1.putName(charIDToTypeID("Lyr "), layersToLink[0].name);
            desc1.putReference(charIDToTypeID("null"), ref1);
            executeAction(charIDToTypeID("slct"), desc1, DialogModes.NO);

            // Add các layer còn lại vào selection
            for (var j = 1; j < layersToLink.length; j++) {
                var desc2 = new ActionDescriptor();
                var ref2 = new ActionReference();
                ref2.putName(charIDToTypeID("Lyr "), layersToLink[j].name);
                desc2.putReference(charIDToTypeID("null"), ref2);
                desc2.putEnumerated(stringIDToTypeID("selectionModifier"), stringIDToTypeID("selectionModifierType"), stringIDToTypeID("addToSelection"));
                executeAction(charIDToTypeID("slct"), desc2, DialogModes.NO);
            }

            // Link selected layers
            var desc3 = new ActionDescriptor();
            var ref3 = new ActionReference();
            ref3.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            desc3.putReference(charIDToTypeID("null"), ref3);
            executeAction(stringIDToTypeID("linkSelectedLayers"), desc3, DialogModes.NO);

            return true;
        } catch (e) {
            return false;
        }
    }

    function positionChainCopyBelowChainRules(sourceLayer, targetLayer) {
        // Lấy bounds của target layer (CHAINRULES)
        var targetBounds = targetLayer.bounds;
        var targetLeft = parseFloat(targetBounds[0]);
        var targetRight = parseFloat(targetBounds[2]);
        var targetBottom = parseFloat(targetBounds[3]);
        var targetCenterX = (targetLeft + targetRight) / 2;

        // Lấy bounds của source layer (CHAIN copy)
        var sourceBounds = sourceLayer.bounds;
        var sourceLeft = parseFloat(sourceBounds[0]);
        var sourceTop = parseFloat(sourceBounds[1]);
        var sourceRight = parseFloat(sourceBounds[2]);
        var sourceWidth = sourceRight - sourceLeft;

        // Tính vị trí mới:
        // - Canh giữa X: centerX của target - width/2 của source
        // - Sát dưới: top edge của source = bottom edge của target
        var newX = targetCenterX - sourceWidth / 2;
        var newY = targetBottom;

        // Tính moveX, moveY
        var moveX = newX - sourceLeft;
        var moveY = newY - sourceTop;

        // Di chuyển layer (sẽ di chuyển cả linked layers cùng nhau)
        doc.activeLayer = sourceLayer;
        sourceLayer.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
    }

    function unlinkLayers(layerNames) {
        try {
            var doc = app.activeDocument;
            var layersToUnlink = [];

            // Tìm các layer theo tên
            for (var i = 0; i < layerNames.length; i++) {
                var layer = findLayerByName(doc, layerNames[i]);
                if (layer) {
                    layersToUnlink.push(layer);
                }
            }

            if (layersToUnlink.length === 0) {
                return false;
            }

            // Unlink từng layer
            for (var j = 0; j < layersToUnlink.length; j++) {
                try {
                    // Select layer
                    var desc = new ActionDescriptor();
                    var ref = new ActionReference();
                    ref.putName(charIDToTypeID("Lyr "), layersToUnlink[j].name);
                    desc.putReference(charIDToTypeID("null"), ref);
                    executeAction(charIDToTypeID("slct"), desc, DialogModes.NO);

                    // Unlink selected layer
                    var desc2 = new ActionDescriptor();
                    var ref2 = new ActionReference();
                    ref2.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
                    desc2.putReference(charIDToTypeID("null"), ref2);
                    executeAction(stringIDToTypeID("unlinkSelectedLayers"), desc2, DialogModes.NO);
                } catch (e) {
                    // Nếu unlink thất bại, bỏ qua (có thể layer không được link)
                }
            }

            return true;
        } catch (e) {
            return false;
        }
    }

})();

