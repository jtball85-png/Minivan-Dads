# Live-store review — joshballart.com POD products (2026-07-23)

Garage review by Claude Code using the JBA Printful API (retail prices +
Printful catalog costs per variant) and public storefront fetches. Margin
math uses Printful's catalog base prices as cost — actual invoiced cost can
differ slightly (fulfillment/branding add-ons), so treat margins as ±2-3pt.
Charter rule this review runs against: **30% margin floor on POD**
(hq/charter/company.md, revenue line 4). Pricing changes are CEO-ONLY —
everything below is a recommendation, nothing was changed.

## Headline: 97 of 189 priced variants are below the 30% floor

| Product | Variants | Margin | Below floor | Verdict |
|---|---|---|---|---|
| Poster (unframed) | 55 | **57–70%** | 0 | ✅ excellent — the model product |
| Cuffed Beanie | 6 | **47%** | 0 | ✅ healthy |
| Poster (framed) | 90 | 25–33% | 60 | ⚠️ borderline — frames are costly |
| Bodysurf Fin Mug | 21 | 23–37% | 20 | ⚠️ most combos under floor |
| Logo Mug | 3 | 23–27% | 3 | ⚠️ under floor |
| **Enamel Cup** | 7 | **11%** | 7 | 🚨 nearly break-even |
| **Tumbler** | 7 | **9%** | 7 | 🚨 nearly break-even — $19.00 retail vs $17.29 cost = **$1.71/sale** |

## Price recommendations (CEO decision required — escalated, not applied)

1. **Tumbler $19 → $27–29.** Cost $17.29. At $28: 38% margin. Printful's
   own suggested retail for this blank is typically $25–30; comparable
   artist tumblers sell $28–35. Selling at $19 is working for free.
2. **Enamel Cup $14 → $19–20.** Cost $12.42. At $19.50: 36%. Enamel camp
   mugs from art brands commonly run $18–24.
3. **Bodysurf Fin Mug: floor at $12.50–13.** Costs vary by combo
   ($6.95–$8.50); $12.50 puts the worst combo at 32%. Alternatively price
   11oz/$12, 15oz/$14, 20oz/$16 (size-laddered, standard practice).
4. **Logo Mug: same ladder as above** (currently $11–13 on $8.50–9.50 costs).
5. **Framed poster: raise the under-floor 60 variants** (mostly larger
   sizes/black frames, e.g. 18×24 Black at $60.39 vs $45.39 cost = 25%).
   A flat +$8 on framed variants clears the floor everywhere. OR: accept
   sub-30% on frames deliberately as a premium-feel offering — CEO's call,
   the charter allows a deliberate exception if ruled.
6. **Poster (unframed): leave alone.** Best economics in the store.

## Copy/SEO review (sample: Tumbler listing, storefront fetch)

What's already good: benefit-led opening paragraph, specs (capacity,
materials, dimensions), 10 photos, made-to-order shipping note, size table.

Gaps found (likely pattern across all 7 — full audit once Shopify API
access exists):
- **No care instructions** (dishwasher/handwash — buyers ask, and it's a
  return-prevention line).
- **Copy tone drifts generic-POD** ("conquering city streets", "frosty
  cocktails") — not the charter's voice (tactile, coastal, plain talk, no
  hype). The brand story (Ventura, CEO's own design, bodysurfing) is
  absent from the description — that's the differentiator vs. every other
  POD tumbler.
- **Titles are colon-chained** ("Sunsets & Sips: Josh Ball Art Bodysurf
  Fin Tumbler") — readable, but the format spends the first words on a
  tagline instead of search terms. "Bodysurf Fin Tumbler — Josh Ball Art"
  front-loads what people actually search.
- No visible meta description control (needs Shopify access to verify/set).

## What "the brain runs the store" means (charter-checked)

CAN be fully machine-run once Shopify API access exists: listing copy,
SEO titles/meta, image selection/order, collection organization, dead-listing
hygiene, weekly audits, margin monitoring with automatic escalations.
ALWAYS stays CEO-only (enforced in code, not just policy): price changes,
publishing new products, brand identity, account/app creation.

## Blockers to full store management (in order)

1. **Shopify Admin API token** — CEO creates it (see chat instructions,
   2026-07-23). Unblocks: descriptions, SEO, images, collections.
2. **Shopify connector build** (`brain/connectors/shopify.py`) — the
   `shopify.*` action types already exist in the registry/limits; the
   connector is the missing piece. Build after (1).
3. **Platform-aware Printful extension** — the current connector's
   product-management paths are manual-store-only; the JBA store needs
   `/sync/products`-based read/edit methods. Needed for print-file-level
   changes; not needed for Shopify listing work.
