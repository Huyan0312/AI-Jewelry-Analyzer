import unittest
from unittest.mock import patch
import sys
import numpy as np
import cv2
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from image_processor import (
    refine_panel_bbox_opencv,
    clean_panel_crop,
    refine_object_bbox_opencv,
)


class TestStandardRefine(unittest.TestCase):

    def setUp(self):
        # Create a synthetic 500x500 image with a white panel and dark object
        self.img = np.ones((500, 500, 3), dtype=np.uint8) * 240
        # Draw a panel table border
        cv2.rectangle(self.img, (50, 50), (450, 450), (20, 20, 20), 4)
        # Draw an object inside panel
        cv2.rectangle(self.img, (150, 150), (350, 350), (100, 100, 100), -1)

    def test_refine_panel_bbox_opencv_success(self):
        ai_panel = [48.0, 48.0, 452.0, 452.0]
        refined, debug = refine_panel_bbox_opencv(self.img, ai_panel)
        meta = debug.get("meta", {})
        self.assertTrue(meta["attempted"])
        self.assertTrue(meta["success"])
        self.assertIsNotNone(refined)
        self.assertGreater(meta["iou_with_ai"], 0.8)

    def test_refine_panel_bbox_opencv_fallback_low_iou(self):
        # AI panel is far away from real panel
        ai_panel = [200.0, 200.0, 250.0, 250.0]
        refined, debug = refine_panel_bbox_opencv(self.img, ai_panel)
        meta = debug.get("meta", {})
        self.assertTrue(meta["attempted"])
        self.assertFalse(meta["success"])
        self.assertIsNotNone(meta["fallback_reason"])

    def test_refine_panel_bbox_opencv_fallback_center_distance(self):
        ai_panel = [48.0, 48.0, 452.0, 452.0]
        with patch("image_processor.MAX_CENTER_DISTANCE_RATIO", -0.01):
            refined, debug = refine_panel_bbox_opencv(self.img, ai_panel)

        self.assertIsNone(refined)
        self.assertFalse(debug["meta"]["success"])
        self.assertIn("center_distance_above_threshold", debug["meta"]["fallback_reason"])
        self.assertEqual(debug["meta"]["final_bbox"], ai_panel)

    def test_refine_panel_bbox_opencv_prefilter_threshold_is_effective(self):
        ai_panel = [48.0, 48.0, 452.0, 452.0]
        with patch("image_processor.PANEL_PREFILTER_MAX_CENTER_DISTANCE_RATIO", -0.01):
            refined, debug = refine_panel_bbox_opencv(self.img, ai_panel)

        self.assertIsNone(refined)
        self.assertEqual(debug["meta"]["fallback_reason"], "no_matching_contour_found")

    def test_clean_panel_crop_retained(self):
        # Panel crop with edge grid lines
        crop = np.ones((200, 200, 3), dtype=np.uint8) * 240
        cv2.line(crop, (0, 5), (199, 5), (30, 30, 30), 2)  # top grid line
        cv2.rectangle(crop, (50, 50), (150, 150), (80, 80, 80), -1)  # object

        clean_crop, info = clean_panel_crop(crop)
        self.assertTrue(info["success"])
        self.assertGreaterEqual(info["content_retained_ratio"], 0.85)
        self.assertTrue(info["trim"]["top"] > 0)

    def test_clean_panel_crop_no_trim_fallback(self):
        # Panel crop without any grid lines
        crop = np.ones((200, 200, 3), dtype=np.uint8) * 240
        cv2.rectangle(crop, (50, 50), (150, 150), (80, 80, 80), -1)

        clean_crop, info = clean_panel_crop(crop)
        self.assertFalse(info["success"])
        self.assertIn("No trim performed", info["fallback_reason"])

    def test_clean_panel_crop_too_small(self):
        crop = np.ones((49, 80, 3), dtype=np.uint8) * 240
        clean_crop, info = clean_panel_crop(crop)
        self.assertFalse(info["success"])
        self.assertIn("quá nhỏ", info["fallback_reason"])
        np.testing.assert_array_equal(clean_crop, crop)

    def test_clean_panel_crop_four_edges_respects_trim_limit(self):
        crop = np.ones((200, 200, 3), dtype=np.uint8) * 240
        cv2.rectangle(crop, (5, 5), (194, 194), (30, 30, 30), 2)
        cv2.rectangle(crop, (70, 70), (130, 130), (80, 80, 80), -1)

        clean_crop, info = clean_panel_crop(crop)

        self.assertTrue(info["success"])
        self.assertTrue(all(value > 0 for value in info["trim"].values()))
        self.assertLessEqual(info["trim"]["left"], int(crop.shape[1] * 0.18))
        self.assertLessEqual(info["trim"]["right"], int(crop.shape[1] * 0.18))
        self.assertLessEqual(info["trim"]["top"], int(crop.shape[0] * 0.18))
        self.assertLessEqual(info["trim"]["bottom"], int(crop.shape[0] * 0.18))
        self.assertGreater(clean_crop.size, 0)

    def test_clean_panel_crop_two_edges(self):
        crop = np.ones((200, 200, 3), dtype=np.uint8) * 240
        cv2.line(crop, (5, 0), (5, 199), (30, 30, 30), 2)
        cv2.line(crop, (0, 5), (199, 5), (30, 30, 30), 2)
        cv2.rectangle(crop, (70, 70), (130, 130), (80, 80, 80), -1)

        _, info = clean_panel_crop(crop)

        self.assertTrue(info["success"])
        self.assertGreater(info["trim"]["left"], 0)
        self.assertGreater(info["trim"]["top"], 0)
        self.assertEqual(info["trim"]["right"], 0)
        self.assertEqual(info["trim"]["bottom"], 0)

    def test_clean_panel_crop_blank_image_keeps_original(self):
        crop = np.ones((200, 200, 3), dtype=np.uint8) * 255
        clean_crop, info = clean_panel_crop(crop)
        self.assertFalse(info["success"])
        self.assertIn("No trim performed", info["fallback_reason"])
        np.testing.assert_array_equal(clean_crop, crop)

    def test_clean_panel_crop_content_loss_fallback(self):
        # Panel crop where trimming top line removes small dark objects in top margin
        crop = np.ones((200, 200, 3), dtype=np.uint8) * 240
        cv2.line(crop, (0, 10), (199, 10), (30, 30, 30), 2)  # thin grid line at y=10
        # Draw small dark objects near edge (width 10 < 60, so not detected as grid lines)
        for x in range(10, 180, 20):
            cv2.rectangle(crop, (x, 2), (x + 10, 7), (20, 20, 20), -1)  # ~450 pixels total
        cv2.rectangle(crop, (95, 95), (105, 105), (20, 20, 20), -1)  # 100 pixels in center

        with patch("image_processor.CONTENT_RETAINED_MIN_RATIO", 0.99):
            clean_crop, info = clean_panel_crop(crop)
        self.assertFalse(info["success"])
        self.assertIn("Mất nội dung", info["fallback_reason"])

    def test_refine_object_bbox_opencv_success(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (100, 100), (300, 300), (50, 50, 50), -1)

        ai_obj_in_panel = [90.0, 90.0, 310.0, 310.0]
        refined, debug = refine_object_bbox_opencv(
            clean_panel, ai_obj_in_panel, (50, 50), 500, 500
        )
        meta = debug.get("meta", {})
        self.assertTrue(meta["attempted"])
        self.assertTrue(meta["success"])
        self.assertIsNotNone(refined)

    def test_refine_object_bbox_opencv_no_content_fallback(self):
        # Empty white clean panel
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240

        ai_obj_in_panel = [90.0, 90.0, 310.0, 310.0]
        refined, debug = refine_object_bbox_opencv(
            clean_panel, ai_obj_in_panel, (50, 50), 500, 500
        )
        meta = debug.get("meta", {})
        self.assertTrue(meta["attempted"])
        self.assertFalse(meta["success"])
        self.assertEqual(meta["fallback_reason"], "no_intersecting_contour_with_ai_bbox")

    def test_refine_object_bbox_opencv_area_ratio_above_threshold_fallback(self):
        # Huge object in panel compared to small AI bbox
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (100, 100), (300, 300), (50, 50, 50), -1)

        ai_obj_in_panel = [180.0, 180.0, 220.0, 220.0]  # small AI bbox (40x40)
        refined, debug = refine_object_bbox_opencv(
            clean_panel, ai_obj_in_panel, (50, 50), 500, 500
        )
        meta = debug.get("meta", {})
        self.assertTrue(meta["attempted"])
        self.assertFalse(meta["success"])
        self.assertIn("area_ratio_above_threshold", meta["fallback_reason"])

    def test_refine_object_bbox_opencv_area_ratio_below_threshold_fallback(self):
        # Tiny object inside large AI bbox
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (195, 195), (205, 205), (50, 50, 50), -1)

        ai_obj_in_panel = [20.0, 20.0, 380.0, 380.0]  # large AI bbox
        refined, debug = refine_object_bbox_opencv(
            clean_panel, ai_obj_in_panel, (50, 50), 500, 500
        )
        meta = debug.get("meta", {})
        self.assertTrue(meta["attempted"])
        self.assertFalse(meta["success"])
        self.assertIn("area_ratio_below_threshold", meta["fallback_reason"])

    def test_refine_object_bbox_opencv_iou_gate(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (100, 100), (300, 300), (50, 50, 50), -1)
        with patch("image_processor.OBJECT_MIN_IOU_THRESHOLD", 1.01):
            refined, debug = refine_object_bbox_opencv(
                clean_panel, [90.0, 90.0, 310.0, 310.0], (50, 50), 500, 500
            )

        self.assertIsNone(refined)
        self.assertIn("iou_below_threshold", debug["meta"]["fallback_reason"])
        self.assertEqual(debug["meta"]["final_bbox"], debug["meta"]["ai_bbox"])

    def test_refine_object_bbox_opencv_center_distance_gate(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (100, 100), (300, 300), (50, 50, 50), -1)
        with patch("image_processor.OBJECT_MAX_CENTER_DISTANCE_RATIO", -0.01):
            refined, debug = refine_object_bbox_opencv(
                clean_panel, [90.0, 90.0, 310.0, 310.0], (50, 50), 500, 500
            )

        self.assertIsNone(refined)
        self.assertIn("center_distance_above_threshold", debug["meta"]["fallback_reason"])
        self.assertEqual(debug["meta"]["final_bbox"], debug["meta"]["ai_bbox"])

    def test_refine_object_bbox_opencv_rejects_distant_noise_and_colored_lines(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (130, 130), (270, 270), (50, 50, 50), -1)
        cv2.rectangle(clean_panel, (325, 150), (350, 180), (20, 20, 20), -1)
        cv2.line(clean_panel, (325, 220), (370, 220), (0, 0, 255), 4)
        cv2.line(clean_panel, (325, 250), (370, 250), (255, 0, 0), 4)

        refined, debug = refine_object_bbox_opencv(
            clean_panel, [120.0, 120.0, 280.0, 280.0], (50, 50), 500, 500
        )

        self.assertIsNotNone(refined)
        self.assertTrue(debug["meta"]["success"])
        self.assertLess(refined[2], 350.0)

    def test_refine_object_bbox_includes_red_dimensions_near_object(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(clean_panel, (145, 125), (255, 275), (30, 160, 220), -1)
        cv2.line(clean_panel, (80, 90), (320, 90), (0, 0, 255), 3)
        cv2.line(clean_panel, (80, 90), (80, 125), (0, 0, 255), 3)
        cv2.line(clean_panel, (320, 90), (320, 125), (0, 0, 255), 3)
        cv2.putText(
            clean_panel,
            "12.10",
            (165, 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
        )

        refined, debug = refine_object_bbox_opencv(
            clean_panel, [70.0, 70.0, 330.0, 300.0], (0, 0), 400, 400
        )

        self.assertIsNotNone(refined)
        self.assertTrue(debug["meta"]["success"])
        self.assertGreater(debug["meta"]["detected_red_annotation_pixels"], 0)
        self.assertLessEqual(refined[1], 90.0)
        self.assertLessEqual(refined[0], 80.0)
        self.assertGreaterEqual(refined[2], 320.0)

    def test_refine_object_bbox_preserves_large_pink_object(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 255
        cv2.ellipse(
            clean_panel,
            (200, 200),
            (65, 100),
            0,
            0,
            360,
            (100, 100, 240),
            -1,
        )

        refined, debug = refine_object_bbox_opencv(
            clean_panel, [110.0, 70.0, 290.0, 330.0], (0, 0), 400, 400
        )

        self.assertIsNotNone(refined)
        self.assertTrue(debug["meta"]["success"])
        self.assertLess(refined[0], 145.0)
        self.assertGreater(refined[2], 255.0)

    def test_refine_object_bbox_keeps_all_drawing_content(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(clean_panel, (110, 55), (290, 145), (40, 160, 220), -1)
        cv2.rectangle(clean_panel, (110, 255), (290, 345), (40, 160, 220), -1)

        refined, debug = refine_object_bbox_opencv(
            clean_panel, [80.0, 20.0, 320.0, 380.0], (0, 0), 400, 400
        )

        self.assertIsNotNone(refined)
        self.assertTrue(debug["meta"]["success"])
        self.assertLessEqual(refined[1], 55.0)
        self.assertGreaterEqual(refined[3], 345.0)

    def test_refine_object_bbox_opencv_min_contour_area_is_effective(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (150, 150), (250, 250), (50, 50, 50), -1)
        with patch("image_processor.OBJECT_MIN_CONTOUR_AREA", 1_000_000):
            refined, debug = refine_object_bbox_opencv(
                clean_panel, [140.0, 140.0, 260.0, 260.0], (50, 50), 500, 500
            )

        self.assertIsNone(refined)
        self.assertEqual(
            debug["meta"]["fallback_reason"],
            "no_intersecting_contour_with_ai_bbox",
        )

    def test_refine_object_bbox_opencv_object_near_panel_edge_is_valid(self):
        clean_panel = np.ones((400, 400, 3), dtype=np.uint8) * 240
        cv2.rectangle(clean_panel, (2, 100), (105, 260), (50, 50, 50), -1)
        refined, debug = refine_object_bbox_opencv(
            clean_panel, [0.0, 90.0, 115.0, 270.0], (50, 50), 500, 500
        )

        self.assertIsNotNone(refined)
        self.assertTrue(debug["meta"]["success"])
        self.assertGreaterEqual(refined[0], 50.0)
        self.assertLessEqual(refined[2], 450.0)


if __name__ == "__main__":
    unittest.main()
