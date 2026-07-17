"""Live-check tool tests — urllib is monkeypatched, no real network calls."""

from __future__ import annotations

import urllib.error

import pytest

from brain.tools import (
    TOOL_SCHEMAS,
    check_domain,
    check_handle,
    execute_tool,
)


class FakeResponse:
    def __init__(self, status=200, body=b""):
        self.status = status
        self._body = body

    def read(self, n=-1):
        return self._body[:n] if n != -1 else self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def raise_http_error(code):
    def _raise(*a, **k):
        raise urllib.error.HTTPError("http://x", code, "err", {}, None)
    return _raise


class TestCheckDomain:
    def test_registered_domain(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(200))
        result = check_domain("minivandads.com")
        assert result == {"domain": "minivandads.com", "status": "registered", "confidence": "high"}

    def test_available_domain_is_404(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", raise_http_error(404))
        result = check_domain("MinivanDads.Shop")  # case/whitespace normalized
        assert result["domain"] == "minivandads.shop"
        assert result["status"] == "available"
        assert result["confidence"] == "high"

    def test_other_http_error_is_low_confidence_unknown(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", raise_http_error(503))
        result = check_domain("minivandads.co")
        assert result["status"] == "unknown"
        assert result["confidence"] == "low"

    def test_network_failure_degrades_gracefully(self, monkeypatch):
        def boom(*a, **k):
            raise TimeoutError("timed out")
        monkeypatch.setattr("urllib.request.urlopen", boom)
        result = check_domain("minivandads.com")
        assert result["status"] == "unknown"
        assert "timed out" in result["note"]


class TestCheckHandle:
    def test_etsy_high_confidence_available(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", raise_http_error(404))
        result = check_handle("etsy", "@minivandads")
        assert result == {"platform": "etsy", "handle": "minivandads",
                          "status": "available", "confidence": "high"}

    def test_etsy_taken(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen",
                            lambda *a, **k: FakeResponse(200, b"<html>a real shop</html>"))
        result = check_handle("etsy", "minivandads")
        assert result["status"] == "taken_or_exists"
        assert result["confidence"] == "high"

    def test_instagram_never_hits_network_and_is_always_inconclusive(self, monkeypatch):
        # Regression: a nonsense handle that cannot possibly exist still
        # came back "taken_or_exists" via the old marker heuristic, live —
        # proof the signal is worthless. Instagram now never even attempts
        # the network call; it's unverifiable by design, not by guesswork.
        def fail_if_called(*a, **k):
            raise AssertionError("Instagram checks must never hit the network")
        monkeypatch.setattr("urllib.request.urlopen", fail_if_called)
        result = check_handle("instagram", "zzqxnonexistenthandle999xyz")
        assert result["status"] == "inconclusive"
        assert result["confidence"] == "unverifiable"

    def test_tiktok_never_hits_network_and_is_always_inconclusive(self, monkeypatch):
        def fail_if_called(*a, **k):
            raise AssertionError("TikTok checks must never hit the network")
        monkeypatch.setattr("urllib.request.urlopen", fail_if_called)
        result = check_handle("tiktok", "anyhandle")
        assert result["status"] == "inconclusive"
        assert result["confidence"] == "unverifiable"

    def test_x_is_always_inconclusive_blocked(self, monkeypatch):
        # No network call should even happen for X.
        def fail_if_called(*a, **k):
            raise AssertionError("X checks must never hit the network")
        monkeypatch.setattr("urllib.request.urlopen", fail_if_called)
        result = check_handle("x", "minivandads")
        assert result["status"] == "inconclusive"
        assert result["confidence"] == "unverifiable"

    def test_unsupported_platform(self):
        result = check_handle("myspace", "minivandads")
        assert result["status"] == "unsupported_platform"

    def test_bot_blocked_response_is_inconclusive_not_available(self, monkeypatch):
        # Observed live: Etsy returns 403 to this tool's requests. Declared
        # "high confidence" in PLATFORM_CONFIG must NOT leak through when
        # the platform actually blocked the check — degrade honestly.
        monkeypatch.setattr("urllib.request.urlopen", raise_http_error(403))
        result = check_handle("etsy", "minivandads")
        assert result["status"] == "inconclusive"
        assert result["confidence"] == "low"


class TestExecuteTool:
    def test_dispatches_domain(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(200))
        result = execute_tool("check_domain_availability", {"domain": "minivandads.com"})
        assert result["status"] == "registered"

    def test_dispatches_handle(self, monkeypatch):
        result = execute_tool("check_handle_availability", {"platform": "x", "handle": "mvd"})
        assert result["confidence"] == "unverifiable"

    def test_unknown_tool(self):
        assert "error" in execute_tool("nonsense_tool", {})


class TestToolSchemas:
    def test_schemas_are_valid_anthropic_shape(self):
        names = {t["name"] for t in TOOL_SCHEMAS}
        assert names == {"check_domain_availability", "check_handle_availability"}
        for t in TOOL_SCHEMAS:
            assert "description" in t and t["description"]
            assert t["input_schema"]["type"] == "object"
