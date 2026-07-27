import unittest
from unittest.mock import patch, MagicMock
import sys
import tempfile
import json
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
HEADLESS_DIR = PROJECT_ROOT.parent / "PTS CS5 SCRIPT"
if str(HEADLESS_DIR) not in sys.path:
    sys.path.insert(0, str(HEADLESS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import headless_detector as hd


def make_valid_view(name):
    return {
        "view": name,
        "coordinate_scale": 1000,
        "panel_bbox": [0, 0, 500, 500],
        "object_bbox": [50, 50, 450, 450],
        "object_center": [250, 250],
    }


def make_valid_all_views_dict():
    names = ["FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "BACK", "PERSPECTIVE"]
    return {
        "sheet": {
            "drawing_number": "888555",
            "drawing_number_raw": "888555 A",
            "metal": "925",
            "brand": "silver",
            "metal_weight": "1.20 gr",
        },
        "views": [make_valid_view(name) for name in names],
        "raw_response": "...",
        "request_meta": {},
        "validation": {"valid": True, "errors": []},
        "error": None,
        "error_type": None,
    }


class TestHeadlessDetectorContract(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = Path(self.temp_dir.name)

        self.input_dir = self.temp_dir_path / "input"
        self.output_dir = self.temp_dir_path / "output"
        self.processing_dir = self.input_dir / "_processing"
        self.failed_dir = self.processing_dir / "_failed"

        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

        self.img_path = self.temp_dir_path / "test_sample.png"
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img.save(self.img_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("lmstudio_client.send_image_to_model_dimensions")
    @patch("headless_detector.send_image_to_model_all_views")
    @patch("image_processor.process_image")
    def test_headless_process_image_success(self, mock_process_image, mock_send_all, mock_dim):
        mock_dim.return_value = None
        mock_send_all.return_value = make_valid_all_views_dict()
        mock_process_image.return_value = {"pixel": {"refined_object_bbox": [50, 50, 450, 450]}}

        with patch.object(hd, "OUTPUT_DIR", self.output_dir), \
             patch.object(hd, "INPUT_DIR", self.input_dir), \
             patch.object(hd, "PROCESSING_DIR", self.processing_dir), \
             patch.object(hd, "FAILED_DIR", self.failed_dir):
            hd.process_image(self.img_path, model_name="test-model", move_source=False)

        self.assertEqual(mock_send_all.call_count, 1)
        self.assertEqual(mock_process_image.call_count, 7)

        # Output JSON created inside temp directory only
        out_json = self.output_dir / "test_sample_all_views_result.json"
        self.assertTrue(out_json.exists())

    @patch("lmstudio_client.send_image_to_model_dimensions")
    @patch("headless_detector.send_image_to_model_all_views")
    @patch("headless_detector._move_to_failed")
    def test_headless_process_image_error_moves_to_failed(self, mock_move_failed, mock_send_all, mock_dim):
        mock_dim.return_value = None
        mock_send_all.return_value = {
            "sheet": {},
            "views": None,
            "raw_response": "",
            "request_meta": {},
            "validation": {"valid": False, "errors": ["SchemaValidationError"]},
            "error": "SchemaValidationError: Missing BACK view",
            "error_type": "SchemaValidationError",
        }

        with patch.object(hd, "OUTPUT_DIR", self.output_dir), \
             patch.object(hd, "INPUT_DIR", self.input_dir), \
             patch.object(hd, "PROCESSING_DIR", self.processing_dir), \
             patch.object(hd, "FAILED_DIR", self.failed_dir):
            hd.process_image(self.img_path, model_name="test-model", move_source=True)

        self.assertEqual(mock_move_failed.call_count, 1)


if __name__ == "__main__":
    unittest.main()
