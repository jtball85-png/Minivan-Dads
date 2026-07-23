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

## Printful account note (RESOLVED 2026-07-23)

The original `.env` key belonged to the parked Minivan Dads Printful account
(store "Theminivandads", now preserved as `PRINTFUL_API_KEY_MVD` /
`PRINTFUL_STORE_ID_MVD`). The CEO created a token for the **Josh Ball Art**
Printful account same day — now the primary `PRINTFUL_API_KEY`, store id
**13032926** (Shopify platform).

### API-verified synced products (2026-07-23, via /sync/products)

| Sync id | Product | Variants |
|---|---|---|
| 334838344 | Catch a Wave of Color: Bodysurf Fin Poster — Framed | 90 |
| 334775587 | Catch a Wave of Color: Bodysurf Fin Poster | 55 |
| 334471140 | Shred in Style: Black Fin Bodysurf **Cuffed Beanie** | 6 |
| 334165864 | Sunsets & Sips: Bodysurf Fin Tumbler | 7 |
| 334161181 | Ride the Foam: Bodysurf Fin Enamel Cup | 7 |
| 334116103 | Josh Ball Art Logo White Glossy Mug (California Living) | 3 |
| 334113961 | Bodysurf Fin White Glossy Mug (21 = 3 sizes × 7 combos) | 21 |

Variant-level reads work (retail prices, SKUs, print files). The beanie was
previously misclassified art-ready-not-live — corrected to live.

### Known token/platform limits (2026-07-23)

- Token lacks the `product_templates/read` scope (403) — CEO to add it in
  Printful → Settings → Developers when convenient (+ Orders read for
  future fulfillment tracking).
- Shopify-platform stores use the ecommerce **sync** API (`/sync/products`),
  not the manual-store `/store/products` API the connector was built
  against — reads + edits of existing synced products are supported;
  **creating new products via API is not** (new products are created in the
  Printful dashboard and pushed to Shopify). The connector needs a
  platform-aware extension before any governed edit actions run against
  this store; new-product pushes remain dashboard work (CEO) for now.

## Not checked in that pass

Other collections (prints, apparel, Jacquard supplies, etc.) — this fetch
covered drinkware only. The known store-wide picture from the 2026-07-21
storefront-agent audit still stands: ~73% of listings are Jacquard supplies
(36+ sold out), own-art commerce nearly empty (the "inverted store"
problem, tracked in hq/directives/storefront.md standing order #1).
