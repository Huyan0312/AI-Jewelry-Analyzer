import unittest
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bbox_utils import (
    STANDARD_VIEWS,
    validate_normalized_bbox,
    validate_normalized_point,
    validate_view_payload,
    validate_all_views_schema,
    detect_coordinate_scale,
    rescale_response_coords,
)


class TestBBoxUtilsValidation(unittest.TestCase):

    def test_validate_normalized_bbox_valid(self):
        ok, msg = validate_normalized_bbox([10, 20, 500, 600])
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_validate_normalized_bbox_invalid_length(self):
        ok, msg = validate_normalized_bbox([10, 20, 500])
        self.assertFalse(ok)
        self.assertIn("đúng 4 phần tử", msg)

        ok2, msg2 = validate_normalized_bbox([10, 20, 500, 600, 700])
        self.assertFalse(ok2)
        self.assertIn("đúng 4 phần tử", msg2)

    def test_validate_normalized_bbox_nan_inf(self):
        ok, msg = validate_normalized_bbox([10, math.nan, 500, 600])
        self.assertFalse(ok)
        self.assertIn("NaN hoặc Infinity", msg)

        ok2, msg2 = validate_normalized_bbox([10, 20, math.inf, 600])
        self.assertFalse(ok2)
        self.assertIn("NaN hoặc Infinity", msg2)

    def test_validate_normalized_bbox_inverted(self):
        ok, msg = validate_normalized_bbox([500, 20, 10, 600])
        self.assertFalse(ok)
        self.assertIn("x1 >= x2", msg)

    def test_validate_normalized_bbox_negative(self):
        ok, msg = validate_normalized_bbox([-10, 20, 500, 600])
        self.assertFalse(ok)
        self.assertIn("tọa độ phải nằm trong", msg)

    def test_validate_normalized_bbox_exceeding_scale(self):
        ok, msg = validate_normalized_bbox([10, 20, 1500, 600], scale=1000.0)
        self.assertFalse(ok)
        self.assertIn("tọa độ phải nằm trong", msg)

    def test_validate_normalized_point_valid(self):
        ok, _ = validate_normalized_point([250, 300])
        self.assertTrue(ok)

    def test_validate_normalized_point_invalid(self):
        ok_bad, _ = validate_normalized_point([250])
        self.assertFalse(ok_bad)

        ok_nan, _ = validate_normalized_point([250, math.nan])
        self.assertFalse(ok_nan)

        ok_neg, _ = validate_normalized_point([-5, 300])
        self.assertFalse(ok_neg)

        ok_exceed, _ = validate_normalized_point([250, 1200])
        self.assertFalse(ok_exceed)

    def test_validate_view_payload_valid(self):
        view_data = {
            "view": "FRONT",
            "coordinate_scale": 1000,
            "panel_bbox": [0, 0, 500, 500],
            "object_bbox": [50, 50, 400, 400],
            "object_center": [225, 225],
        }
        ok, errs = validate_view_payload(view_data)
        self.assertTrue(ok)
        self.assertEqual(len(errs), 0)

    def test_validate_view_payload_invalid_coordinate_scale(self):
        v_500 = {
            "view": "FRONT",
            "coordinate_scale": 500,
            "panel_bbox": [0, 0, 500, 500],
            "object_bbox": [50, 50, 400, 400],
            "object_center": [225, 225],
        }
        ok, errs = validate_view_payload(v_500)
        self.assertFalse(ok)
        self.assertTrue(any("không hợp lệ" in e for e in errs))

        v_abc = {
            "view": "FRONT",
            "coordinate_scale": "abc",
            "panel_bbox": [0, 0, 500, 500],
            "object_bbox": [50, 50, 400, 400],
            "object_center": [225, 225],
        }
        ok2, errs2 = validate_view_payload(v_abc)
        self.assertFalse(ok2)
        self.assertTrue(any("không phải số" in e for e in errs2))

    def test_validate_view_payload_object_outside_panel(self):
        view_data = {
            "view": "FRONT",
            "panel_bbox": [100, 100, 400, 400],
            "object_bbox": [50, 50, 450, 450],
            "object_center": [250, 250],
        }
        ok, errs = validate_view_payload(view_data)
        self.assertFalse(ok)
        self.assertTrue(any("vượt ngoài panel_bbox" in e for e in errs))

    def test_validate_view_payload_center_outside_object(self):
        view_data = {
            "view": "FRONT",
            "panel_bbox": [0, 0, 500, 500],
            "object_bbox": [100, 100, 300, 300],
            "object_center": [50, 50],
        }
        ok, errs = validate_view_payload(view_data)
        self.assertFalse(ok)
        self.assertTrue(any("nằm ngoài object_bbox" in e for e in errs))

    def test_validate_all_views_schema_complete_7_views(self):
        all_7 = [
            {"view": v, "panel_bbox": [0, 0, 500, 500], "object_bbox": [10, 10, 400, 400], "object_center": [200, 200]}
            for v in ["FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "BACK", "PERSPECTIVE"]
        ]
        ok, errs, found = validate_all_views_schema(all_7)
        self.assertTrue(ok)
        self.assertEqual(len(errs), 0)
        self.assertEqual(found, STANDARD_VIEWS)

    def test_validate_all_views_schema_missing_view(self):
        only_6 = [
            {"view": v, "panel_bbox": [0, 0, 500, 500], "object_bbox": [10, 10, 400, 400], "object_center": [200, 200]}
            for v in ["FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "PERSPECTIVE"]
        ]
        ok, errs, found = validate_all_views_schema(only_6)
        self.assertFalse(ok)
        self.assertTrue(any("Thiếu các view" in e and "BACK" in e for e in errs))

    def test_validate_all_views_schema_duplicate_view(self):
        dup_front = [
            {"view": "FRONT", "panel_bbox": [0, 0, 500, 500], "object_bbox": [10, 10, 400, 400], "object_center": [200, 200]},
            {"view": "FRONT", "panel_bbox": [0, 0, 500, 500], "object_bbox": [10, 10, 400, 400], "object_center": [200, 200]},
        ]
        ok, errs, _ = validate_all_views_schema(dup_front)
        self.assertFalse(ok)
        self.assertTrue(any("Trùng lặp view 'FRONT'" in e for e in errs))

    def test_validate_all_views_schema_invalid_view_name(self):
        bad_name = [
            {"view": "SIDE", "panel_bbox": [0, 0, 500, 500], "object_bbox": [10, 10, 400, 400], "object_center": [200, 200]},
        ]
        ok, errs, _ = validate_all_views_schema(bad_name)
        self.assertFalse(ok)
        self.assertTrue(any("Tên view lạ 'SIDE'" in e for e in errs))

    def test_detect_coordinate_scale_explicit(self):
        data_1000 = {"coordinate_scale": 1000, "panel_bbox": [0, 0, 50, 50]}
        scale_type, mult = detect_coordinate_scale(data_1000)
        self.assertEqual(scale_type, "normalized_0_1000")
        self.assertEqual(mult, 1.0)

        data_100 = {"coordinate_scale": 100, "panel_bbox": [0, 0, 50, 50]}
        scale_type2, mult2 = detect_coordinate_scale(data_100)
        self.assertEqual(scale_type2, "normalized_0_100")
        self.assertEqual(mult2, 10.0)

    def test_rescale_response_coords_100_to_1000(self):
        original = {
            "view": "FRONT",
            "coordinate_scale": 100,
            "panel_bbox": [0, 0, 50, 50],
            "object_bbox": [5, 5, 45, 45],
            "object_center": [25, 25],
        }

        rescaled = rescale_response_coords(original, 10.0)

        # Confirm original is NOT mutated
        self.assertEqual(original["coordinate_scale"], 100)
        self.assertEqual(original["panel_bbox"], [0, 0, 50, 50])

        # Confirm rescaled properties
        self.assertEqual(rescaled["coordinate_scale"], 1000)
        self.assertEqual(rescaled["panel_bbox"], [0.0, 0.0, 500.0, 500.0])
        self.assertEqual(rescaled["object_bbox"], [50.0, 50.0, 450.0, 450.0])
        self.assertEqual(rescaled["object_center"], [250.0, 250.0])

        # Confirm rescaled view passes validate_view_payload
        ok, errs = validate_view_payload(rescaled)
        self.assertTrue(ok, f"Rescaled payload failed validation: {errs}")

    def test_rescale_response_coords_multiplier_1_preserves_scale(self):
        original = {
            "view": "FRONT",
            "coordinate_scale": 1000,
            "panel_bbox": [0, 0, 500, 500],
        }
        rescaled = rescale_response_coords(original, 1.0)
        self.assertEqual(rescaled["coordinate_scale"], 1000)
        self.assertEqual(rescaled["panel_bbox"], [0, 0, 500, 500])

    def test_rescale_response_coords_invalid_value_raises(self):
        bad_coords = {
            "view": "FRONT",
            "panel_bbox": [0, "abc", 50, 50],
        }
        with self.assertRaises(ValueError):
            rescale_response_coords(bad_coords, 10.0)


if __name__ == "__main__":
    unittest.main()
