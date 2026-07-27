#target photoshop;

/**
 * KS SCALE NECKLACE - PHASE 5.1: POSITION RULE
 * Photoshop CS5+ — Position rule layers
 * 
 * Workflow:
 * - ALLDIMENSIONS: canh trái (left edges) với Bounding Box Stroke và sát trên Bounding Box Stroke (cách 5px)
 * - CHAINRULES: canh top edges với ALLDIMENSIONS và sát trái Bounding Box Stroke (cách 5px)
 * - RULELINKS: canh top edges với CHAINRULES và sát trái CHAINRULES (cách 5px)
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

        // Tìm layer ALLDIMENSIONS
        var allDimensionsLayer = findLayerByName(doc, "ALLDIMENSIONS");
        if (!allDimensionsLayer) {
            throw new Error("Không tìm thấy layer 'ALLDIMENSIONS'.");
        }

        // Tìm layer Bounding Box Stroke
        var boundingBoxLayer = findLayerByName(doc, "Bounding Box Stroke");
        if (!boundingBoxLayer) {
            throw new Error("Không tìm thấy layer 'Bounding Box Stroke'.");
        }

        // Position ALLDIMENSIONS: canh trái (left edges) với Bounding Box Stroke và sát trên Bounding Box Stroke (cách 5px)
        positionAllDimensionsAboveBoundingBox(allDimensionsLayer, boundingBoxLayer, 5);

        // Tìm layer CHAINRULES
        var chainRulesLayer = findLayerByName(doc, "CHAINRULES");
        if (chainRulesLayer) {
            // Position CHAINRULES: canh top edges với ALLDIMENSIONS và sát trái Bounding Box Stroke (cách 5px)
            positionChainRulesLeftOfBoundingBox(chainRulesLayer, allDimensionsLayer, boundingBoxLayer, 5);

            // Tìm layer RULELINKS
            var ruleLinksLayer = findLayerByName(doc, "RULELINKS");
            if (ruleLinksLayer) {
                // Position RULELINKS: canh top edges với CHAINRULES và sát trái CHAINRULES (cách 5px)
                positionRuleLinksLeftOfChainRules(ruleLinksLayer, chainRulesLayer, 5);
            }
        }

    } catch (err) {
        alert("Lỗi Position Rule:\n\n" + err.message);
    } finally {
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;
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

    function positionAllDimensionsAboveBoundingBox(sourceLayer, targetLayer, gap) {
        // Lấy bounds của target layer (Bounding Box Stroke)
        var targetBounds = targetLayer.bounds;
        var targetLeft = parseFloat(targetBounds[0]);
        var targetTop = parseFloat(targetBounds[1]);

        // Lấy bounds của source layer (ALLDIMENSIONS)
        var sourceBounds = sourceLayer.bounds;
        var sourceLeft = parseFloat(sourceBounds[0]);
        var sourceTop = parseFloat(sourceBounds[1]);
        var sourceBottom = parseFloat(sourceBounds[3]);
        var sourceHeight = sourceBottom - sourceTop;

        // Tính vị trí mới:
        // - Canh trái (left edges): left edge của source = left edge của target
        // - Bottom edge của source = top edge của target - gap
        var newX = targetLeft;
        var newY = targetTop - sourceHeight - gap;

        // Tính moveX, moveY
        var moveX = newX - sourceLeft;
        var moveY = newY - sourceTop;

        // Di chuyển layer
        doc.activeLayer = sourceLayer;
        sourceLayer.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
    }

    function positionChainRulesLeftOfBoundingBox(sourceLayer, alignTopLayer, boundingBoxLayer, gap) {
        // Lấy bounds của alignTopLayer (ALLDIMENSIONS) để canh top edges
        var alignTopBounds = alignTopLayer.bounds;
        var alignTopTop = parseFloat(alignTopBounds[1]);

        // Lấy bounds của boundingBoxLayer (Bounding Box Stroke) để canh sát trái
        var boundingBoxBounds = boundingBoxLayer.bounds;
        var boundingBoxLeft = parseFloat(boundingBoxBounds[0]);

        // Lấy bounds của source layer (CHAINRULES)
        var sourceBounds = sourceLayer.bounds;
        var sourceLeft = parseFloat(sourceBounds[0]);
        var sourceTop = parseFloat(sourceBounds[1]);
        var sourceRight = parseFloat(sourceBounds[2]);
        var sourceWidth = sourceRight - sourceLeft;

        // Tính vị trí mới:
        // - Canh top edges: top edge của source = top edge của ALLDIMENSIONS
        // - Sát trái: right edge của source = left edge của Bounding Box Stroke - gap
        var newX = boundingBoxLeft - sourceWidth - gap;
        var newY = alignTopTop;

        // Tính moveX, moveY
        var moveX = newX - sourceLeft;
        var moveY = newY - sourceTop;

        // Di chuyển layer
        doc.activeLayer = sourceLayer;
        sourceLayer.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
    }

    function positionRuleLinksLeftOfChainRules(sourceLayer, targetLayer, gap) {
        // Lấy bounds của target layer (CHAINRULES)
        var targetBounds = targetLayer.bounds;
        var targetLeft = parseFloat(targetBounds[0]);
        var targetTop = parseFloat(targetBounds[1]);

        // Lấy bounds của source layer (RULELINKS)
        var sourceBounds = sourceLayer.bounds;
        var sourceLeft = parseFloat(sourceBounds[0]);
        var sourceTop = parseFloat(sourceBounds[1]);
        var sourceRight = parseFloat(sourceBounds[2]);
        var sourceWidth = sourceRight - sourceLeft;

        // Tính vị trí mới:
        // - Canh top edges: top edge của source = top edge của target
        // - Sát trái: right edge của source = left edge của target - gap
        var newX = targetLeft - sourceWidth - gap;
        var newY = targetTop;

        // Tính moveX, moveY
        var moveX = newX - sourceLeft;
        var moveY = newY - sourceTop;

        // Di chuyển layer
        doc.activeLayer = sourceLayer;
        sourceLayer.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
    }

})();

