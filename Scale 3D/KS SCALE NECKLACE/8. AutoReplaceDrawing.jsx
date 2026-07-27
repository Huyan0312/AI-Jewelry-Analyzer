/**
 * 9. ĐỌC FILE DRAWING VÀ SỬA CHAINRULES
 * Photoshop CS5+ — Đọc file Drawing.txt và thay thế văn bản trong layer Chainrules
 * Đã tối ưu hóa hiệu năng cho CS5
 * 
 * Quy trình:
 * 1. Đọc drawing từ Cache/state.txt
 * 2. Kiểm tra số (phải đúng 6 chữ số) — đọc từ Cache/state.txt
 * 3. Tìm layer "Chainrules" (Dùng Action Manager để tìm nhanh)
 * 4. Mở Edit Content của smart object
 * 5. Tìm layer văn bản "888888" (Ưu tiên tìm theo tên layer trước, sau đó tìm theo nội dung)
 * 6. Thay thế văn bản và Lưu
 */

#target photoshop

(function () {
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

    // Tối ưu hóa Giao diện và Lịch sử
    var oldDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;
    try { app.playbackDisplayDialogs = DialogModes.NO; } catch (e) { }

    var startState = null;
    try {
        // Snapshot lịch sử nếu cần (CS5 có thể bỏ qua để tiết kiệm bộ nhớ)
    } catch (e) { }

    try {
        if (!app.documents.length) throw new Error("Không có tài liệu đang mở.");
        var doc = app.activeDocument;

        // ====================================
        // 1. ĐỌC DRAWING TỪ CACHE/STATE.TXT
        // ====================================

        var scriptFile = new File($.fileName);
        var scriptFolder = scriptFile.parent;
        var cacheFile = getKSNecklaceStateFile(scriptFolder);

        if (!cacheFile.exists) {
            throw new Error("Không tìm thấy file cache tại:\n" + cacheFile.fsName);
        }

        cacheFile.open("r");
        var cacheContent = cacheFile.read();
        cacheFile.close();

        var content = "";
        var lines = (cacheContent || "").replace(/\r/g, "").split("\n");
        for (var i = 0; i < lines.length; i++) {
            if (lines[i].indexOf("drawing=") === 0) {
                content = lines[i].substring(8).replace(/^\s+|\s+$/g, "");
                break;
            }
        }
        if (typeof content !== "string") content = String(content);

        // ====================================
        // 2. KIỂM TRA DỮ LIỆU
        // ====================================

        var isOnlyDigits = /^\d+$/.test(content);
        var isExactly6Digits = content.length === 6;

        if (!isOnlyDigits || !isExactly6Digits) {
            var errorMsg = "❌ DỮ LIỆU KHÔNG HỢP LỆ!\n\n";
            errorMsg += "Nội dung: " + content + "\n";
            if (!isOnlyDigits) errorMsg += "Lý do: Chứa ký tự không phải số\n";
            else errorMsg += "Lý do: Phải đúng 6 chữ số (hiện có " + content.length + ")\n";
            throw new Error(errorMsg);
        }

        // ====================================
        // 3. TÌM LAYER CHAINRULES (PHƯƠNG PHÁP NHANH)
        // ====================================

        // Dùng Action Manager chọn layer theo tên (nhanh hơn vòng lặp)
        var layerFound = false;
        if (selectLayerByName("Chainrules")) layerFound = true;
        else if (selectLayerByName("chainrules")) layerFound = true;
        else if (selectLayerByName("CHAINRULES")) layerFound = true;

        if (!layerFound) {
            throw new Error("Không tìm thấy layer 'Chainrules'.");
        }

        var chainRulesLayer = doc.activeLayer;

        if (chainRulesLayer.kind !== LayerKind.SMARTOBJECT) {
            throw new Error("Layer 'Chainrules' không phải là Smart Object.");
        }

        // ====================================
        // 4. MỞ SMART OBJECT
        // ====================================

        var docCountBefore = app.documents.length;

        // Mở Smart Object
        executeAction(stringIDToTypeID("placedLayerEditContents"), undefined, DialogModes.NO);

        // Kiểm tra document mới
        var smartDoc = null;
        // Thử tối đa 10 lần, mỗi lần 100ms (nhanh hơn sleep 500ms cố định)
        for (var i = 0; i < 10; i++) {
            if (app.documents.length > docCountBefore) {
                smartDoc = app.activeDocument;
                break;
            }
            $.sleep(100);
        }

        if (!smartDoc) {
            // Fallback: lấy document cuối cùng
            if (app.documents.length > docCountBefore) {
                smartDoc = app.documents[app.documents.length - 1];
            } else {
                throw new Error("Không mở được Smart Object.");
            }
        }

        app.activeDocument = smartDoc;

        // ====================================
        // 5. TÌM VÀ THAY THẾ VĂN BẢN (PHƯƠNG PHÁP NHANH)
        // ====================================

        var textLayer = null;

        // CÁCH 1: Tìm theo tên layer "888888" (Nhanh nhất)
        // Layer văn bản thường có tên giống nội dung
        if (selectLayerByName("888888")) {
            if (smartDoc.activeLayer.kind === LayerKind.TEXT) {
                textLayer = smartDoc.activeLayer;
            }
        }

        // CÁCH 2: Nếu không tìm thấy theo tên, duyệt layer (Chậm hơn nhưng chắc chắn)
        if (!textLayer) {
            textLayer = findTextLayerWithContent(smartDoc, "888888");
        }

        if (!textLayer) {
            smartDoc.close(SaveOptions.DONOTSAVECHANGES);
            throw new Error("Không tìm thấy layer văn bản chứa '888888' trong Smart Object.");
        }

        // Thay thế Văn bản
        try {
            // Đảm bảo textItem.contents được cập nhật
            textLayer.textItem.contents = content;
        } catch (e) {
            smartDoc.close(SaveOptions.DONOTSAVECHANGES);
            throw new Error("Lỗi khi thay đổi văn bản: " + e.message);
        }

        // ====================================
        // 6. LƯU VÀ ĐÓNG
        // ====================================

        smartDoc.close(SaveOptions.SAVECHANGES);

        // Quay lại doc gốc (thường tự động, nhưng chắc chắn)
        app.activeDocument = doc;

    } catch (e) {
        app.displayDialogs = DialogModes.ALL;
        alert(e.message);
    } finally {
        app.displayDialogs = oldDialogs;
        try { app.playbackDisplayDialogs = DialogModes.ALL; } catch (e) { }
    }

    // ====================================
    // CÁC HÀM HỖ TRỢ
    // ====================================

    function selectLayerByName(name) {
        try {
            var desc = new ActionDescriptor();
            var ref = new ActionReference();
            ref.putName(charIDToTypeID("Lyr "), name);
            desc.putReference(charIDToTypeID("null"), ref);
            desc.putBoolean(charIDToTypeID("MkVs"), false);
            executeAction(charIDToTypeID("slct"), desc, DialogModes.NO);
            return true;
        } catch (e) {
            return false;
        }
    }

    function findTextLayerWithContent(root, searchText) {
        try {
            for (var i = 0; i < root.layers.length; i++) {
                var layer = root.layers[i];
                if (layer.kind === LayerKind.TEXT) {
                    // Kiểm tra nội dung
                    if (layer.textItem.contents.indexOf(searchText) >= 0) {
                        return layer;
                    }
                } else if (layer.typename === "LayerSet") {
                    var found = findTextLayerWithContent(layer, searchText);
                    if (found) return found;
                }
            }
        } catch (e) { }
        return null;
    }

})();