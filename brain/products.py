"""The unified product view — one shape for a product regardless of platform.

Printful sync products and (later) Etsy listings both normalize into a
`ProductView`, so the storefront agent, the CEO dashboard, and `brain ask`
all read products the same way. Stdlib-only (like brain/models.py) so hq.py
can persist a catalog snapshot without pulling in the connectors.

The catalog snapshot lives at hq/products/catalog.json (machine-written via
hq.write_product_catalog) — the dashboard and agents read that file, never a
live API. Refreshing it (the one live pull) is an explicit sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VariantView:
    color: str
    size: str
    catalog_variant_id: int | None = None   # Printful catalog id (product+color+size)
    sync_variant_id: int | None = None       # the store-product variant id
    retail_price: str | None = None          # platform stores price as a string, e.g. "26.00"
    base_cost: float | None = None           # our cost (Printful), when known

    @property
    def margin(self) -> float | None:
        if self.retail_price in (None, "", "0.00", "0") or self.base_cost is None:
            return None
        try:
            return round(float(self.retail_price) - self.base_cost, 2)
        except ValueError:
            return None

    def to_dict(self) -> dict:
        return {
            "color": self.color, "size": self.size,
            "catalog_variant_id": self.catalog_variant_id,
            "sync_variant_id": self.sync_variant_id,
            "retail_price": self.retail_price, "base_cost": self.base_cost,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VariantView":
        return cls(
            color=d.get("color", ""), size=d.get("size", ""),
            catalog_variant_id=d.get("catalog_variant_id"),
            sync_variant_id=d.get("sync_variant_id"),
            retail_price=d.get("retail_price"), base_cost=d.get("base_cost"),
        )


@dataclass
class ProductView:
    platform: str                  # "printful" | "etsy"
    product_id: str                # platform product id (as a string)
    title: str
    status: str                    # "synced" | "unsynced" | "draft" | ...
    external_id: str | None = None
    variants: list[VariantView] = field(default_factory=list)
    thumbnail_url: str | None = None
    url: str | None = None

    @property
    def colorways(self) -> list[str]:
        seen: list[str] = []
        for v in self.variants:
            if v.color and v.color not in seen:
                seen.append(v.color)
        return seen

    @property
    def sizes(self) -> list[str]:
        seen: list[str] = []
        for v in self.variants:
            if v.size and v.size not in seen:
                seen.append(v.size)
        return seen

    @property
    def price_range(self) -> str:
        prices = sorted({float(v.retail_price) for v in self.variants
                         if v.retail_price not in (None, "", "0.00", "0")})
        if not prices:
            return "not set"
        if len(prices) == 1:
            return f"${prices[0]:.2f}"
        return f"${prices[0]:.2f}–${prices[-1]:.2f}"

    def to_dict(self) -> dict:
        return {
            "platform": self.platform, "product_id": self.product_id,
            "title": self.title, "status": self.status,
            "external_id": self.external_id,
            "thumbnail_url": self.thumbnail_url, "url": self.url,
            "colorways": self.colorways, "sizes": self.sizes,
            "price_range": self.price_range,
            "variants": [v.to_dict() for v in self.variants],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProductView":
        return cls(
            platform=d["platform"], product_id=str(d["product_id"]),
            title=d.get("title", ""), status=d.get("status", ""),
            external_id=d.get("external_id"),
            thumbnail_url=d.get("thumbnail_url"), url=d.get("url"),
            variants=[VariantView.from_dict(v) for v in d.get("variants", [])],
        )


def _color_size_from_sync_variant(sv: dict) -> tuple[str, str]:
    """Printful sync variants carry a display name like
    'Product Name / Color / Size'. Take the trailing two ' / ' segments as
    color and size (our product names use '—', not ' / ', so this is safe)."""
    parts = [p.strip() for p in str(sv.get("name", "")).split(" / ")]
    if len(parts) >= 3:
        return parts[-2], parts[-1]
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", ""


def product_view_from_shopify(node: dict, storefront_base: str | None = None) -> ProductView:
    """Normalize one Shopify GraphQL product node (as returned by
    ShopifyConnector.list_products) into a ProductView. Color/size come from
    each variant's named selectedOptions when present, falling back to the
    ' / '-split of the variant title (Printful-pushed products use
    'Size / Color' or single-option titles)."""
    variants = []
    for edge in (node.get("variants") or {}).get("edges", []):
        v = edge["node"]
        opts = {o["name"].strip().lower(): o["value"]
                for o in v.get("selectedOptions", [])}
        color = opts.get("color") or opts.get("colour") or ""
        size = opts.get("size") or ""
        if not (color or size):
            parts = [p.strip() for p in str(v.get("title", "")).split(" / ")]
            if len(parts) == 2:
                size, color = parts[0], parts[1]
            elif parts and parts[0] not in ("", "Default Title"):
                color = parts[0]
        variants.append(VariantView(
            color=color, size=size,
            sync_variant_id=int(v["legacyResourceId"]) if v.get("legacyResourceId") else None,
            retail_price=v.get("price"),
        ))
    thumb = (((node.get("featuredMedia") or {}).get("preview") or {})
             .get("image") or {}).get("url")
    handle = node.get("handle")
    url = (f"{storefront_base.rstrip('/')}/products/{handle}"
           if storefront_base and handle else None)
    return ProductView(
        platform="shopify",
        product_id=str(node.get("legacyResourceId") or node.get("id", "")),
        title=node.get("title", ""),
        status=str(node.get("status", "")).lower(),
        external_id=node.get("handle"),
        thumbnail_url=thumb, url=url,
        variants=variants,
    )


def product_view_from_printful(detail: dict) -> ProductView:
    """Normalize one Printful GET /store/products/{id} result
    ({'sync_product': ..., 'sync_variants': [...]}) into a ProductView."""
    sp = detail["sync_product"]
    svs = detail.get("sync_variants", [])
    variants = []
    for sv in svs:
        color, size = _color_size_from_sync_variant(sv)
        variants.append(VariantView(
            color=color, size=size,
            catalog_variant_id=sv.get("variant_id"),
            sync_variant_id=sv.get("id"),
            retail_price=sv.get("retail_price"),
        ))
    synced = sp.get("synced")
    status = "synced" if synced else "unsynced"
    return ProductView(
        platform="printful", product_id=str(sp.get("id")),
        title=sp.get("name", ""), status=status,
        external_id=sp.get("external_id"),
        thumbnail_url=sp.get("thumbnail_url"),
        variants=variants,
    )
