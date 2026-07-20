---
name: garage-design
description: Walk a research file down the product pipeline — pick which product(s) it's worth making, draft real vector (SVG) designs sized to real or industry-standard print-area dimensions, and composite a flat preview onto the real template art so the CEO can actually see it, not just read about it. Use when the CEO wants to see actual design concepts, not just written research, for a hat/patch/shirt/mug idea. Produces draft files and flat preview images only — never touches Printful's write API, never generates a real photorealistic mockup, never creates a real product, never spends money. Going live is a separate, deliberate future build (a real governed Printful connector), not this skill.
---

# Garage Design

Turns research into something you can actually look at — real SVG files,
not a written description of what a design might look like. Garage-only:
no credentials required, no external writes, nothing goes live. See
`CLAUDE.md`'s "Two rooms" section for the garage/board distinction this
assumes, and `.claude/skills/garage-research/SKILL.md` for the research
workflow this typically follows.

## Core principle

A design draft should be an actual file the CEO can open and look at —
not a text description of a design. If you can't produce a real SVG for
an idea, say so and explain why, rather than describing a design in
prose and calling it a draft.

**Capability boundary, stated plainly:** there is no computer-use/GUI-
automation tool available — Photoshop and Illustrator cannot actually be
operated by Claude Code, even if the CEO offers access. What's real:
writing valid SVG directly as code (opens natively in Illustrator via
File > Open, or in any browser) and calling Printful's public APIs for
reference data. Never claim or imply GUI-app usage that isn't happening.

---

## Step 0: Clarify scope (lead with what the CEO already said)

Same discipline as `garage-research` — state your understanding back in
one line for anything already answered, only ask about genuine gaps:

1. **Source material** — which research/concepts to draw from (a garage
   research file, a promoted `hq/research/` exhibit, or specific lines/
   ideas the CEO states directly in the request).
2. **Target product(s), grounded in the lineup research, not just the
   request.** If `garage/research/product-lineup-and-color-combos-*.md`
   (or a similar lineup/margin research file) is on file, check it before
   picking a product — state *why* a product fits (margin, existing
   white space, quality signal), not just *that* it was asked for. If
   the CEO names a product the lineup research flagged as weak (e.g. a
   thin-margin or seasonally-limited SKU), say so plainly and let them
   decide — don't silently swap it out, and don't silently ignore the
   research either.
3. **How many directions** — one polished concept, or several rough
   directions to choose between? Default to 2-3 unless told otherwise —
   a single option isn't a real choice.

---

## Step 1: Pull real print-area reference data

Check sources in this order — prefer the most-real, least-approximate
one available:

1. **`garage/design/printful-templates/`** — real, curated Printful
   template/guideline files (the CEO has already supplied some; check
   its `README.md` for what's covered and their confirmed specs before
   assuming a gap). If the target product is here, use its confirmed
   numbers directly — no API call needed. If the CEO offers to add more
   product templates from their own Printful downloads, take them —
   real files beat API calls or approximations every time.
2. **Printful's live API**, if a template isn't available locally.
   Product catalog browsing is unauthenticated (confirmed:
   `GET https://api.printful.com/products` and `/products/{id}` both
   return real data with no key). **Exact print-area dimensions/DPI live
   behind `/mockup-generator/printfiles/{id}`, which requires a Printful
   API key** (confirmed: returns 401 without one). If `PRINTFUL_API_KEY`
   is present in `.env` (same `python-dotenv` pattern as
   `ANTHROPIC_API_KEY`), use it here.
3. **Industry-standard fallback dimensions** (below) — only when neither
   of the above covers the target product. **Label every dimension used
   as "industry-standard approximation, not Printful's confirmed
   number"** in the companion `.md` file. Never present an approximation
   as if it were a verified Printful spec.

**Product-type mismatch check, before drafting anything:** confirm the
*construction*, not just the size, matches what the research assumed.
Example already found: the hats/patches research assumed a structured
trucker cap with a leather patch; the only real hat template on file so
far is a soft knit beanie (embroidery-only, no patch attachment,
5"×1.75" front area — narrower/shorter than the 4.5"×2.5" fallback
guess). Don't silently apply a beanie's specs to a patch concept — flag
the mismatch and ask whether to adapt the concept to what's actually
templated, or keep the patch concept on the approximate fallback until a
real structured-cap/patch template is available.

**Standard fallback dimensions** (widely published DTG/embroidery
conventions — cite as approximate, not authoritative):

| Product | Placement | Approx. print/embroidery area |
|---|---|---|
| Adult t-shirt | Front, centered | ~12in × 16in (DTG standard) |
| Adult t-shirt | Left chest | ~4in × 4in |
| Structured/trucker cap | Front panel embroidery | ~4.5in × 2.5in |
| Leather/PVC patch (any hat) | Full-crown patch | ~3.5in × 2.25in (oval/rounded-rect — matches the dominant shape found in the hats/patches research) |

Use a canvas scaled to whichever of these applies, at a clean reference
scale (e.g. 100px = 1in) so the file's proportions are meaningful even
before real Printful numbers replace them.

---

## Step 2: Draft the SVG(s)

Write real SVG — `<svg>` root sized to the Step 1 dimensions, `<text>`
for typography, `<path>`/`<rect>`/`<ellipse>` for shapes. No raster image
embeds (nothing here can generate a PNG/JPEG). Apply what research has
already established, don't reinvent it:

- **Copy** — pull from the ranked sayings/one-liners already on file
  (garage or promoted) rather than writing new lines inside this skill;
  if a fresh line is genuinely needed, that's `garage-research` territory
  first, not this skill's job.
- **Shape/color/typography conventions** — apply the hats/patches
  research's findings directly (e.g. oval/rounded-rectangle for patches,
  arched-top-line + straight-subtext for two-line patch copy, avoid the
  "clichés to avoid" list, avoid the named legal-risk patterns — no
  single bold vehicle silhouette, no mascot echoing an existing famous
  mascot's pose, no three-piece rocker construction).
- **Safe margin** — keep text/critical elements inside ~90% of the
  canvas; production print files need bleed/safety margins Printful's
  real specs would define exactly, but a conservative margin now avoids
  drafts that would obviously fail once real numbers are available.

---

## Step 3: Flat composite preview (when a real template is on file)

If `garage/design/printful-templates/{product}/` has a template PNG
**and** a `print-area.json` calibration file (pixel bbox of the
print-area guide box — see the t-shirt folder for the pattern), run:

```
.venv/Scripts/python.exe garage/design/compose_preview.py \
    <svg_path> <template_png_path> <print-area.json_path> \
    garage/design/{slug}-{date}-preview.png
```

(`pip install -e ".[garage]"` first if `svglib`/`reportlab`/`pycairo`/
`rlPyCairo`/`Pillow` aren't installed yet — see `pyproject.toml`'s
`garage` extra.) This rasterizes the SVG and pastes it onto the real
template art, centered in the calibrated print-area box.

**Say exactly what this is, every time: a flat composite preview — the
design placed at roughly the right position/scale/color on real
template art.** It is emphatically **not** a photorealistic mockup — no
fabric drape, no product photography, no lighting, no curvature (for
mugs). That needs Printful's real Mockup Generator API and the governed
connector this project has not built. Don't let a good-looking flat
composite get mistaken for one.

No calibration file for the target product yet? Skip this step, say so,
and note that calibrating one (viewing the template image, estimating
the print-area box's pixel bounds, writing a `print-area.json` next to
it) is a one-time, doable-now task if the CEO wants it — not a blocker
that requires the real connector.

**Also generate the print-ready export, every time, not just the flat
preview:** `python compose_preview.py print <svg> <width_in> <height_in>
<output> [dpi]` (default 300 DPI, matching Printful's own stated
standard). These answer two different questions — the flat preview is
for placement/color, the print export is for "is this actually usable."
Don't let the low-resolution preview stand in for a real print-quality
check; produce both, and say which is which.

**Actually look at both renders before presenting anything as
finished — this is not optional.** View the flat preview *and* the
print-ready export (full-size, not just described) yourself before
calling a draft done. A design that looks fine as an SVG description in
your head can still be off-center, too small, or badly proportioned
once actually rendered — that's exactly the kind of thing a review step
exists to catch. If something looks wrong, fix it and re-render before
presenting, the way any other bug gets fixed before it ships — don't
hand the CEO a first-pass render with a known defect noted as a
to-do-later. If a fix is genuinely imperfect (e.g. hand-picked
coordinates instead of real font-metric centering), say so plainly
rather than either hiding it or leaving it for someone else to notice.

---

## Step 4: Save

Per direction, same slug:
- `garage/design/{slug}-{date}.svg` — the actual draft.
- `garage/design/{slug}-{date}-preview.png` — the flat composite, if
  Step 3 ran.
- `garage/design/{slug}-{date}.md` — companion: what it is, which
  research/copy it draws from, which dimensions were used and whether
  they're Printful-confirmed or industry-standard approximations, a
  one-line rationale per direction (if multiple), **and an explicit
  review-status line** — `status: draft — pending CEO review` by
  default. Never write `approved` or anything implying sign-off unless
  the CEO actually said so in this conversation; this line is read by
  a human, not auto-advanced by anything.

---

## Step 5: Present

Describe what was drafted, how to open it (any browser; Illustrator via
File > Open for the SVG), and whether a flat preview was produced.
State plainly, every time:

- Whether dimensions used are Printful-confirmed (real template or API
  key) or industry-standard approximations — say which.
- The flat-preview caveat from Step 3, if one was produced.
- **Where this pipeline stops.** This skill's job ends at an
  approved-or-not flat preview and a complete draft package. Turning
  that into a real Printful product — a true photorealistic mockup, an
  actual listing, anything "live" — requires the separate governed
  Printful connector (API credentials, the executor framework, real
  external writes, real money/brand exposure) that this project has
  deliberately not built yet. Never imply this skill can push anything
  live, and don't build toward it inline even if asked in passing —
  that's a distinct decision the CEO makes deliberately, the same way
  the connector's deferral itself was decided.

---

## Things to avoid

- Describing a design in prose and presenting that as a "draft" — if you
  can't produce a real SVG, say so.
- Implying Photoshop/Illustrator were used to produce anything — they
  weren't, and can't be, without a computer-use tool this environment
  doesn't have.
- Presenting industry-standard approximate dimensions as if they were
  Printful's own confirmed numbers.
- Presenting a flat composite preview as if it were a photorealistic
  Printful mockup.
- Writing new copy/sayings inside this skill — that's `garage-research`'s
  job; this skill applies what's already been found, not what to say.
- Picking a product without checking the lineup research first, if one
  exists on file.
- Writing `approved` (or implying it) in a companion file's status line
  without the CEO having actually said so.
- Reaching for the Printful write API (mockup generation, product
  creation) — this skill never does that, and never edges toward it
  "just this once." If the CEO wants a real mockup or product, that's
  the separate governed-connector build, not a scope creep of this
  skill.
