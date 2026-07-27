import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import image_processor as ip


class TestPerspectiveRefine(unittest.TestCase):

    @staticmethod
    def _base_image():
        return np.ones((400, 400, 3), dtype=np.uint8) * 255

    def test_bbox_only_selects_yellow_model_and_ignores_artifacts(self):
        img = self._base_image()
        cv2.ellipse(img, (200, 200), (65, 85), 0, 0, 360, (0, 190, 230), -1)
        cv2.putText(img, "PERSPECTIVE", (105, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
        cv2.line(img, (110, 125), (290, 125), (0, 0, 255), 3)
        cv2.rectangle(img, (315, 170), (350, 220), (255, 0, 0), -1)

        started = time.perf_counter()
        bbox, debug = ip.refine_perspective_object_opencv(
            img, [100.0, 100.0, 300.0, 300.0], 400, 400, mode="bbox_only"
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        meta = debug["meta"]

        self.assertIsNotNone(bbox)
        self.assertTrue(meta["success"])
        self.assertEqual(meta["mode"], "bbox_only")
        self.assertTrue(meta["mask_available"])
        self.assertFalse(meta["mask_applied"])
        self.assertEqual(meta["selected_components"], 1)
        self.assertGreater(meta["removed_red_pixels"], 0)
        self.assertGreater(meta["removed_text_grid_pixels"], 0)
        self.assertLess(bbox[2], 315.0)
        self.assertLess(elapsed_ms, 500.0)

    def test_silver_grayscale_model_is_detected(self):
        img = self._base_image()
        cv2.ellipse(img, (200, 200), (60, 80), 0, 0, 360, (165, 165, 165), -1)

        bbox, debug = ip.refine_perspective_object_opencv(
            img, [110.0, 100.0, 290.0, 300.0], 400, 400
        )

        self.assertIsNotNone(bbox)
        self.assertTrue(debug["meta"]["success"])
        self.assertIsNone(debug["meta"]["fallback_reason"])

    def test_bbox_includes_red_dimension_annotations(self):
        img = self._base_image()
        cv2.circle(img, (200, 210), 60, (0, 190, 230), -1)
        cv2.line(img, (120, 90), (280, 90), (0, 0, 255), 3)
        cv2.putText(
            img, "12.10", (170, 82),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2,
        )

        bbox, debug = ip.refine_perspective_object_opencv(
            img, [100.0, 60.0, 300.0, 300.0], 400, 400
        )

        self.assertIsNotNone(bbox)
        self.assertLessEqual(bbox[1], 80.0)
        self.assertGreater(debug["meta"]["included_red_annotation_pixels"], 0)

    def test_two_tone_red_object_keeps_both_disconnected_halves(self):
        img = self._base_image()
        cv2.ellipse(img, (145, 200), (45, 85), 0, 0, 360, (0, 190, 230), -1)
        # Mảng hồng thuộc vật thể, không phải annotation màu đỏ.
        cv2.ellipse(img, (255, 200), (45, 85), 0, 0, 360, (100, 100, 240), -1)

        bbox, debug = ip.refine_perspective_object_opencv(
            img, [80.0, 90.0, 320.0, 310.0], 400, 400
        )

        self.assertIsNotNone(bbox)
        self.assertTrue(debug["meta"]["success"])
        self.assertGreaterEqual(debug["meta"]["selected_components"], 2)
        self.assertLessEqual(bbox[0], 100.0)
        self.assertGreaterEqual(bbox[2], 300.0)
        self.assertLess(debug["meta"]["removed_red_pixels"], 50)

    def test_component_outside_ai_bbox_does_not_expand_result(self):
        img = self._base_image()
        cv2.circle(img, (170, 200), 55, (0, 190, 230), -1)
        cv2.circle(img, (325, 200), 35, (0, 255, 0), -1)

        bbox, debug = ip.refine_perspective_object_opencv(
            img, [100.0, 120.0, 250.0, 280.0], 400, 400
        )

        self.assertTrue(debug["meta"]["success"])
        self.assertLess(bbox[2], 270.0)
        self.assertEqual(debug["meta"]["selected_components"], 1)

    def test_panel_bbox_blocks_neighbor_view_dimensions(self):
        img = self._base_image()
        cv2.circle(img, (150, 210), 55, (0, 190, 230), -1)
        cv2.line(img, (315, 120), (390, 120), (0, 0, 255), 3)
        cv2.putText(
            img, "0.60", (320, 110),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2,
        )

        bbox, debug = ip.refine_perspective_object_opencv(
            img,
            [70.0, 120.0, 240.0, 300.0],
            400,
            400,
            panel_bbox_px=[0.0, 0.0, 300.0, 400.0],
        )

        self.assertIsNotNone(bbox)
        self.assertTrue(debug["meta"]["success"])
        self.assertLessEqual(bbox[2], 300.0)

    def test_no_component_falls_back_with_reason(self):
        img = self._base_image()
        bbox, debug = ip.refine_perspective_object_opencv(
            img, [100.0, 100.0, 300.0, 300.0], 400, 400
        )

        self.assertIsNone(bbox)
        self.assertFalse(debug["meta"]["success"])
        self.assertEqual(
            debug["meta"]["fallback_reason"],
            "no_component_related_to_ai_bbox",
        )
        self.assertEqual(debug["meta"]["final_bbox"], [100.0, 100.0, 300.0, 300.0])

    def test_object_at_paper_edge_stays_in_image(self):
        img = self._base_image()
        cv2.circle(img, (35, 45), 28, (0, 190, 230), -1)

        bbox, debug = ip.refine_perspective_object_opencv(
            img, [0.0, 0.0, 100.0, 120.0], 400, 400
        )

        self.assertIsNotNone(bbox)
        self.assertTrue(debug["meta"]["success"])
        self.assertGreaterEqual(bbox[0], 0.0)
        self.assertGreaterEqual(bbox[1], 0.0)
        self.assertLessEqual(bbox[2], 400.0)
        self.assertLessEqual(bbox[3], 400.0)

    def test_masked_object_replaces_red_and_background_pixels(self):
        img = self._base_image()
        cv2.circle(img, (200, 200), 70, (0, 190, 230), -1)
        cv2.line(img, (120, 200), (280, 200), (0, 0, 255), 3)

        bbox, debug = ip.refine_perspective_object_opencv(
            img,
            [100.0, 100.0, 300.0, 300.0],
            400,
            400,
            mode="masked_object",
        )
        masked = debug["_masked_object_crop"]
        meta = debug["meta"]

        self.assertIsNotNone(bbox)
        self.assertTrue(meta["mask_applied"])
        self.assertGreater(masked.size, 0)
        center_y = masked.shape[0] // 2
        center_x = masked.shape[1] // 2
        self.assertTrue(np.all(masked[center_y, center_x] == 255))
        self.assertTrue(np.all(masked[0, 0] == 255))

    def test_process_image_masked_mode_saves_masked_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            img_path = root / "perspective.png"
            output_dir = root / "output"
            img = self._base_image()
            cv2.circle(img, (200, 200), 70, (0, 190, 230), -1)
            cv2.line(img, (120, 200), (280, 200), (0, 0, 255), 3)
            ok, encoded = cv2.imencode(".png", img)
            self.assertTrue(ok)
            encoded.tofile(str(img_path))
            payload = {
                "view": "PERSPECTIVE",
                "coordinate_scale": 1000,
                "panel_bbox": [0, 0, 1000, 1000],
                "object_bbox": [250, 250, 750, 750],
                "object_center": [500, 500],
            }

            with patch.object(ip, "OUTPUT_DIR", output_dir), \
                 patch.object(ip, "DEBUG_DIR", output_dir / "debug"), \
                 patch.object(ip, "PERSPECTIVE_OUTPUT_MODE", "masked_object"):
                result = ip.process_image(
                    img_path,
                    payload,
                    model_name="test-model",
                    coord_scale_type="normalized_0_1000",
                    target_view="PERSPECTIVE",
                    enable_refine=True,
                    save_json=False,
                )

            saved = cv2.imdecode(
                np.fromfile(result["output_files"]["object_image"], dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            self.assertTrue(result["opencv"]["object_refine_success"])
            self.assertEqual(result["opencv"]["object_meta"]["mode"], "masked_object")
            self.assertTrue(result["opencv"]["object_meta"]["mask_applied"])
            self.assertTrue(np.all(saved[saved.shape[0] // 2, saved.shape[1] // 2] >= 250))

    def test_process_image_bbox_only_crop_uses_original_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            img_path = root / "perspective.png"
            output_dir = root / "output"
            img = self._base_image()
            cv2.circle(img, (200, 200), 70, (0, 190, 230), -1)
            cv2.line(img, (120, 200), (280, 200), (0, 0, 255), 3)
            ok, encoded = cv2.imencode(".png", img)
            self.assertTrue(ok)
            encoded.tofile(str(img_path))
            payload = {
                "view": "PERSPECTIVE",
                "coordinate_scale": 1000,
                "panel_bbox": [0, 0, 1000, 1000],
                "object_bbox": [250, 250, 750, 750],
                "object_center": [500, 500],
            }

            with patch.object(ip, "OUTPUT_DIR", output_dir), \
                 patch.object(ip, "DEBUG_DIR", output_dir / "debug"), \
                 patch.object(ip, "PERSPECTIVE_OUTPUT_MODE", "bbox_only"):
                result = ip.process_image(
                    img_path,
                    payload,
                    model_name="test-model",
                    coord_scale_type="normalized_0_1000",
                    target_view="PERSPECTIVE",
                    enable_refine=True,
                    save_json=False,
                )

            saved = cv2.imdecode(
                np.fromfile(result["output_files"]["object_image"], dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            x1, y1, x2, y2 = result["pixel"]["refined_object_bbox"]
            expected = img[y1:y2, x1:x2]
            self.assertEqual(result["opencv"]["object_meta"]["mode"], "bbox_only")
            self.assertFalse(result["opencv"]["object_meta"]["mask_applied"])
            np.testing.assert_array_equal(saved, expected)


if __name__ == "__main__":
    unittest.main()
