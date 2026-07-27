import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gui import AnalysisAllViewsWorker
from result_contract import EXPECTED_VIEWS


class TestGuiWorkers(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image_path = self.root / "worker.png"
        image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        ok, encoded = cv2.imencode(".png", image)
        self.assertTrue(ok)
        encoded.tofile(str(self.image_path))

    def tearDown(self):
        self.temp.cleanup()

    def _response(self, names):
        return {
            "sheet": {"drawing_number": "123456", "metal": "925"},
            "views": [
                {
                    "view": name,
                    "coordinate_scale": 1000,
                    "panel_bbox": [0, 0, 1000, 1000],
                    "object_bbox": [100, 100, 900, 900],
                    "object_center": [500, 500],
                }
                for name in names
            ],
            "raw_response": "fixture",
        }

    def _fake_process(self, image_path, payload, *args, **kwargs):
        view = kwargs["target_view"]
        crop = self.root / f"{view}.png"
        crop.write_bytes(b"png")
        return {
            "view_name": view,
            "validation": {"valid": True},
            "output_files": {"object_image": str(crop)},
        }

    def test_full_response_emits_finished_contract(self):
        worker = AnalysisAllViewsWorker(self.image_path, "model", "url")
        finished = []
        errors = []
        worker.finished.connect(finished.append)
        worker.error.connect(errors.append)
        with patch(
            "lmstudio_client.send_image_to_model_all_views",
            return_value=self._response(EXPECTED_VIEWS),
        ), patch("image_processor.process_image", side_effect=self._fake_process):
            worker.run()

        self.assertFalse(errors)
        self.assertEqual(len(finished), 1)
        self.assertEqual(finished[0]["status"], "SUCCESS")
        self.assertEqual(finished[0]["sheet"]["drawing_number"], "123456")

    def test_missing_view_emits_partial_not_false_success(self):
        worker = AnalysisAllViewsWorker(self.image_path, "model", "url")
        finished = []
        errors = []
        worker.finished.connect(finished.append)
        worker.error.connect(errors.append)
        with patch(
            "lmstudio_client.send_image_to_model_all_views",
            return_value=self._response(EXPECTED_VIEWS[:-1]),
        ), patch("image_processor.process_image", side_effect=self._fake_process):
            worker.run()

        self.assertFalse(errors)
        self.assertEqual(finished[0]["status"], "PARTIAL")
        self.assertEqual(finished[0]["validation"]["missing_views"], ["PERSPECTIVE"])

    def test_one_crop_error_keeps_good_views_but_status_is_partial(self):
        def process_with_failure(image_path, payload, *args, **kwargs):
            if kwargs["target_view"] == "BACK":
                raise RuntimeError("crop failed")
            return self._fake_process(image_path, payload, *args, **kwargs)

        worker = AnalysisAllViewsWorker(self.image_path, "model", "url")
        finished = []
        worker.finished.connect(finished.append)
        with patch(
            "lmstudio_client.send_image_to_model_all_views",
            return_value=self._response(EXPECTED_VIEWS),
        ), patch("image_processor.process_image", side_effect=process_with_failure):
            worker.run()

        self.assertEqual(finished[0]["status"], "PARTIAL")
        self.assertEqual(finished[0]["validation"]["views_saved"], 6)
        self.assertIn("BACK", finished[0]["validation"]["failed_views"])


if __name__ == "__main__":
    unittest.main()
