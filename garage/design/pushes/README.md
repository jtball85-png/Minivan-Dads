# Push specs — one YAML per Printful product push

Run with `garage/design/push_printful_product.py` (dry-run by default;
`--live --ceo-note "..."` only after the CEO approves that specific push).
Printful catalog product ids and size strings are verified against the live
catalog API at spec-writing time — note Printful's size strings use the
Unicode double-prime (″), not a straight quote.

## Status board (2026-07-23)

| Spec | Product (catalog id) | Status | Blocker |
|---|---|---|---|
| `quiet-game-tee.yaml` | Bella+Canvas 3001 tee (71) | historical — pushed 2026-07-20, MVD era, parked | — |
| `bodysurf-fin-water-bottle.yaml` | Stainless Steel Water Bottle (382) | prepared + dry-run rehearsed | needs JBA Printful token + hosted print file |
| `bodysurf-fin-die-cut-stickers.yaml` | Die-Cut Stickers (957) | prepared + dry-run rehearsed | needs JBA token + a TRANSPARENT print file (see spec) |
| `bodysurf-fin-tee.yaml` | Bella+Canvas 3001 tee (71) | prepared | needs JBA token + print file exported from the drive's finished tee art |

## Candidates evaluated but NOT spec'd (and why)

Grounded in `garage/research/product-lineup-and-color-combos-2026-07-19.md`
and the real embroidery constraints on file:

- **Beach Towel (259, 30″×60″)** — strong coastal-brand fit for this design;
  recommended as the next spec IF the CEO likes it. Held back only because
  it's a judgment call on brand fit (big-format placement of the fin needs a
  look), not an economics one.
- **Adidas Dad Hat (638)** — the lineup research favors dad hats over
  beanies, BUT this design can't go on it as-is: embroidery minimums
  (0.25–0.3in letter height, no fine negative-space detail — see the real
  Printful guidelines PDF in `printful-templates/embroidered-beanie/`) rule
  out the fin's internal "BODY SURF" lettering at hat scale. Needs a
  simplified mark (CEO's call, CEO's art) before a hat is possible.
- **Tote bags** — explicitly negative finding in the lineup research (the
  one credible product-matched review panned Printful tote print quality).
  Not recommended without ordering a sample first.
- **All-over-print products (hoodies, etc.)** — different art format
  (repeating pattern, not a placed graphic); out of scope for this design's
  current masters.

## Poster note

The poster is already LIVE on joshballart.com ("Catch a Wave of Color",
poster + framed variants) — discovered 2026-07-23, manifest corrected. No
spec needed unless the CEO wants additional sizes/colorways listed, which
would also reopen the large-file-hosting question for the 489MB of poster
art on the drive.
