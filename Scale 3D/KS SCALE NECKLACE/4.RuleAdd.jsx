#target photoshop;

/**
 * KS SCALE NECKLACE - PHASE 5: ADD RULES
 * Photoshop CS5+ — Place 3 rule images vào document
 * 
 * Workflow:
 * 1. Đọc brand từ Cache/state.txt (đã được lưu từ script 1.Scale.jsx)
 * 2. Tìm 3 file trong DATA/{brand}/:
 *    - All dimensions.png
 *    - Chainrules.png
 *    - Rulelinks.png
 * 3. Place từng file vào document
 * 4. Đặt tên layer tương ứng
 * 5. Căn chỉnh vị trí (có thể cần điều chỉnh theo layout)
 */

(function () {
    var RULE_FILES = [
        { filename: "All dimensions", layerName: "ALLDIMENSIONS" },
        { filename: "Chainrules", layerName: "CHAINRULES" },
        { filename: "Rulelinks", layerName: "RULELINKS" }
    ];
    var supportedExtensions = /\.(png|psd|tif|tiff|jpg|jpeg|bmp)$/i;

    var oldDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;
    try { app.playbackDisplayDialogs = DialogModes.NO; } catch (e) { }

    var prevRU = app.preferences.rulerUnits;

    try {
        if (!app.documents.length) throw new Error("Không có tài liệu đang mở.");
        var doc = app.activeDocument;
        app.preferences.rulerUnits = Units.PIXELS;

        // Đọc brand và chain từ Cache/state.txt (đã được lưu từ script 1.Scale.jsx)
        var selectedBrand;
        var selectedChain;
        try {
            var state = readStateFromFile();
            selectedBrand = state.brand;
            selectedChain = state.chain || "NONE";
        } catch (readError) {
            app.displayDialogs = DialogModes.ALL;
            alert("Lỗi đọc Cache/state.txt:\n\n" + readError.message + "\n\nHãy đảm bảo đã chạy script '1.Scale.jsx' trước.");
            app.displayDialogs = DialogModes.NO;
            throw readError;
        }

        if (!selectedBrand) {
            throw new Error("Không tìm thấy brand trong Cache/state.txt. Hãy chạy script '1.Scale.jsx' trước.");
        }

        // Nếu brand là "NONE" thì ngưng không làm gì
        if (selectedBrand.toUpperCase() === "NONE") {
            return; // Dừng script, không làm gì cả
        }

        // Tìm folder DATA trực tiếp
        var dataFolder = getDataFolder();
        if (!dataFolder) {
            throw new Error("Không tìm thấy folder DATA/");
        }

        // Tìm folder brand được chọn trong DATA/
        var brandFolder = getBrandFolder(dataFolder, selectedBrand);
        if (!brandFolder) {
            throw new Error("Không tìm thấy folder DATA/" + selectedBrand + "/");
        }

        var placedLayers = [];

        // Place từng file rule
        for (var i = 0; i < RULE_FILES.length; i++) {
            var ruleInfo = RULE_FILES[i];
            var rulesFile = null;

            if (ruleInfo.layerName === "ALLDIMENSIONS") {
                rulesFile = getFileForAllDimensions(dataFolder, brandFolder, selectedBrand, selectedChain, ruleInfo.filename);
            } else {
                rulesFile = findRuleFile(brandFolder, ruleInfo.filename);
            }

            if (!rulesFile) {
                throw new Error("Không tìm thấy file '" + ruleInfo.filename + "' trong " + brandFolder.fsName);
            }

            var placedLayer = placeFile(rulesFile);
            if (!placedLayer) {
                throw new Error("Không thể place file '" + rulesFile.fsName + "'.");
            }

            placedLayer.name = ruleInfo.layerName;
            placedLayers.push(placedLayer);
        }

        // Căn chỉnh các layer rules (có thể cần điều chỉnh theo layout)
        // Tạm thời để các layer ở vị trí mặc định sau khi place
        // Có thể thêm logic căn chỉnh sau nếu cần

        // Set active layer là layer cuối cùng được place
        if (placedLayers.length > 0) {
            doc.activeLayer = placedLayers[placedLayers.length - 1];
        }

        // KHÔNG tự động gọi script StartRuleLogic ở đây
        // Vì script 5. StartRuleLogic.jsx đã được gọi từ START.jsx
        // và nó sẽ tự động gọi tất cả script 5.1, 5.2, 5.3, 5.4
        // Nếu gọi ở đây sẽ tạo vòng lặp vô hạn!

    } catch (err) {
        alert("Lỗi Add Rules:\n\n" + err.message);
    } finally {
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;
        try { app.playbackDisplayDialogs = DialogModes.ALL; } catch (e) { }
    }

    function getParentFolder() {
        try {
            // Lấy đường dẫn script hiện tại - giống như script 1. Scale.jsx
            var scriptFile = new File($.fileName);
            var scriptFolder = scriptFile.parent;
            var parentFolder = scriptFolder.parent;
            return parentFolder;
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

    // Hàm trim() tự viết cho Photoshop CS5 (không hỗ trợ String.trim())
    function trimString(str) {
        if (typeof str !== "string") {
            str = String(str);
        }
        // Loại bỏ whitespace ở đầu và cuối bằng regex
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

    function readStateFromFile() {
        try {
            var scriptFile = new File($.fileName);
            var scriptFolder = scriptFile.parent;
            var stateFile = getKSNecklaceStateFile(scriptFolder);
            if (!stateFile.exists) {
                throw new Error("Không tìm thấy file state.txt tại: " + stateFile.fsName);
            }
            stateFile.open("r");
            var content = stateFile.read();
            stateFile.close();

            if (typeof content !== "string") content = String(content);
            var lines = content.split(/\r?\n/);
            var state = { brand: null, chain: "NONE" };

            for (var i = 0; i < lines.length; i++) {
                var line = trimString(lines[i] || "");
                if (!line) continue;
                if (line.indexOf("brand=") === 0) {
                    var brandName = trimString(line.substring(6));
                    if (brandName.toUpperCase() === "NONE") {
                        state.brand = "NONE";
                    } else {
                        var normalizedBrand = brandName.replace(/\s+/g, "").toLowerCase();
                        var brandMapping = { "14k": "14k", "silver": "silver", "labgrown": "labgrown" };
                        state.brand = brandMapping[normalizedBrand] || normalizedBrand;
                    }
                } else if (line.indexOf("chain=") === 0) {
                    state.chain = trimString(line.substring(6)) || "NONE";
                }
            }
            return state;
        } catch (e) {
            throw new Error("Lỗi khi đọc Cache/state.txt: " + e.message);
        }
    }

    function getFileForAllDimensions(dataFolder, brandFolder, brand, chain, fallbackFilename) {
        var chainVal = trimString(String(chain || ""));
        if (chainVal === "" || chainVal.toUpperCase() === "NONE") {
            return findRuleFile(brandFolder, fallbackFilename);
        }
        var brandKey = String(brand || "").replace(/\s+/g, "").toLowerCase();
        var chainFolderName = "";
        if (brandKey === "14k") chainFolderName = "14K Chain";
        else if (brandKey === "silver") chainFolderName = "Silver Chain";
        if (!chainFolderName) return findRuleFile(brandFolder, fallbackFilename);

        var chainFolderPath = dataFolder.fsName + "/CHAIN/" + chainFolderName;
        var chainFolder = new Folder(chainFolderPath);
        if (!chainFolder.exists) return findRuleFile(brandFolder, fallbackFilename);

        var chainFile = findChainFileInFolder(chainFolderPath, chainVal);
        if (chainFile) return chainFile;
        return findRuleFile(brandFolder, fallbackFilename);
    }

    function findChainFileInFolder(chainFolderPath, baseName) {
        var base = trimString(String(baseName || ""));
        if (!base) return null;
        var targetBase = base.toLowerCase();
        var exts = [".jpg", ".jpeg", ".png"];
        for (var e = 0; e < exts.length; e++) {
            var f = new File(chainFolderPath + "/" + base + exts[e]);
            if (f.exists) return f;
        }
        var folder = new Folder(chainFolderPath);
        if (!folder.exists) return null;
        var files = folder.getFiles(function (file) {
            return file instanceof File && /\.(jpg|jpeg|png)$/i.test(file.name);
        });
        for (var k = 0; k < files.length; k++) {
            var name = files[k].name.replace(/\.(jpg|jpeg|png)$/i, "");
            if (name.toLowerCase() === targetBase) return files[k];
        }
        return null;
    }

    function findRuleFile(brandFolder, filenameBase) {
        var files = brandFolder.getFiles(function (f) {
            return f instanceof File && supportedExtensions.test(f.name);
        });

        for (var i = 0; i < files.length; i++) {
            var base = decodeURI(files[i].name).replace(/\.[^\.]+$/, "").toLowerCase();
            var targetBase = filenameBase.toLowerCase();
            if (base === targetBase || base.indexOf(targetBase) >= 0) {
                return files[i];
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


