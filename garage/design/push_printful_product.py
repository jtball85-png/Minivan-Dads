"""Generalized driver: turn an approved design into a real Printful product
through the governed executor, from a spec file instead of hardcoded
constants (generalizes the one-off create_printful_product.py used for the
quiet-game tee on 2026-07-20 — same 5 governed steps, now reusable).

Spec files live in garage/design/pushes/*.yaml — one per push, a durable
record of every product attempt. See quiet-game-tee.yaml for the reference
shape.

Modes:
  (default)   dry-run only — resolves real variants, submits through the
              executor at the CURRENT capability mode. If capability is
              dry_run (the standing default), nothing live happens: the
              executor logs the intended call and returns before touching
              the connector.
  --live      the CEO-approved path: promotes capability to supervised
              (recording the CEO note), performs the real create, then
              generates verification mockups. Only run this after the CEO
              has explicitly approved THIS push in conversation.

Usage:
  .venv/Scripts/python.exe garage/design/push_printful_product.py \
      garage/design/pushes/<spec>.yaml --files front=<public_url> [...]
      [--live --ceo-note "CEO approved <what> on <date>"]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv


def parse_files_arg(pairs: list[str]) -> dict[str, str]:
    out = {}
    for pair in pairs:
        placement, _, url = pair.partition("=")
        if not url:
            sys.exit(f"--files needs placement=<url>, got: {pair!r}")
        out[placement] = url
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="path to a pushes/*.yaml spec")
    ap.add_argument("--files", nargs="+", required=True,
                    metavar="placement=url",
                    help="public print-file URL per placement in the spec")
    ap.add_argument("--live", action="store_true",
                    help="CEO-approved: promote capability to supervised and "
                         "actually create the product (+ mockups)")
    ap.add_argument("--ceo-note", default=None,
                    help="required with --live: the CEO-approval note "
                         "recorded in capabilities.yaml")
    args = ap.parse_args()
    if args.live and not args.ceo_note:
        sys.exit("--live requires --ceo-note recording the CEO's approval.")

    spec = yaml.safe_load(Path(args.spec).read_text(encoding="utf-8"))
    file_urls = parse_files_arg(args.files)
    spec_placements = [f["placement"] for f in spec["files"]]
    missing = [p for p in spec_placements if p not in file_urls]
    if missing:
        sys.exit(f"spec expects file URL(s) for placement(s) {missing}; "
                 f"got {sorted(file_urls)}")

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

    # 1. Resolve catalog variant ids — live, unauthenticated, read-only.
    lookup = connector.list_catalog_variant_ids(
        spec["printful_product_id"], spec["colors"], spec["sizes"])
    if lookup["missing"]:
        print("MISSING color/size combos (not offered):", lookup["missing"])
    variant_ids = list(lookup["variants"].values())
    if not variant_ids:
        sys.exit("No variants resolved — check the spec's colors/sizes "
                 "against the Printful catalog product.")
    print(f"Resolved {len(variant_ids)} variant(s) "
          f"({len(spec['colors'])} color(s) x {len(spec['sizes'])} size(s)).")
    for (color, size), vid in lookup["variants"].items():
        print(f"  {color:18} {size:6} -> variant {vid}")

    caps_path = hq.root / "actions" / "capabilities.yaml"
    ex = Executor(
        hq=hq, registry=REGISTRY,
        limits=load_limits(registry=REGISTRY),
        capabilities=load_capabilities(caps_path),
        connectors={"printful": connector},
        capabilities_path=caps_path,
    )

    intent = ActionIntent(
        agent=spec.get("agent", "creative"),
        action_type="printful.create_product",
        params={
            "product_id": spec["printful_product_id"],
            "variant_ids": variant_ids,
            "files": [{"placement": f["placement"],
                       "url": file_urls[f["placement"]],
                       **({"position": f["position"]} if f.get("position") else {})}
                      for f in spec["files"]],
            "product_name": spec["product_name"],
            "external_id": spec["external_id"],
        },
        rationale=spec.get("rationale", "").strip(),
        directive_version=str(spec.get("directive_version", "")),
    )

    # 2. Submit at current capability (dry_run default: logs intent, no write).
    result = ex.submit(intent)
    print(f"\n[{'dry-run' if result.result == 'dry_run' else result.result}] "
          f"action_id={result.id}")
    if result.result == "dry_run":
        print("  Nothing was created. This is what WOULD be sent. To go "
              "live (after CEO approval): re-run with --live --ceo-note '...'")
    if not args.live:
        return

    # 3. --live: CEO approved -> promote to supervised, persist the grant.
    write_capability(caps_path, intent.agent, "printful.create_product",
                     ActionMode.SUPERVISED, note=args.ceo_note)
    ex.capabilities = load_capabilities(caps_path)

    # 4. The real create.
    live = ex.submit(intent)
    print(f"[live]    result={live.result} action_id={live.id}")
    if live.result != "executed":
        print("  reasons:", live.reasons)
        sys.exit(1)

    # 5. Verification mockups — one representative variant per colorway.
    rep: dict[str, int] = {}
    for (color, _size), vid in lookup["variants"].items():
        rep.setdefault(color, vid)
    first_placement = spec["files"][0]["placement"]
    print(f"\nGenerating mockups for {len(rep)} colorway(s) (async, ~30-60s)…")
    mockups = connector.generate_mockups(
        spec["printful_product_id"], list(rep.values()),
        file_urls[first_placement], placement=first_placement)
    print(f"Got {len(mockups)} mockup group(s):")
    for m in mockups:
        print(f"  variant {m.get('variant_ids')}  placement={m.get('placement')}")
        print(f"    mockup: {m.get('mockup_url')}")


if __name__ == "__main__":
    main()
