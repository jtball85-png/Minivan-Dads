"""Josh Ball Art — print derivation pipeline (masters -> print-ready files).

The master is never touched: full-res, native ratio, borderless. This script
derives white-border print files for the standard sheet trio (8x10, 11x14,
16x20) per the fine-art convention: the image scales to fit INSIDE the sheet
at its natural aspect ratio, centered, and the white border absorbs the
ratio difference. Sheets auto-rotate to match image orientation (a landscape
image gets a 20x16 sheet, not a 16x20).

Resolution honesty: sheet canvas is always 300 DPI; the image's EFFECTIVE DPI
(source pixels / printed inches) is measured per size and flagged:
  >=300 excellent · >=200 acceptable (FinerWorks floor) · <200 FAIL (do not
  sell at this size; never upscaled silently).

Output per master: ready/{name}/{size}.jpg (sRGB JPEG q95, 300 DPI tag) +
proofs/{name}-proof.jpg contact sheet + a printed DPI report.

Usage:
  .venv/Scripts/python.exe garage/prints/derive_prints.py            # all masters
  .venv/Scripts/python.exe garage/prints/derive_prints.py <file>...  # specific
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
MASTERS, READY, PROOFS = ROOT / "masters", ROOT / "ready", ROOT / "proofs"
DPI = 300
# (sheet short side, long side, minimum border) in inches
SHEETS = [("8x10", 8, 10, 0.5), ("11x14", 11, 14, 0.75), ("16x20", 16, 20, 1.0)]


def derive(master_path: Path) -> list[str]:
    img = Image.open(master_path)
    img = img.convert("RGB")  # print files ship flattened sRGB
    iw, ih = img.size
    landscape = iw >= ih
    out_dir = READY / master_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    report, sheet_files = [], []

    for name, s_short, s_long, min_border in SHEETS:
        sw_in, sh_in = (s_long, s_short) if landscape else (s_short, s_long)
        # printable window inside the minimum border
        win_w, win_h = sw_in - 2 * min_border, sh_in - 2 * min_border
        scale = min(win_w / iw, win_h / ih)          # inches per source pixel
        pw_in, ph_in = iw * scale, ih * scale        # printed image size
        eff_dpi = iw / pw_in                          # = ih / ph_in
        verdict = ("excellent" if eff_dpi >= 300 else
                   "acceptable" if eff_dpi >= 200 else "FAIL — too small")

        sheet = Image.new("RGB", (round(sw_in * DPI), round(sh_in * DPI)), "white")
        placed = img.resize((round(pw_in * DPI), round(ph_in * DPI)), Image.LANCZOS)
        sheet.paste(placed, ((sheet.width - placed.width) // 2,
                             (sheet.height - placed.height) // 2))
        out = out_dir / f"{name}.jpg"
        sheet.save(out, "JPEG", quality=95, dpi=(DPI, DPI))
        sheet_files.append((name, sheet, verdict))
        report.append(f"  {name:6} sheet {sw_in}x{sh_in}\"  image {pw_in:.1f}x{ph_in:.1f}\" "
                      f" effective {eff_dpi:.0f} DPI  -> {verdict}")

    # proof contact sheet: the three layouts side by side, scaled down
    PROOFS.mkdir(exist_ok=True)
    thumb_h = 700
    thumbs = []
    for name, sheet, verdict in sheet_files:
        t = sheet.copy()
        t.thumbnail((thumb_h * 2, thumb_h), Image.LANCZOS)
        thumbs.append((name, t, verdict))
    total_w = sum(t.width for _, t, _ in thumbs) + 40 * (len(thumbs) + 1)
    proof = Image.new("RGB", (total_w, thumb_h + 110), (34, 36, 40))
    d = ImageDraw.Draw(proof)
    x = 40
    for name, t, verdict in thumbs:
        proof.paste(t, (x, 40))
        color = (120, 220, 150) if "FAIL" not in verdict else (240, 120, 110)
        d.text((x, thumb_h + 55), f"{name}  ·  {verdict}", fill=color)
        x += t.width + 40
    proof_path = PROOFS / f"{master_path.stem}-proof.jpg"
    proof.save(proof_path, "JPEG", quality=90)
    report.append(f"  proof: {proof_path}")
    return report


def main(args: list[str]) -> None:
    MASTERS.mkdir(parents=True, exist_ok=True)
    targets = ([Path(a) for a in args] if args else
               sorted(p for p in MASTERS.iterdir()
                      if p.suffix.lower() in (".tif", ".tiff", ".jpg", ".jpeg", ".png")))
    if not targets:
        print(f"No masters found in {MASTERS} — drop a flattened full-res export there.")
        return
    for m in targets:
        print(f"\n{m.name}  ({Image.open(m).size[0]}x{Image.open(m).size[1]} px)")
        for line in derive(m):
            print(line)


if __name__ == "__main__":
    main(sys.argv[1:])
