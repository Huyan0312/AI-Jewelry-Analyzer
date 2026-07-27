#target photoshop

// ============================================================
// AI_AutoDetect test.jsx
// Phase ($.global.ksAIPhase):
//   "queue"       — chi gui job AI (detector chay song song)
//   "waitOnly"    — doi JSON + doc sheet (khong copy View)
//   "copyOnly"    — copy View tu JSON da co
//   "waitAndCopy" — doi JSON + CpTL tao View 1..7
//   "full"/khong set — queue + wait + copy (chay doc lap)
// Silent: $.global.ksScaleSilentAI = true
// ============================================================

var PROJECT_ROOT = new File($.fileName).parent;
var BASE_PY_DIR  = PROJECT_ROOT.fsName + "\\PTS CS5 SCRIPT";
var INPUT_DIR    = BASE_PY_DIR + "\\input";
var OUTPUT_DIR   = PROJECT_ROOT.fsName + "\\Scale 3D\\KS";
var TIMING_LOG   = BASE_PY_DIR + "\\cache\\timing_log.txt";
var TIMEOUT_SEC  = 180;
var POLL_MS      = 300;
var VIEW_ORDER   = ["FRONT", "LEFT", "TOP", "PERSPECTIVE", "BACK", "RIGHT", "BOTTOM"];
var IMAGE_EXTS   = [".jpg", ".jpeg", ".png"];

function isSilent() {
    return (typeof $.global.ksScaleSilentAI !== "undefined" && $.global.ksScaleSilentAI);
}

function getPhase() {
    if (typeof $.global.ksAIPhase !== "undefined" && $.global.ksAIPhase) {
        return String($.global.ksAIPhase);
    }
    return "full";
}

function showError(message) {
    if (isSilent()) throw new Error(message);
    alert("Loi:\n" + message);
}

function showInfo(message) {
    if (isSilent()) return;
    alert(message);
}

function nowMs() {
    return new Date().getTime();
}

function appendTimingLog(line) {
    try {
        var f = new File(TIMING_LOG);
        var folder = f.parent;
        if (!folder.exists) folder.create();
        f.open("a");
        f.encoding = "UTF-8";
        var d = new Date();
        var ts = d.getFullYear() + "-" +
            ("0" + (d.getMonth() + 1)).slice(-2) + "-" +
            ("0" + d.getDate()).slice(-2) + " " +
            ("0" + d.getHours()).slice(-2) + ":" +
            ("0" + d.getMinutes()).slice(-2) + ":" +
            ("0" + d.getSeconds()).slice(-2);
        f.write(ts + " | PS_AI | " + line + "\n");
        f.close();
    } catch (e) { }
}

function jsonEscape(str) {
    return String(str)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n");
}

function getFileExtension(fileName) {
    var dot = fileName.lastIndexOf(".");
    if (dot < 0) return "";
    return fileName.substring(dot).toLowerCase();
}

function isSupportedImageExt(ext) {
    for (var i = 0; i < IMAGE_EXTS.length; i++) {
        if (IMAGE_EXTS[i] === ext) return true;
    }
    return false;
}

function resolveSourceImagePath(doc) {
    // File chua Save: doc.fullName throw "The document has not yet been saved."
    try {
        var srcFile = doc.fullName; // File object
        if (!srcFile) return null;
        if (!srcFile.exists) return null;
        var ext = getFileExtension(srcFile.name);
        if (!isSupportedImageExt(ext)) return null;
        return srcFile.fsName;
    } catch (e) {
        return null;
    }
}

function writeJobJson(jobFile, imagePath, baseName) {
    // Lay selection crop path neu co (duoc set boi 1.Scale.jsx sau khi tô vung)
    var selCrop = (typeof $.global.ksSelCropPath !== "undefined" && $.global.ksSelCropPath)
        ? String($.global.ksSelCropPath) : "";
    // Lay expected direction tu aspect ratio cua selection (H/W/"")
    var expectedDir = (typeof $.global.ksSelExpectedDir !== "undefined" && $.global.ksSelExpectedDir)
        ? String($.global.ksSelExpectedDir) : "";
    var selNormBbox = (typeof $.global.ksSelNormBbox !== "undefined" && $.global.ksSelNormBbox)
        ? $.global.ksSelNormBbox : null;
    var payload = '{"image_path":"' + jsonEscape(imagePath) +
                  '","base_name":"' + jsonEscape(baseName) + '"';
    if (selCrop) {
        payload += ',"selection_crop_path":"' + jsonEscape(selCrop) + '"';
    }
    if (expectedDir) {
        payload += ',"sel_expected_dir":"' + jsonEscape(expectedDir) + '"';
    }
    if (selNormBbox && selNormBbox.length === 4) {
        payload += ',"selection_norm_bbox":[' + selNormBbox.join(",") + ']';
    }
    payload += '}';
    jobFile.open("w");
    jobFile.encoding = "UTF-8";
    jobFile.write(payload);
    jobFile.close();
    return jobFile.exists;
}

function exportImageToInput(doc, exportFile) {
    var jpegOpts = new JPEGSaveOptions();
    jpegOpts.quality = 10;
    jpegOpts.embedColorProfile = false;
    jpegOpts.formatOptions = FormatOptions.STANDARDBASELINE;
    jpegOpts.matte = MatteType.NONE;

    // 1) Thuong: Save a Copy tu doc dang mo
    try {
        doc.saveAs(exportFile, jpegOpts, true, Extension.LOWERCASE);
        if (exportFile.exists) return true;
    } catch (e1) {
        // CS5: doc chua tung Save co the throw "has not yet been saved"
    }

    // 2) Fallback: duplicate roi saveAs (ho tro doc Untitled / chua save)
    var dup = null;
    try {
        dup = doc.duplicate("_ai_tmp_export", true);
        dup.saveAs(exportFile, jpegOpts, true, Extension.LOWERCASE);
        return exportFile.exists;
    } catch (e2) {
        throw new Error(
            "Khong export duoc anh cho AI.\n" +
            "Hay File > Save As (JPG/PSD) roi chay lai.\n" +
            "(" + e2.message + ")"
        );
    } finally {
        if (dup) {
            try { dup.close(SaveOptions.DONOTSAVECHANGES); } catch (e3) { }
        }
    }
}

function isDetectorRunning() {
    var statusFile = new File(BASE_PY_DIR + "\\cache\\launcher_status.json");
    if (!statusFile.exists) return false;
    try {
        statusFile.open("r");
        var content = statusFile.read();
        statusFile.close();
        var statusJson = eval("(" + content + ")");
        return !!(statusJson && statusJson.detector_running === true);
    } catch (e) {
        return false;
    }
}

function ensureDetectorRunning() {
    if (isDetectorRunning()) return true;

    // Tu dong kich hoat ps_watcher.pyw ngam qua VBScript / BAT / PYW
    var vbsFile = new File(BASE_PY_DIR + "\\start_watcher.vbs");
    var executed = false;

    if (vbsFile.exists) {
        try { executed = vbsFile.execute(); } catch (eExec) {}
    }

    if (!executed) {
        var batFile = new File(BASE_PY_DIR + "\\start_watcher.bat");
        if (batFile.exists) {
            try { executed = batFile.execute(); } catch (eBat) {}
        }
    }

    if (!executed) {
        var pywFile = new File(BASE_PY_DIR + "\\ps_watcher.pyw");
        if (pywFile.exists) {
            try { executed = pywFile.execute(); } catch (ePyw) {}
        }
    }

    // Cho toi da 10 giay de Detector tao status JSON (~0.2s khi chay)
    for (var i = 0; i < 33; i++) {
        $.sleep(300);
        if (isDetectorRunning()) return true;
    }

    return isDetectorRunning();
}

function getJsonPath(baseName) {
    return OUTPUT_DIR + "\\" + baseName + "_all_views_result.json";
}

/** Chi gui job — detector Python xu ly song song luc user mo dialog */
function queueAIJob(doc, baseName) {
    var t0 = nowMs();
    if (!ensureDetectorRunning()) {
        showError("Khong the tu dong kich hoat AI Detector.\nVui long kiem tra LM Studio & Python.");
        appendTimingLog(baseName + " | queue FAIL | detector_off | " + (nowMs() - t0) + "ms");
        return false;
    }

    var tCheck = nowMs() - t0;
    var jsonFile = new File(getJsonPath(baseName));
    if (jsonFile.exists) jsonFile.remove();

    var tResolve0 = nowMs();
    var sourcePath = resolveSourceImagePath(doc);
    var tResolve = nowMs() - tResolve0;
    var queueOK = false;
    var mode = "";

    if (sourcePath) {
        var tWrite0 = nowMs();
        var jobFile = new File(INPUT_DIR + "\\" + baseName + ".job.json");
        if (jobFile.exists) jobFile.remove();
        queueOK = writeJobJson(jobFile, sourcePath, baseName);
        mode = "job_link";
        appendTimingLog(
            baseName + " | queue | mode=job_link | check=" + tCheck +
            "ms | resolve=" + tResolve + "ms | write_job=" + (nowMs() - tWrite0) +
            "ms | total=" + (nowMs() - t0) + "ms | path=" + sourcePath
        );
    }

    if (!queueOK) {
        var exportFile = new File(INPUT_DIR + "\\" + baseName + ".jpg");
        try {
            var tExp0 = nowMs();
            queueOK = exportImageToInput(doc, exportFile);
            mode = "export_jpg";
            appendTimingLog(
                baseName + " | queue | mode=export_jpg | check=" + tCheck +
                "ms | resolve=" + tResolve + "ms | export=" + (nowMs() - tExp0) +
                "ms | total=" + (nowMs() - t0) + "ms"
            );
        } catch (e) {
            showError("Khong gui duoc anh cho AI:\n" + e.message);
            appendTimingLog(baseName + " | queue FAIL | export | " + e.message);
            return false;
        }
    }

    if (!queueOK) {
        showError("Khong tao duoc job AI.");
        appendTimingLog(baseName + " | queue FAIL | no_job");
        return false;
    }

    $.global.ksAIBaseName = baseName;
    $.global.ksAIQueued = true;
    $.global.ksAIQueueMs = nowMs() - t0;
    $.global.ksAIQueueMode = mode;
    return true;
}

/** Doi JSON (neu chua co) — timeout con lai; hien palette neu AI chua xong */
function waitForAIJson(baseName) {
    var jsonPath = getJsonPath(baseName);
    var jsonFile = new File(jsonPath);
    var t0 = nowMs();
    if (jsonFile.exists) {
        appendTimingLog(baseName + " | wait | already_ready | 0ms");
        $.global.ksAIWaitMs = 0;
        $.global.ksAIWaitPolls = 0;
        return jsonFile;
    }

    // === PROGRESS UI ===
    var pWin = null, pBar = null, pStatus = null, pStep = null, pTime = null;
    // Uoc tinh thoi gian tu session truoc (doc tu timing_log neu co)
    var estSec = 14; // mac dinh 14s
    try {
        var logF = new File(TIMING_LOG);
        if (logF.exists) {
            logF.open("r"); logF.encoding = "UTF-8";
            var lastLine = ""; var line;
            while (!logF.eof) { line = logF.readln(); if (line) lastLine = line; }
            logF.close();
            // Format: "... | lm=11243ms ..."
            var m = lastLine.match(/lm=(\d+)ms/);
            if (m) { var ms = parseInt(m[1]); if (ms > 3000 && ms < 120000) estSec = Math.ceil(ms / 1000) + 4; }
        }
    } catch(eLog) {}

    var STEPS = [
        "1. Queue job AI",
        "2. Export selection crop",
        "3. AI phan tich (7 views)...",
        "4. Doc H/W dimensions...",
        "5. Hoan tat"
    ];
    // Step 1 & 2 da xong truoc khi vao day
    var curStep = 2; // 0-based, dang o step 2 (AI phan tich)

    try {
        pWin = new Window("palette", "AI Detector", undefined, { resizeable: false });
        pWin.orientation = "column";
        pWin.alignChildren = ["fill", "top"];
        pWin.margins = [14, 12, 14, 14];
        pWin.spacing = 6;

        // Title
        var titleRow = pWin.add("group");
        titleRow.orientation = "row";
        titleRow.add("statictext", undefined, "JEWELRY AI DETECTOR");

        // Separator line via panel
        pWin.add("panel", undefined, "");

        // Step list
        var stepsPanel = pWin.add("panel", undefined, "");
        stepsPanel.orientation = "column";
        stepsPanel.alignChildren = ["left", "top"];
        stepsPanel.margins = [8, 4, 8, 6];
        stepsPanel.spacing = 3;
        var stepLabels = [];
        for (var si = 0; si < STEPS.length; si++) {
            var prefix = (si < curStep) ? "v " : (si === curStep ? "> " : "  o ");
            var lbl = stepsPanel.add("statictext", undefined, prefix + STEPS[si]);
            try { lbl.characters = 38; } catch(e) {}
            stepLabels.push(lbl);
        }

        // Progress bar
        pWin.add("panel", undefined, "");
        var barGroup = pWin.add("group");
        barGroup.orientation = "column";
        barGroup.alignChildren = ["fill", "top"];
        barGroup.spacing = 4;
        pBar = barGroup.add("progressbar", [0, 0, 300, 14], 0, 100);
        pBar.value = 5;

        // Status row
        var statusRow = barGroup.add("group");
        statusRow.orientation = "row";
        statusRow.alignChildren = ["left", "center"];
        pStatus = statusRow.add("statictext", undefined, "Dang gui anh len AI...");
        try { pStatus.characters = 36; } catch(e) {}

        pWin.center();
        pWin.show();
        try { pWin.update(); } catch(e) {}
    } catch(eWin) {
        pWin = null;
    }

    // Spinner chars cho step dang chay
    var spinChars = ["-", "\\", "|", "/"];
    var spinIdx = 0;

    // Kiem tra detector moi bao nhieu lan poll (~ moi 3 giay)
    var CHECK_DETECTOR_EVERY = Math.max(1, Math.round(3000 / POLL_MS));
    var maxIter = Math.floor((TIMEOUT_SEC * 1000) / POLL_MS);
    try {
        for (var t = 0; t < maxIter; t++) {
            $.sleep(POLL_MS);
            jsonFile = new File(jsonPath);
            if (jsonFile.exists) {
                var waited = nowMs() - t0;
                $.global.ksAIWaitMs = waited;
                $.global.ksAIWaitPolls = t + 1;
                appendTimingLog(
                    baseName + " | wait | ok | waited=" + waited +
                    "ms | polls=" + (t + 1)
                );
                // Update UI: hoan tat
                if (pWin) {
                    try {
                        if (pBar) pBar.value = 95;
                        if (pStatus) pStatus.text = "Dang doc ket qua...";
                        if (stepLabels && stepLabels[3]) stepLabels[3].text = "v " + STEPS[3];
                        if (stepLabels && stepLabels[4]) stepLabels[4].text = "> " + STEPS[4];
                        pWin.update();
                    } catch(e) {}
                    $.sleep(200); // show brief "hoan tat" state
                }
                return jsonFile;
            }

            // === KIEM TRA DETECTOR CON SONG KHONG (moi ~3s) ===
            // Neu detector bi crash/tat → dung ngay, khong cho het timeout
            if ((t + 1) % CHECK_DETECTOR_EVERY === 0) {
                if (!isDetectorRunning()) {
                    appendTimingLog(baseName + " | wait | ABORT | detector_stopped | t=" + t + " | elapsed=" + (nowMs() - t0) + "ms");
                    if (pWin) {
                        try {
                            if (pBar) pBar.value = 0;
                            if (pStatus) pStatus.text = "Detector da tat!";
                            pWin.update();
                        } catch(e) {}
                        $.sleep(500);
                    }
                    showError("Detector da dung dot ngot — model co the bi loi.\nKiem tra lai Python launcher va thu lai.");
                    return null;
                }
            }

            // Update progress UI
            if (pWin) {
                try {
                    var sec = Math.floor((nowMs() - t0) / 1000);
                    var pct = Math.min(90, Math.round((sec / estSec) * 88) + 5);
                    if (pBar) pBar.value = pct;

                    // Update step indicators
                    spinIdx = (spinIdx + 1) % 4;
                    var spin = spinChars[spinIdx];
                    if (stepLabels) {
                        // Step 0,1 done
                        stepLabels[0].text = "v " + STEPS[0];
                        stepLabels[1].text = ($.global.ksSelCropPath ? "v " : "v ") + STEPS[1];
                        // Step 2: AI phan tich (dang chay)
                        if (sec < estSec - 3) {
                            stepLabels[2].text = spin + " " + STEPS[2];
                            if (pStatus) pStatus.text = "Dang nhan dang 7 views...";
                        } else {
                            // Gan xong → chon sang step 4
                            stepLabels[2].text = "v " + STEPS[2];
                            stepLabels[3].text = spin + " " + STEPS[3];
                            if (pStatus) pStatus.text = "Dang doc H/W...";
                        }
                    }
                    pWin.update();
                } catch(eUp) {}
            }
        }
    } finally {
        if (pWin) {
            try { pWin.close(); } catch(eClose) {}
        }
    }

    appendTimingLog(baseName + " | wait | TIMEOUT " + TIMEOUT_SEC + "s");
    showError("Timeout " + TIMEOUT_SEC + "s — khong nhan duoc JSON tu AI.");
    return null;
}


function activateBackground(doc) {
    try {
        doc.activeLayer = doc.backgroundLayer;
        return true;
    } catch (e) {
        if (doc.layers.length > 0) {
            doc.activeLayer = doc.layers[doc.layers.length - 1];
            return true;
        }
        return false;
    }
}

function setSelectionRect(x1, y1, x2, y2) {
    var desc = new ActionDescriptor();
    var ref = new ActionReference();
    ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
    desc.putReference(charIDToTypeID("null"), ref);

    var r = new ActionDescriptor();
    r.putUnitDouble(charIDToTypeID("Top "), charIDToTypeID("#Pxl"), y1);
    r.putUnitDouble(charIDToTypeID("Left"), charIDToTypeID("#Pxl"), x1);
    r.putUnitDouble(charIDToTypeID("Btom"), charIDToTypeID("#Pxl"), y2);
    r.putUnitDouble(charIDToTypeID("Rght"), charIDToTypeID("#Pxl"), x2);
    desc.putObject(charIDToTypeID("T   "), charIDToTypeID("Rctn"), r);

    executeAction(charIDToTypeID("setd"), desc, DialogModes.NO);
}

function deselectAll() {
    try {
        var desc = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
        desc.putReference(charIDToTypeID("null"), ref);
        desc.putEnumerated(charIDToTypeID("T   "), charIDToTypeID("Ordn"), charIDToTypeID("None"));
        executeAction(charIDToTypeID("setd"), desc, DialogModes.NO);
    } catch (e) {
        try { app.activeDocument.selection.deselect(); } catch (e2) {}
    }
}

function unitToPixels(value) {
    try { return value.as("px"); } catch (e) {}
    return parseFloat(value);
}

function pasteCleanedObjectFile(doc, imagePath, x1, y1) {
    var cleanFile = new File(imagePath);
    if (!cleanFile.exists) return false;

    var cleanDoc = null;
    try {
        cleanDoc = app.open(cleanFile);
        app.activeDocument = cleanDoc;
        cleanDoc.selection.selectAll();
        cleanDoc.selection.copy(true);
        cleanDoc.close(SaveOptions.DONOTSAVECHANGES);
        cleanDoc = null;

        app.activeDocument = doc;
        doc.paste();
        var pastedLayer = doc.activeLayer;
        var bounds = pastedLayer.bounds;
        var currentLeft = unitToPixels(bounds[0]);
        var currentTop = unitToPixels(bounds[1]);
        pastedLayer.translate(x1 - currentLeft, y1 - currentTop);
        return true;
    } catch (e) {
        try {
            if (cleanDoc) cleanDoc.close(SaveOptions.DONOTSAVECHANGES);
        } catch (closeError) {}
        try { app.activeDocument = doc; } catch (activateError) {}
        return false;
    }
}

function copyViewsFromJSON(doc, jsonFile) {
    var t0 = nowMs();
    jsonFile.open("r");
    var jsonContent = jsonFile.read();
    jsonFile.close();
    var tRead = nowMs() - t0;

    var raw = eval("(" + jsonContent + ")");
    var data = null;
    var sheet = null;

    // Format moi: { sheet, views } — format cu: [ ...views ]
    if (raw && raw.views && raw.views.length !== undefined) {
        data = raw.views;
        sheet = raw.sheet || null;
    } else if (raw && raw.length !== undefined) {
        data = raw;
    }

    if (sheet) {
        $.global.ksAISheet = sheet;
        appendTimingLog(
            (typeof $.global.ksAIBaseName !== "undefined" ? $.global.ksAIBaseName : "?") +
            " | sheet | drawing=" + (sheet.drawing_number || "") +
            " | metal=" + (sheet.metal || "") +
            " | brand=" + (sheet.brand || "")
        );
    } else {
        $.global.ksAISheet = null;
    }

    if (!data || data.length === 0) {
        showError("File JSON trong hoac sai dinh dang.");
        return 0;
    }

    var prevRU = app.preferences.rulerUnits;
    var oldDialogs = app.displayDialogs;
    app.preferences.rulerUnits = Units.PIXELS;
    app.displayDialogs = DialogModes.NO;

    var copied = 0;
    var tCopy0 = nowMs();
    try {
        for (var o = 0; o < VIEW_ORDER.length; o++) {
            var targetView = VIEW_ORDER[o];
            var viewData = null;
            for (var i = 0; i < data.length; i++) {
                if (data[i].view_name === targetView) {
                    viewData = data[i];
                    break;
                }
            }
            if (!viewData) continue;

            var bbox = viewData.pixel ? viewData.pixel.object_bbox : null;
            if (!bbox || bbox.length !== 4) continue;

            var x1 = parseInt(bbox[0], 10);
            var y1 = parseInt(bbox[1], 10);
            var x2 = parseInt(bbox[2], 10);
            var y2 = parseInt(bbox[3], 10);
            if (isNaN(x1) || isNaN(y1) || isNaN(x2) || isNaN(y2)) continue;
            if (x2 <= x1 || y2 <= y1) continue;

            var hasQualityContract = (
                viewData.validation &&
                typeof viewData.validation.quality_valid !== "undefined"
            );
            var qualityValid = !hasQualityContract || viewData.validation.quality_valid === true;
            if (!qualityValid) {
                appendTimingLog(baseName + " | skip " + targetView + " | quality_invalid");
                continue;
            }

            var cleanedImage = null;
            if (viewData.output_files && viewData.output_files.object_image) {
                cleanedImage = viewData.output_files.object_image;
            }

            var copiedCleaned = false;
            if (cleanedImage) {
                copiedCleaned = pasteCleanedObjectFile(doc, cleanedImage, x1, y1);
            }

            if (!copiedCleaned) {
                if (hasQualityContract) {
                    appendTimingLog(baseName + " | skip " + targetView + " | clean_file_missing");
                    continue;
                }
                // Tương thích JSON cũ chưa có cleaned crop/quality contract.
                setSelectionRect(x1, y1, x2, y2);
                if (!activateBackground(doc)) {
                    throw new Error("Khong tim thay Background.");
                }
                executeAction(charIDToTypeID("CpTL"), undefined, DialogModes.NO);
            }

            try { doc.activeLayer.name = "View " + (copied + 1); } catch (e) {}
            deselectAll();
            copied++;
        }
    } finally {
        deselectAll();
        app.preferences.rulerUnits = prevRU;
        app.displayDialogs = oldDialogs;
    }
    var tCopy = nowMs() - tCopy0;
    $.global.ksAICopyMs = nowMs() - t0;
    appendTimingLog(
        (typeof $.global.ksAIBaseName !== "undefined" ? $.global.ksAIBaseName : "?") +
        " | copy | views=" + copied + " | read_json=" + tRead +
        "ms | cptl=" + tCopy + "ms | total=" + (nowMs() - t0) + "ms"
    );
    return copied;
}

function readSheetFromJsonFile(jsonFile) {
    try {
        jsonFile.open("r");
        var jsonContent = jsonFile.read();
        jsonFile.close();
        var raw = eval("(" + jsonContent + ")");
        if (raw && raw.sheet) {
            $.global.ksAISheet = raw.sheet;
            return raw.sheet;
        }
    } catch (e) { }
    $.global.ksAISheet = null;
    return null;
}

/** Chi doi JSON + doc sheet — dung truoc Dialog Scale */
function waitOnly(baseName) {
    var t0 = nowMs();
    var jsonFile = waitForAIJson(baseName);
    if (!jsonFile) {
        $.global.ksAIJsonReady = false;
        $.global.ksAISheet = null;
        return null;
    }
    var sheet = readSheetFromJsonFile(jsonFile);
    $.global.ksAIJsonReady = true;
    $.global.ksAIJsonFile = jsonFile.fsName;
    $.global.ksAIWaitOnlyMs = nowMs() - t0;
    appendTimingLog(
        baseName + " | waitOnly | ok | wait=" + ($.global.ksAIWaitMs || 0) +
        "ms | drawing=" + (sheet && sheet.drawing_number ? sheet.drawing_number : "") +
        " | brand=" + (sheet && sheet.brand ? sheet.brand : "") +
        " | total=" + (nowMs() - t0) + "ms"
    );
    return jsonFile;
}

/** Chi copy View — JSON da co san */
function copyOnly(doc, baseName) {
    var t0 = nowMs();
    var jsonPath = getJsonPath(baseName);
    var jsonFile = new File(jsonPath);
    if (!jsonFile.exists) {
        showError("Khong tim thay JSON AI de copy View:\n" + jsonPath);
        $.global.ksScaleAICopied = 0;
        return 0;
    }
    var count = copyViewsFromJSON(doc, jsonFile);
    $.global.ksScaleAICopied = count;
    $.global.ksAICopyOnlyMs = nowMs() - t0;
    appendTimingLog(
        baseName + " | copyOnly | views=" + count +
        " | total=" + (nowMs() - t0) + "ms"
    );
    return count;
}

function waitAndCopy(doc, baseName) {
    var t0 = nowMs();
    var jsonFile = waitForAIJson(baseName);
    if (!jsonFile) {
        $.global.ksScaleAICopied = 0;
        return 0;
    }
    var count = copyViewsFromJSON(doc, jsonFile);
    $.global.ksScaleAICopied = count;
    $.global.ksAIWaitAndCopyMs = nowMs() - t0;
    appendTimingLog(
        baseName + " | waitAndCopy TOTAL | wait=" +
        ($.global.ksAIWaitMs || 0) + "ms | copy=" +
        ($.global.ksAICopyMs || 0) + "ms | total=" + (nowMs() - t0) + "ms"
    );
    showInfo("AI xong.\nJSON: " + jsonFile.name + "\nDa copy " + count + " View tu Background.");
    return count;
}

// ---------------------------------------------------------------
if (app.documents.length === 0) {
    showError("Vui long mo mot buc anh trong Photoshop truoc!");
} else {
    var doc = app.activeDocument;
    var docName = doc.name;
    var baseName = docName.substring(0, docName.lastIndexOf("."));
    if (baseName === "") baseName = docName;

    var phase = getPhase();
    appendTimingLog(baseName + " | phase=" + phase + " | START");

    if (typeof $.global.ksAIBaseName !== "undefined" && $.global.ksAIBaseName) {
        if (phase === "waitOnly" || phase === "copyOnly" || phase === "waitAndCopy") {
            baseName = $.global.ksAIBaseName;
        }
    }

    if (phase === "queue") {
        $.global.ksScaleAICopied = 0;
        $.global.ksAIJsonReady = false;
        queueAIJob(doc, baseName);
    } else if (phase === "waitOnly") {
        waitOnly(baseName);
    } else if (phase === "copyOnly") {
        copyOnly(doc, baseName);
    } else if (phase === "waitAndCopy") {
        waitAndCopy(doc, baseName);
    } else {
        // full: queue + wait + copy
        if (queueAIJob(doc, baseName)) {
            waitAndCopy(doc, baseName);
        } else {
            $.global.ksScaleAICopied = 0;
        }
    }
}
