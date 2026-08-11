"""Affilia — lifecycle wrapper around omniflash.ExtensionBridge.

Mirrors the proven pattern from flow-agent/cli/api.py's lifespan(): create one
ExtensionBridge, call bridge.start() on app startup, bridge.close() on shutdown.
The Chrome extension connects via the FastAPI /ws route (see routers/status.py
websocket registered in main.py), not via bridge.start()'s standalone listeners.
"""

import sys
from pathlib import Path
from typing import Optional

from . import settings

if str(settings.ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(settings.ENGINE_DIR))

from omniflash import ExtensionBridge  # noqa: E402

_bridge: Optional[ExtensionBridge] = None


async def init_bridge() -> ExtensionBridge:
    global _bridge
    _bridge = ExtensionBridge()
    _bridge.set_preferred_instance(settings.get_flow_extension_instance_id())
    await _bridge.start()
    return _bridge


async def close_bridge() -> None:
    global _bridge
    if _bridge:
        await _bridge.close()
        _bridge = None


def get_bridge() -> ExtensionBridge:
    global _bridge
    if _bridge is None:
        _bridge = ExtensionBridge()
        _bridge.set_preferred_instance(settings.get_flow_extension_instance_id())
        # Note: start() is normally called in init_bridge, but we instantiate it here to prevent RuntimeError
    return _bridge


def status_snapshot() -> dict:
    if _bridge is None:
        return {"state": "starting", "extension_connected": False, "logged_in": False, "instances": [], "total_connected_profiles": 0}
    
    # Prune any closed/stale websockets from _instances
    stale_ids = []
    for i_id, entry in list(_bridge._instances.items()):
        ws = entry.get("ws")
        if ws is None:
            stale_ids.append(i_id)
        elif hasattr(ws, "client_state") and str(ws.client_state).upper() in ("DISCONNECTED", "CLOSED"):
            stale_ids.append(i_id)
        elif hasattr(ws, "closed") and ws.closed:
            stale_ids.append(i_id)
    for s_id in stale_ids:
        _bridge._instances.pop(s_id, None)

    instances = _bridge.instance_snapshot()
    
    # Deduplicate by instance_name or project_id if duplicate connections exist
    unique_instances = []
    seen_keys = set()
    for inst in instances:
        key = inst.get("name") or inst.get("id")
        if key not in seen_keys:
            seen_keys.add(key)
            unique_instances.append(inst)

    any_connected = len(unique_instances) > 0
    any_logged_in = any(i.get("logged_in") for i in unique_instances)

    if any_connected and any_logged_in:
        state = "ready"
    elif any_connected:
        state = "connected_no_login"
    else:
        state = "disconnected"

    return {
        "state": state,
        "extension_connected": any_connected,
        "logged_in": any_logged_in,
        "active_extension_instance_id": _bridge.active_instance_id,
        "selected_extension_instance_id": _bridge._preferred_instance_id,
        "extension_instances": unique_instances,
        "total_connected_profiles": len(unique_instances),
    }


async def ensure_ready(timeout: int = 15) -> None:
    """Raise a clear, user-facing error if the bridge isn't ready for a generation call."""
    bridge = get_bridge()
    if status_snapshot()["state"] == "ready":
        return
    connected = await bridge.wait_for_extension(timeout=timeout, max_retries=1)
    if not connected:
        raise RuntimeError(
            "Google Flow belum terhubung. Pastikan extension Flow Agent sudah dimuat di "
            "Chrome (chrome://extensions) dan kamu sudah login di "
            "labs.google/fx/tools/flow, lalu coba lagi."
        )
