"""
UBTECH mini SDK gọi connection.closed; websockets>=11 dùng connection.state.
Gọi apply_mini_websocket_compat() trước mọi import mini_sdk / mini.channels.
"""
from __future__ import annotations

_applied = False


def apply_mini_websocket_compat() -> None:
    global _applied
    if _applied:
        return
    try:
        from websockets.asyncio.client import ClientConnection
        from websockets.protocol import State
    except ImportError:
        return
    if getattr(ClientConnection, "_alphamini_closed_shim", False):
        _applied = True
        return

    def _closed_shim(self) -> bool:
        try:
            return self.state is State.CLOSED
        except Exception:
            return True

    ClientConnection.closed = property(_closed_shim)  # type: ignore[assignment]
    ClientConnection._alphamini_closed_shim = True
    _applied = True
