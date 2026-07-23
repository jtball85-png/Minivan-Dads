"""Reconcile the CEO's design-asset drive against the repo and the live
Printful catalog into one generated manifest: "what art exists, where, and
is it live?"

READ-ONLY against the drive: enumerates and measures, never writes, moves,
or deletes anything there. Merges three inputs:

  1. assets-manifest.seed.yaml  — hand-curated judgment (art-ready vs.
     template-only vs. live) captured at inventory time; a filename
     heuristic can't reliably make these calls, so they live in a
     reviewable file instead.
  2. hq/products/catalog.json   — the machine-verified Printful store
     snapshot (refresh with `brain sync-products` first; read-only here —
     only brain/hq.py ever writes under hq/).
  3. shopify-live-note.md       — the dated MANUAL Shopify snapshot
     (presence noted, never parsed as truth).

Outputs (generated, never hand-edited): assets-manifest.json +
assets-manifest.md — same machine/human pairing convention as
hq/products/catalog.{json,md}.

Also emits a junk report (``__MACOSX``, ``.DS_Store``, AppleDouble ``._*``
files, leftover ``*.zip`` archives) as candidates for a HUMAN-reviewed
cleanup — this script itself deletes nothing, ever.

Garage-only tooling (like compose_preview.py): never imported by brain/.

Usage:
    .venv/Scripts/python.exe garage/design/reconcile_assets.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent          # garage/design
REPO = HERE.parent.parent
SEED = HERE / "assets-manifest.seed.yaml"
CATALOG = REPO / "hq" / "products" / "catalog.json"
SHOPIFY_NOTE = HERE / "shopify-live-note.md"
OUT_JSON = HERE / "assets-manifest.json"
OUT_MD = HERE / "assets-manifest.md"

JUNK_DIR_NAMES = {"__MACOSX"}
JUNK_FILE_NAMES = {".DS_Store"}


def scan_product_dir(root: Path) -> dict:
    """Read-only walk of one product folder: size, file-type census, junk."""
    total = 0
    types: dict[str, int] = {}
    junk: list[str] = []
    zips: list[str] = []
    for p in root.rglob("*"):
        rel = str(p.relative_to(root))
        if p.is_dir():
            if p.name in JUNK_DIR_NAMES:
                junk.append(rel + "\\ (dir)")
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        total += size
        suffix = p.suffix.lower() or "(none)"
        types[suffix] = types.get(suffix, 0) + 1
        if p.name in JUNK_FILE_NAMES or p.name.startswith("._"):
            junk.append(rel)
        elif suffix == ".zip":
            zips.append(rel)
    # Junk inside a __MACOSX dir is implied by the dir entry; keep the list short.
    junk = [j for j in junk if "__MACOSX" not in j] + \
           [j for j in junk if "__MACOSX" in j and j.endswith("(dir)")]
    return {"exists": True, "size_mb": round(total / 1_000_000, 1),
            "file_types": dict(sorted(types.items(), key=lambda kv: -kv[1])),
            "junk": sorted(junk), "leftover_zips": sorted(zips)}


def load_catalog() -> tuple[list[dict], str]:
    if not CATALOG.exists():
        return [], "hq/products/catalog.json missing — run `brain sync-products`"
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    products = data.get("products", data if isinstance(data, list) else [])
    return products, data.get("generated_at", "unknown") if isinstance(data, dict) else "unknown"


def main() -> None:
    seed = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    drive_root = Path(seed["drive_root"])
    drive_ok = drive_root.exists()

    catalog_products, catalog_generated = load_catalog()
    catalog_names = [
        f"{p.get('title', '?')}  [{p.get('platform', '?')}, {p.get('status', '?')}, "
        f"price: {p.get('price_range', '?')}]"
        for p in catalog_products
    ]

    shopify_note = {"present": SHOPIFY_NOTE.exists(),
                    "path": str(SHOPIFY_NOTE.relative_to(REPO)),
                    "caveat": "manual snapshot, dated inside the file — may be stale"}

    manifest: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "drive_root": str(drive_root),
        "drive_mounted": drive_ok,
        "printful_catalog": {"generated_at": catalog_generated,
                             "product_names": catalog_names},
        "shopify_note": shopify_note,
        "designs": {},
        "brand_logos": seed.get("brand_logos", {}),
        "junk_report": [],
    }
    if not drive_ok:
        manifest["warning"] = (f"drive not mounted at {drive_root} — seed facts "
                               "reported unverified, no scan performed")

    for design_name, design in seed["designs"].items():
        entry = {k: v for k, v in design.items() if k != "products"}
        products = []
        # Single-product candidate entries (no "products" list) scan themselves.
        product_list = design.get("products") or ([design] if "drive_dir" in design else [])
        for prod in product_list:
            row = {k: prod[k] for k in ("key", "drive_dir", "printful_type",
                                        "art_status", "note") if k in prod}
            if drive_ok and "drive_dir" in prod:
                pdir = drive_root / prod["drive_dir"]
                row["scan"] = (scan_product_dir(pdir) if pdir.exists()
                               else {"exists": False,
                                     "error": f"folder not found: {pdir}"})
                if row["scan"].get("junk") or row["scan"].get("leftover_zips"):
                    manifest["junk_report"].append({
                        "folder": str(pdir),
                        "junk": row["scan"].get("junk", []),
                        "leftover_zips": row["scan"].get("leftover_zips", []),
                    })
            products.append(row)
        if products and "products" in design:
            entry["products"] = products
        elif products:
            entry.update(products[0])
        manifest["designs"][design_name] = entry

    OUT_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    OUT_MD.write_text(render_md(manifest), encoding="utf-8")
    print(f"Wrote {OUT_JSON.relative_to(REPO)} and {OUT_MD.relative_to(REPO)}")
    print(f"Drive mounted: {drive_ok}. Junk report entries: "
          f"{len(manifest['junk_report'])} folder(s).")
    if not drive_ok:
        sys.exit(0)  # informative, not an error — seed-only manifest still written


def render_md(m: dict) -> str:
    lines = [
        "# Assets manifest — GENERATED, do not hand-edit",
        "",
        f"_Generated: {m['generated_at']} · drive mounted: {m['drive_mounted']}"
        f" · Printful catalog as of: {m['printful_catalog']['generated_at']}_",
        "",
        "Regenerate: `.venv/Scripts/python.exe garage/design/reconcile_assets.py`",
        "(run `brain sync-products` first for a fresh Printful snapshot).",
        "Judgment calls live in `assets-manifest.seed.yaml`;",
        "Shopify live-state is manual — see `shopify-live-note.md` (dated, may be stale).",
        "",
    ]
    if m.get("warning"):
        lines += [f"> **Warning:** {m['warning']}", ""]
    for design, entry in m["designs"].items():
        lines += [f"## Design: {design}", ""]
        if entry.get("master"):
            lines += [f"- Master (git-tracked): `{entry['master']}`"]
        if entry.get("colorways"):
            lines += ["- Colorways: " + ", ".join(entry["colorways"])]
        products = entry.get("products") or ([entry] if entry.get("drive_dir") else [])
        if products:
            lines += ["", "| Product | Art status | Size | Junk? | Note |",
                      "|---|---|---|---|---|"]
            for p in products:
                scan = p.get("scan", {})
                size = f"{scan['size_mb']}MB" if scan.get("size_mb") is not None else "—"
                junk = ("yes" if scan.get("junk") or scan.get("leftover_zips")
                        else ("no" if scan.get("exists") else "?"))
                note = (p.get("note") or "").split(";")[0][:80]
                lines.append(f"| {p.get('key', p.get('printful_type', '?'))} "
                             f"| **{p.get('art_status', '?')}** | {size} | {junk} | {note} |")
        lines += [""]
    lines += ["## Live Printful store (machine-verified via brain sync-products)", ""]
    names = m["printful_catalog"]["product_names"]
    lines += [f"- {n}" for n in names] or ["- (catalog empty or missing)"]
    lines += ["", "## Junk report (candidates for HUMAN-reviewed cleanup — nothing auto-deleted)", ""]
    if m["junk_report"]:
        for j in m["junk_report"]:
            lines += [f"### {j['folder']}", ""]
            lines += [f"- `{x}`" for x in j["junk"]]
            lines += [f"- `{x}` (leftover zip)" for x in j["leftover_zips"]]
            lines += [""]
    else:
        lines += ["(none found)", ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
