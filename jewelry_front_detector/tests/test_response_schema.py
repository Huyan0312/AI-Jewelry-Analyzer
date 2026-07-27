import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lmstudio_client import (
    extract_json_safe,
    _normalize_drawing_number,
    _normalize_brand_metal,
    normalize_all_views_payload,
)


class TestResponseSchema(unittest.TestCase):

    def test_extract_json_safe_pure_json(self):
        data = '{"view": "FRONT", "panel_bbox": [0, 0, 100, 100]}'
        result = extract_json_safe(data)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("view"), "FRONT")

    def test_extract_json_safe_code_fence(self):
        data = """Here is the result:
```json
{
  "view": "FRONT",
  "panel_bbox": [10, 20, 30, 40]
}
```
Hope this helps!"""
        result = extract_json_safe(data)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("view"), "FRONT")

    def test_extract_json_safe_embedded_json(self):
        data = 'Sure! {"drawing_number": "888400", "views": []} Thanks.'
        result = extract_json_safe(data)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("drawing_number"), "888400")

    def test_extract_json_safe_invalid_text(self):
        self.assertIsNone(extract_json_safe("Not a json at all!"))
        self.assertIsNone(extract_json_safe(""))
        self.assertIsNone(extract_json_safe(None))

    def test_normalize_drawing_number(self):
        num, raw = _normalize_drawing_number("889486 A")
        self.assertEqual(num, "889486")
        self.assertEqual(raw, "889486 A")

        num, raw = _normalize_drawing_number("DF27.COMP072_DI_06202026")
        self.assertEqual(num, "06202026")
        self.assertEqual(raw, "DF27.COMP072_DI_06202026")

        num, raw = _normalize_drawing_number("null")
        self.assertIsNone(num)
        self.assertIsNone(raw)

    def test_normalize_brand_metal(self):
        m, b = _normalize_brand_metal("925 Sterling Silver", "Silver")
        self.assertEqual(m, "925")
        self.assertEqual(b, "silver")

        m, b = _normalize_brand_metal("14K Yellow Gold", "14k")
        self.assertEqual(m, "14K")
        self.assertEqual(b, "14k")

        m, b = _normalize_brand_metal(None, None)
        self.assertIsNone(m)
        self.assertEqual(b, "NONE")

    def test_normalize_all_views_payload_object_format(self):
        parsed = {
            "drawing_number": "888900 B+F",
            "metal": "925",
            "brand": "silver",
            "metal_weight": "0.55 gr",
            "views": [
                {
                    "view": "FRONT",
                    "panel_bbox": [0, 0, 500, 500],
                    "object_bbox": [10, 10, 400, 400],
                }
            ],
        }
        views, sheet = normalize_all_views_payload(parsed)
        self.assertEqual(len(views), 1)
        self.assertEqual(sheet["drawing_number"], "888900")
        self.assertEqual(sheet["drawing_number_raw"], "888900 B+F")
        self.assertEqual(sheet["metal"], "925")
        self.assertEqual(sheet["brand"], "silver")
        self.assertEqual(sheet["metal_weight"], "0.55 gr")

    def test_normalize_all_views_payload_list_format(self):
        parsed = [
            {
                "view": "FRONT",
                "panel_bbox": [0, 0, 500, 500],
                "object_bbox": [10, 10, 400, 400],
            }
        ]
        views, sheet = normalize_all_views_payload(parsed)
        self.assertEqual(len(views), 1)
        self.assertIsNone(sheet["drawing_number"])


if __name__ == "__main__":
    unittest.main()
