import unittest
from unittest.mock import patch, MagicMock
import sys
import json
import tempfile
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lmstudio_client import (
    prepare_image_data_url_for_lm,
    send_image_to_model,
    send_image_to_model_all_views,
)


def make_valid_view_item(name):
    return {
        "view": name,
        "coordinate_scale": 1000,
        "panel_bbox": [0, 0, 500, 500],
        "object_bbox": [50, 50, 450, 450],
        "object_center": [250, 250],
    }


def make_valid_all_views_payload():
    names = ["FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "BACK", "PERSPECTIVE"]
    return {
        "drawing_number": "999000",
        "coordinate_scale": 1000,
        "views": [make_valid_view_item(name) for name in names],
    }


class TestLMStudioPayload(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = Path(self.temp_dir.name)

        # Create a small sample image (100x100 RGB)
        self.small_img_path = self.temp_dir_path / "small.png"
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(self.small_img_path)

        # Create a large sample image (3000x2000 RGB)
        self.large_img_path = self.temp_dir_path / "large.jpg"
        img_large = Image.new("RGB", (3000, 2000), color=(0, 255, 0))
        img_large.save(self.large_img_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prepare_image_small_no_resize(self):
        data_url, meta = prepare_image_data_url_for_lm(self.small_img_path, max_size=2048)
        self.assertTrue(data_url.startswith("data:image/jpeg;base64,"))
        self.assertFalse(meta["resized"])
        self.assertEqual(meta["send_w"], 100)
        self.assertEqual(meta["send_h"], 100)

    def test_prepare_image_large_resized(self):
        data_url, meta = prepare_image_data_url_for_lm(self.large_img_path, max_size=2048)
        self.assertTrue(data_url.startswith("data:image/jpeg;base64,"))
        self.assertTrue(meta["resized"])
        self.assertEqual(meta["send_w"], 2048)
        self.assertEqual(meta["send_h"], 1365)
        self.assertEqual(meta["orig_w"], 3000)

    @patch("requests.post")
    def test_send_image_to_model_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        valid_view = make_valid_view_item("FRONT")
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(valid_view)
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = send_image_to_model(self.small_img_path, model="test-model", target_view="FRONT")
        self.assertIsNone(res["error"])
        self.assertIsNone(res["error_type"])
        self.assertIsNotNone(res["parsed_json"])
        self.assertEqual(res["parsed_json"]["view"], "FRONT")
        self.assertTrue(res["validation"]["valid"])

    @patch("requests.post")
    def test_send_image_to_model_single_view_schema_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Incomplete payload: missing object_bbox and object_center
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"view": "FRONT", "panel_bbox": [0,0,100,100]}'}}]
        }
        mock_post.return_value = mock_resp

        res = send_image_to_model(self.small_img_path, model="test-model", target_view="FRONT", retry_count=0)
        self.assertEqual(res["error_type"], "SchemaValidationError")
        self.assertIsNone(res["views"])
        self.assertFalse(res["validation"]["valid"])

    @patch("requests.post")
    def test_send_image_to_model_all_views_retry_on_invalid_json_then_success(self, mock_post):
        # 1st attempt returns invalid JSON, 2nd attempt returns valid 7-views payload
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {"choices": [{"message": {"content": "Not JSON at all!"}}]}

        resp2 = MagicMock()
        resp2.status_code = 200
        valid_payload = make_valid_all_views_payload()
        resp2.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(valid_payload)
                    }
                }
            ]
        }
        mock_post.side_effect = [resp1, resp2]

        res = send_image_to_model_all_views(self.small_img_path, model="test-model", retry_count=2)
        self.assertEqual(mock_post.call_count, 2)
        self.assertIsNone(res["error"])
        self.assertEqual(len(res["views"]), 7)
        self.assertEqual(res["sheet"]["drawing_number"], "999000")
        self.assertTrue(res["validation"]["valid"])

    @patch("requests.post")
    def test_send_image_to_model_all_views_schema_error(self, mock_post):
        # Returns incomplete payload (only 1 view)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"drawing_number": "999000", "views": [make_valid_view_item("FRONT")]})
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = send_image_to_model_all_views(self.small_img_path, model="test-model", retry_count=0)
        self.assertEqual(res["error_type"], "SchemaValidationError")
        self.assertIsNone(res["views"])
        self.assertFalse(res["validation"]["valid"])

    @patch("requests.post")
    def test_send_image_to_model_connection_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        res = send_image_to_model(self.small_img_path, model="test-model")
        self.assertEqual(res["error_type"], "ConnectionError")
        self.assertIn("Không thể kết nối", res["error"])


if __name__ == "__main__":
    unittest.main()
