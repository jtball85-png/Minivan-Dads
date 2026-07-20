"""Driver: turn an approved design into a real Printful product, through the
governed executor. Dry-run first (shows the exact call), then the
CEO-approved supervised create, then real mockups for verification.

Reads PRINTFUL_API_KEY + PRINTFUL_STORE_ID from .env. Creates an unpublished,
deletable sync product — no order, no money. Usage constants at the top are
the current test (quiet-game tee); generalize later into a department action.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# --- the test's specifics -------------------------------------------------
PRODUCT_ID = 71                       # Bella + Canvas 3001 Unisex Staple Tee
COLORS = ["Black", "Navy", "Dark Grey Heather"]
SIZES = ["S", "M", "L", "XL", "2XL"]
PLACEMENT = "front"
PRODUCT_NAME = "Let's play the quiet game. — Tee"
EXTERNAL_ID = "mvd-quiet-game-tee-v1"
# ------------------------------------------------------------------------


def main(print_file_url: str) -> None:
    load_dotenv()
    from brain.actions.limits import (load_capabilities, load_limits,
                                      write_capability)
    from brain.actions.models import ActionIntent, ActionMode
    from brain.actions.registry import REGISTRY
    from brain.config import load_config
    from brain.connectors.printful import PrintfulConnector
    from brain.executor import Executor
    from brain.hq import HQ

    config = load_config()
    hq = HQ(config)
    connector = PrintfulConnector(
        api_key=os.environ["PRINTFUL_API_KEY"],
        store_id=int(os.environ["PRINTFUL_STORE_ID"]),
    )

    # 1. Resolve catalog variant ids (color×size) — live, unauthenticated.
    lookup = connector.list_catalog_variant_ids(PRODUCT_ID, COLORS, SIZES)
    if lookup["missing"]:
        print("MISSING color/size combos (not offered):", lookup["missing"])
    variant_ids = list(lookup["variants"].values())
    print(f"Resolved {len(variant_ids)} variants ({len(COLORS)} colors x {len(SIZES)} sizes).")
    for (color, size), vid in lookup["variants"].items():
        print(f"  {color:18} {size:3} -> variant {vid}")

    caps_path = hq.root / "actions" / "capabilities.yaml"
    ex = Executor(
        hq=hq, registry=REGISTRY,
        limits=load_limits(registry=REGISTRY),
        capabilities=load_capabilities(caps_path),
        connectors={"printful": connector},
        capabilities_path=caps_path,
    )

    intent = ActionIntent(
        agent="creative", action_type="printful.create_product",
        params={
            "product_id": PRODUCT_ID, "variant_ids": variant_ids,
            "print_file_url": print_file_url, "placement": PLACEMENT,
            "product_name": PRODUCT_NAME, "external_id": EXTERNAL_ID,
        },
        rationale="First governed Printful connector test — CEO-approved, "
                  "quiet-game tee, 3 dark colorways.",
        directive_version="2026-07-20",
    )

    # 2. Dry-run (default capability) — logs the intended call, no live write.
    dry = ex.submit(intent)
    print(f"\n[dry-run] result={dry.result} action_id={dry.id} "
          f"(this is what WOULD be sent; nothing created yet)")

    # 3. CEO approved this test -> promote to supervised, persist the grant.
    write_capability(caps_path, "creative", "printful.create_product",
                     ActionMode.SUPERVISED,
                     note="CEO-approved first connector test, 2026-07-20")
    ex.capabilities = load_capabilities(caps_path)

    # 4. The real create.
    live = ex.submit(intent)
    print(f"[live]    result={live.result} action_id={live.id}")
    if live.result != "executed":
        print("  reasons:", live.reasons)
        sys.exit(1)

    # 5. Mockups — one representative variant per colorway (size doesn't change
    #    the visual), for verification.
    rep = {}
    for (color, size), vid in lookup["variants"].items():
        rep.setdefault(color, vid)   # first size per color
    rep_ids = list(rep.values())
    print(f"\nGenerating mockups for {len(rep_ids)} colorways (this is async, ~30-60s)…")
    mockups = connector.generate_mockups(PRODUCT_ID, rep_ids, print_file_url,
                                         placement=PLACEMENT)
    print(f"Got {len(mockups)} mockup group(s):")
    for m in mockups:
        print(f"  variant {m.get('variant_ids')}  placement={m.get('placement')}")
        print(f"    mockup: {m.get('mockup_url')}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python create_printful_product.py <public_print_file_url>")
        sys.exit(2)
    main(sys.argv[1])
