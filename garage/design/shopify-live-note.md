# Shopify live-store snapshot (manual — may be stale)

Snapshot date: **2026-07-21** (live fetch of joshballart.com by Claude Code).
This is a manual eyeball record, NOT machine-verified — that's why it lives
in garage/ and not hq/products/ (everything under hq/ is written only by
hq.py from verified API reads). Refresh by asking Claude Code to re-check
the storefront. A real Shopify connector (which would make this file
obsolete) is a separate, CEO-gated future build.

## Confirmed live: /collections/drinkware

| Product | URL path | Price | Variants seen |
|---|---|---|---|
| Bodysurf Fin White Glossy Mug | `/products/white-glossy-mug-1` | from $9.00 | Sizes 11oz/15oz/20oz; color combos: Red Yellow, Peach Burnt Orange, Blue Pink, Peach Blue, Lime Green Electric Blue, Lavender Teal, Black White |
| Josh Ball Art Logo White Glossy Mug | `/products/white-glossy-mug` | from $9.00 | "California Living" logo design |
| Bodysurf Fin Enamel Cup | `/products/ride-the-foam-with-every-sip-josh-ball-art-bodysurf-fin-enamel-cup` | $14.00 | White, 12oz |
| Bodysurf Fin Tumbler | `/products/wine-tumbler` | from $19.00 | White ("Sunsets & Sips") |

## Not checked in that pass

Other collections (prints, apparel, Jacquard supplies, etc.) — this fetch
covered drinkware only. The known store-wide picture from the 2026-07-21
storefront-agent audit still stands: ~73% of listings are Jacquard supplies
(36+ sold out), own-art commerce nearly empty (the "inverted store"
problem, tracked in hq/directives/storefront.md standing order #1).
