import sys
import os
import re
from pathlib import Path

PROJECT_DIR = r"E:\CODE\SciptAuto=AI\AI Super\AI PTS"

def main():
    tests_summary = {"passed": 0, "failed": 0, "blocked": 0}
    findings = []

    print("=== STARTING QA VERIFICATION FOR JOB part4-photoshop-paths-clean-crops ===")

    # -------------------------------------------------------------------------
    # TEST 1: Path Audit - Check no hardcoded 'd:\CODE\Agent' or 'pvhan' in active files
    # -------------------------------------------------------------------------
    active_files = [
        os.path.join(PROJECT_DIR, "AI_AutoDetect test.jsx"),
        os.path.join(PROJECT_DIR, "PTS CS5 SCRIPT", "headless_detector.py"),
        os.path.join(PROJECT_DIR, "PTS CS5 SCRIPT", "start_watcher.bat"),
        os.path.join(PROJECT_DIR, "PTS CS5 SCRIPT", "start_watcher.vbs"),
        os.path.join(PROJECT_DIR, "Scale 3D", "KS SCALE NECKLACE", "1.Scale.jsx"),
        os.path.join(PROJECT_DIR, "Scale 3D", "KS SCALE NECKLACE", "START.jsx"),
        os.path.join(PROJECT_DIR, "Scale 3D", "KS SCALE NECKLACE", "START to Stroke.jsx")
    ]

    hardcoded_found = False
    for filepath in active_files:
        if not os.path.exists(filepath):
            print(f"[SKIP/BLOCKED] File not found: {filepath}")
            tests_summary["blocked"] += 1
            continue

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if re.search(r"d:\\CODE\\Agent\\AutoNhanDangAnh", content, re.IGNORECASE) or re.search(r"C:\\Users\\pvhan", content, re.IGNORECASE):
            hardcoded_found = True
            print(f"[FAIL] Hardcoded path found in: {filepath}")
            findings.append({
                "severity": "P0",
                "title": f"Hardcoded path d:\\CODE\\Agent or pvhan remaining in active file",
                "file": filepath,
                "line": None,
                "evidence": "Path matching d:\\CODE\\Agent or pvhan found",
                "reproduction": f"Search for d:\\CODE\\Agent in {filepath}"
            })

    if not hardcoded_found:
        tests_summary["passed"] += 1
        print("[PASS] Test 1: All active files clean of hardcoded D:\\CODE\\Agent and pvhan paths")
    else:
        tests_summary["failed"] += 1

    # -------------------------------------------------------------------------
    # TEST 2: Dynamic Project Root Resolution in JSX files
    # -------------------------------------------------------------------------
    jsx_auto_detect = os.path.join(PROJECT_DIR, "AI_AutoDetect test.jsx")
    with open(jsx_auto_detect, "r", encoding="utf-8", errors="ignore") as f:
        auto_content = f.read()

    if "$.fileName" in auto_content and "Scale 3D" in auto_content:
        tests_summary["passed"] += 1
        print("[PASS] Test 2: AI_AutoDetect test.jsx uses $.fileName dynamic root and output path Scale 3D/KS")
    else:
        tests_summary["failed"] += 1
        print("[FAIL] Test 2: AI_AutoDetect test.jsx missing $.fileName dynamic root")
        findings.append({
            "severity": "P1",
            "title": "AI_AutoDetect test.jsx missing $.fileName dynamic root",
            "file": jsx_auto_detect,
            "line": None,
            "evidence": "$.fileName or Scale 3D not found in JSX",
            "reproduction": f"Inspect {jsx_auto_detect}"
        })

    # -------------------------------------------------------------------------
    # TEST 3: start_watcher.bat dynamic Python resolution
    # -------------------------------------------------------------------------
    bat_path = os.path.join(PROJECT_DIR, "PTS CS5 SCRIPT", "start_watcher.bat")
    with open(bat_path, "r", encoding="utf-8", errors="ignore") as f:
        bat_content = f.read()

    if "%~dp0" in bat_content and "pyw.exe" in bat_content and "pythonw.exe" in bat_content:
        tests_summary["passed"] += 1
        print("[PASS] Test 3: start_watcher.bat uses %~dp0 and searches for pyw/pythonw dynamically")
    else:
        tests_summary["failed"] += 1
        print("[FAIL] Test 3: start_watcher.bat missing dynamic python search logic")

    # -------------------------------------------------------------------------
    # TEST 4: Photoshop JSX 7 Clean Views Acceptance Gate
    # -------------------------------------------------------------------------
    scale1_jsx = os.path.join(PROJECT_DIR, "Scale 3D", "KS SCALE NECKLACE", "1.Scale.jsx")
    with open(scale1_jsx, "r", encoding="utf-8", errors="ignore") as f:
        scale1_content = f.read()

    if "ksScaleAICopied < 7" in scale1_content:
        tests_summary["passed"] += 1
        print("[PASS] Test 4: 1.Scale.jsx enforces < 7 clean views threshold check")
    else:
        tests_summary["failed"] += 1
        print("[FAIL] Test 4: 1.Scale.jsx missing < 7 views acceptance gate check")
        findings.append({
            "severity": "P1",
            "title": "1.Scale.jsx does not enforce < 7 clean views acceptance threshold",
            "file": scale1_jsx,
            "line": None,
            "evidence": "ksScaleAICopied < 7 check not found",
            "reproduction": f"Inspect {scale1_jsx}"
        })

    # -------------------------------------------------------------------------
    # TEST 5: Photoshop Clean PNG crop priority in AI_AutoDetect test.jsx
    # -------------------------------------------------------------------------
    if "object_image" in auto_content and "quality_valid" in auto_content:
        tests_summary["passed"] += 1
        print("[PASS] Test 5: AI_AutoDetect test.jsx checks quality_valid and prefers object_image PNG crop")
    else:
        tests_summary["failed"] += 1
        print("[FAIL] Test 5: AI_AutoDetect test.jsx missing object_image/quality_valid logic")

    print(f"=== SUMMARY: {tests_summary} ===")
    return tests_summary, findings

if __name__ == "__main__":
    main()
