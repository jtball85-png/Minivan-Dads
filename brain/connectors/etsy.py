"""Etsy connector — ready, not wired.

The unified product model, the storefront agent, and the dashboard all already
speak "one product shape regardless of platform," so Etsy has a real slot. But
there is no Etsy shop yet (the CEO opens + connects it), and no OAuth token.
Until those exist, every live method raises EtsyNotConnected with a plain next
step — nothing silently no-ops or pretends.

Turning Etsy on later is: the CEO opens an Etsy shop and connects it to
Printful (browser OAuth on their side); we add ETSY_* creds to .env, register
this connector in the executor's connectors map and the sync command, and fill
in the HTTP calls. The protocol shape here does not change.
"""

from __future__ import annotations

from brain.actions.models import ActionType


class EtsyNotConnected(RuntimeError):
    def __init__(self, detail: str = ""):
        super().__init__(
            "Etsy is not connected yet. Open an Etsy shop and connect it to "
            "Printful, then add ETSY_* credentials. " + detail
        )


class EtsyConnector:
    """Implements the executor Connector protocol + a catalog read, but stays
    inert until credentials are present."""

    def __init__(self, api_key: str | None = None, shop_id: str | None = None,
                 transport=None):
        self.api_key = api_key
        self.shop_id = shop_id
        self._transport = transport

    @property
    def connected(self) -> bool:
        return bool(self.api_key and self.shop_id)

    def _require_connected(self) -> None:
        if not self.connected:
            raise EtsyNotConnected()

    # -- catalog read (for the unified product view) ----------------------

    def list_listings(self) -> list[dict]:
        self._require_connected()
        raise EtsyNotConnected("list_listings not implemented until wiring.")

    # -- Connector protocol (executor-only) -------------------------------

    def read_state(self, action_type: ActionType, params: dict) -> dict:
        self._require_connected()
        raise EtsyNotConnected()

    def execute(self, action_type: ActionType, params: dict) -> dict:
        self._require_connected()
        raise EtsyNotConnected()

    def restore(self, action_type: ActionType, snapshot: dict) -> dict:
        self._require_connected()
        raise EtsyNotConnected()
