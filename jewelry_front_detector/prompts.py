"""
prompts.py
Chứa system prompt và user prompt gửi đến model Vision trong LM Studio.
"""

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT  (ngắn gọn – model nhỏ ít bị lạc khi system prompt dài)
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a precise visual-grounding assistant for jewelry technical drawings. "
    "You output ONLY valid JSON — no markdown, no explanation, no code fences."
)


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-VIEW PROMPT  (dùng khi chạy từng view riêng lẻ)
# ─────────────────────────────────────────────────────────────────────────────
def get_user_prompt(target_view: str = "FRONT") -> str:
    all_views = ["FRONT", "LEFT", "RIGHT", "TOP", "BOTTOM", "BACK", "PERSPECTIVE"]
    other_views_str = ", ".join(v for v in all_views if v != target_view.upper())

    return f"""You are given a full jewelry technical drawing sheet. Locate the {target_view.upper()} view only.

OUTPUT TWO bounding boxes (coordinates normalized 0–1000, origin = top-left of the full image):

panel_bbox  → the complete rectangular cell/panel that holds the {target_view.upper()} label and content.
              • Follow the visible grid border of the cell.
              • EXCEPTION (PERSPECTIVE only): if it floats without a border, draw a tight imaginary box.
              • Must NOT include other views or the info table on the left.

object_bbox → tight box around ONLY the jewelry model & drawing content INSIDE the {target_view.upper()} panel:
              • INCLUDE: jewelry shape, gemstones, dimension arrows (red/blue), measurement numbers.
              • EXCLUDE: label text "{target_view.upper()}", header text/notes ("NOTES:", "OTES:", "133mm2"), grid border lines, empty white space.
              • Must be strictly inside panel_bbox and SMALLER than panel_bbox.

object_center → [cx, cy] midpoint of object_bbox.

Other views to ignore: {other_views_str}

Return ONLY this JSON:
{{
  "view": "{target_view.upper()}",
  "coordinate_space": "normalized_0_1000_full_image",
  "coordinate_scale": 1000,
  "panel_bbox": [x1, y1, x2, y2],
  "object_bbox": [x1, y1, x2, y2],
  "object_center": [cx, cy]
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# ALL-VIEWS PROMPT  (dùng trong pipeline chính — lần 1)
# ─────────────────────────────────────────────────────────────────────────────
def get_all_views_user_prompt() -> str:
    return """\
You are given a full jewelry technical drawing sheet. Complete TWO tasks.

══════════════════════════════════════════════════════════════════════
TASK A — SHEET METADATA
══════════════════════════════════════════════════════════════════════

drawing_number:
  • Located in the TOP-RIGHT corner of the sheet (large red or black text).
  • Examples: "888800-MOD", "889060 A", "DF27.COMP072_DI_06202026".
  • Extract ONLY the leading numeric group (e.g. "888800-MOD" → "888800").
  • Do NOT copy suffixes (-MOD), revision letters, or the title on the top-left.

metal + brand:
  • Find the "Metal Weight(grams) / Metal" table (usually left side of sheet).
  • The ACTIVE metal row is the one whose weight cell contains a real number (e.g. "0.53 gr", "1.20gr").
  • A weight of "---", "--", "—", or empty = NOT active.
  • Rules:
      – 925 row has real weight  → metal="925",  brand="silver"
      – 14K row has real weight  → metal="14K",  brand="14k"
      – Lab Grown row active     → metal="LG",   brand="labgrown"
  • If both rows are dashes       → metal=null,  brand="NONE",  metal_weight=null

══════════════════════════════════════════════════════════════════════
TASK B — LOCATE ALL 7 VIEWS
══════════════════════════════════════════════════════════════════════

Standard views to find: FRONT, LEFT, RIGHT, TOP, BOTTOM, BACK, PERSPECTIVE.

!! YOU MUST OUTPUT ALL 7 VIEWS. Do NOT stop after 2 or 3. !!

Layout pattern (typical — may vary):
  Row 1 (top):    [FRONT]  [LEFT]   [TOP]
  Row 2 (bottom): [BACK]   [RIGHT]  [BOTTOM]
  Floating corner (no label, no border): [PERSPECTIVE] — the 3D isometric shape

PERSPECTIVE rules:
  • Almost always present as a 3D angled model in a corner (often bottom-left).
  • Usually HAS NO text label and NO grid border.
  • Draw a generous box around the ENTIRE 3D shape (including top curves, bottom tips, prongs, and outer details).
  • Exclude any header text ("NOTES:", "133mm2"), weight numbers ("0.53", "925"), grid border lines, or text labels ("PERSPECTIVE").

For EACH view provide:

  panel_bbox  → full rectangular cell including its label and content.
                Follow visible grid borders. For PERSPECTIVE use a box around the 3D model.

  object_bbox → box around ALL drawing content inside the panel:
                INCLUDE: entire jewelry model, gemstones, dimension arrows (red/blue/black),
                         measurement numbers (red, blue, or inside yellow boxes), all outer edges.
                EXCLUDE: view label text ("FRONT", "LEFT" …), header text/notes, grid border lines,
                         empty white background.
                Must be INSIDE panel_bbox.

  object_center → [cx, cy] center of object_bbox.

All coordinates: normalized integers 0–1000 (0,0 = top-left; 1000,1000 = bottom-right of full image).

══════════════════════════════════════════════════════════════════════
REQUIRED JSON OUTPUT (return this structure — fill in real numbers)
══════════════════════════════════════════════════════════════════════

{
  "drawing_number": "888800",
  "metal": "925",
  "brand": "silver",
  "metal_weight": "0.53 gr",
  "coordinate_scale": 1000,
  "views": [
    {
      "view": "FRONT",
      "coordinate_space": "normalized_0_1000_full_image",
      "panel_bbox": [x1, y1, x2, y2],
      "object_bbox": [x1, y1, x2, y2],
      "object_center": [cx, cy]
    },
    {
      "view": "LEFT",
      "coordinate_space": "normalized_0_1000_full_image",
      "panel_bbox": [x1, y1, x2, y2],
      "object_bbox": [x1, y1, x2, y2],
      "object_center": [cx, cy]
    },
    {
      "view": "TOP",
      "coordinate_space": "normalized_0_1000_full_image",
      "panel_bbox": [x1, y1, x2, y2],
      "object_bbox": [x1, y1, x2, y2],
      "object_center": [cx, cy]
    },
    {
      "view": "BACK",
      "coordinate_space": "normalized_0_1000_full_image",
      "panel_bbox": [x1, y1, x2, y2],
      "object_bbox": [x1, y1, x2, y2],
      "object_center": [cx, cy]
    },
    {
      "view": "RIGHT",
      "coordinate_space": "normalized_0_1000_full_image",
      "panel_bbox": [x1, y1, x2, y2],
      "object_bbox": [x1, y1, x2, y2],
      "object_center": [cx, cy]
    },
    {
      "view": "BOTTOM",
      "coordinate_space": "normalized_0_1000_full_image",
      "panel_bbox": [x1, y1, x2, y2],
      "object_bbox": [x1, y1, x2, y2],
      "object_center": [cx, cy]
    },
    {
      "view": "PERSPECTIVE",
      "coordinate_space": "normalized_0_1000_full_image",
      "panel_bbox": [x1, y1, x2, y2],
      "object_bbox": [x1, y1, x2, y2],
      "object_center": [cx, cy]
    }
  ]
}

STRICT RULES:
- Output ONLY the JSON above — no extra text, no markdown, no code fences.
- views array MUST contain all 7 entries (FRONT, LEFT, TOP, BACK, RIGHT, BOTTOM, PERSPECTIVE).
- All coordinate values must be integers in range [0, 1000].
- object_bbox must be inside and smaller than its panel_bbox.
- If drawing_number or metal cannot be read → use null / "NONE" accordingly."""
