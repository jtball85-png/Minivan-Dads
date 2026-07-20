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
                 transport: Transport | None = None):
        self.api_key = api_key
        self.base_url = base_url
        self._transport = transport or _urllib_transport

    def _call(self, method: str, path: str, body: dict | None = None, auth: bool = False):
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        if auth:
            if not self.api_key:
                raise PrintfulError(0, "PRINTFUL_API_KEY required for this call but not set")
            headers["Authorization"] = f"Bearer {self.api_key}"
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else None
        status, data = self._transport(method, self.base_url + path, headers, body_bytes)
        if status >= 400 or status == 0:
            raise PrintfulError(status, (data or {}).get("error") or data)
        return data

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

    # -- Connector protocol (executor-only: execute / read_state / restore)

    def read_state(self, action_type: ActionType, params: dict) -> dict:
        # Pre-create there is nothing to capture except the external_id we're
        # about to claim — that's what rollback needs.
        return {"external_id": params["external_id"],
                "note": "pre-create snapshot; rollback deletes @external_id"}

    def execute(self, action_type: ActionType, params: dict) -> dict:
        sync_variants = [
            {"variant_id": vid,
             "files": [{"type": params["placement"], "url": params["print_file_url"]}]}
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
        self._call("DELETE", f"/store/products/@{ext}", auth=True)
        return {"deleted_external_id": ext}

    # -- verification (free, non-mutating; not a governed write) ---------

    def generate_mockups(self, product_id: int, variant_ids: list[int],
                         image_url: str, placement: str = "front",
                         poll_seconds: float = 2.0, max_polls: int = 40,
                         sleep: Callable[[float], None] = time.sleep) -> list[dict]:
        """Kick off Printful's async Mockup Generator and poll to completion.
        Returns the mockup entries (each with a real mockup_url) — the
        instrument for verifying the design renders correctly per colorway.
        Non-mutating: makes preview images, changes nothing in the store."""
        task = self._call(
            "POST", f"/mockup-generator/create-task/{product_id}",
            body={"variant_ids": variant_ids,
                  "files": [{"placement": placement, "image_url": image_url}]},
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
