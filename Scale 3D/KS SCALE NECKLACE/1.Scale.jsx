/**
 * KS SCALE NECKLACE - PHASE 1: SCALE
 * Photoshop CS5+ — Scale workflow
 *
 * Workflow:
 *  1. Gui job AI (queue)
 *  2. Bat buoc co selection tay (do mm / tinh scale%)
 *  3. Doi AI xong (JSON + sheet Drawing/Metal)
 *  4. Dialog: brand / hanger / chain / drawing / mm / huong (H|W) — da prefill tu AI
 *  5. Tinh scalePercent tu selection
 *  6. Copy View 1..7 tu JSON
 *  7. Doi 200 PPI, group View 1..7 + Shape 1/2 (marker, neu co) + scale, fill BG, ungroup
 *     (Shape 1/2 = marker cu Shape 8/9, dung cho Chain/Hanger)
 */

#target photoshop

// ====================================
// 🎛️ CONFIGURATION FLAGS
// ====================================
var CONFIG = {
    enableResolutionChange: true,     // Doi resolution ve 200 PPI
    enableGrouping: true,             // Tao group truoc khi scale
    enableHistoryOptimization: true,  // Giam history states
    enableBatchMove: true,            // Move nhieu layers vao group cung luc
    enableActionManager: true,        // Dung Action Manager (nhanh hon DOM)
    enableAIViews: true,              // Chay AI_AutoDetect test truoc khi thu thap
    showAlerts: false
};

// Suy ra workspace từ vị trí script; không phụ thuộc ổ đĩa hoặc Windows user.
var SCALE_SCRIPT_FOLDER = new File($.fileName).parent;
var PROJECT_ROOT = SCALE_SCRIPT_FOLDER.parent.parent;
var BASE_PY_DIR = PROJECT_ROOT.fsName + "\\PTS CS5 SCRIPT";
var INPUT_DIR = BASE_PY_DIR + "\\input";
var OUTPUT_DIR = PROJECT_ROOT.fsName + "\\Scale 3D\\KS";
var AI_AUTODETECT_TEST = PROJECT_ROOT.fsName + "\\AI_AutoDetect test.jsx";
var TIMING_LOG = BASE_PY_DIR + "\\cache\\timing_log.txt";
var TIMING_SUMMARY = BASE_PY_DIR + "\\cache\\last_run_timing.txt";

// ====================================
// 💾 CACHE STATE — Cache/User_{key}/state.txt (check, drawing, brand, hanger, chain)
// ====================================
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

function getKSNecklaceCacheRoot(scriptFolder) {
    var cacheFolder = new Folder(scriptFolder.fsName + "/Cache");
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

function getKSNecklaceUserCacheFolder(scriptFolder) {
    var cacheRoot = getKSNecklaceCacheRoot(scriptFolder);
    var key = getCacheUserKey();
    var userFolder = new Folder(cacheRoot.fsName + "/User_" + key);
    if (!userFolder.exists) userFolder.create();
    migrateLegacyKSNecklaceStateIfNeeded(cacheRoot, userFolder);
    return userFolder;
}

function getCacheStatePath() {
    var scriptFolder = new File($.fileName).parent;
    var userFolder = getKSNecklaceUserCacheFolder(scriptFolder);
    return userFolder.fsName + "/state.txt";
}

function readCacheState() {
    var state = { check: "false", drawing: "888888", brand: "NONE", hanger: "NONE", chain: "NONE" };
    try {
        var path = getCacheStatePath();
        var f = new File(path);
        if (!f.exists) return state;
        f.open("r");
        var content = f.read();
        f.close();
        if (content) {
            content = content.replace(/\r/g, "");
            var lines = content.split("\n");
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i].replace(/^\s+|\s+$/g, "");
                var eq = line.indexOf("=");
                if (eq > 0) {
                    var key = line.substring(0, eq).replace(/^\s+|\s+$/g, "");
                    var val = line.substring(eq + 1).replace(/^\s+|\s+$/g, "");
                    if (key === "check") state.check = val;
                    if (key === "drawing") state.drawing = val;
                    if (key === "brand") state.brand = val;
                    if (key === "hanger") state.hanger = val;
                    if (key === "chain") state.chain = val;
                }
            }
        }
    } catch (e) { }
    return state;
}

function saveCacheState(state) {
    try {
        var path = getCacheStatePath();
        var f = new File(path);
        var s = state || {};
        var check = (s.check !== undefined) ? String(s.check) : "false";
        var drawing = (s.drawing !== undefined && s.drawing !== "") ? String(s.drawing) : "888888";
        var brand = (s.brand !== undefined) ? String(s.brand) : "NONE";
        var hanger = (s.hanger !== undefined) ? String(s.hanger) : "NONE";
        var chain = (s.chain !== undefined) ? String(s.chain) : "NONE";
        f.open("w");
        f.write("check=" + check + "\n");
        f.write("drawing=" + drawing + "\n");
        f.write("brand=" + brand + "\n");
        f.write("hanger=" + hanger + "\n");
        f.write("chain=" + chain + "\n");
        f.close();
    } catch (e) { }
}

function appendScaleTimingLog(line) {
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
        f.write(ts + " | SCALE | " + line + "\n");
        f.close();
    } catch (e) { }
}

function writeTimingSummary(docName, timing, extraLines) {
    // Ghi ngam file tong — khong alert
    try {
        var f = new File(TIMING_SUMMARY);
        var folder = f.parent;
        if (!folder.exists) folder.create();
        f.open("w");
        f.encoding = "UTF-8";
        var d = new Date();
        var ts = d.getFullYear() + "-" +
            ("0" + (d.getMonth() + 1)).slice(-2) + "-" +
            ("0" + d.getDate()).slice(-2) + " " +
            ("0" + d.getHours()).slice(-2) + ":" +
            ("0" + d.getMinutes()).slice(-2) + ":" +
            ("0" + d.getSeconds()).slice(-2);
        f.write("=== TIMING RUN ===\n");
        f.write("time: " + ts + "\n");
        f.write("doc:  " + docName + "\n");
        f.write("\n--- SCALE steps ---\n");
        f.write(timing.summaryText() + "\n");
        if (extraLines && extraLines.length) {
            f.write("\n--- AI (PS) ---\n");
            for (var i = 0; i < extraLines.length; i++) {
                f.write(extraLines[i] + "\n");
            }
        }
        // Ghep them last detector timing neu co
        try {
            var det = new File(BASE_PY_DIR + "\\cache\\last_detector_timing.json");
            if (det.exists) {
                det.open("r");
                var raw = det.read();
                det.close();
                f.write("\n--- DETECTOR (last_detector_timing.json) ---\n");
                f.write(raw + "\n");
            }
        } catch (e2) { }
        f.write("\n(Chi tiet theo dong: timing_log.txt)\n");
        f.close();

        // Append 1 dong tom tat vao log day du
        appendScaleTimingLog("SUMMARY_FILE written: " + TIMING_SUMMARY);
    } catch (e) { }
}

function makeTimingTracker() {
    return {
        t0: new Date().getTime(),
        last: new Date().getTime(),
        steps: [],
        mark: function (name) {
            var now = new Date().getTime();
            var delta = now - this.last;
            var fromStart = now - this.t0;
            this.steps.push({ name: name, delta: delta, fromStart: fromStart });
            this.last = now;
            appendScaleTimingLog(name + " | step=" + delta + "ms | cum=" + fromStart + "ms");
            return delta;
        },
        summaryText: function () {
            var lines = [];
            for (var i = 0; i < this.steps.length; i++) {
                var s = this.steps[i];
                lines.push(s.name + ": " + s.delta + "ms (cum " + s.fromStart + "ms)");
            }
            lines.push("TOTAL: " + (new Date().getTime() - this.t0) + "ms");
            return lines.join("\n");
        }
    };
}

// ====================================
// 📁 GET HANGER FILES FROM DATA/Hanger — chỉ lấy file có tên không chứa "RULES"
// ====================================
function getHangerFiles(scriptFolder) {
    try {
        var dataFolder = new Folder(scriptFolder.fsName + "/DATA/Hanger");
        if (!dataFolder.exists) {
            return ["NONE"];
        }

        var hangerFiles = ["NONE"];
        var files = dataFolder.getFiles("*.png");

        for (var i = 0; i < files.length; i++) {
            var fileName = files[i].name;
            if (fileName.toUpperCase().indexOf("RULES") >= 0) continue; // bỏ qua file tên có chữ RULES
            var nameWithoutExt = fileName.replace(/\.png$/i, "");
            if (nameWithoutExt) {
                hangerFiles.push(nameWithoutExt);
            }
        }

        return hangerFiles;
    } catch (e) {
        return ["NONE"];
    }
}

// ====================================
// 📁 GET CHAIN FILES — DATA/CHAIN/14K Chain hoặc Silver Chain, chỉ .jpg và .png
// ====================================
function getChainFiles(scriptFolder, brandKey) {
    try {
        var subFolder = "";
        if (brandKey === "14k") subFolder = "14K Chain";
        else if (brandKey === "silver") subFolder = "Silver Chain";
        else return [];

        var chainFolder = new Folder(scriptFolder.fsName + "/DATA/CHAIN/" + subFolder);
        if (!chainFolder.exists) return [];

        var names = [];
        var jpgs = chainFolder.getFiles("*.jpg");
        var pngs = chainFolder.getFiles("*.png");
        for (var i = 0; i < jpgs.length; i++) names.push(jpgs[i].name.replace(/\.(jpg|jpeg)$/i, ""));
        for (var j = 0; j < pngs.length; j++) names.push(pngs[j].name.replace(/\.png$/i, ""));
        return names;
    } catch (e) {
        return [];
    }
}

// ====================================
// 🚀 BATCH MOVE HELPERS
// ====================================
function selectMultipleLayers(doc, layers) {
    if (!layers || layers.length === 0) return false;

    try {
        var desc = new ActionDescriptor();
        var list = new ActionList();

        for (var i = 0; i < layers.length; i++) {
            try {
                var ref = new ActionReference();
                ref.putIdentifier(charIDToTypeID('Lyr '), layers[i].itemIndex);
                list.putReference(ref);
            } catch (e) { }
        }

        if (list.count === 0) return false;

        desc.putList(charIDToTypeID('null'), list);
        executeAction(charIDToTypeID('slct'), desc, DialogModes.NO);

        return true;
    } catch (e) {
        // Fallback: Select bằng layer itemIndex
        try {
            if (layers.length === 0) return false;

            doc.activeLayer = layers[0];

            for (var i = 1; i < layers.length; i++) {
                try {
                    var idslct = charIDToTypeID("slct");
                    var desc = new ActionDescriptor();
                    var ref = new ActionReference();
                    ref.putIdentifier(charIDToTypeID('Lyr '), layers[i].itemIndex);
                    desc.putReference(charIDToTypeID("null"), ref);
                    desc.putEnumerated(stringIDToTypeID("selectionModifier"),
                        stringIDToTypeID("selectionModifierType"),
                        stringIDToTypeID("addToSelection"));
                    executeAction(idslct, desc, DialogModes.NO);
                } catch (e2) { }
            }

            return true;
        } catch (e3) {
            return false;
        }
    }
}

(function () {
    // Khởi tạo cache: check=false (chưa nhập liệu), giữ nguyên drawing, brand, hanger, chain
    var prev = readCacheState();
    saveCacheState({ check: "false", drawing: prev.drawing, brand: prev.brand, hanger: prev.hanger, chain: prev.chain });

    var startTime = new Date().getTime();

    var oldDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;

    try {
        app.playbackDisplayDialogs = DialogModes.NO;
    } catch (e) { }

    try {
        var desc = new ActionDescriptor();
        desc.putBoolean(stringIDToTypeID("state"), false);
        executeAction(stringIDToTypeID("showDialogs"), desc, DialogModes.NO);
    } catch (e) { }

    var prevRU = app.preferences.rulerUnits;

    // ====================================
    // 🚀 PERFORMANCE OPTIMIZATION
    // ====================================
    var savedHistoryStates = app.preferences.maximumHistoryStates;
    if (CONFIG.enableHistoryOptimization) {
        app.preferences.maximumHistoryStates = 5;
    }

    // Tắt UI refresh
    try {
        var idsetd = charIDToTypeID("setd");
        var desc999 = new ActionDescriptor();
        var idnull = charIDToTypeID("null");
        var ref999 = new ActionReference();
        ref999.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("RedU"));
        ref999.putEnumerated(charIDToTypeID("capp"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        desc999.putReference(idnull, ref999);
        var desc998 = new ActionDescriptor();
        desc998.putBoolean(charIDToTypeID("RedU"), false);
        desc999.putObject(charIDToTypeID("T   "), charIDToTypeID("Prpr"), desc998);
        executeAction(idsetd, desc999, DialogModes.NO);
    } catch (e) { }

    try {
        if (!app.documents.length) throw new Error("Không có tài liệu đang mở.");
        var doc = app.activeDocument;

        // Shape 1/2 = marker chain/hanger (truoc day la Shape 8/9)
        var shape1 = null;
        var shape2 = null;

        // ===============================================
        // PHASE 1: SCALE
        // ===============================================

        var timing = makeTimingTracker();
        appendScaleTimingLog("=== START " + doc.name + " ===");

        // ==== BUOC 0: Gui job AI NGAY khi bam script (truoc selection + Dialog) ====
        // START.jsx co the da queue san → bo qua neu ksAIQueued=true
        if (CONFIG.enableAIViews) {
            // Neu START.jsx da queue truoc (ksAIQueued=true) thi bo qua, khong queue lan 2
            if (!$.global.ksAIQueued) {
                var aiScript = new File(AI_AUTODETECT_TEST);
                if (!aiScript.exists) {
                    throw new Error("Khong tim thay AI_AutoDetect test.jsx:\n" + AI_AUTODETECT_TEST);
                }
                $.global.ksScaleSilentAI = true;
                $.global.ksAIPhase = "queue";
                // KHONG reset ksAIQueued=false o day — de tranh conflict voi START.jsx
                try {
                    $.evalFile(aiScript);
                } finally {
                    $.global.ksAIPhase = "";
                }
                if (!$.global.ksAIQueued) {
                    $.global.ksScaleSilentAI = false;
                    throw new Error("Khong gui duoc job AI. Kiem tra Launcher + Detector.");
                }
            }
            // else: ksAIQueued=true → START.jsx da queue roi, bo qua (khong double-queue)
        }
        timing.mark("0_queue_AI");

        // ==== BUOC 1: Bat buoc co selection tay ====
        var b;
        try {
            b = doc.selection.bounds;
        } catch (e) {
            // Da queue AI roi — don job neu user chua co selection
            try {
                var failBase = (typeof $.global.ksAIBaseName !== "undefined" && $.global.ksAIBaseName)
                    ? $.global.ksAIBaseName
                    : doc.name.replace(/\.[^\.]+$/, "");
                var pendingJobFail = new File(INPUT_DIR + "\\" + failBase + ".job.json");
                if (pendingJobFail.exists) pendingJobFail.remove();
            } catch (cleanE) { }
            $.global.ksAIQueued = false;
            throw new Error("Hay tao VUNG CHON (selection) truoc khi chay script.");
        }

        // Luu px ngay (AI/dialog co the clear selection) — dung cho tinh wMM/hMM
        var selLeftPx = b[0].as("px");
        var selTopPx = b[1].as("px");
        var selRightPx = b[2].as("px");
        var selBottomPx = b[3].as("px");
        // Luu theo ruler unit cua document — dung cho doc.crop() chinh xac
        var selLeft   = b[0].value;
        var selTop    = b[1].value;
        var selRight  = b[2].value;
        var selBottom = b[3].value;
        timing.mark("1_selection");

        // ==== EXPORT SELECTION CROP cho AI lan 2 ====
        // Dung doc.duplicate() — an toan hon doc.crop()+flatten()+restore
        // dupDoc hoan toan doc lap, dong lai sau khi save, doc goc khong bi anh huong
        $.global.ksSelCropPath = "";
        $.global.ksSelExpectedDir = "";   // H / W / "" (de AI tu quyet)
        $.global.ksSelNormBbox = [];
        try {
            var docWPx = doc.width.as("px");
            var docHPx = doc.height.as("px");
            if (docWPx > 0 && docHPx > 0) {
                $.global.ksSelNormBbox = [
                    Math.round((selLeftPx / docWPx) * 1000),
                    Math.round((selTopPx / docHPx) * 1000),
                    Math.round((selRightPx / docWPx) * 1000),
                    Math.round((selBottomPx / docHPx) * 1000)
                ];
            }
        } catch (eNorm) {}
        if (CONFIG.enableAIViews) {
            try {
                var selW = selRightPx - selLeftPx;
                var selH = selBottomPx - selTopPx;

                // Gui y chieu mong muon (H/W) dua tren hinh dang vung chon nguoi dung khoanh tay
                if (selH > 0 && selW > 0) {
                    $.global.ksSelExpectedDir = (selH >= selW) ? "H" : "W";
                } else {
                    $.global.ksSelExpectedDir = "";
                }

                if (selW > 10 && selH > 10) {
                    var cropBaseName = (typeof $.global.ksAIBaseName !== "undefined" && $.global.ksAIBaseName)
                        ? $.global.ksAIBaseName
                        : doc.name.replace(/\.[^\.]+$/, "");
                    var cropFileName = cropBaseName + "__sel_crop.jpg";
                    var cropFilePath = INPUT_DIR + "\\" + cropFileName;
                    var cropFile = new File(cropFilePath);

                    // Duplicate doc → crop duplicate chinh xac theo vung chon → flatten → saveAs → close
                    // Doc goc KHONG bi thay doi gi ca
                    var dupDoc = doc.duplicate("_sel_crop_tmp", true);
                    try {
                        app.activeDocument = dupDoc;
                        // Crop chinh xac theo ranh gioi vung chon cua nguoi dung (khong mo rong le)
                        dupDoc.crop([selLeft, selTop, selRight, selBottom]);
                        dupDoc.flatten();
                        var jpgOpts = new JPEGSaveOptions();
                        jpgOpts.quality = 10;
                        jpgOpts.embedColorProfile = false;
                        jpgOpts.formatOptions = FormatOptions.STANDARDBASELINE;
                        dupDoc.saveAs(cropFile, jpgOpts, true, Extension.LOWERCASE);
                        if (cropFile.exists) {
                            $.global.ksSelCropPath = cropFile.fsName;
                        }
                    } catch (cropErr) {
                        $.global.ksSelCropPath = "";
                    } finally {
                        // Dong dupDoc, tra active doc ve doc goc
                        try { dupDoc.close(SaveOptions.DONOTSAVECHANGES); } catch(cE) {}
                        try { app.activeDocument = doc; } catch(rE) {}
                    }
                }
            } catch (cropOuterErr) {
                $.global.ksSelCropPath = "";
            }
        }
        timing.mark("1c_sel_crop");



        var scriptFile = new File($.fileName);
        var scriptFolder = scriptFile.parent;
        var hangerFiles = getHangerFiles(scriptFolder);
        timing.mark("1b_hanger_list");

        // ==== BUOC 2: Doi AI xong (JSON + sheet) TRUOC Dialog ====
        if (CONFIG.enableAIViews) {
            var aiScriptWait = new File(AI_AUTODETECT_TEST);
            if (!aiScriptWait.exists) {
                throw new Error("Khong tim thay AI_AutoDetect test.jsx:\n" + AI_AUTODETECT_TEST);
            }
            $.global.ksScaleSilentAI = true;
            $.global.ksAIPhase = "waitOnly";
            $.global.ksAIJsonReady = false;
            try {
                $.evalFile(aiScriptWait);
            } finally {
                $.global.ksAIPhase = "";
                $.global.ksScaleSilentAI = false;
            }
            if (!$.global.ksAIJsonReady) {
                throw new Error("AI chua tra JSON. Kiem tra Launcher + LM Studio.");
            }
        }
        timing.mark("2_wait_AI");

        // ==== BUOC 3: Dialog (AI da xong — prefill Drawing + Metal) ====
        /** Co Shape 2 (marker layout 9, cu Shape 9) → Hanger mo. */
        function docHasLayerNamedLayer9(container) {
            try {
                var L = container.layers;
                for (var i = 0; i < L.length; i++) {
                    var ly = L[i];
                    if (ly.typename === "ArtLayer") {
                        if (ly.name === "Shape 2") return true;
                    }
                    if (ly.typename === "LayerSet" && docHasLayerNamedLayer9(ly)) return true;
                }
            } catch (e) {}
            return false;
        }

        /** Doc sheet tu AI (uu tien $.global.ksAISheet sau waitOnly). */
        function tryReadAISheet() {
            try {
                if (typeof $.global.ksAISheet !== "undefined" && $.global.ksAISheet) {
                    return $.global.ksAISheet;
                }
                var bn = (typeof $.global.ksAIBaseName !== "undefined" && $.global.ksAIBaseName)
                    ? $.global.ksAIBaseName
                    : doc.name.replace(/\.[^\.]+$/, "");
                var jf = new File(OUTPUT_DIR + "\\" + bn + "_all_views_result.json");
                if (!jf.exists) return null;
                jf.open("r");
                var txt = jf.read();
                jf.close();
                var raw = eval("(" + txt + ")");
                if (raw && raw.sheet) {
                    $.global.ksAISheet = raw.sheet;
                    return raw.sheet;
                }
            } catch (eRead) { }
            return null;
        }

        function showAutoStatusPalette(drawingValue, brandVal, mmValue, dir, aiW, aiH) {
            try {
                if (typeof $.global.ksStatusWin !== "undefined" && $.global.ksStatusWin) {
                    try { $.global.ksStatusWin.close(); } catch (eClose) {}
                }

                var win = new Window("palette", "AI Auto Detector — Progress Status");
                win.orientation = "column";
                win.alignChildren = "fill";
                win.spacing = 8;
                win.margins = 14;

                var title = win.add("statictext", undefined, "⚡ AI DETECTOR — ĐANG XỬ LÝ...");
                title.alignment = "center";
                try { title.graphics.font = ScriptUI.newFont("Segoe UI", "BOLD", 12); } catch (e) {}

                var pnl = win.add("panel", undefined, " Thông số AI ");
                pnl.orientation = "column";
                pnl.alignChildren = "left";
                pnl.spacing = 4;
                pnl.margins = 10;

                pnl.add("statictext", undefined, "• Mã bản vẽ (Drawing) : " + (drawingValue || "888888"));
                
                var brandDisplay = (brandVal === "14k") ? "14K" : (brandVal === "silver" ? "Silver (925)" : (brandVal === "labgrown" ? "Lab Grown" : "NONE"));
                pnl.add("statictext", undefined, "• Chất liệu (Metal/Brand) : " + brandDisplay);

                var dirDisplay = (dir === "H") ? "Chiều cao (H)" : ((dir === "W") ? "Chiều ngang (W)" : "Tỉ lệ RD");
                pnl.add("statictext", undefined, "• Kích thước Scale    : " + mmValue + " mm (" + dirDisplay + ")");

                if (aiW > 0 || aiH > 0) {
                    pnl.add("statictext", undefined, "• Chi tiết AI           : W=" + (aiW || 0) + "mm | H=" + (aiH || 0) + "mm");
                }

                var lblStatus = win.add("statictext", undefined, "⏳ Đang tự động thực thi quy trình...");
                lblStatus.alignment = "center";

                win.center();
                win.show();
                win.update();
                app.refresh();

                $.global.ksStatusWin = win;
            } catch (eErr) {}
        }

        function autoGetDirectionResult(layoutHasLayer9) {
            var sheet = tryReadAISheet() || {};
            var drawingValue = sheet.drawing_number ? String(sheet.drawing_number) : (prev.drawing || "888888");

            var brandVal = "NONE";
            if (sheet.brand) {
                var b = String(sheet.brand).toLowerCase();
                if (b === "silver" || sheet.metal === "925") brandVal = "silver";
                else if (b === "14k" || String(sheet.metal || "").toUpperCase() === "14K") brandVal = "14k";
                else if (b === "labgrown") brandVal = "labgrown";
            }

            var aiW = parseFloat(sheet.front_width_mm || 0);
            var aiH = parseFloat(sheet.front_height_mm || 0);
            var aiDir = sheet.scale_direction ? String(sheet.scale_direction).toUpperCase() : "";

            var dir = aiDir;
            var suggestMm = 0;

            if (dir === "H" && aiH > 0) {
                suggestMm = aiH;
            } else if (dir === "W" && aiW > 0) {
                suggestMm = aiW;
            } else if (aiH > 0) {
                dir = "H";
                suggestMm = aiH;
            } else if (aiW > 0) {
                dir = "W";
                suggestMm = aiW;
            } else {
                if (typeof selH !== "undefined" && typeof selW !== "undefined" && selW > 0) {
                    dir = (selH / selW > 1.2) ? "H" : "W";
                } else {
                    dir = "H";
                }
                suggestMm = 17.2;
            }

            var mmValue = String(Math.round(suggestMm * 100) / 100);

            // Bảng hiển thị thông số không gây gián đoạn (palette) hiển thị trên màn hình suốt quá trình chạy
            showAutoStatusPalette(drawingValue, brandVal, mmValue, dir, aiW, aiH);

            saveCacheState({
                check: "true",
                drawing: drawingValue,
                brand: brandVal,
                hanger: "NONE",
                chain: "NONE"
            });

            return {
                dir: dir,
                def: mmValue,
                brand: brandVal,
                drawing: drawingValue,
                chain: "NONE"
            };
        }

        function showDirectionDialog(layoutHasLayer9) {
            var dlg = new Window("dialog", "Chế độ Scale Necklace KS");
            dlg.orientation = "column";
            dlg.alignChildren = "fill";
            dlg.spacing = 6;
            dlg.margins = 12;

            // Phần chọn brand (radio button - chỉ chọn 1) - đặt lên trước
            var brandTitle = dlg.add("statictext", undefined, "Chọn chất liệu:");
            var brandGroup = dlg.add("group");
            brandGroup.orientation = "row";
            brandGroup.spacing = 8;
            brandGroup.alignment = "center";

            // Tạo radio button group để chỉ cho chọn 1
            var brandRadioGroup = brandGroup.add("panel");
            brandRadioGroup.orientation = "row";
            brandRadioGroup.spacing = 8;
            brandRadioGroup.alignment = "center";
            brandRadioGroup.margins = 4;

            var brandEmpty = brandRadioGroup.add("radiobutton", undefined, "Empty");
            var brand14K = brandRadioGroup.add("radiobutton", undefined, "14K");
            var brandSilver = brandRadioGroup.add("radiobutton", undefined, "Silver (925)");
            var brandLabGrown = brandRadioGroup.add("radiobutton", undefined, "Lab Grown");

            // Set Empty là mặc định
            brandEmpty.value = true;

            // Hanger + Chain cùng hàng (layout 9 view → Hanger bị làm mờ, không ẩn)
            var hangerRow = dlg.add("group");
            hangerRow.orientation = "row";
            hangerRow.spacing = 7;
            hangerRow.alignment = "fill";
            var hangerGroup = hangerRow.add("group");
            hangerGroup.orientation = "row";
            hangerGroup.spacing = 7;
            hangerGroup.alignment = "left";
            var hangerLabel = hangerGroup.add("statictext", undefined, "Hanger :");
            hangerLabel.preferredSize.width = 58;
            var hangerDropdown = hangerGroup.add("dropdownlist", undefined, hangerFiles);
            hangerDropdown.selection = 0; // Luôn NONE khi mở dialog
            hangerDropdown.preferredSize.width = 100;
            var chainGroup = hangerRow.add("group");
            chainGroup.orientation = "row";
            chainGroup.spacing = 0;
            chainGroup.alignment = "left";
            var chainLabel = chainGroup.add("statictext", undefined, "Chain :");
            chainLabel.preferredSize.width = 38;
            var chainDropdown = chainGroup.add("dropdownlist", undefined, []);
            chainDropdown.preferredSize.width = 100;

            // Hanger + Chain: làm mờ khi Empty (cả hai); Chain thêm làm mờ khi Lab Grown
            var chainFiles = []; // list tên file cho dropdown hiện tại
            function updateChainUI() {
                var brand = getSelectedBrand();
                var hangerSelectable = !layoutHasLayer9; // 9 view → luôn mờ Hanger (trừ khi Empty đã tắt cả hàng)
                if (brand === "NONE") {
                    hangerGroup.enabled = false;
                    chainGroup.enabled = false;
                    chainFiles = ["NONE"];
                    chainDropdown.removeAll();
                    chainDropdown.add("item", "NONE");
                    chainDropdown.selection = 0;
                } else {
                    hangerGroup.enabled = hangerSelectable;
                    if (brand === "labgrown") {
                        chainGroup.enabled = false;
                        chainFiles = ["NONE"];
                        chainDropdown.removeAll();
                        chainDropdown.add("item", "NONE");
                        chainDropdown.selection = 0;
                    } else {
                        chainGroup.enabled = true;
                        chainFiles = getChainFiles(scriptFolder, brand);
                        chainDropdown.removeAll();
                        for (var i = 0; i < chainFiles.length; i++) chainDropdown.add("item", chainFiles[i]);
                        chainDropdown.selection = chainFiles.length > 0 ? 0 : -1;
                    }
                }
            }
            updateChainUI(); // ban đầu Empty -> Hanger + Chain bị làm mờ

            brandEmpty.onClick = function () { updateChainUI(); };
            brand14K.onClick = function () { updateChainUI(); };
            brandSilver.onClick = function () { updateChainUI(); };
            brandLabGrown.onClick = function () { updateChainUI(); };

            // Phần nhập Drawing và mm (chia đều 2 cột)
            var inputRowGroup = dlg.add("group");
            inputRowGroup.orientation = "row";
            inputRowGroup.spacing = 8;
            inputRowGroup.alignment = "fill";

            // Cột 1: Drawing
            var drawingGroup = inputRowGroup.add("group");
            drawingGroup.orientation = "row";
            drawingGroup.spacing = 8;
            drawingGroup.alignment = "left";
            var drawingLabel = drawingGroup.add("statictext", undefined, "Drawing :");
            drawingLabel.preferredSize.width = 58;
            var drawingInput = drawingGroup.add("edittext", undefined, "");
            drawingInput.preferredSize.width = 100;

            // Cột 2: mm
            var mmGroup = inputRowGroup.add("group");
            mmGroup.orientation = "row";
            mmGroup.spacing = 8;
            mmGroup.alignment = "left";
            var mmLabel = mmGroup.add("statictext", undefined, "mm :");
            var mmInput = mmGroup.add("edittext", undefined, "17.2");
            mmInput.preferredSize.width = 100;
            mmInput.active = true;

            // Hint AI sheet (drawing / metal)
            var aiHint = dlg.add("statictext", undefined, "AI: dang doc Drawing + Metal...");
            try { aiHint.characters = 52; } catch (eHint) { }

            // Phần chọn chiều scale
            var scaleTitle = dlg.add("statictext", undefined, "Scale theo chiều nào?");
            var g = dlg.add("group");
            g.orientation = "row";
            g.alignment = "center";
            g.spacing = 8;
            var rs = null;

            // Hàm lấy brand đã chọn
            function getSelectedBrand() {
                if (brand14K.value) {
                    return "14k";
                } else if (brandSilver.value) {
                    return "silver";
                } else if (brandLabGrown.value) {
                    return "labgrown";
                } else {
                    // Empty hoặc không chọn gì thì lưu "NONE"
                    return "NONE";
                }
            }

            function applySheetToDialog(sheet, fromLate, applyBrand) {
                if (!sheet) return false;
                if (applyBrand === undefined) applyBrand = true;
                var applied = false;
                var dn = sheet.drawing_number ? String(sheet.drawing_number) : "";
                if (dn && (!drawingInput.text || drawingInput.text === "")) {
                    drawingInput.text = dn;
                    applied = true;
                }
                if (applyBrand) {
                    var b = sheet.brand ? String(sheet.brand).toLowerCase() : "";
                    if (b === "silver" || sheet.metal === "925") {
                        brandSilver.value = true;
                        brandEmpty.value = false;
                        brand14K.value = false;
                        brandLabGrown.value = false;
                        applied = true;
                    } else if (b === "14k" || String(sheet.metal || "").toUpperCase() === "14K") {
                        brand14K.value = true;
                        brandEmpty.value = false;
                        brandSilver.value = false;
                        brandLabGrown.value = false;
                        applied = true;
                    }
                    updateChainUI();
                }

                // === PREFILL mm + preset nút H/W từ AI lần 2 ===
                // Dung parseFloat truc tiep — tranh loi falsy 0.0 trong JS
                var aiW  = parseFloat(sheet.front_width_mm  || 0);
                var aiH  = parseFloat(sheet.front_height_mm || 0);
                var aiDir = sheet.scale_direction ? String(sheet.scale_direction).toUpperCase() : "";
                var aiConf = sheet.dim_confidence ? String(sheet.dim_confidence) : "";

                // Chi can chieu dang dung > 0 la du de prefill
                // (Vi du: user chon vung H, AI tra W=0 H=10.5 → suggestMm=10.5 ✓)
                var suggestMm = (aiDir === "H") ? aiH : aiW;
                if (suggestMm > 0) {
                    // Chỉ prefill nếu ô mm còn mặc định (chưa nhập tay)
                    if (!mmInput.text || mmInput.text === "17.2" || mmInput.text === "") {
                        mmInput.text = String(Math.round(suggestMm * 100) / 100);
                        applied = true;
                    }

                    // Preset nút scale_direction
                    if (aiDir === "H" && typeof btnH !== "undefined") {
                        try { btnH.active = true; } catch(e) {}
                    } else if (typeof btnW !== "undefined") {
                        try { btnW.active = true; } catch(e) {}
                    }
                }


                // Cập nhật hint text với đầy đủ thông tin
                if (aiHint) {
                    var hint = "AI: Drawing=" + (dn || "?") +
                        " | Metal=" + (sheet.metal || "?") +
                        (sheet.metal_weight ? (" (" + sheet.metal_weight + ")") : "");
                    if (suggestMm > 0) {
                        hint += " | W=" + (aiW || "?") + " H=" + (aiH || "?") + " \u2192" + (aiDir || "?");
                        if (aiConf) hint += " [" + aiConf + "]";
                    }
                    if (fromLate) hint += " [da dien]";
                    aiHint.text = hint;
                }

                return applied;
            }

            // Prefill tu AI (da wait xong truoc Dialog)
            var earlySheet = tryReadAISheet();
            if (earlySheet) applySheetToDialog(earlySheet, false, true);
            else if (aiHint) aiHint.text = "AI: khong doc duoc Drawing/Metal — nhap tay";


            // Hàm đóng dialog và set kết quả
            function closeDialog(dir) {
                var drawingValue = drawingInput.text || "";
                if (drawingValue === "") {
                    drawingValue = "888888";
                }
                var mmValue = mmInput.text || "";

                // Kiểm tra nếu chưa nhập mm hoặc giá trị không hợp lệ
                if (mmValue === "" || mmValue === null || isNaN(mmValue) || parseFloat(mmValue) <= 0) {
                    alert("❌ LỖI: Vui lòng nhập giá trị mm hợp lệ!\n\n" +
                        "Giá trị phải là số lớn hơn 0.\n" +
                        "Ví dụ: 4.00, 17.2, 10.5");
                    // Focus vào ô mm để người dùng nhập lại
                    mmInput.active = true;
                    return; // Không đóng dialog, yêu cầu nhập lại
                }

                // Lấy Hanger đã chọn (NONE khi Empty, layout 9 view — Hanger mờ, hoặc Lab Grown chỉ tắt Chain)
                var hangerText = "NONE";
                if (hangerGroup.enabled) {
                    var sel = hangerDropdown.selection;
                    if (sel != null) {
                        var idx = (typeof sel === "number") ? sel : (sel.index !== undefined ? sel.index : 0);
                        if (idx >= 0 && idx < hangerFiles.length) {
                            hangerText = hangerFiles[idx];
                        } else if (sel.text) {
                            hangerText = sel.text;
                        }
                    }
                }
                var chainText = "NONE";
                var chainIdx = -1;
                if (chainDropdown.selection != null) {
                    if (typeof chainDropdown.selection === "number") chainIdx = chainDropdown.selection;
                    else if (chainDropdown.selection.index !== undefined) chainIdx = chainDropdown.selection.index;
                }
                if (chainGroup.enabled && chainFiles.length > 0 && chainIdx >= 0 && chainIdx < chainFiles.length) {
                    chainText = chainFiles[chainIdx];
                }
                saveCacheState({
                    check: "true",
                    drawing: drawingValue,
                    brand: getSelectedBrand(),
                    hanger: hangerText,
                    chain: chainText
                });

                rs = {
                    dir: dir,
                    def: mmValue,
                    brand: getSelectedBrand(),
                    drawing: drawingValue,
                    chain: chainText
                };
                dlg.close();
            }

            var btnH = g.add("button", undefined, "Chiều cao (H)");
            btnH.onClick = function () {
                closeDialog("H");
            };

            var btnW = g.add("button", undefined, "Chiều ngang (W)");
            btnW.onClick = function () {
                closeDialog("W");
            };

            var btnRing = g.add("button", undefined, "Tỉ lệ RD");
            btnRing.onClick = function () {
                closeDialog("RD");  // RD = scale theo min(H,W) — đường kính đều
            };

            dlg.center();
            dlg.show();

            return rs;
        }

        var layoutHasLayer9 = docHasLayerNamedLayer9(doc);
        var dirRes;
        if (typeof $.global.ksScaleAuto !== "undefined" && $.global.ksScaleAuto) {
            dirRes = autoGetDirectionResult(layoutHasLayer9);
        } else {
            dirRes = showDirectionDialog(layoutHasLayer9);
        }
        timing.mark("3_dialog");
        if (!dirRes) {
            // User huy Dialog: khong wait/copy View; don job neu chua bi detector nhan
            try {
                var cancelBase = (typeof $.global.ksAIBaseName !== "undefined" && $.global.ksAIBaseName)
                    ? $.global.ksAIBaseName
                    : doc.name.replace(/\.[^\.]+$/, "");
                var pendingJob = new File(INPUT_DIR + "\\" + cancelBase + ".job.json");
                if (pendingJob.exists) pendingJob.remove();
                // JSON neu AI da xong van ok — lan sau queue se xoa truoc khi gui lai
            } catch (cancelErr) { }
            $.global.ksScaleSilentAI = false;
            $.global.ksAIPhase = "";
            $.global.ksAIQueued = false;
            saveCacheState({
                check: "false",
                drawing: prev.drawing,
                brand: prev.brand,
                hanger: prev.hanger,
                chain: prev.chain
            });
            appendScaleTimingLog("CANCEL dialog | " + timing.summaryText().replace(/\n/g, " | "));
            return; // thoat em, khong throw
        }

        var drawingValue = dirRes.drawing || "888888";

        // ==== BUOC 4: Tinh scale% tu selection da luu ====
        var res = doc.resolution;
        function pxToMM(px) {
            return (px / res) * 25.4;
        }

        var wMM = pxToMM(selRightPx - selLeftPx);
        var hMM = pxToMM(selBottomPx - selTopPx);
        // RD = tỉ lệ đường kính: lấy chiều nhỏ hơn (min) để scale đều tròn
        var measured;
        if (dirRes.dir === "H") {
            measured = hMM;
        } else if (dirRes.dir === "RD") {
            measured = Math.min(wMM, hMM);
        } else {
            measured = wMM; // "W"
        }

        if (measured <= 0) throw new Error("Vung chon qua nho / khong hop le.");

        var realInput = dirRes.def;
        if (realInput == null || realInput === "" || isNaN(realInput)) {
            throw new Error("Giá trị mm không hợp lệ.");
        }
        var real = parseFloat(realInput);
        var scalePercent = (real / measured) * 100;
        timing.mark("4_calc_scale");

        // ==== BUOC 5: Copy View tu JSON AI (da wait truoc Dialog) ====
        if (CONFIG.enableAIViews) {
            var aiScriptCopy = new File(AI_AUTODETECT_TEST);
            $.global.ksScaleSilentAI = true;
            $.global.ksAIPhase = "copyOnly";
            $.global.ksScaleAICopied = 0;
            try {
                $.evalFile(aiScriptCopy);
            } finally {
                $.global.ksAIPhase = "";
                $.global.ksScaleSilentAI = false;
            }
            if (!$.global.ksScaleAICopied || $.global.ksScaleAICopied < 7) {
                throw new Error(
                    "AI khong tao du 7 View sach. Kiem tra quality JSON, Launcher va LM Studio."
                );
            }
        }
        timing.mark("5_copy_AI");

        // ==== BUOC 6: Doi resolution ve 200ppi ====
        if (CONFIG.enableResolutionChange) {
            try {
                doc.resizeImage(undefined, undefined, 200);
            } catch (e) { }
        }
        timing.mark("6_resolution_200");

        // ==== BUOC 7: Thu thap View 1..7 + Shape 1/2 (marker) ====
        var want = {
            "View 1": 1, "View 2": 1, "View 3": 1, "View 4": 1,
            "View 5": 1, "View 6": 1, "View 7": 1,
            "Shape 1": 1, "Shape 2": 1
        };
        var list = [];

        function walk(container) {
            var L = container.layers;
            for (var i = 0; i < L.length; i++) {
                var ly = L[i];
                if (ly.typename === "ArtLayer") {
                    if (want[ly.name]) list.push(ly);
                } else if (ly.typename === "LayerSet") {
                    walk(ly);
                }
            }
        }

        walk(doc);
        if (list.length === 0) {
            throw new Error("Khong tim thay View 1..7 / Shape 1/2 de scale.");
        }

        for (var i = 0; i < list.length; i++) {
            var name = list[i].name;
            if (name === "Shape 1") shape1 = list[i];
            if (name === "Shape 2") shape2 = list[i];
        }
        timing.mark("7_collect_views");

        // ==== BUOC 8: Group View + scale ====
        var grp;

        if (CONFIG.enableGrouping && CONFIG.enableBatchMove) {
            var batchSuccess = false;
            try {
                if (selectMultipleLayers(doc, list)) {
                    executeAction(stringIDToTypeID('groupLayersEvent'), undefined, DialogModes.NO);
                    grp = doc.activeLayer;
                    grp.name = "Shapes + Layer 1";
                    batchSuccess = true;
                }
            } catch (e) {
                batchSuccess = false;
            }

            if (!batchSuccess) {
                grp = doc.layerSets.add();
                grp.name = "Shapes + Layer 1";
                for (var k = list.length - 1; k >= 0; k--) {
                    try {
                        list[k].move(grp, ElementPlacement.INSIDE);
                    } catch (e) { }
                }
            }
        } else if (CONFIG.enableGrouping) {
            grp = doc.layerSets.add();
            grp.name = "Shapes + Layer 1";
            for (var k = list.length - 1; k >= 0; k--) {
                try {
                    list[k].move(grp, ElementPlacement.INSIDE);
                } catch (e) { }
            }
        }

        if (grp) {
            try {
                grp.resize(scalePercent, scalePercent, AnchorPosition.MIDDLECENTER);
            } catch (e) {
                throw new Error("Không thể scale group: " + e.message);
            }
        }
        timing.mark("8_group_scale");

        // ==== BUOC 9: Fill Background trang ====
        var bg;
        try {
            bg = doc.backgroundLayer;
        } catch (e) {
            throw new Error("File khong co Background layer.");
        }
        doc.activeLayer = bg;

        if (CONFIG.enableActionManager) {
            try {
                var idsetd = charIDToTypeID("setd");
                var desc = new ActionDescriptor();
                var ref = new ActionReference();
                ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
                desc.putReference(charIDToTypeID("null"), ref);
                desc.putEnumerated(charIDToTypeID("T   "), charIDToTypeID("Ordn"), charIDToTypeID("Al  "));
                executeAction(idsetd, desc, DialogModes.NO);
            } catch (e) {
                doc.selection.selectAll();
            }

            try {
                var idFl = charIDToTypeID("Fl  ");
                var descFl = new ActionDescriptor();
                descFl.putEnumerated(charIDToTypeID("Usng"), charIDToTypeID("FlCn"), charIDToTypeID("Wht "));
                descFl.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), 100);
                descFl.putEnumerated(charIDToTypeID("Md  "), charIDToTypeID("BlnM"), charIDToTypeID("Nrml"));
                executeAction(idFl, descFl, DialogModes.NO);
            } catch (e) {
                var white = new SolidColor();
                white.rgb.red = 255;
                white.rgb.green = 255;
                white.rgb.blue = 255;
                doc.selection.fill(white);
            }

            try {
                var idsetd2 = charIDToTypeID("setd");
                var desc2 = new ActionDescriptor();
                var ref2 = new ActionReference();
                ref2.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
                desc2.putReference(charIDToTypeID("null"), ref2);
                desc2.putEnumerated(charIDToTypeID("T   "), charIDToTypeID("Ordn"), charIDToTypeID("None"));
                executeAction(idsetd2, desc2, DialogModes.NO);
            } catch (e) {
                doc.selection.deselect();
            }
        } else {
            doc.selection.selectAll();
            var whiteDom = new SolidColor();
            whiteDom.rgb.red = 255;
            whiteDom.rgb.green = 255;
            whiteDom.rgb.blue = 255;
            doc.selection.fill(whiteDom);
            doc.selection.deselect();
        }
        timing.mark("9_fill_bg");

        // ==== BUOC 10: Doi View ra khoi group, xoa group ====
        function findGroupByName(name) {
            for (var gi = 0; gi < doc.layerSets.length; gi++) {
                if (doc.layerSets[gi].name === name) return doc.layerSets[gi];
            }
            return null;
        }

        function moveNamedLayerOutOfGroup(group, layerName) {
            if (!group) return false;
            try {
                for (var mi = 0; mi < group.layers.length; mi++) {
                    if (group.layers[mi].name === layerName) {
                        group.layers[mi].move(group, ElementPlacement.PLACEAFTER);
                        return true;
                    }
                }
            } catch (e) { }
            return false;
        }

        var viewsGroup = grp || findGroupByName("Shapes + Layer 1");
        if (viewsGroup) {
            for (var vi = 1; vi <= 7; vi++) {
                moveNamedLayerOutOfGroup(viewsGroup, "View " + vi);
            }
            // Marker Chain/Hanger (cu Shape 8/9)
            moveNamedLayerOutOfGroup(viewsGroup, "Shape 1");
            moveNamedLayerOutOfGroup(viewsGroup, "Shape 2");
            try {
                viewsGroup.remove();
            } catch (e) { }
        }
        timing.mark("10_ungroup_views");

        // Zoom
        app.runMenuItem(stringIDToTypeID('fitOnScreen'));
        app.runMenuItem(stringIDToTypeID('actualPixels'));
        timing.mark("11_zoom");

        // Tính thời gian thực thi
        var endTime = new Date().getTime();
        var executionTime = (endTime - startTime) / 1000;

        var aiDetail =
            "AI queue=" + ($.global.ksAIQueueMs || "?") + "ms" +
            " wait=" + ($.global.ksAIWaitMs || "?") + "ms" +
            " copy=" + ($.global.ksAICopyMs || "?") + "ms" +
            " mode=" + ($.global.ksAIQueueMode || "?");
        appendScaleTimingLog("DONE | " + aiDetail);
        appendScaleTimingLog(timing.summaryText().replace(/\n/g, " || "));
        writeTimingSummary(doc.name, timing, [
            aiDetail,
            "wait_polls=" + ($.global.ksAIWaitPolls || "?"),
            "views_copied=" + ($.global.ksScaleAICopied || 0)
        ]);

        // Thông báo kết quả (khong hien timing — timing chi ghi file ngam)
        if (CONFIG.showAlerts) {
            var message = "✅ HOÀN THÀNH PHASE 1 - SCALE!\n\n";
            message += "📏 Scale: " + scalePercent.toFixed(2) + "%\n";
            message += "📐 Số đo thật: " + real + "mm\n";
            message += "🎯 Hướng: " + (dirRes.dir === "H" ? "Chiều cao" : "Chiều ngang") + "\n";
            message += "🖼️ Resolution: " + (CONFIG.enableResolutionChange ? "200 PPI" : doc.resolution + " PPI") + "\n";
            message += "✅ Đã scale View và dời View ra khỏi group\n";
            if (shape1) message += "✅ Có Shape 1 (marker Chain/Hanger)\n";
            if (shape2) message += "✅ Có Shape 2 (marker Chain/Hanger)\n";
            message += "\n⏱️ Thời gian: " + executionTime.toFixed(2) + " giây\n";
            alert(message);
        }

    } catch (e) {
        if (CONFIG.showAlerts) alert("❌ LỖI PHASE 1: " + e.message);
        else alert("Loi Scale: " + e.message);
    } finally {
        // BẬT LẠI UI REFRESH
        try {
            var idsetd = charIDToTypeID("setd");
            var desc999 = new ActionDescriptor();
            var idnull = charIDToTypeID("null");
            var ref999 = new ActionReference();
            ref999.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("RedU"));
            ref999.putEnumerated(charIDToTypeID("capp"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            desc999.putReference(idnull, ref999);
            var desc998 = new ActionDescriptor();
            desc998.putBoolean(charIDToTypeID("RedU"), true);
            desc999.putObject(charIDToTypeID("T   "), charIDToTypeID("Prpr"), desc998);
            executeAction(idsetd, desc999, DialogModes.NO);
        } catch (e) { }

        // Restore history states
        if (CONFIG.enableHistoryOptimization) {
            try {
                app.preferences.maximumHistoryStates = savedHistoryStates;
            } catch (e) { }
        }

        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = prevRU;

        try {
            app.playbackDisplayDialogs = DialogModes.ALL;
        } catch (e) { }
    }
})();
