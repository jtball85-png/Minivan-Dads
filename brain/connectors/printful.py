"""Printful connector — the first real external-write connector.

Only the executor calls execute()/restore(); everything else here is read
(catalog lookup) or verification (mockups), which the action-layer spec
lets agents do freely. Product creation places NO order and spends NO
money — it creates an unpublished sync product in the CEO's Printful store,
fully deletable, so restore() is a clean delete.

Rollback design: the executor snapshots BEFORE execute, so a create can't
learn its own new product id in time to undo it. We instead set a
deterministic Printful **external_id** (carried in params, snapshotted
pre-execute); restore() deletes by `@external_id`. Idiomatic to Printful's
own external-id feature, no executor change needed.

Auth: PRINTFUL_API_KEY (Bearer) from the environment. Catalog reads are
unauthenticated. HTTP is stdlib urllib (matching brain/tools.py) with an
injectable transport so tests never hit the network.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable

from brain.actions.models import ActionType

BASE_URL = "https://api.printful.com"
USER_AGENT = "MinivanDads/1.0 (governed Printful connector)"


class PrintfulError(RuntimeError):
    def __init__(self, status: int, detail):
        super().__init__(f"Printful API error {status}: {detail}")
        self.status = status
        self.detail = detail


# transport(method, url, headers, body_bytes) -> (status_int, parsed_json_or_None)
Transport = Callable[[str, str, dict, bytes | None], tuple[int, dict | None]]


def _urllib_transport(method: str, url: str, headers: dict, body: bytes | None):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {"raw": raw}
        return e.code, parsed


class PrintfulConnector:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL,
                 transport: Transport | None = None, store_id: int | None = None):
        self.api_key = api_key
        self.base_url = base_url
        self.store_id = store_id  # account-level tokens must name the store
        self._transport = transport or _urllib_transport

    def _call(self, method: str, path: str, body: dict | None = None, auth: bool = False):
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        if auth:
            if not self.api_key:
                raise PrintfulError(0, "PRINTFUL_API_KEY required for this call but not set")
            headers["Authorization"] = f"Bearer {self.api_key}"
            # Account-level tokens require the target store; store-scoped
            # tokens ignore this header, so sending it is always safe.
            if self.store_id is not None:
                headers["X-PF-Store-Id"] = str(self.store_id)
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else None
        status, data = self._transport(method, self.base_url + path, headers, body_bytes)
        if status >= 400 or status == 0:
            raise PrintfulError(status, (data or {}).get("error") or data)
        return data

    def resolve_store_id(self) -> int:
        """Auto-detect the store for an account-level token: with exactly one
        store, use it; otherwise say so plainly rather than guess."""
        data = self._call("GET", "/stores", auth=True)
        stores = data.get("result", [])
        if len(stores) == 1:
            self.store_id = stores[0]["id"]
            return self.store_id
        if not stores:
            raise PrintfulError(0, "no Printful store exists yet — add a "
                                   "'Manual order platform / API' store first")
        raise PrintfulError(0, f"{len(stores)} stores found; set PRINTFUL_STORE_ID "
                               "to pick one: " + ", ".join(f"{s['id']}={s['name']}" for s in stores))

    # -- catalog reads (unauthenticated) --------------------------------

    def list_catalog_variant_ids(self, product_id: int,
                                 colors: list[str], sizes: list[str]) -> dict:
        """{(color, size): catalog_variant_id} for the requested colors×sizes.
        Variant ids encode product+color+size — always use these, never the
        product id, when creating products (mixing them up makes the wrong
        item). Warns via the returned 'missing' key if a combo isn't offered."""
        data = self._call("GET", f"/products/{product_id}", auth=False)
        variants = data["result"]["variants"]
        found = {}
        for v in variants:
            if v["color"] in colors and v["size"] in sizes:
                found[(v["color"], v["size"])] = v["id"]
        missing = [(c, s) for c in colors for s in sizes if (c, s) not in found]
        return {"variants": found, "missing": missing}

    # -- store reads (authenticated) — for the unified catalog --------------

    def list_products(self) -> list[dict]:
        """Every sync product in the store, each fully expanded to
        {'sync_product': ..., 'sync_variants': [...]} (the list endpoint omits
        variants, so we fetch each product's detail). Read-only."""
        listing = self._call("GET", "/store/products", auth=True)
        details = []
        for item in listing.get("result", []):
            detail = self._call("GET", f"/store/products/{item['id']}", auth=True)
            details.append(detail["result"])
        return details

    def get_product(self, external_id: str) -> dict:
        """One sync product by external_id: {'sync_product', 'sync_variants'}."""
        return self._call("GET", f"/store/products/@{external_id}", auth=True)["result"]

    # -- Connector protocol (executor-only: execute / read_state / restore)

    def read_state(self, action_type: ActionType, params: dict) -> dict:
        """Snapshot the pre-action state so restore() can undo. The shape
        depends on the action: create captures just the external_id it will
        claim; edits capture the current name / retail prices."""
        if action_type.name == "printful.create_product":
            # Pre-create there is nothing to capture except the external_id we're
            # about to claim — that's what rollback needs.
            return {"external_id": params["external_id"],
                    "note": "pre-create snapshot; rollback deletes @external_id"}
        ext = params["external_id"]
        current = self.get_product(ext)
        snap = {"external_id": ext, "name": current["sync_product"].get("name")}
        snap["retail_prices"] = [
            {"id": sv["id"], "retail_price": sv.get("retail_price")}
            for sv in current.get("sync_variants", [])
        ]
        return snap

    def execute(self, action_type: ActionType, params: dict) -> dict:
        if action_type.name == "printful.create_product":
            return self._create_product(params)
        if action_type.name == "printful.update_product":
            self._call("PUT", f"/store/products/@{params['external_id']}",
                       body={"sync_product": {"name": params["name"]}}, auth=True)
            return {"external_id": params["external_id"], "updated": "name"}
        if action_type.name == "printful.set_retail_price":
            current = self.get_product(params["external_id"])
            price = f"{float(params['retail_price']):.2f}"
            sync_variants = [{"id": sv["id"], "retail_price": price}
                             for sv in current.get("sync_variants", [])]
            self._call("PUT", f"/store/products/@{params['external_id']}",
                       body={"sync_variants": sync_variants}, auth=True)
            return {"external_id": params["external_id"], "retail_price": price,
                    "variants_priced": len(sync_variants)}
        raise PrintfulError(0, f"unhandled action {action_type.name!r}")

    def _create_product(self, params: dict) -> dict:
        # One or more print files per variant — e.g. front + sleeve_left. Each
        # {placement, url, position?} becomes a Printful file entry. Without a
        # position Printful prints the file at its NATIVE physical size (a
        # too-small file then floats tiny in the print area) — so callers pass
        # an explicit position to fill the print area deterministically.
        files = []
        for f in params["files"]:
            entry = {"type": f["placement"], "url": f["url"]}
            if f.get("position") is not None:
                entry["position"] = f["position"]
            files.append(entry)
        sync_variants = [
            {"variant_id": vid, "files": files}
            for vid in params["variant_ids"]
        ]
        body = {
            "sync_product": {
                "name": params["product_name"],
                "external_id": params["external_id"],
            },
            "sync_variants": sync_variants,
        }
        data = self._call("POST", "/store/products", body=body, auth=True)
        return {"printful_id": data["result"]["id"],
                "external_id": params["external_id"],
                "variants_created": len(sync_variants)}

    def restore(self, action_type: ActionType, snapshot: dict) -> dict:
        ext = snapshot["external_id"]
        if action_type.name == "printful.create_product":
            self._call("DELETE", f"/store/products/@{ext}", auth=True)
            return {"deleted_external_id": ext}
        if action_type.name == "printful.update_product":
            self._call("PUT", f"/store/products/@{ext}",
                       body={"sync_product": {"name": snapshot.get("name")}}, auth=True)
            return {"restored_external_id": ext, "restored": "name"}
        if action_type.name == "printful.set_retail_price":
            sync_variants = [{"id": r["id"], "retail_price": r["retail_price"]}
                             for r in snapshot.get("retail_prices", [])]
            self._call("PUT", f"/store/products/@{ext}",
                       body={"sync_variants": sync_variants}, auth=True)
            return {"restored_external_id": ext, "restored": "retail_prices"}
        raise PrintfulError(0, f"unhandled restore for {action_type.name!r}")

    # -- verification (free, non-mutating; not a governed write) ---------

    def front_print_area(self, product_id: int, placement: str = "front") -> dict:
        """The print-area dimensions for a placement (needed to position a
        design in the mockup generator). Returns {'width','height',...}."""
        data = self._call("GET", f"/mockup-generator/printfiles/{product_id}", auth=True)
        result = data["result"]
        # variant_printfiles maps placement -> printfile_id; look up its dims.
        pf_id = result["variant_printfiles"][0]["placements"][placement]
        for pf in result["printfiles"]:
            if pf["printfile_id"] == pf_id:
                return pf
        raise PrintfulError(0, f"no printfile dims for placement {placement!r}")

    def generate_mockups(self, product_id: int, variant_ids: list[int],
                         image_url: str, placement: str = "front",
                         position: dict | None = None,
                         poll_seconds: float = 2.0, max_polls: int = 40,
                         sleep: Callable[[float], None] = time.sleep) -> list[dict]:
        """Kick off Printful's async Mockup Generator and poll to completion.
        Returns the mockup entries (each with a real mockup_url) — the
        instrument for verifying the design renders correctly per colorway.
        Non-mutating: makes preview images, changes nothing in the store.

        `position` places the design in the print area; if omitted, the
        design is fit to fill the full area (correct for a full-canvas
        design like ours)."""
        if position is None:
            area = self.front_print_area(product_id, placement)
            position = {"area_width": area["width"], "area_height": area["height"],
                        "width": area["width"], "height": area["height"],
                        "top": 0, "left": 0}
        task = self._call(
            "POST", f"/mockup-generator/create-task/{product_id}",
            body={"variant_ids": variant_ids, "format": "png",
                  "files": [{"placement": placement, "image_url": image_url,
                             "position": position}]},
            auth=True,
        )
        task_key = task["result"]["task_key"]
        for _ in range(max_polls):
            sleep(poll_seconds)
            res = self._call("GET", f"/mockup-generator/task?task_key={task_key}", auth=True)
            status = res["result"]["status"]
            if status == "completed":
                return res["result"]["mockups"]
            if status == "failed":
                raise PrintfulError(0, f"mockup task failed: {res['result']}")
        raise TimeoutError("Printful mockup task did not complete in time")
