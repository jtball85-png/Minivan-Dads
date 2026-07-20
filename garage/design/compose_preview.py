"""Garage-only tooling for the garage-design skill: rasterize a drafted
SVG and composite it onto a real flat Printful template PNG, inside the
template's print-area guide box.

Produces a FLAT COMPOSITE PREVIEW — the design placed at roughly the
right position/scale/color on the real template art. This is NOT a
photorealistic product mockup (no fabric drape, no lighting, no product
photography) — that requires Printful's real Mockup Generator API and
the governed connector this project has deliberately not built yet.

Not imported by anything under brain/ — pip install -e ".[garage]" first.

Two independent commands — run both, they answer different questions:

    python compose_preview.py preview <svg_path> <template_png_path>
        <calibration_json_path> <output_png_path>
        -> flat composite for placement/color/scale checking. LOW
           resolution (whatever the calibrated print-area box's pixel
           size is on the template graphic — typically far below print
           quality). Never treat this file as print-ready.

    python compose_preview.py print <svg_path> <width_in> <height_in>
        <output_png_path> [dpi, default 300]
        -> the actual print-ready rasterization, at real DPI (Printful's
           own upload examples use 300). THIS is the file that answers
           "is it high enough resolution," not the preview.

calibration_json_path points at a small JSON file describing where the
print-area guide box sits on the template PNG, in pixels:
    {"x": 466, "y": 1314, "width": 188, "height": 244,
     "note": "however this was determined"}
"""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg


def rasterize_svg(svg_path: Path, target_width: int, target_height: int) -> Image.Image:
    """SVG -> PIL Image, scaled to fit inside (target_width, target_height)
    preserving aspect ratio (never stretched/distorted)."""
    drawing = svg2rlg(str(svg_path))
    scale = min(target_width / drawing.width, target_height / drawing.height)
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)

    buf = BytesIO()
    renderPM.drawToFile(drawing, buf, fmt="PNG", backend="rlPyCairo")
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


def export_print_ready(svg_path: Path, width_in: float, height_in: float,
                        output_path: Path, dpi: int = 300) -> Path:
    """Rasterize the SVG at real print resolution (default Printful's own
    300 DPI standard, per their upload example) — a genuinely print-ready
    file, not the small placement-preview render. Independent of the
    flat composite preview; this is the deliverable if a design is
    actually approved."""
    px_w, px_h = round(width_in * dpi), round(height_in * dpi)
    image = rasterize_svg(svg_path, px_w, px_h)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, dpi=(dpi, dpi))
    return output_path


def compose(svg_path: Path, template_png_path: Path, calibration_path: Path,
            output_path: Path) -> Path:
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    box_x, box_y = calibration["x"], calibration["y"]
    box_w, box_h = calibration["width"], calibration["height"]

    template = Image.open(template_png_path).convert("RGBA")
    design = rasterize_svg(svg_path, box_w, box_h)

    # Center the (aspect-preserved) design inside the print-area box.
    paste_x = box_x + (box_w - design.width) // 2
    paste_y = box_y + (box_h - design.height) // 2

    composite = template.copy()
    composite.alpha_composite(design, dest=(paste_x, paste_y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    composite.save(output_path)
    return output_path


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "preview" and len(args) == 5:
        svg_p, template_p, calib_p, out_p = (Path(a) for a in args[1:5])
        result = compose(svg_p, template_p, calib_p, out_p)
        print(f"Wrote flat composite preview (LOW-RES, placement-check only, not print-ready): {result}")
    elif args and args[0] == "print" and len(args) in (5, 6):
        svg_p = Path(args[1])
        w_in, h_in = float(args[2]), float(args[3])
        out_p = Path(args[4])
        dpi = int(args[5]) if len(args) == 6 else 300
        result = export_print_ready(svg_p, w_in, h_in, out_p, dpi=dpi)
        print(f"Wrote print-ready export ({dpi} DPI, {round(w_in*dpi)}x{round(h_in*dpi)}px): {result}")
    else:
        print(__doc__)
        raise SystemExit(1)
