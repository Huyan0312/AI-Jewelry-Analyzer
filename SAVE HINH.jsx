//target photoshop
// Dựa trên file gốc SAVE HINH.jsx fileciteturn0file0

// ==== Hàm căn giữa cửa sổ trên màn hình được chọn ====
function centerWindowOnSelectedScreen(win, defaultWidth, defaultHeight) {
    win.onShow = function() {
        try {
            var screens = $.screens;
            var selectedIdx = 0;
            var configFile = new File("D:/HuyAn/OK/selected_screen.txt");
            if (configFile.exists && configFile.open("r")) {
                var val = parseInt(configFile.readln(), 10);
                configFile.close();
                if (!isNaN(val) && val < screens.length) {
                    selectedIdx = val;
                }
            }
            
            var screen = screens[selectedIdx];
            var screenWidth = screen.right - screen.left;
            var screenHeight = screen.bottom - screen.top;
            
            win.layout.layout(true);
            var winWidth = win.bounds.right - win.bounds.left;
            var winHeight = win.bounds.bottom - win.bounds.top;
            
            var x = screen.left + (screenWidth - winWidth) / 2;
            var y = screen.top + (screenHeight - winHeight) / 2;
            
            win.frameLocation = [x, y];
        } catch (e) {
            win.center();
        }
    };
}





// ==== 0. Biến toàn cục cho tên tuỳ chỉnh ====
var customName = null;
var moveToFinish = false; // Điều khiển checkbox

// ==== 1. Cấu hình file Config ====
function getConfigFile() {
    var scriptFile = new File($.fileName);
    var folder = scriptFile.parent;
    // Dự phòng nếu $.fileName không trả về đường dẫn đúng (khi chạy evalFile hoặc Action)
    if (!folder || !folder.exists || folder.fsName.indexOf("Adobe Photoshop") !== -1) {
        folder = new Folder("d:/HuyAn/OK/SAVEHINH");
    }
    return new File(folder + '/config.txt');
}

function readConfig() {
    var config = {};
    var configFile = getConfigFile();
    if (configFile.exists) {
        configFile.open('r');
        configFile.encoding = "UTF-8";
        while (!configFile.eof) {
            var line = configFile.readln();
            if (!line || line.indexOf('=') === -1) continue;
            var parts = line.split('=');
            var key = parts.shift();
            var val = parts.join('=');
            config[key] = val;
        }
        configFile.close();
    }
    return config;
}

function writeConfig(key, folderPath) {
    var config = readConfig();
    config[key] = folderPath;
    var configFile = getConfigFile();
    configFile.encoding = "UTF-8";
    if (configFile.open('w')) {
        for (var k in config) {
            if (config.hasOwnProperty(k)) {
                configFile.writeln(k + '=' + config[k]);
            }
        }
        configFile.close();
    } else {
        alert("❌ Không thể ghi file config.txt! Hãy kiểm tra quyền truy cập thư mục.");
    }
}

// ==== 1.1 Helper functions cho Multi-layer ====
function getSelectedLayerIDs() {
    var selectedLayers = [];
    try {
        var ref = new ActionReference();
        ref.putEnumerated(charIDToTypeID("Dcmn"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var desc = executeActionGet(ref);
        if (desc.hasKey(stringIDToTypeID("targetLayers"))) {
            var list = desc.getList(stringIDToTypeID("targetLayers"));
            for (var i = 0; i < list.count; i++) {
                var index = list.getReference(i).getIndex();
                var refL = new ActionReference();
                refL.putIndex(charIDToTypeID("Lyr "), index);
                selectedLayers.push(executeActionGet(refL).getInteger(stringIDToTypeID("layerID")));
            }
        } else {
            var refA = new ActionReference();
            refA.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            selectedLayers.push(executeActionGet(refA).getInteger(stringIDToTypeID("layerID")));
        }
    } catch (e) {
        if (app.activeDocument.activeLayer) {
            try { selectedLayers.push(app.activeDocument.activeLayer.id); } catch(e2) {}
        }
    }
    return selectedLayers;
}

function selectLayerByID(id) {
    var desc = new ActionDescriptor();
    var ref = new ActionReference();
    ref.putIdentifier(charIDToTypeID("Lyr "), id);
    desc.putReference(charIDToTypeID("null"), ref);
    executeAction(charIDToTypeID("slct"), desc, DialogModes.NO);
}

function cropToActiveLayer(padding) {
    var doc = app.activeDocument;
    try {
        // Kiểm tra Background layer
        var refB = new ActionReference();
        refB.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var isBg = false;
        try { isBg = executeActionGet(refB).getBoolean(stringIDToTypeID("background")); } catch(e) {}

        if (isBg) {
            doc.selection.selectAll();
        } else {
            // Chọn vùng trong suốt của layer
            var idsetd = charIDToTypeID("setd");
            var desc = new ActionDescriptor();
            var idnull = charIDToTypeID("null");
            var ref = new ActionReference();
            var idChnl = charIDToTypeID("Chnl");
            var idfsel = charIDToTypeID("fsel");
            ref.putProperty(idChnl, idfsel);
            desc.putReference(idnull, ref);
            var idT = charIDToTypeID("T   ");
            var ref2 = new ActionReference();
            var idChnl2 = charIDToTypeID("Chnl");
            var idChnlAlpha = charIDToTypeID("Trsp");
            ref2.putEnumerated(idChnl2, idChnl2, idChnlAlpha);
            desc.putReference(idT, ref2);
            executeAction(idsetd, desc, DialogModes.NO);
        }

        var bounds = doc.selection.bounds;
        var left   = bounds[0].value - padding;
        var top    = bounds[1].value - padding;
        var right  = bounds[2].value + padding;
        var bottom = bounds[3].value + padding;

        left   = Math.max(left, 0);
        top    = Math.max(top, 0);
        right  = Math.min(right, doc.width.value);
        bottom = Math.min(bottom, doc.height.value);

        doc.crop([left, top, right, bottom]);
        doc.selection.deselect();
        return true;
    } catch (e) {
        alert("❌ Lỗi khi xác định vùng Crop: " + e.message);
        return false;
    }
}

// ==== 2. Hàm lưu JPEG với kiểm tra trùng tên và tên tuỳ chỉnh ====
function saveToConfiguredFolder(configName, askToMove) {
    if (app.documents.length === 0) {
        alert('Không có file nào đang mở!');
        return;
    }
    var config = readConfig();
    var saveFolder = config[configName] ? new Folder(config[configName]) : null;
    if (!saveFolder || !saveFolder.exists) {
        saveFolder = Folder.selectDialog('Chọn thư mục lưu cho: ' + configName.toUpperCase());
        if (!saveFolder) { setStatus('❌ Đã hủy chọn thư mục.', true); return; }
        writeConfig(configName, saveFolder.fsName);
    }

    var doc = app.activeDocument;
    var layerIDs = getSelectedLayerIDs();
    var initialName = customName;
    var successCount = 0;

    var historySnapshot = doc.activeHistoryState;

    for (var i = 0; i < layerIDs.length; i++) {
        selectLayerByID(layerIDs[i]);

        var cropSuccess = cropToActiveLayer(2);
        if (!cropSuccess) continue;

        var baseName = initialName && initialName.length > 0 ? initialName : doc.name.replace(/\.[^\.]+$/, '');
        var saveFile = new File(saveFolder + '/' + baseName + '.jpg');
        var counter = 1;
        while (saveFile.exists) {
            saveFile = new File(saveFolder + '/' + baseName + '_' + counter + '.jpg');
            counter++;
        }

        var jpgOptions = new JPEGSaveOptions();
        jpgOptions.quality = 12;
        jpgOptions.formatOptions = FormatOptions.STANDARDBASELINE;
        jpgOptions.embedColorProfile = true;
        jpgOptions.matte = MatteType.NONE;
        doc.saveAs(saveFile, jpgOptions, true);

        if (moveToFinish) {
            try {
                var originalFile = doc.fullName;
                if (originalFile && originalFile.exists) {
                    var finishFolder = new Folder(originalFile.parent + '/Finish');
                    if (!finishFolder.exists) finishFolder.create();
                    var movedFile = new File(finishFolder + '/' + originalFile.name);
                    originalFile.copy(movedFile);
                    originalFile.remove();
                }
            } catch (e) {}
        }

        doc.activeHistoryState = historySnapshot;
        successCount++;
    }

    customName = null;
    if (successCount > 0) {
        win.close();
    } else {
        setStatus('❌ Không có layer nào được lưu.', true);
    }
}

// ==== 3. Hàm lưu PNG full nét cho RULE2D ====
function savePngToConfiguredFolder(configName, askToMove) {
    if (app.documents.length === 0) {
        alert('Không có file nào đang mở!');
        return;
    }
    var config = readConfig();
    var saveFolder = config[configName] ? new Folder(config[configName]) : null;
    if (!saveFolder || !saveFolder.exists) {
        saveFolder = Folder.selectDialog('Chọn thư mục lưu cho: ' + configName.toUpperCase());
        if (!saveFolder) { setStatus('❌ Đã hủy chọn thư mục.', true); return; }
        writeConfig(configName, saveFolder.fsName);
    }

    var doc = app.activeDocument;
    var layerIDs = getSelectedLayerIDs();
    var initialName = customName;
    var successCount = 0;

    var historySnapshot = doc.activeHistoryState;

    for (var i = 0; i < layerIDs.length; i++) {
        selectLayerByID(layerIDs[i]);

        var cropSuccess = cropToActiveLayer(2);
        if (!cropSuccess) continue;

        var baseName = initialName && initialName.length > 0 ? initialName : doc.name.replace(/\.[^\.]+$/, '');
        var saveFile = new File(saveFolder + '/' + baseName + '.png');
        var counter = 1;
        while (saveFile.exists) {
            saveFile = new File(saveFolder + '/' + baseName + '_' + counter + '.png');
            counter++;
        }

        // Lưu PNG
        var pngOptions = new PNGSaveOptions();
        pngOptions.compression = 0;
        pngOptions.interlaced = false;
        doc.saveAs(saveFile, pngOptions, true, Extension.LOWERCASE);

        if (moveToFinish) {
            try {
                var originalFile = doc.fullName;
                if (originalFile && originalFile.exists) {
                    var finishFolder = new Folder(originalFile.parent + '/Finish');
                    if (!finishFolder.exists) finishFolder.create();
                    var movedFile = new File(finishFolder + '/' + originalFile.name);
                    originalFile.copy(movedFile);
                    originalFile.remove();
                }
            } catch (e) {}
        }

        doc.activeHistoryState = historySnapshot;
        successCount++;
    }

    customName = null;
    if (successCount > 0) {
        win.close();
    } else {
        setStatus('❌ Không có layer nào được lưu.', true);
    }
}

// ==== 4. UI ====
var win = new Window('dialog', 'SAVE NHANH', undefined, {closeButton: true});
win.orientation = 'column';
win.alignChildren = ['fill','center'];
win.spacing = 0;
win.margins = 2;

// Nhóm nhập tên
var nameGroup = win.add('group');
nameGroup.orientation = 'row';
nameGroup.alignChildren = ['left','center'];
var lbl = nameGroup.add('statictext', undefined, 'Đặt tên file:');
lbl.justify = 'left';
var nameInput = nameGroup.add('edittext', undefined, '');
nameInput.characters = 10;
nameInput.onChanging = function() {
    customName = nameInput.text;
};
if (app.documents.length) {
    var doc = app.activeDocument;
    var baseName = doc.name.replace(/\.[^\.]+$/, '');
    var numMatch = baseName.match(/(\d+)/);
    if (numMatch) {
        nameInput.text = numMatch[1];
        customName = nameInput.text;
    }
}

// Checkbox dọn file gốc
var moveGroup = win.add('group');
moveGroup.orientation = 'row';
moveGroup.alignChildren = ['left','center'];

var moveCheckbox = moveGroup.add('checkbox', undefined, 'Dọn vào thư mục Finish sau khi lưu');
moveCheckbox.value = false; // Mặc định không tích

moveCheckbox.onClick = function() {
    moveToFinish = moveCheckbox.value; // Ghi lại trạng thái checkbox
};

// Nút lưu
var btnPanel = win.add('group');
btnPanel.orientation = 'row';
btnPanel.alignChildren = ['fill','center'];
btnPanel.spacing = 8;
var btn3D    = btnPanel.add('button', undefined, 'SCALE 3D');
var btnDD    = btnPanel.add('button', undefined, 'File DD');
var btn2D    = btnPanel.add('button', undefined, 'File 2D');
var btn2DExp = btnPanel.add('button', undefined, '2D Export');
var btnRule2D= btnPanel.add('button', undefined, 'RULE 2D');
btn3D.onClick     = function() { saveToConfiguredFolder('3D', false); };
btnDD.onClick     = function() { saveToConfiguredFolder('DD', false); };
btn2D.onClick     = function() { saveToConfiguredFolder('2D', false); };
btn2DExp.onClick  = function() { saveToConfiguredFolder('2DExport', false); };
btnRule2D.onClick = function() { savePngToConfiguredFolder('RULE2D', false); };

// Thông báo trạng thái
var statusPanel = win.add('group');
statusPanel.alignment = 'center';
var statusText = statusPanel.add('statictext', undefined, 'Sẵn sàng...');
statusText.characters = 30;
statusText.justify = 'center';

function setStatus(msg, isError) {
    statusText.text = msg;
    var color = isError ? [1, 0, 0, 1] : [0, 0.5, 0, 1];
    statusText.graphics.foregroundColor = statusText.graphics.newPen(statusText.graphics.PenType.SOLID_COLOR, color, 1);
}

// Nút đóng
var btnClose = win.add('button', undefined, 'Đóng', {name:'cancel'});
centerWindowOnSelectedScreen(win);
win.show();
