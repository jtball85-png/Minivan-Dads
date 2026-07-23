# Shopify live-store snapshot (manual — may be stale)

Snapshot dates: **2026-07-21** (drinkware collection) + **2026-07-23**
(all-products pass) — live fetches of joshballart.com by Claude Code.
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

## Confirmed live: prints (2026-07-23 pass)

| Product | Price |
|---|---|
| Catch a Wave of Color: Bodysurf Fin Enhanced Matte Paper Poster | from $23.00 |
| Catch a Wave of Color: Bodysurf Fin Enhanced Matte Paper Poster **Framed** | from $45.09 |

(Poster was previously classified art-ready-not-live in the manifest —
corrected to live 2026-07-23.)

## Printful account note (2026-07-23, important)

The `.env` `PRINTFUL_API_KEY` belongs to a Printful account whose ONLY
store is **"Theminivandads"** (id 18493772, 1 sync product, 0 product
templates). The joshballart products above are fulfilled by a **different
Printful account** the brain has no API access to. CEO action needed: create
an API token in the joshballart Printful account (Settings → Developers)
and update `.env`. Until then, live-store review is storefront-fetch only.

## Not checked in that pass

Other collections (prints, apparel, Jacquard supplies, etc.) — this fetch
covered drinkware only. The known store-wide picture from the 2026-07-21
storefront-agent audit still stands: ~73% of listings are Jacquard supplies
(36+ sold out), own-art commerce nearly empty (the "inverted store"
problem, tracked in hq/directives/storefront.md standing order #1).
