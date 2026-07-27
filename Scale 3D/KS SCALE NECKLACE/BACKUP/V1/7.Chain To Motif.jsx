#target photoshop;

/**
 * KS SCALE NECKLACE - PHASE 5.2: CHAIN TO MOTIF
 * Photoshop CS5+ — Copy Layer 1, add chain và position cùng với Shape 8, Shape 9
 * 
 * Workflow:
 * - Copy Layer 1 tại chỗ
 * - Tìm Shape 8 và Shape 9 (đi chung với Layer 1)
 * - Link Layer 1 copy với Shape 8 và Shape 9
 * - Position: sát trái Bounding Box Stroke (cách 50px) - di chuyển cả 3 layers cùng nhau
 * - Add chain từ DATA/{brand}/ và canh trục với Shape 8 và Shape 9
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

        // Tìm layer Layer 1
        var layer1 = findLayerByName(doc, "Layer 1");
        if (!layer1) {
            throw new Error("Không tìm thấy layer 'Layer 1'.");
        }

        // Tìm layer Bounding Box Stroke
        var boundingBoxLayer = findLayerByName(doc, "Bounding Box Stroke");
        if (!boundingBoxLayer) {
            throw new Error("Không tìm thấy layer 'Bounding Box Stroke'.");
        }

        // Tìm Shape 8 và Shape 9
        var shape8 = findLayerByName(doc, "shape 8");
        var shape9 = findLayerByName(doc, "shape 9");

        if (!shape8) {
            throw new Error("Không tìm thấy layer 'Shape 8'.");
        }
        if (!shape9) {
            throw new Error("Không tìm thấy layer 'Shape 9'.");
        }

        // Copy Layer 1 tại chỗ
        var layer1Copy = duplicateLayer(layer1, "Layer 1 copy");
        if (!layer1Copy) {
            throw new Error("Không thể copy Layer 1.");
        }

        // Link Layer 1 copy với Shape 8 và Shape 9
        linkLayers([layer1Copy.name, shape8.name, shape9.name]);

        // Position Layer 1 copy: sát trái Bounding Box Stroke (cách 50px)
        // Di chuyển Layer 1 copy sẽ di chuyển cả 3 layers cùng nhau (vì đã link)
        positionLayer1CopyLeftOfBoundingBox(layer1Copy, boundingBoxLayer, 50);

        // Add chain và canh trục với Shape 8 và Shape 9
        addChainAndPosition(shape8, shape9);

        // Xóa Shape 8 và Shape 9 sau khi đã position chain xong
        try { shape8.remove(); } catch (e) { }
        try { shape9.remove(); } catch (e) { }

    } catch (err) {
        alert("Lỗi Chain To Motif:\n\n" + err.message);
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

    function duplicateLayer(layer, newName) {
        try {
            // Select layer by name
            var desc1 = new ActionDescriptor();
            var ref1 = new ActionReference();
            ref1.putName(charIDToTypeID("Lyr "), layer.name);
            desc1.putReference(charIDToTypeID("null"), ref1);
            desc1.putBoolean(charIDToTypeID("MkVs"), false);
            executeAction(charIDToTypeID("slct"), desc1, DialogModes.NO);

            // Duplicate layer
            var desc2 = new ActionDescriptor();
            var ref2 = new ActionReference();
            ref2.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            desc2.putReference(charIDToTypeID("null"), ref2);
            executeAction(charIDToTypeID("Dplc"), desc2, DialogModes.NO);

            // Rename duplicated layer
            var duplicatedLayer = app.activeDocument.activeLayer;
            duplicatedLayer.name = newName;

            return duplicatedLayer;
        } catch (e) {
            return null;
        }
    }

    function positionLayer1CopyLeftOfBoundingBox(sourceLayer, targetLayer, gap) {
        // Lấy bounds của target layer (Bounding Box Stroke)
        var targetBounds = targetLayer.bounds;
        var targetLeft = parseFloat(targetBounds[0]);

        // Lấy bounds của source layer (Layer 1 copy)
        var sourceBounds = sourceLayer.bounds;
        var sourceLeft = parseFloat(sourceBounds[0]);
        var sourceRight = parseFloat(sourceBounds[2]);
        var sourceTop = parseFloat(sourceBounds[1]);
        var sourceWidth = sourceRight - sourceLeft;

        // Tính vị trí mới:
        // - Sát trái: right edge của source = left edge của target - gap
        var newX = targetLeft - sourceWidth - gap;
        var newY = sourceTop; // Giữ nguyên Y

        // Tính moveX, moveY
        var moveX = newX - sourceLeft;
        var moveY = 0; // Không di chuyển Y

        // Di chuyển layer (sẽ di chuyển cả linked layers cùng nhau)
        doc.activeLayer = sourceLayer;
        sourceLayer.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
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

    function getParentFolder() {
        try {
            return new File($.fileName).parent.parent;
        } catch (e) {
            return null;
        }
    }

    function getDataFolder() {
        try {
            // DATA nằm cùng cấp với script (trong thư mục "1-4 Phases")
            var scriptFile = new File($.fileName);
            var scriptFolder = scriptFile.parent;
            var dataFolder = new Folder(scriptFolder.fsName + "/DATA");
            if (!dataFolder.exists) return null;

            return dataFolder;
        } catch (e) {
            return null;
        }
    }

    // Hàm trim() tự viết cho Photoshop CS5 (không hỗ trợ String.trim())
    function trimString(str) {
        if (typeof str !== "string") {
            str = String(str);
        }
        // Loại bỏ whitespace ở đầu và cuối bằng regex
        return str.replace(/^\s+|\s+$/g, "");
    }

    function readBrandFromFile() {
        try {
            // Tìm folder DATA để đọc file mode_info.txt (cùng cấp với script)
            var scriptFile = new File($.fileName);
            var scriptFolder = scriptFile.parent;
            // DATA nằm cùng cấp với script (trong thư mục "1-4 Phases")
            var dataFolder = new Folder(scriptFolder.fsName + "/DATA");
            if (!dataFolder.exists) {
                throw new Error("Không tìm thấy folder DATA tại: " + dataFolder.fsName);
            }

            var modeInfoFile = new File(dataFolder.fsName + "/mode_info.txt");
            if (!modeInfoFile.exists) {
                throw new Error("Không tìm thấy file mode_info.txt tại: " + modeInfoFile.fsName);
            }

            // Đọc nội dung file
            modeInfoFile.open("r");
            var content = modeInfoFile.read();
            modeInfoFile.close();

            // Đảm bảo content là string
            if (typeof content !== "string") {
                content = String(content);
            }

            // Parse brand từ dòng "brand=..."
            // Xử lý cả \r\n và \n
            var lines = content.split(/\r?\n/);
            for (var i = 0; i < lines.length; i++) {
                // Dùng hàm trimString() thay vì .trim()
                var line = trimString(lines[i] || "");
                if (line && line.indexOf("brand=") === 0) {
                    var brandName = trimString(line.substring(6));
                    // Nếu là "NONE" thì trả về "NONE"
                    if (brandName.toUpperCase() === "NONE") {
                        return "NONE";
                    }
                    // Loại bỏ khoảng trắng và chuyển về lowercase để normalize
                    var normalizedBrand = brandName.replace(/\s+/g, "").toLowerCase();
                    // Mapping ngược lại từ folder name về brand code
                    var brandMapping = {
                        "14k": "14k",
                        "silver": "silver",
                        "labgrown": "labgrown"
                    };
                    // Nếu có trong mapping thì dùng, không thì dùng normalized brand
                    return brandMapping[normalizedBrand] || normalizedBrand;
                }
            }

            return null;
        } catch (e) {
            // Ném lỗi để hàm gọi có thể xử lý
            throw new Error("Lỗi khi đọc file mode_info.txt: " + e.message);
        }
    }

    function getBrandFolder(dataFolder, brand) {
        try {
            // Normalize brand name: loại bỏ khoảng trắng và chuyển về lowercase
            var normalizedBrand = brand.replace(/\s+/g, "").toLowerCase();

            // Mapping brand name to folder name
            var brandMapping = {
                "14k": "14K",
                "silver": "Silver",
                "labgrown": "Labgrown"
            };

            var folderName = brandMapping[normalizedBrand] || brand;

            var brandFolder = new Folder(dataFolder.fsName + "/" + folderName);
            if (brandFolder.exists) {
                return brandFolder;
            }

            // Nếu không tìm thấy với tên chính xác, tìm folder có chứa brand name
            var folders = dataFolder.getFiles(function (f) {
                return f instanceof Folder;
            });

            for (var i = 0; i < folders.length; i++) {
                var folderNameLower = folders[i].name.replace(/\s+/g, "").toLowerCase();
                var brandLower = normalizedBrand;
                if (folderNameLower.indexOf(brandLower) >= 0 || brandLower.indexOf(folderNameLower) >= 0) {
                    return folders[i];
                }
            }

            return null;
        } catch (e) {
            return null;
        }
    }

    function findChainFile(dataFolder, brandFolder) {
        try {
            var supportedExtensions = /\.(png|psd|tif|tiff|jpg|jpeg|bmp)$/i;

            // Tìm file chain trong brand folder được chỉ định
            if (!brandFolder || !brandFolder.exists) {
                return null;
            }

            var files = brandFolder.getFiles(function (f) {
                return f instanceof File && supportedExtensions.test(f.name);
            });

            for (var j = 0; j < files.length; j++) {
                var fileName = files[j].name.toLowerCase();
                // Tìm file có chứa "chain" trong tên nhưng không phải "chainrules"
                if (fileName.indexOf("chain") >= 0 && fileName.indexOf("rules") < 0) {
                    return files[j];
                }
            }

            return null;
        } catch (e) {
            return null;
        }
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

    function addChainAndPosition(shape8, shape9) {
        try {
            // Đọc brand từ file mode_info.txt
            var selectedBrand;
            try {
                selectedBrand = readBrandFromFile();
            } catch (readError) {
                throw new Error("Lỗi đọc file mode_info.txt:\n\n" + readError.message + "\n\nHãy đảm bảo đã chạy script '1. Scale.jsx' trước.");
            }

            if (!selectedBrand || selectedBrand.toUpperCase() === "NONE") {
                throw new Error("Không tìm thấy thông tin brand hoặc brand là NONE. Hãy chạy script '1. Scale.jsx' trước.");
            }

            // Tìm folder DATA và brand folder
            var dataFolder = getDataFolder();
            if (!dataFolder) {
                throw new Error("Không tìm thấy folder DATA/");
            }

            var brandFolder = getBrandFolder(dataFolder, selectedBrand);
            if (!brandFolder) {
                throw new Error("Không tìm thấy folder DATA/" + selectedBrand + "/");
            }

            // Tìm file chain trong brand folder
            var chainFile = findChainFile(dataFolder, brandFolder);
            if (!chainFile) {
                throw new Error("Không tìm thấy file Chain trong " + brandFolder.fsName);
            }

            // Place chain file
            var chain = placeFile(chainFile);
            if (!chain) {
                throw new Error("Không thể place file Chain.");
            }

            chain.name = "CHAIN";

            // Định vị chain với Shape 8 (tương tự 4.1.Autochain.jsx)
            var sb = shape8.bounds;
            var sLeft = parseFloat(sb[0]);
            var sBottom = parseFloat(sb[3]);
            var sTop = parseFloat(sb[1]);
            var sRight = parseFloat(sb[2]);
            var sCenterX = (sLeft + sRight) / 2;
            var sCenterY = (sTop + sBottom) / 2;

            var cb = chain.bounds;
            var cLeft = parseFloat(cb[0]);
            var cTop = parseFloat(cb[1]);
            var cBottom = parseFloat(cb[3]);
            var cHeight = cBottom - cTop;

            var newLeft = sCenterX;
            var newTop = sCenterY - cHeight;

            var moveX = newLeft - cLeft;
            var moveY = newTop - cTop;

            doc.activeLayer = chain;
            chain.translate(UnitValue(moveX, "px"), UnitValue(moveY, "px"));
            try { chain.move(shape8, ElementPlacement.PLACEBEFORE); } catch (e) { }
            chain.translate(UnitValue(-2, "px"), UnitValue(2, "px"));

            // Duplicate và flip ngang
            var chainCopy = chain.duplicate();
            chainCopy.name = "CHAIN copy";
            doc.activeLayer = chainCopy;
            try { chainCopy.resize(-100, 100, AnchorPosition.MIDDLECENTER); } catch (e) { }

            // Định vị chain copy với Shape 9
            var sb2 = shape9.bounds;
            var s2Left = parseFloat(sb2[0]);
            var s2Top = parseFloat(sb2[1]);
            var s2Right = parseFloat(sb2[2]);
            var s2Bottom = parseFloat(sb2[3]);
            var s2CenterX = (s2Left + s2Right) / 2;
            var s2CenterY = (s2Top + s2Bottom) / 2;

            var cb2 = chainCopy.bounds;
            var c2Left = parseFloat(cb2[0]);
            var c2Top = parseFloat(cb2[1]);
            var c2Right = parseFloat(cb2[2]);
            var c2Bottom = parseFloat(cb2[3]);
            var c2Width = c2Right - c2Left;
            var c2Height = c2Bottom - c2Top;

            var newLeft2 = s2CenterX - c2Width;
            var newTop2 = s2CenterY - c2Height;
            var moveX2 = newLeft2 - c2Left;
            var moveY2 = newTop2 - c2Top;
            chainCopy.translate(UnitValue(moveX2, "px"), UnitValue(moveY2, "px"));
            try { chainCopy.move(shape9, ElementPlacement.PLACEBEFORE); } catch (e) { }
            chainCopy.translate(UnitValue(2, "px"), UnitValue(2, "px"));

            // Merge 2 chains
            try {
                mergeLayersByNames(doc, ["CHAIN", "CHAIN copy"]);
            } catch (e) { }

        } catch (e) {
            // Nếu có lỗi khi add chain, không throw để không ảnh hưởng phần trước
        }
    }

    function mergeLayersByNames(doc, names) {
        if (!names || !names.length) return;
        selectLayerByName(names[0], false);
        for (var i = 1; i < names.length; i++) {
            selectLayerByName(names[i], true);
        }
        executeAction(stringIDToTypeID("mergeLayers"), undefined, DialogModes.NO);
    }

    function selectLayerByName(name, add) {
        var desc = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putName(charIDToTypeID("Lyr "), name);
        desc.putReference(charIDToTypeID("null"), ref);
        var selectionModifier = stringIDToTypeID("selectionModifier");
        var modifierType = add ? stringIDToTypeID("addToSelection") : stringIDToTypeID("setSelection");
        desc.putEnumerated(selectionModifier, stringIDToTypeID("selectionModifierType"), modifierType);
        desc.putBoolean(stringIDToTypeID("makeVisible"), false);
        executeAction(charIDToTypeID("slct"), desc, DialogModes.NO);
    }

})();

