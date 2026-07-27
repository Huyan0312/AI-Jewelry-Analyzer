import unittest
from unittest.mock import patch
import sys
import tempfile
import json
import cv2
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import image_processor as ip


class TestProcessImageIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = Path(self.temp_dir.name)
        self.output_dir = self.temp_dir_path / "output"
        self.debug_dir = self.output_dir / "debug"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.img_path = self.temp_dir_path / "sample_img.jpg"

        # Create a synthetic 500x500 image with a panel border and an object inside
        arr = np.ones((500, 500, 3), dtype=np.uint8) * 240
        # Panel border
        cv2.rectangle(arr, (50, 50), (450, 450), (20, 20, 20), 4)
        # Object inside panel
        cv2.rectangle(arr, (150, 150), (350, 350), (80, 80, 80), -1)

        success, buf = cv2.imencode(".jpg", arr)
        with open(self.img_path, "wb") as f:
            f.write(buf.tobytes())

        self.ai_response = {
            "view": "FRONT",
            "coordinate_scale": 1000,
            "panel_bbox": [100, 100, 900, 900],
            "object_bbox": [300, 300, 700, 700],
            "object_center": [500, 500],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_process_image_standard_refine_success(self):
        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir):
            res = ip.process_image(
                self.img_path,
                self.ai_response,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="FRONT",
                enable_refine=True,
                save_json=True,
            )

        self.assertEqual(res["source_image"], str(self.img_path))
        self.assertEqual(res["image_size"], {"width": 500, "height": 500})
        self.assertTrue(res["opencv"]["panel_refine_success"])
        self.assertTrue(res["opencv"]["object_refine_success"])
        self.assertTrue(res["opencv"]["panel_meta"]["success"])
        self.assertTrue(res["opencv"]["object_meta"]["success"])
        self.assertTrue(res["validation"]["valid"])
        self.assertTrue(res["validation"]["ai_bbox_valid"])
        self.assertTrue(res["validation"]["refined_panel_bbox_valid"])
        self.assertTrue(res["validation"]["refined_object_bbox_valid"])
        self.assertTrue(res["validation"]["object_crop_valid"])

        # Confirm output files were saved ONLY inside temporary directory
        self.assertTrue(Path(res["output_files"]["result_image"]).exists())
        self.assertTrue(Path(res["output_files"]["result_image"]).is_relative_to(self.output_dir))
        self.assertTrue(Path(res["output_files"]["json"]).exists())
        saved_json = json.loads(Path(res["output_files"]["json"]).read_text(encoding="utf-8"))
        self.assertEqual(saved_json["output_files"]["json"], res["output_files"]["json"])
        for declared_path in saved_json["output_files"].values():
            if declared_path:
                self.assertTrue(Path(declared_path).is_file())

    def test_panel_bottom_edge_snap_recovers_space_beyond_truncated_panel(self):
        truncated_panel = [50.0, 50.0, 450.0, 330.0]
        panel_debug = {
            "meta": {
                "attempted": True,
                "success": True,
                "method": "opencv",
                "candidate_bbox": truncated_panel,
                "final_bbox": truncated_panel,
            }
        }

        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir), \
             patch(
                 "image_processor.refine_panel_bbox_opencv",
                 return_value=(truncated_panel, panel_debug),
             ):
            edge_panel_response = dict(
                self.ai_response,
                panel_bbox=[100, 100, 900, 940],
            )
            res = ip.process_image(
                self.img_path,
                edge_panel_response,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="BOTTOM",
                enable_refine=True,
                save_json=False,
            )

        # AI panel ends at y=470 (within 8% of the 500 px image bottom), so a
        # contour truncated at y=330 must not cap the object search domain.
        self.assertEqual(res["pixel"]["refined_panel_bbox"], [50, 50, 450, 500])
        self.assertTrue(res["opencv"]["panel_meta"]["bottom_edge_snap_applied"])
        self.assertEqual(
            res["opencv"]["panel_meta"]["pre_bottom_edge_snap_bbox"],
            truncated_panel,
        )

    def test_process_image_all_six_standard_views(self):
        standard_views = ["FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "BACK"]
        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir), \
             patch("image_processor.refine_panel_bbox_opencv", wraps=ip.refine_panel_bbox_opencv) as spy_panel, \
             patch("image_processor.clean_panel_crop", wraps=ip.clean_panel_crop) as spy_clean, \
             patch("image_processor.refine_object_bbox_opencv", wraps=ip.refine_object_bbox_opencv) as spy_obj, \
             patch("image_processor.refine_perspective_object_opencv") as mock_persp:

            for view in standard_views:
                with self.subTest(view=view):
                    spy_panel.reset_mock()
                    spy_clean.reset_mock()
                    spy_obj.reset_mock()
                    mock_persp.reset_mock()

                    ai_resp = dict(self.ai_response, view=view)
                    res = ip.process_image(
                        self.img_path,
                        ai_resp,
                        model_name="test-model",
                        coord_scale_type="normalized_0_1000",
                        target_view=view,
                        enable_refine=True,
                        save_json=False,
                    )
                    self.assertTrue(res["opencv"]["panel_refine_success"])
                    self.assertTrue(res["opencv"]["object_refine_success"])
                    self.assertTrue(res["validation"]["valid"])
                    spy_panel.assert_called_once()
                    spy_clean.assert_called_once()
                    spy_obj.assert_called_once()
                    mock_persp.assert_not_called()

    def test_process_image_perspective_view_handling(self):
        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir), \
             patch("image_processor.refine_perspective_object_opencv") as mock_refine_persp, \
             patch("image_processor.refine_panel_bbox_opencv") as mock_refine_panel, \
             patch("image_processor.clean_panel_crop") as mock_clean_panel, \
             patch("image_processor.refine_object_bbox_opencv") as mock_refine_object:

            mock_refine_persp.return_value = (
                [150.0, 150.0, 350.0, 350.0],
                {"meta": {"attempted": True, "success": True, "method": "perspective_custom"}},
            )

            ai_resp = dict(self.ai_response, view="PERSPECTIVE")
            res = ip.process_image(
                self.img_path,
                ai_resp,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="PERSPECTIVE",
                enable_refine=True,
                save_json=False,
            )

            mock_refine_panel.assert_not_called()
            mock_clean_panel.assert_not_called()
            mock_refine_object.assert_not_called()
            mock_refine_persp.assert_called_once()
            self.assertFalse(res["opencv"]["panel_meta"]["attempted"])
            self.assertEqual(res["opencv"]["panel_meta"]["fallback_reason"], "perspective_special_handling")
            self.assertEqual(res["opencv"]["object_meta"]["final_bbox"], [150.0, 150.0, 350.0, 350.0])
            self.assertIn("thresholds", res["opencv"]["object_meta"])

    def test_process_image_fallback_on_blank_image(self):
        blank_path = self.temp_dir_path / "blank_img.jpg"
        arr = np.ones((500, 500, 3), dtype=np.uint8) * 240
        _, buf = cv2.imencode(".jpg", arr)
        with open(blank_path, "wb") as f:
            f.write(buf.tobytes())

        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir):
            res = ip.process_image(
                blank_path,
                self.ai_response,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="FRONT",
                enable_refine=True,
                save_json=False,
            )

        self.assertFalse(res["opencv"]["panel_refine_success"])
        self.assertFalse(res["opencv"]["object_refine_success"])
        self.assertIsNotNone(res["opencv"]["panel_meta"]["fallback_reason"])
        self.assertIsNotNone(res["opencv"]["object_meta"]["fallback_reason"])

    def test_process_image_disabled_refine(self):
        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir):
            res = ip.process_image(
                self.img_path,
                self.ai_response,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="FRONT",
                enable_refine=False,
                save_json=False,
            )

        self.assertFalse(res["opencv"]["panel_meta"]["attempted"])
        self.assertEqual(res["opencv"]["panel_meta"]["fallback_reason"], "disabled_by_config")
        self.assertEqual(res["opencv"]["object_meta"]["fallback_reason"], "disabled_by_config")

    def test_process_image_invalid_refined_candidate_falls_back(self):
        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir), \
             patch("image_processor.refine_object_bbox_opencv") as mock_refine_obj:
            # Mock candidate object bbox out of image bounds
            mock_refine_obj.return_value = (
                [600.0, 600.0, 700.0, 700.0],
                {"meta": {"attempted": True, "success": True, "candidate_bbox": [600, 600, 700, 700], "final_bbox": [600, 600, 700, 700]}},
            )

            res = ip.process_image(
                self.img_path,
                self.ai_response,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="FRONT",
                enable_refine=True,
                save_json=False,
            )

        self.assertFalse(res["opencv"]["object_refine_success"])
        self.assertEqual(res["pixel"]["refined_object_bbox"], res["pixel"]["ai_object_bbox"])
        self.assertEqual(res["opencv"]["object_meta"]["final_bbox"], [float(v) for v in res["pixel"]["ai_object_bbox"]])
        self.assertIn("candidate_bbox_invalid", res["opencv"]["object_meta"]["fallback_reason"])
        self.assertTrue(any("Object refine bị từ chối" in item for item in res["validation"]["warnings"]))

    def test_process_image_invalid_panel_candidate_falls_back(self):
        bad_panel = [600.0, 600.0, 700.0, 700.0]
        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir), \
             patch("image_processor.refine_panel_bbox_opencv") as mock_refine_panel:
            mock_refine_panel.return_value = (
                bad_panel,
                {
                    "meta": {
                        "attempted": True,
                        "success": True,
                        "candidate_bbox": bad_panel,
                        "final_bbox": bad_panel,
                    }
                },
            )
            res = ip.process_image(
                self.img_path,
                self.ai_response,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="FRONT",
                enable_refine=True,
                save_json=False,
            )

        self.assertFalse(res["opencv"]["panel_refine_success"])
        self.assertEqual(res["pixel"]["refined_panel_bbox"], res["pixel"]["ai_panel_bbox"])
        self.assertEqual(
            res["opencv"]["panel_meta"]["final_bbox"],
            [float(v) for v in res["pixel"]["ai_panel_bbox"]],
        )
        self.assertEqual(res["opencv"]["panel_meta"]["candidate_bbox"], bad_panel)
        self.assertIn("candidate_bbox_invalid", res["opencv"]["panel_meta"]["fallback_reason"])
        self.assertTrue(any("Panel refine bị từ chối" in item for item in res["validation"]["warnings"]))

    def test_process_image_inverted_and_zero_area_object_candidates_fall_back(self):
        invalid_candidates = (
            [350.0, 150.0, 150.0, 350.0],
            [200.0, 200.0, 200.0, 250.0],
        )
        for candidate in invalid_candidates:
            with self.subTest(candidate=candidate), \
                 patch.object(ip, "OUTPUT_DIR", self.output_dir), \
                 patch.object(ip, "DEBUG_DIR", self.debug_dir), \
                 patch("image_processor.refine_object_bbox_opencv") as mock_refine_obj:
                mock_refine_obj.return_value = (
                    candidate,
                    {
                        "meta": {
                            "attempted": True,
                            "success": True,
                            "candidate_bbox": candidate,
                            "final_bbox": candidate,
                        }
                    },
                )
                res = ip.process_image(
                    self.img_path,
                    self.ai_response,
                    model_name="test-model",
                    coord_scale_type="normalized_0_1000",
                    target_view="FRONT",
                    enable_refine=True,
                    save_json=False,
                )

            self.assertFalse(res["opencv"]["object_refine_success"])
            self.assertEqual(res["pixel"]["refined_object_bbox"], res["pixel"]["ai_object_bbox"])
            self.assertEqual(
                res["opencv"]["object_meta"]["final_bbox"],
                [float(v) for v in res["pixel"]["ai_object_bbox"]],
            )
            self.assertIn("candidate_bbox_invalid", res["opencv"]["object_meta"]["fallback_reason"])

    def test_process_image_does_not_declare_failed_image_outputs(self):
        with patch.object(ip, "OUTPUT_DIR", self.output_dir), \
             patch.object(ip, "DEBUG_DIR", self.debug_dir), \
             patch("image_processor.save_cv2_image", return_value=False):
            res = ip.process_image(
                self.img_path,
                self.ai_response,
                model_name="test-model",
                coord_scale_type="normalized_0_1000",
                target_view="FRONT",
                enable_refine=True,
                save_json=False,
            )

        self.assertIsNone(res["output_files"]["result_image"])
        self.assertIsNone(res["output_files"]["panel_image"])
        self.assertIsNone(res["output_files"]["object_image"])
        self.assertTrue(any("Không lưu được result_image" in item for item in res["validation"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
