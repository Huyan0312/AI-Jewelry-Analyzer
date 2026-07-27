import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import run_auto_test as batch
from result_contract import (
    EXPECTED_VIEWS,
    build_all_views_result,
    make_batch_entry,
    save_json_with_self_path,
)


class TestPhase5Contract(unittest.TestCase):

    @staticmethod
    def _view_result(root: Path, view: str, valid: bool = True):
        crop = root / f"{view.lower()} object.png"
        if valid:
            crop.write_bytes(b"png")
        return {
            "view_name": view,
            "pixel": {
                "ai_object_bbox": [10, 10, 90, 90],
                "refined_object_bbox": [12, 12, 88, 88],
            },
            "opencv": {
                "object_refine_success": True,
                "object_meta": {"fallback_reason": None},
            },
            "validation": {"valid": valid},
            "output_files": {"object_image": str(crop) if valid else None},
        }

    def test_all_views_success_requires_seven_unique_saved_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            views = [self._view_result(root, view) for view in EXPECTED_VIEWS]
            result = build_all_views_result(
                sheet={"drawing_number": "888555", "metal": "925"},
                views=views,
                raw_response="fixture",
            )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertTrue(result["validation"]["valid"])
        self.assertEqual(result["validation"]["views_saved"], 7)
        self.assertEqual(result["sheet"]["drawing_number"], "888555")

    def test_missing_or_failed_crop_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            views = [self._view_result(root, view) for view in EXPECTED_VIEWS[:-1]]
            views[0] = self._view_result(root, EXPECTED_VIEWS[0], valid=False)
            result = build_all_views_result(sheet={}, views=views)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertFalse(result["validation"]["valid"])
        self.assertEqual(result["validation"]["missing_views"], ["PERSPECTIVE"])
        self.assertIn("FRONT", result["validation"]["failed_views"])

    def test_master_json_contains_its_own_path_in_unicode_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Thư mục có khoảng trắng" / "kết quả.json"
            payload = {"status": "SUCCESS", "output_files": {}}
            self.assertTrue(save_json_with_self_path(payload, path))
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved["output_files"]["json"], str(path))

    def test_batch_entry_preserves_sheet_and_required_fields(self):
        all_views = {
            "status": "FAILED",
            "sheet": {
                "drawing_number": "999000",
                "metal": "925",
                "brand": "silver",
                "metal_weight": 1.25,
            },
            "validation": {
                "views_expected": 7,
                "views_received": 0,
                "views_saved": 0,
            },
            "views": [],
            "output_files": {},
        }
        entry = make_batch_entry("sample.png", all_views, 0.25, [400, 400])
        self.assertEqual(entry["sheet"]["drawing_number"], "999000")
        self.assertEqual(entry["sheet"]["metal_weight"], 1.25)
        self.assertEqual(entry["views_expected"], 7)

    def test_clean_refuses_target_outside_allowed_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed = root / "allowed"
            outside = root / "outside"
            allowed.mkdir()
            outside.mkdir()
            with self.assertRaises(ValueError):
                batch.clean_old_results(outside, allowed_root=allowed)

    def test_end_to_end_fixture_creates_seven_crops_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "Auto Test"
            results_dir = root / "Results"
            source_dir.mkdir()
            image_path = source_dir / "ảnh mẫu.png"
            image = np.ones((500, 500, 3), dtype=np.uint8) * 240
            cv2.rectangle(image, (50, 50), (450, 450), (20, 20, 20), 4)
            cv2.rectangle(image, (150, 150), (350, 350), (80, 80, 80), -1)
            ok, encoded = cv2.imencode(".png", image)
            self.assertTrue(ok)
            encoded.tofile(str(image_path))

            def fake_sender(*args, **kwargs):
                return {
                    "sheet": {
                        "drawing_number": "888555",
                        "metal": "925",
                        "brand": "silver",
                        "metal_weight": 1.0,
                    },
                    "views": [
                        {
                            "view": view,
                            "coordinate_scale": 1000,
                            "panel_bbox": [100, 100, 900, 900],
                            "object_bbox": [300, 300, 700, 700],
                            "object_center": [500, 500],
                        }
                        for view in EXPECTED_VIEWS
                    ],
                    "raw_response": "fixture",
                }

            entries = batch.run_batch_test(
                clean=False,
                model_name="fixture-model",
                auto_test_dir=source_dir,
                results_dir=results_dir,
                send_all_views=fake_sender,
            )

            self.assertEqual(entries[0]["status"], "SUCCESS")
            self.assertEqual(entries[0]["views_saved"], 7)
            self.assertEqual(entries[0]["sheet"]["drawing_number"], "888555")
            self.assertTrue((results_dir / "batch_summary.json").is_file())
            for view in entries[0]["views"]:
                self.assertGreater(view["crop_size"][0], 0)
                self.assertGreater(view["crop_size"][1], 0)
                self.assertTrue(Path(view["crop_file"]).is_file())


if __name__ == "__main__":
    unittest.main()
