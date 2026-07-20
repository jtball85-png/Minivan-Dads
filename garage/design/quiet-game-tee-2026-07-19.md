# Design draft: "Let's play the quiet game." — t-shirt

status: finalized — pending CEO review via real Printful mockups (governed
connector build, 2026-07-20)

## Product selection (grounded in lineup research)

T-shirt, per `garage/research/product-lineup-and-color-combos-2026-07-19.md`:
kept as the brand-identity anchor per that research's own framing — not
a margin play (thinnest-margin category found in the research), but the
right product for a first, recognizable piece.

## Copy

"Let's play the quiet game." — from
`garage/research/dad-sayings-and-roadtrip-oneliners-2026-07-19.md`,
Section 5B (independently verified touchstone, documented enough to be
referenced in Pixar's *Up*; also directly confirms one of the CEO's own
remembered lines). Used verbatim — no new copy written for this draft.

## Color

White text on any dark garment. Confirmed to read cleanly on all three
target colorways — **Black, Navy, and Heather grey** — with a single
transparent print file (see the 3-up colorway check run 2026-07-20).
Black is the #1 ranked shirt combo from the color-combo research; navy and
heather are also cross-product anchors in that same research. Single-color
print, no distressed treatment.

## The upload file (transparent) vs. the preview swatch (black)

`quiet-game-tee-2026-07-19-upload-300dpi.png` is the file that goes to
Printful: **transparent background, white text only.** The black rectangle
in the SVG / flat preview is a preview-only contrast swatch — it is NOT in
the upload file. Printing a black box would waste ink on a black shirt and
look broken on navy/heather; the transparent file prints only the white
text, so one file serves all three dark colorways. (Note: the garage
rasterizer fills white and can't emit transparency directly — the upload
file is made by rendering white-on-solid-black and converting luminance to
alpha. A reusable transparent-export helper for the garage-design tooling
is a worthwhile follow-up, since every dark-garment design needs this.)

## Dimensions

**Printful-confirmed**, not an approximation: 12in × 16in front print
area, from the real template at
`garage/design/printful-templates/t-shirt-bella-canvas-3001/` (Bella +
Canvas 3001 — the exact product Printful's own API returns for a
t-shirt query).

## Files

- `quiet-game-tee-2026-07-19.svg` — the draft, 1200×1600px canvas
  (100px/in @ 12×16in).
- `quiet-game-tee-2026-07-19-preview.png` — flat composite preview,
  design placed in the real template's print-area guide. **Low
  resolution by design (~16 px/in at the calibrated print-area box) —
  for placement/color checking only, never treat as print-ready.**
- `quiet-game-tee-2026-07-19-print-300dpi.png` — the actual print-ready
  export, 3600×4800px at 300 DPI (Printful's own stated standard). This
  is the file that answers "is it high enough resolution" — yes.

**Flat preview caveat:** the black rectangle represents the intended
black-shirt colorway *for contrast-checking within the print zone only*
— it is not the whole garment recolored, and this is not a
photorealistic mockup (no fabric drape, lighting, or product
photography). That needs the real Printful connector, not yet built.

## Measured sizes (empirical, from the rendered 300 DPI file)

- **Cap height ≈ 0.93 in** per line — roughly inch-tall caps, readable.
- **Text block ≈ 2.43 in tall × 6.55 in wide**, inside the 12 × 16 in
  front print area with comfortable margin.
- **Vertical centering: exact (0 px offset)** — measured, not eyeballed.

## Revision history (caught on self-review, fixed before presenting)

- v1: text read small in the flat preview; the block sat above center.
- v2 (07-19): font size 110→130, re-centered by hand — improved but the
  y-coords were hand-picked, leaving a small residual offset, flagged
  honestly.
- **v3 (07-20, current): centering resolved empirically.** Rasterized the
  SVG, measured the white-text bounding box in pixels, and shifted the
  block by the measured +6 px so its ink-center sits exactly on canvas
  center (re-measured offset = 0). Also produced the transparent upload
  file and verified the design on all three colorways. The design is now
  finalized; the remaining review is the CEO's, via real Printful mockups.
