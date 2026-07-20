# Design → Store Pipeline (the repeatable process)

**Purpose.** Turn a research insight into a live, selling product — the same
way every time. This is the playbook Minivan Dads runs for *every* new design,
not a one-off. Read it top to bottom once; after that it's a checklist.

**Plain-language rule of the whole thing:** the machine (Claude Code + the
department agents) does the making and the drafting; **you (CEO) do the four
things the charter reserves for a human — spend money, own the brand, sign
legal, and hit Publish.** Everything the machine builds stops politely at
those walls with a draft ready for your yes.

---

## The flywheel (not a line)

```
  (1) RESEARCH ──▶ (2) DESIGN ──▶ (3) PRODUCT + MOCKUP ──▶ (4) LISTING DRAFT
        ▲                                                        │
        │                                                        ▼
  (7) LEARN ◀── (6) FULFILL + TRACK ◀────────────────── (5) PUBLISH (your click)
```

Step 7 feeds step 1: what actually sells tells research what to design next.
That loop is what makes this compound instead of just repeat.

---

## The steps — what happens, who drives, where the wall is

| # | Step | Machine does | You do | Built? |
|---|------|--------------|--------|--------|
| 1 | **Research** | Finds what's selling / trending, writes a sourced recommendation | Pick the direction | ✅ `garage-research` |
| 2 | **Design** | Builds a print-ready design from the research | Approve the look (taste) | ✅ `garage-design` |
| 3 | **Product + mockup** | Creates the Printful product, verifies text/size/colors on real mockups | Eyeball the mockups | ✅ Printful connector |
| 4 | **Listing draft** | Drafts Etsy title, description, SEO tags; recommends a price; picks images | Approve/tweak copy; **set the price** | ⏳ Phase 4 |
| 5 | **Publish** | (prepares everything) | **Click Publish** — CEO-only | 🔒 your click |
| 6 | **Fulfill + track** | Printful auto-produces & ships; agent monitors and flags problems | Nothing routine | ⏳ small build |
| 7 | **Learn** | Reads sales/reviews, feeds the next research round | Read the weekly report | ⏳ Phase 4 |

**The four CEO-only walls (charter, every phase):** spending money · brand
identity · legal · publishing/account creation. These are deliberate, not
limitations to engineer around.

---

## How the machine "accesses" the store (important)

I do **not** log into Etsy's website — no browser, and I never hold your Etsy
password. Access is always through **APIs you authorize**:

- **Printful API** (already connected) — creates products, reads orders and
  shipping status. This alone covers making products and tracking fulfillment.
- **Etsy connection** — you link your Etsy shop to Printful once (a browser
  click on your side). After that, Printful can push products to Etsy and
  **auto-fulfills Etsy orders**, pushing tracking back to the buyer.
- **Optional Etsy connector** — if you want the agent to actively edit Etsy
  listings (titles, descriptions, SEO tags, image order), I can build a
  connector you authorize once. It can then "spruce up" listings
  programmatically — **but Publish and price stay your click.**

**What the machine can spruce up:** listing titles, descriptions, SEO tags,
product attributes, image selection/order, price *recommendations*.
**What stays yours (browser + judgment):** the shop name and banner, the About
page, shop policies, the price itself, and the Publish button.

---

## STEP ZERO — open your Etsy shop (only you can do this)

Do this once. It's the current bottleneck; nothing downstream can happen until
Etsy exists and is connected to Printful.

1. Go to **etsy.com/sell** → **Open your shop** (use the brand email).
2. **Shop preferences:** language English, country United States, currency USD.
3. **Name the shop** — this is brand identity, your call. Suggest
   `theminivandads` (matches the handle) or `MinivanDads`. Etsy will tell you
   if it's taken.
4. **Billing** — add a card for Etsy's small fees (listings are ~$0.20 each;
   Etsy takes a cut per sale). This is real money, so it's yours to set up.
5. **Get-paid setup (Etsy Payments)** — connect your bank account so sales pay
   out to you.
6. **Turn on two-factor authentication.**
7. **Shop policies** — for print-on-demand, the standard is *no returns except
   defective/wrong item* (Printful reprints those free). I can draft the exact
   wording for you to paste.
8. **Connect to Printful:** in Printful → **Stores → Choose platform → Etsy →
   Connect**, and authorize. This is the browser click that gives the machine
   API access.
9. **Tell me it's connected** and share the new Printful store name/ID. Then I
   push the Quiet Game tee into it and hand you a ready-to-review listing.

---

## Running the pipeline for the NEXT design (the repeatable loop)

Once the store exists, every future product is just:

1. **"Research X"** → I bring back a sourced recommendation.
2. **You pick one** → I design it and show a mockup.
3. **You approve the look** → I create the product + verify mockups.
4. **I draft the listing** (copy, SEO, price rec, images) → you approve + set price.
5. **You click Publish.**
6. Printful fulfills automatically; the agent watches orders and reports.
7. The weekly report tells us what to research next.

Your recurring job shrinks to four things: **pick, approve the look, set the
price, click Publish.** Everything else is drafted for you.

---

## What's built vs. pending (as of 2026-07-20)

- ✅ Steps 1–3 fully working (research, design, product + verified mockups).
- ✅ Printful connector with governed create + rollback; multi-file (front +
  sleeve); explicit print positioning.
- ⏳ Step 4 listing drafts + SEO + price rec — Phase 4 (buildable now).
- ⏳ Step 6 order/tracking read — small extension of the Printful connector.
- ⏳ Step 7 sales/review learning loop — Phase 4 (Storefront + Customer agents).
- 🔒 Step zero (Etsy shop) — **waiting on the CEO.**

**Governance stays on rails the whole way:** every product write goes through
the executor (dry-run by default, CEO-approved to go live, one-click rollback,
append-only log). Publishing, pricing, and account/brand actions never leave
the CEO's hands.
