"""Printful connector tests — a fake transport, never hits the network.
Includes a full governance round-trip through the real Executor:
dry-run -> supervised create -> rollback (delete)."""

from __future__ import annotations

import json

import pytest

from brain.actions.models import ActionIntent, ActionMode
from brain.actions.registry import REGISTRY
from brain.connectors.printful import PrintfulConnector, PrintfulError
from brain.executor import Executor
from brain.models import DepartmentConfig


class FakeTransport:
    """Records calls; returns canned (status, json) per (method, path-prefix)."""

    def __init__(self):
        self.calls = []
        self.responses = {}   # (method, path_contains) -> (status, json)

    def set(self, method, path_contains, status, body):
        self.responses[(method, path_contains)] = (status, body)

    def __call__(self, method, url, headers, body_bytes):
        parsed_body = json.loads(body_bytes) if body_bytes else None
        self.calls.append({"method": method, "url": url, "headers": headers, "body": parsed_body})
        for (m, frag), resp in self.responses.items():
            if m == method and frag in url:
                return resp
        return 200, {"result": {}}


CATALOG_71 = {"result": {"variants": [
    {"id": 1001, "color": "Black", "size": "S"},
    {"id": 1002, "color": "Black", "size": "M"},
    {"id": 2001, "color": "Navy", "size": "S"},
    {"id": 3001, "color": "Dark Grey Heather", "size": "S"},
    {"id": 9999, "color": "Red", "size": "S"},
]}}


class TestCatalogLookup:
    def test_filters_by_color_and_size_and_reports_missing(self):
        t = FakeTransport()
        t.set("GET", "/products/71", 200, CATALOG_71)
        c = PrintfulConnector(transport=t)
        out = c.list_catalog_variant_ids(71, ["Black", "Navy"], ["S", "M"])
        assert out["variants"][("Black", "S")] == 1001
        assert out["variants"][("Black", "M")] == 1002
        assert out["variants"][("Navy", "S")] == 2001
        assert ("Navy", "M") in out["missing"]   # Navy/M not in catalog
        # catalog read is unauthenticated — no Authorization header
        assert "Authorization" not in t.calls[0]["headers"]


class TestExecuteAndRestore:
    def test_execute_builds_sync_product_body_and_needs_auth(self):
        t = FakeTransport()
        t.set("POST", "/store/products", 200, {"result": {"id": 555}})
        c = PrintfulConnector(api_key="k", transport=t)
        params = {
            "product_id": 71, "variant_ids": [1001, 2001, 3001],
            "files": [
                {"placement": "front", "url": "https://host/design.png"},
                {"placement": "sleeve_left", "url": "https://host/sleeve.png"},
            ],
            "product_name": "Quiet Game Tee", "external_id": "mvd-quiet-game",
        }
        result = c.execute(REGISTRY["printful.create_product"], params)
        assert result["printful_id"] == 555
        assert result["variants_created"] == 3
        body = t.calls[0]["body"]
        assert body["sync_product"]["external_id"] == "mvd-quiet-game"
        assert len(body["sync_variants"]) == 3
        # each variant carries BOTH print files (front + sleeve)
        assert body["sync_variants"][0] == {
            "variant_id": 1001,
            "files": [{"type": "front", "url": "https://host/design.png"},
                      {"type": "sleeve_left", "url": "https://host/sleeve.png"}],
        }
        assert t.calls[0]["headers"]["Authorization"] == "Bearer k"

    def test_execute_passes_file_position_when_given(self):
        """Regression: without a position Printful prints the file at its native
        size (a small file floats tiny in the print area). An explicit position
        must reach the API body per file; files without one omit the key."""
        t = FakeTransport()
        t.set("POST", "/store/products", 200, {"result": {"id": 9}})
        c = PrintfulConnector(api_key="k", transport=t)
        pos = {"area_width": 1800, "area_height": 2400, "width": 1800,
               "height": 2400, "top": 0, "left": 0}
        c.execute(REGISTRY["printful.create_product"], {
            "product_id": 71, "variant_ids": [1001],
            "files": [{"placement": "front", "url": "https://host/f.png", "position": pos},
                      {"placement": "sleeve_left", "url": "https://host/s.png"}],
            "product_name": "n", "external_id": "e"})
        files = t.calls[0]["body"]["sync_variants"][0]["files"]
        assert files[0] == {"type": "front", "url": "https://host/f.png", "position": pos}
        assert files[1] == {"type": "sleeve_left", "url": "https://host/s.png"}  # no position key

    def test_execute_without_key_raises(self):
        c = PrintfulConnector(api_key=None, transport=FakeTransport())
        with pytest.raises(PrintfulError, match="PRINTFUL_API_KEY required"):
            c.execute(REGISTRY["printful.create_product"],
                      {"product_id": 71, "variant_ids": [1],
                       "files": [{"placement": "front", "url": "u"}],
                       "product_name": "n", "external_id": "e"})

    def test_read_state_captures_external_id_for_rollback(self):
        c = PrintfulConnector(api_key="k", transport=FakeTransport())
        snap = c.read_state(REGISTRY["printful.create_product"], {"external_id": "mvd-x"})
        assert snap["external_id"] == "mvd-x"

    def test_restore_deletes_by_external_id(self):
        t = FakeTransport()
        t.set("DELETE", "/store/products/@mvd-x", 200, {"result": {}})
        c = PrintfulConnector(api_key="k", transport=t)
        out = c.restore(REGISTRY["printful.create_product"], {"external_id": "mvd-x"})
        assert out["deleted_external_id"] == "mvd-x"
        assert t.calls[0]["method"] == "DELETE"
        assert "@mvd-x" in t.calls[0]["url"]

    def test_http_error_raises_printful_error(self):
        t = FakeTransport()
        t.set("POST", "/store/products", 401, {"error": {"message": "unauthorized"}})
        c = PrintfulConnector(api_key="bad", transport=t)
        with pytest.raises(PrintfulError) as ei:
            c.execute(REGISTRY["printful.create_product"],
                      {"product_id": 71, "variant_ids": [1],
                       "files": [{"placement": "front", "url": "u"}],
                       "product_name": "n", "external_id": "e"})
        assert ei.value.status == 401


class TestListProducts:
    def test_expands_each_product_to_variants(self):
        t = FakeTransport()
        t.set("GET", "/store/products/555", 200, {"result": {
            "sync_product": {"id": 555, "name": "Tee"},
            "sync_variants": [{"id": 11, "variant_id": 4018, "name": "Tee / Black / M"}],
        }})
        t.set("GET", "/store/products", 200, {"result": [{"id": 555}]})
        c = PrintfulConnector(api_key="k", transport=t)
        details = c.list_products()
        assert len(details) == 1
        assert details[0]["sync_product"]["id"] == 555
        assert details[0]["sync_variants"][0]["variant_id"] == 4018


class TestUpdateActions:
    CURRENT = {"result": {
        "sync_product": {"id": 555, "external_id": "mvd-x", "name": "Old Name"},
        "sync_variants": [{"id": 11, "retail_price": "24.00"},
                          {"id": 12, "retail_price": "24.00"}],
    }}

    def test_update_product_puts_new_name(self):
        t = FakeTransport()
        t.set("PUT", "/store/products/@mvd-x", 200, {"result": {}})
        c = PrintfulConnector(api_key="k", transport=t)
        out = c.execute(REGISTRY["printful.update_product"],
                        {"external_id": "mvd-x", "name": "New Name"})
        assert out == {"external_id": "mvd-x", "updated": "name"}
        assert t.calls[0]["method"] == "PUT"
        assert t.calls[0]["body"] == {"sync_product": {"name": "New Name"}}

    def test_read_state_snapshots_name_and_prices(self):
        t = FakeTransport()
        t.set("GET", "/store/products/@mvd-x", 200, self.CURRENT)
        c = PrintfulConnector(api_key="k", transport=t)
        snap = c.read_state(REGISTRY["printful.update_product"], {"external_id": "mvd-x"})
        assert snap["name"] == "Old Name"
        assert snap["retail_prices"] == [{"id": 11, "retail_price": "24.00"},
                                         {"id": 12, "retail_price": "24.00"}]

    def test_restore_update_product_reapplies_old_name(self):
        t = FakeTransport()
        t.set("PUT", "/store/products/@mvd-x", 200, {"result": {}})
        c = PrintfulConnector(api_key="k", transport=t)
        c.restore(REGISTRY["printful.update_product"],
                  {"external_id": "mvd-x", "name": "Old Name"})
        assert t.calls[0]["body"] == {"sync_product": {"name": "Old Name"}}

    def test_set_retail_price_prices_every_variant(self):
        t = FakeTransport()
        t.set("GET", "/store/products/@mvd-x", 200, self.CURRENT)
        t.set("PUT", "/store/products/@mvd-x", 200, {"result": {}})
        c = PrintfulConnector(api_key="k", transport=t)
        out = c.execute(REGISTRY["printful.set_retail_price"],
                        {"external_id": "mvd-x", "retail_price": 28})
        assert out["retail_price"] == "28.00"
        assert out["variants_priced"] == 2
        put = [call for call in t.calls if call["method"] == "PUT"][0]
        assert put["body"] == {"sync_variants": [
            {"id": 11, "retail_price": "28.00"}, {"id": 12, "retail_price": "28.00"}]}

    def test_restore_set_retail_price_reapplies_old_prices(self):
        t = FakeTransport()
        t.set("PUT", "/store/products/@mvd-x", 200, {"result": {}})
        c = PrintfulConnector(api_key="k", transport=t)
        c.restore(REGISTRY["printful.set_retail_price"],
                  {"external_id": "mvd-x",
                   "retail_prices": [{"id": 11, "retail_price": "24.00"}]})
        assert t.calls[0]["body"] == {"sync_variants": [{"id": 11, "retail_price": "24.00"}]}


class TestStoreId:
    def test_store_id_sets_header_on_auth_calls(self):
        t = FakeTransport()
        t.set("POST", "/store/products", 200, {"result": {"id": 1}})
        c = PrintfulConnector(api_key="k", store_id=12345, transport=t)
        c.execute(REGISTRY["printful.create_product"],
                  {"product_id": 71, "variant_ids": [1],
                   "files": [{"placement": "front", "url": "u"}],
                   "product_name": "n", "external_id": "e"})
        assert t.calls[0]["headers"]["X-PF-Store-Id"] == "12345"

    def test_resolve_single_store(self):
        t = FakeTransport()
        t.set("GET", "/stores", 200, {"result": [{"id": 777, "name": "Minivan Dads"}]})
        c = PrintfulConnector(api_key="k", transport=t)
        assert c.resolve_store_id() == 777
        assert c.store_id == 777

    def test_resolve_no_store_raises(self):
        t = FakeTransport()
        t.set("GET", "/stores", 200, {"result": []})
        c = PrintfulConnector(api_key="k", transport=t)
        with pytest.raises(PrintfulError, match="no Printful store exists"):
            c.resolve_store_id()

    def test_resolve_multiple_stores_raises(self):
        t = FakeTransport()
        t.set("GET", "/stores", 200, {"result": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]})
        c = PrintfulConnector(api_key="k", transport=t)
        with pytest.raises(PrintfulError, match="2 stores found"):
            c.resolve_store_id()


POS = {"area_width": 1800, "area_height": 2400, "width": 1800,
       "height": 2400, "top": 0, "left": 0}


class TestMockups:
    def test_polls_until_completed(self):
        seq = iter([
            (200, {"result": {"status": "pending"}}),
            (200, {"result": {"status": "completed",
                              "mockups": [{"mockup_url": "https://m/1.png"}]}}),
        ])

        def transport(method, url, headers, body):
            parsed = json.loads(body) if body else None
            if "create-task" in url:
                assert parsed["files"][0]["position"] == POS
                return 200, {"result": {"task_key": "abc"}}
            return next(seq)

        c = PrintfulConnector(api_key="k", transport=transport)
        mockups = c.generate_mockups(71, [1001], "https://host/d.png", position=POS,
                                     poll_seconds=0, sleep=lambda s: None)
        assert mockups == [{"mockup_url": "https://m/1.png"}]

    def test_failed_task_raises(self):
        def transport(method, url, headers, body):
            if "create-task" in url:
                return 200, {"result": {"task_key": "abc"}}
            return 200, {"result": {"status": "failed"}}

        c = PrintfulConnector(api_key="k", transport=transport)
        with pytest.raises(PrintfulError, match="mockup task failed"):
            c.generate_mockups(71, [1001], "u", position=POS,
                               poll_seconds=0, sleep=lambda s: None)

    def test_auto_position_fetches_print_area(self):
        """With no explicit position, the connector fetches the print-area
        dims and fills them — matching a full-canvas design."""
        printfiles = {"result": {
            "variant_printfiles": [{"variant_id": 1, "placements": {"front": 1}}],
            "printfiles": [{"printfile_id": 1, "width": 1800, "height": 2400}],
        }}
        captured = {}

        def transport(method, url, headers, body):
            parsed = json.loads(body) if body else None
            if "printfiles" in url:
                return 200, printfiles
            if "create-task" in url:
                captured["position"] = parsed["files"][0]["position"]
                return 200, {"result": {"task_key": "k"}}
            return 200, {"result": {"status": "completed", "mockups": []}}

        c = PrintfulConnector(api_key="k", transport=transport)
        c.generate_mockups(71, [1001], "u", poll_seconds=0, sleep=lambda s: None)
        assert captured["position"] == {"area_width": 1800, "area_height": 2400,
                                        "width": 1800, "height": 2400, "top": 0, "left": 0}


class TestExecutorGovernanceRoundTrip:
    """The real Executor + PrintfulConnector(fake transport): the full
    governed path — dry-run by default, supervised creates, rollback deletes."""

    def _harness(self, tmp_hq_root, config, hq, transport):
        config.departments["creative"] = DepartmentConfig(
            name="creative", tier=1, status="active", report_cadence="weekly")
        from brain.actions.limits import AgentLimits
        limits = {"creative": AgentLimits(allowed_actions=["printful.create_product"])}
        connector = PrintfulConnector(api_key="k", transport=transport)
        ex = Executor(
            hq=hq, registry=REGISTRY, limits=limits,
            capabilities={}, connectors={"printful": connector},
            capabilities_path=tmp_hq_root / "actions" / "capabilities.yaml",
            env={},
        )
        return ex

    def _intent(self):
        return ActionIntent(
            agent="creative", action_type="printful.create_product",
            params={"product_id": 71, "variant_ids": [1001, 2001, 3001],
                    "files": [{"placement": "front", "url": "https://host/design.png"},
                              {"placement": "sleeve_left", "url": "https://host/sleeve.png"}],
                    "product_name": "Quiet Game Tee", "external_id": "mvd-quiet-game"},
            rationale="first connector test", directive_version="2026-07-20",
        )

    def test_default_dry_run_touches_no_network(self, tmp_hq_root, config, hq):
        t = FakeTransport()
        ex = self._harness(tmp_hq_root, config, hq, t)
        record = ex.submit(self._intent())
        assert record.result == "dry_run"
        assert t.calls == []   # dry-run never touches Printful

    def test_supervised_creates_then_rollback_deletes(self, tmp_hq_root, config, hq):
        t = FakeTransport()
        t.set("POST", "/store/products", 200, {"result": {"id": 555}})
        t.set("DELETE", "/store/products/@mvd-quiet-game", 200, {"result": {}})
        ex = self._harness(tmp_hq_root, config, hq, t)
        ex.capabilities["creative"] = {"printful.create_product": ActionMode.SUPERVISED}

        record = ex.submit(self._intent())
        assert record.result == "executed"
        assert any(c["method"] == "POST" and "/store/products" in c["url"] for c in t.calls)
        # snapshot captured the external_id
        assert hq.read_snapshot(record.id)["external_id"] == "mvd-quiet-game"

        rolled = ex.rollback(record.id)
        assert rolled.result == "rolled_back"
        assert any(c["method"] == "DELETE" and "@mvd-quiet-game" in c["url"] for c in t.calls)
