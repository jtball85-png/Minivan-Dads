"""The action registry: every write an agent could ever make, as code.

Unregistered action = impossible action. Adding an action type here is a
code change the CEO reviews — no runtime registration exists on purpose.
"""

from __future__ import annotations

import re

from brain.actions.models import ActionType

REGISTRY: dict[str, ActionType] = {
    t.name: t
    for t in [
        ActionType(
            name="shopify.update_listing_copy",
            connector="shopify",
            params={"product_id": "str", "title": "str", "description": "str", "seo": "str"},
            snapshot_params=("product_id",),
        ),
        ActionType(
            name="shopify.update_listing_images",
            connector="shopify",
            params={"product_id": "str", "images": "list"},
            snapshot_params=("product_id",),
        ),
        ActionType(
            name="shopify.set_price",
            connector="shopify",
            params={"product_id": "str", "new_price": "float"},
            snapshot_params=("product_id",),
        ),
        ActionType(
            name="shopify.create_discount",
            connector="shopify",
            params={"code": "str", "percent": "float", "expiry": "str"},
        ),
        ActionType(
            name="printful.create_product",
            connector="printful",
            params={"template": "str", "variants": "list"},
        ),
        ActionType(
            name="meta.adjust_budget",
            connector="meta_ads",
            params={"campaign_id": "str", "new_daily_budget": "float"},
            snapshot_params=("campaign_id",),
        ),
        ActionType(
            name="meta.pause_adset",
            connector="meta_ads",
            params={"adset_id": "str"},
            snapshot_params=("adset_id",),
        ),
        ActionType(
            name="meta.create_campaign",
            connector="meta_ads",
            params={"name": "str", "objective": "str", "daily_budget": "float"},
        ),
        ActionType(
            name="meta.publish_post",
            connector="meta_publish",
            params={"caption": "str", "media": "list", "schedule_time": "str"},
            irreversible=True,  # a published post has no meaningful rollback
        ),
    ]
}

# Defense-in-depth beyond the always_escalate flag: action-type NAMES matching
# these patterns are denied in the executor no matter what the registry or
# limits.yaml say. Even a future mis-registered action can't slip through.
# Per spec §4: deletes, branding, payments/payouts, legal/tos, spend caps.
HARD_DENIAL_PATTERNS: tuple[str, ...] = (
    r"\.delete_",
    r"\bdelete\b",
    r"payment",
    r"payout",
    r"branding",
    r"\brename\b",
    r"store_name",
    r"terms",
    r"legal",
    r"spend_cap",
    r"account",
)

_COMPILED_DENIALS = [re.compile(p) for p in HARD_DENIAL_PATTERNS]


def is_hard_denied(action_type_name: str) -> bool:
    return any(p.search(action_type_name) for p in _COMPILED_DENIALS)
