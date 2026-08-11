"""Omni Flash — ExtensionBridge.

WebSocket + HTTP server that communicates with the Chrome extension.
Handles auth token capture, API proxying, and request/response routing.
"""

import asyncio
import contextvars
import json
import logging
import random
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

import websockets

from .config import (
    WS_PORT, HTTP_PORT, API_BASE, API_KEY, DEFAULT_PROJECT,
    CLIENT_CTX, USER_AGENTS, API_REQUEST_TIMEOUT,
    MAX_CONCURRENT_REQUESTS, REQUEST_MIN_INTERVAL,
)
"""Omni Flash — ExtensionBridge.

WebSocket + HTTP server that communicates with the Chrome extension.
Handles auth token capture, API proxying, and request/response routing.
"""

import asyncio
import json
import logging
import random
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

import websockets

from .config import (
    WS_PORT, HTTP_PORT, API_BASE, API_KEY,
    CLIENT_CTX, USER_AGENTS, API_REQUEST_TIMEOUT,
    MAX_CONCURRENT_REQUESTS, REQUEST_MIN_INTERVAL,
)

log = logging.getLogger("omniflash.bridge")


class ExtensionBridge:
    """WebSocket server that Chrome extension connects to."""

    def __init__(self):
        self._ws = None
        self._instances: dict[str, dict] = {}
        self._preferred_instance_id: str | None = None
        self.active_instance_id: str | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._flow_key = None
        self._connected = asyncio.Event()
        self._loop = None
        self._rr_idx = 0
        # Late/orphan-response reconciliation: remember a small window of recent
        # requests so a response that arrives after its caller gave up is not
        # silently dropped but handed to the orphan handler instead.
        self._req_meta: dict[str, dict] = {}
        self._orphan_handler = None
        # The extension retries delivery until acked, so the same response may
        # arrive more than once. Track ids already resolved/recovered to make
        # delivery idempotent (no duplicate saves).
        self._seen_ids: dict[str, bool] = {}
        # Rate limiting: cap concurrent generations and space them out so we
        # don't trip Google's UNUSUAL_ACTIVITY throttle. Semaphore is created
        # lazily on the running loop (see _get_rate_limit).
        self._rate_sem: asyncio.Semaphore | None = None
        self._rate_lock: asyncio.Lock | None = None
        self._last_request_at: float = 0.0
        self._last_credits: int | None = None
        self._job_instance_id = contextvars.ContextVar(
            f"omniflash_job_instance_{id(self)}", default=None
        )

    def get_last_credits(self) -> int | None:
        return self._last_credits

    def update_last_credits(self, credits, instance_id=None):
        try:
            val = int(credits)
            self._last_credits = val
            target_id = instance_id or self._job_instance_id.get() or self.active_instance_id
            if target_id and target_id in self._instances:
                self._instances[target_id]["credits"] = val
        except (ValueError, TypeError):
            pass

    def _get_target_ws_with_entry(self):
        target_id = self._preferred_instance_id or self._job_instance_id.get()
        if target_id:
            entry = self._instances.get(target_id)
            if entry and entry.get("ws") and not entry.get("quota_exhausted"):
                return entry["ws"], entry
        available = [(e["ws"], e) for e in self._instances.values() if e.get("ws") and e.get("flow_key") and not e.get("quota_exhausted")]
        if available:
            idx = self._rr_idx % len(available)
            ws, entry = available[idx]
            return ws, entry
        if self._ws:
            active_entry = self._instances.get(self.active_instance_id)
            if active_entry and active_entry.get("ws"):
                return self._ws, active_entry
        return None, None

    def _get_target_ws(self):
        ws, _ = self._get_target_ws_with_entry()
        return ws

    def acquire_job_instance(self, force_new=False):
        """Pick a sticky Chrome instance entry for an entire job run.
        In Auto mode, uses Round-Robin per job (incrementing _rr_idx once per job).
        """
        if self._preferred_instance_id:
            entry = self._instances.get(self._preferred_instance_id)
            if entry and entry.get("ws"):
                pid = entry.get("project_id") or "auto"
                name = entry.get("name") or f"Chrome {self._preferred_instance_id[:8]}"
                return pid, name

        current_job_instance_id = self._job_instance_id.get()
        if not force_new and current_job_instance_id:
            entry = self._instances.get(current_job_instance_id)
            if entry and entry.get("ws"):
                pid = entry.get("project_id") or "auto"
                name = entry.get("name") or f"Chrome {current_job_instance_id[:8]}"
                return pid, name

        available = [
            (inst_id, e) for inst_id, e in self._instances.items()
            if e.get("ws") and e.get("flow_key") and not e.get("quota_exhausted")
        ]
        if available:
            idx = self._rr_idx % len(available)
            self._rr_idx += 1
            inst_id, entry = available[idx]
            self._job_instance_id.set(inst_id)
            pid = entry.get("project_id") or "auto"
            name = entry.get("name") or "Chrome Extension"
            return pid, name
        return "auto", "Chrome Extension"

    def mark_current_instance_unavailable(self, reason="quota_exhausted"):
        target_id = self._preferred_instance_id or self._job_instance_id.get() or self.active_instance_id
        if target_id and target_id in self._instances:
            self._instances[target_id]["quota_exhausted"] = True
            self._instances[target_id]["unavailable_reason"] = reason
            log.warning("Menandai akun Flow '%s' tidak tersedia (%s).", self._instances[target_id].get("name", target_id), reason)

    def mark_current_instance_exhausted(self):
        self.mark_current_instance_unavailable("quota_exhausted")

    def switch_to_next_available_instance(self, reason="quota_exhausted"):
        self.mark_current_instance_unavailable(reason)
        available = [
            (inst_id, e) for inst_id, e in self._instances.items()
            if e.get("ws") and e.get("flow_key") and not e.get("quota_exhausted")
        ]
        if available:
            idx = self._rr_idx % len(available)
            self._rr_idx += 1
            inst_id, entry = available[idx]
            self._job_instance_id.set(inst_id)
            self._activate_instance(inst_id, entry)
            pid = entry.get("project_id") or "auto"
            name = entry.get("name") or f"Chrome {inst_id[:8]}"
            log.info("Otomatis beralih ke akun Flow cadangan berikutnya: '%s'", name)
            return pid, name
        return None

    def release_job_instance(self):
        self._job_instance_id.set(None)

    def get_active_instance_info(self):
        """Returns (project_id, instance_name) of the active target Chrome instance."""
        return self.acquire_job_instance(force_new=False)

    def set_preferred_instance(self, instance_id):
        """Select the only extension instance allowed to proxy Flow calls."""
        self._preferred_instance_id = (instance_id or "").strip() or None
        selected = self._instances.get(self._preferred_instance_id) if self._preferred_instance_id else None
        if selected:
            self._activate_instance(self._preferred_instance_id, selected)
        elif self._preferred_instance_id:
            self._ws = None
            self._flow_key = None
            self.active_instance_id = None
            self._connected.clear()

    def _activate_instance(self, instance_id, entry):
        self.active_instance_id = instance_id
        self._ws = entry["ws"]
        self._flow_key = entry.get("flow_key")
        if self._flow_key:
            self._connected.set()
        else:
            self._connected.clear()

    def register_instance(self, instance_id, ws, instance_name=None, project_id=None):
        instance_id = str(instance_id or "").strip()
        if not instance_id:
            raise ValueError("Extension instance id is required")
        previous = self._instances.get(instance_id, {})
        entry = {
            "ws": ws,
            "name": (instance_name or previous.get("name") or f"Chrome {instance_id[:8]}").strip(),
            "flow_key": previous.get("flow_key"),
            "project_id": project_id or previous.get("project_id"),
        }
        self._instances[instance_id] = entry
        if instance_id == self._preferred_instance_id:
            self._activate_instance(instance_id, entry)
        elif self._preferred_instance_id is None and self._ws is None:
            # Backward-compatible first connection until the user pairs one.
            self._activate_instance(instance_id, entry)
        return entry

    def unregister_instance(self, instance_id, ws):
        entry = self._instances.get(instance_id)
        if not entry or entry.get("ws") is not ws:
            return
        self._instances.pop(instance_id, None)
        if self.active_instance_id == instance_id and self._ws is ws:
            self._ws = None
            self._flow_key = None
            self.active_instance_id = None
            self._connected.clear()

    def record_instance_token(self, instance_id, flow_key):
        entry = self._instances.get(instance_id)
        if entry is not None:
            entry["flow_key"] = flow_key
        if instance_id == self.active_instance_id:
            self._flow_key = flow_key
            if flow_key:
                self._connected.set()

    def record_instance_project_id(self, instance_id, project_id):
        if not project_id:
            return
        entry = self._instances.get(instance_id)
        if entry is not None:
            entry["project_id"] = str(project_id).strip()

    def refresh_all_credits(self):
        """Trigger all connected extension instances to fetch fresh credit balance."""
        for instance_id, entry in list(self._instances.items()):
            ws = entry.get("ws")
            if ws:
                req_id = f"credits_{uuid.uuid4().hex[:8]}"
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._send_to_ws(ws, {"type": "REFRESH_CREDITS", "id": req_id}), self._loop)

    def instance_snapshot(self):
        self.refresh_all_credits()
        return [
            {
                "id": instance_id,
                "name": entry["name"],
                "project_id": entry.get("project_id"),
                "credits": entry.get("credits"),
                "connected": True,
                "logged_in": bool(entry.get("flow_key")),
                "selected": instance_id == self._preferred_instance_id,
                "active": instance_id == self.active_instance_id,
            }
            for instance_id, entry in self._instances.items()
        ]

    async def _send_to_ws(self, ws, msg):
        if hasattr(ws, "send_text"):
            await ws.send_text(json.dumps(msg))
        else:
            await ws.send(json.dumps(msg))

    def _get_rate_limit(self):
        """Lazily build the concurrency semaphore + spacing lock on the active
        loop (they must be bound to the loop that awaits them)."""
        if self._rate_sem is None:
            self._rate_sem = asyncio.Semaphore(max(1, MAX_CONCURRENT_REQUESTS))
        if self._rate_lock is None:
            self._rate_lock = asyncio.Lock()
        return self._rate_sem, self._rate_lock

    def _mark_seen(self, req_id, max_keep=256):
        self._seen_ids[req_id] = True
        while len(self._seen_ids) > max_keep:
            oldest = next(iter(self._seen_ids))
            self._seen_ids.pop(oldest, None)

    def set_orphan_handler(self, handler):
        """Register async fn(data, meta) called when a response arrives for a
        request whose caller already timed out. Lets late-but-successful
        generations be recovered instead of discarded."""
        self._orphan_handler = handler

    def _remember_request(self, req_id, meta, max_keep=64):
        self._req_meta[req_id] = meta
        while len(self._req_meta) > max_keep:
            oldest = next(iter(self._req_meta))
            self._req_meta.pop(oldest, None)

    async def send_message(self, msg, ws=None):
        target_ws = ws or self._get_target_ws()
        if not target_ws:
            return
        try:
            if hasattr(target_ws, "send_text"):
                await target_ws.send_text(json.dumps(msg))
            else:
                await target_ws.send(json.dumps(msg))
        except Exception as e:
            log.warning("Failed to send message: %s", e)

    async def handle_fastapi_ws(self, ws):
        instance_id = None

        # Send callback config to extension
        import os
        space_id = os.environ.get("SPACE_ID")
        if space_id:
            author, name = space_id.split("/")
            subdomain = f"{author.lower()}-{name.lower()}".replace("_", "-")
            callback_url = f"https://{subdomain}.hf.space/api/ext/callback"
        else:
            callback_url = f"http://127.0.0.1:{os.environ.get('OPENAI_API_PORT', '8001')}/api/ext/callback"

        try:
            first_raw = await ws.receive_text()
            first_data = json.loads(first_raw)
            instance_id = first_data.get("instanceId") or f"legacy-{id(ws)}"
            instance_name = first_data.get("instanceName") or "Chrome (extension lama)"
            self.register_instance(instance_id, ws, instance_name)
            log.info("Extension instance connected: %s (%s)", instance_name, instance_id)
        except Exception as e:
            log.warning("Extension handshake failed: %s", e)
            return

        await self._send_to_ws(ws, {
            "type": "callback_config",
            "secret": "flow_secret",
            "callback_url": callback_url
        })

        # Send current state + resend token if we have one
        await self._send_to_ws(ws, {
            "type": "extension_ready",
            "selected": instance_id == self._preferred_instance_id,
        })
        # Request extension to fetch remaining credit balance immediately
        await self._send_to_ws(ws, {
            "type": "REFRESH_CREDITS",
            "id": f"credits_{uuid.uuid4().hex[:8]}"
        })

        try:
            await self._handle_message(first_data, instance_id)
            while True:
                raw = await ws.receive_text()
                data = json.loads(raw)
                await self._handle_message(data, instance_id)
        except Exception as e:
            log.warning("FastAPI WebSocket disconnected: %s", e)
        finally:
            self.unregister_instance(instance_id, ws)

    async def start(self):
        """Start WS server and HTTP callback server."""
        self._loop = asyncio.get_event_loop()
        self._start_http_server()

        self._ws_server = await websockets.serve(
            self._on_connect, "127.0.0.1", WS_PORT
        )
        log.info("WebSocket server on ws://127.0.0.1:%d", WS_PORT)
        log.info("HTTP callback on http://127.0.0.1:%d", HTTP_PORT)
        log.info("Waiting for Chrome extension to connect...")

    async def wait_for_extension(self, timeout=90, max_retries=3):
        """Wait until extension connects and sends flow key.

        Phase 1: Wait for WebSocket connection from extension.
        Phase 2: If no token, auto-open/refresh Flow tab and wait for token.
        """
        # Phase 1: Wait for WS connection
        try:
            await asyncio.wait_for(self._wait_for_ws(), 30)
        except asyncio.TimeoutError:
            log.error("Extension didn't connect in 30s")
            log.error("   Make sure Flow Agent extension is installed and enabled in Chrome")
            return False

        # If token already present, we're good
        if self._flow_key:
            return True

        # Phase 2: Extension connected but no token — auto-fix
        log.info("Extension connected but no auth token — auto-fixing...")

        for attempt in range(1, max_retries + 1):
            log.info("Attempt %d/%d: Opening/refreshing Flow tab...", attempt, max_retries)
            await self._request_flow_tab()

            # Wait for token to arrive (token_captured message)
            token_arrived = await self._wait_for_token(20)
            if token_arrived:
                log.info("Token captured after auto-fix!")
                return True

            log.warning("Token not captured yet...")

        log.error("Could not get auth token after %d retries", max_retries)
        log.error("   Make sure you're logged into Google at labs.google/fx/tools/flow")
        return False

    async def _wait_for_ws(self):
        """Wait until a WebSocket connection is established."""
        while not self._get_target_ws():
            await asyncio.sleep(0.5)

    async def _wait_for_token(self, timeout):
        """Wait until a valid token is captured."""
        self._connected.clear()
        try:
            await asyncio.wait_for(self._connected.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            _, entry = self._get_target_ws_with_entry()
            return entry is not None and bool(entry.get("flow_key"))

    async def _request_flow_tab(self):
        """Ask extension to open or refresh a Flow tab."""
        target_ws, _ = self._get_target_ws_with_entry()
        if not target_ws:
            return
        try:
            log.info("Requesting extension to open/refresh Flow tab...")
            await self.send_message({"method": "open_flow_tab"}, ws=target_ws)
            # Wait for page to fully load before requesting token refresh
            await asyncio.sleep(8)
            log.info("Requesting token refresh from Flow tab...")
            await self.send_message({"method": "refresh_flow_tab"}, ws=target_ws)
        except Exception as e:
            log.debug("Failed to request flow tab: %s", e)

    async def health_check(self):
        """Quick check if extension is ready with valid token."""
        target_ws, entry = self._get_target_ws_with_entry()
        if not target_ws or not (entry and entry.get("flow_key")):
            return False
        try:
            req_id = str(uuid.uuid4())
            future = self._loop.create_future()
            self._pending[req_id] = future
            await self.send_message({
                "id": req_id,
                "method": "get_status",
            }, ws=target_ws)
            result = await asyncio.wait_for(future, timeout=5)
            self._pending.pop(req_id, None)
            return result.get("result", {}).get("flowKeyPresent", False)
        except Exception:
            self._pending.pop(req_id, None)
            return False

    async def _on_connect(self, ws):
        self._ws = ws
        log.info("Extension connected!")
        try:
            async for raw in ws:
                data = json.loads(raw)
                await self._handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            log.warning("Extension disconnected")
            self._ws = None
            self._connected.clear()

    async def start(self):
        """Start WS server and HTTP callback server."""
        self._loop = asyncio.get_event_loop()
        self._start_http_server()

        self._ws_server = await websockets.serve(
            self._on_connect, "127.0.0.1", WS_PORT
        )
        log.info("WebSocket server on ws://127.0.0.1:%d", WS_PORT)
        log.info("HTTP callback on http://127.0.0.1:%d", HTTP_PORT)
        log.info("Waiting for Chrome extension to connect...")

    async def wait_for_extension(self, timeout=90, max_retries=3):
        """Wait until extension connects and sends flow key.

        Phase 1: Wait for WebSocket connection from extension.
        Phase 2: If no token, auto-open/refresh Flow tab and wait for token.
        """
        # Phase 1: Wait for WS connection
        try:
            await asyncio.wait_for(self._wait_for_ws(), 30)
        except asyncio.TimeoutError:
            log.error("Extension didn't connect in 30s")
            log.error("   Make sure Flow Agent extension is installed and enabled in Chrome")
            return False

        # If token already present, we're good
        if self._flow_key:
            return True

        # Phase 2: Extension connected but no token — auto-fix
        log.info("Extension connected but no auth token — auto-fixing...")

        for attempt in range(1, max_retries + 1):
            log.info("Attempt %d/%d: Opening/refreshing Flow tab...", attempt, max_retries)
            await self._request_flow_tab()

            # Wait for token to arrive (token_captured message)
            token_arrived = await self._wait_for_token(20)
            if token_arrived:
                log.info("Token captured after auto-fix!")
                return True

            log.warning("Token not captured yet...")

        log.error("Could not get auth token after %d retries", max_retries)
        log.error("   Make sure you're logged into Google at labs.google/fx/tools/flow")
        return False

    async def _wait_for_ws(self):
        """Wait until a WebSocket connection is established."""
        while not self._ws:
            await asyncio.sleep(0.5)

    async def _wait_for_token(self, timeout):
        """Wait until a valid token is captured."""
        self._connected.clear()
        try:
            await asyncio.wait_for(self._connected.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return self._flow_key is not None

    async def _request_flow_tab(self):
        """Ask extension to open or refresh a Flow tab."""
        if not self._ws:
            return
        try:
            log.info("Requesting extension to open/refresh Flow tab...")
            await self.send_message({"method": "open_flow_tab"})
            # Wait for page to fully load before requesting token refresh
            await asyncio.sleep(8)
            log.info("Requesting token refresh from Flow tab...")
            await self.send_message({"method": "refresh_flow_tab"})
        except Exception as e:
            log.debug("Failed to request flow tab: %s", e)

    async def health_check(self):
        """Quick check if extension is ready with valid token."""
        if not self._ws or not self._flow_key:
            return False
        try:
            req_id = str(uuid.uuid4())
            future = self._loop.create_future()
            self._pending[req_id] = future
            await self.send_message({
                "id": req_id,
                "method": "get_status",
            })
            result = await asyncio.wait_for(future, timeout=5)
            self._pending.pop(req_id, None)
            return result.get("result", {}).get("flowKeyPresent", False)
        except Exception:
            self._pending.pop(req_id, None)
            return False

    async def _on_connect(self, ws):
        self._ws = ws
        log.info("Extension connected!")
        try:
            async for raw in ws:
                data = json.loads(raw)
                await self._handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            log.warning("Extension disconnected")
            self._ws = None
            self._connected.clear()

    async def _handle_message(self, data, instance_id=None):
        msg_type = data.get("type")
        if data.get("projectId"):
            self.record_instance_project_id(instance_id or self.active_instance_id, data.get("projectId"))

        if msg_type == "token_captured":
            first_time = self._flow_key is None
            self.record_instance_token(instance_id or self.active_instance_id, data.get("flowKey"))
            if first_time:
                log.info("Auth token captured")
            else:
                log.debug("Auth token refreshed")
            if instance_id == self.active_instance_id:
                self._connected.set()

        elif msg_type == "extension_ready":
            log.info("Extension ready (flowKey=%s, projectId=%s)", "yes" if data.get("flowKeyPresent") else "no", data.get("projectId") or "auto")
            if instance_id == self.active_instance_id and data.get("flowKeyPresent") and self._flow_key:
                self._connected.set()

        elif msg_type in ("pong", "ping"):
            instance = self._instances.get(instance_id)
            if msg_type == "ping" and instance:
                await self._send_to_ws(instance["ws"], {"type": "pong"})

        else:
            req_id = data.get("id")
            self._route_response(req_id, data)

    def _route_response(self, req_id, data):
        """Route an extension response. Fast path resolves the waiting future;
        if the caller already timed out, hand the response to the orphan
        handler so a late-but-successful generation isn't lost. Delivery is
        idempotent: a redelivered id is acknowledged but not acted on twice."""
        if isinstance(data, dict):
            creds = data.get("remainingCredits")
            if creds is None and isinstance(data.get("data"), dict):
                creds = data["data"].get("remainingCredits")
            if creds is not None:
                self.update_last_credits(creds)
        if not req_id:
            return
        fut = self._pending.get(req_id)
        if fut is not None:
            if not fut.done():
                self._mark_seen(req_id)
                fut.set_result(data)
            return
        # Duplicate of an already-handled response (extension retried after the
        # ack was lost) — acknowledge silently, don't recover it again.
        if req_id in self._seen_ids:
            return
        # No waiting future: caller already gave up. Try to recover it.
        self._mark_seen(req_id)
        meta = self._req_meta.pop(req_id, None)
        if self._orphan_handler is not None:
            handler = self._orphan_handler
            coro = handler(data, meta or {})
            if self._loop is not None:
                asyncio.ensure_future(coro, loop=self._loop)
        else:
            log.warning("Dropped orphan response for %s (no handler)", req_id)

    def handle_http_callback(self, data):
        """Called from HTTP thread when extension sends callback."""
        req_id = data.get("id")
        if req_id:
            # Ack known ids (waiting, recoverable, or already-seen duplicates)
            # so the extension's durable outbox stops retrying. Route it on the
            # loop thread; _route_response dedups and recovers as needed.
            if (req_id in self._pending or req_id in self._req_meta
                    or req_id in self._seen_ids):
                self._loop.call_soon_threadsafe(
                    self._resolve_pending, req_id, data
                )
                return True
        if data.get("type") == "token_captured":
            self._flow_key = data.get("flowKey")
            self._loop.call_soon_threadsafe(self._connected.set)
            return True
        return False

    def _resolve_pending(self, req_id, data):
        self._route_response(req_id, data)

    async def api_request(self, url_path, body, captcha_action="VIDEO_GENERATION", method="POST", timeout=None, meta=None):
        """Send API request through Chrome extension.

        Generation requests (those with a non-empty captcha_action) are rate
        limited: at most MAX_CONCURRENT_REQUESTS in flight and spaced at least
        REQUEST_MIN_INTERVAL seconds apart. Non-generation calls (polling,
        credits — captcha_action="") bypass the limiter so they stay responsive.
        """
        target_ws, _ = self._get_target_ws_with_entry()
        if not target_ws:
            switched = self.switch_to_next_available_instance()
            if switched:
                target_ws, _ = self._get_target_ws_with_entry()
            if not target_ws:
                return {"error": "Extension not connected"}

        # Only throttle credit/captcha-consuming generation calls.
        if captcha_action:
            sem, lock = self._get_rate_limit()
            async with sem:
                await self._space_out_requests(lock)
                return await self._do_api_request(url_path, body, captcha_action, method, timeout, meta)
        return await self._do_api_request(url_path, body, captcha_action, method, timeout, meta)

    async def _space_out_requests(self, lock):
        """Enforce a minimum gap between the starts of consecutive generation
        requests so bursts don't trip Google's UNUSUAL_ACTIVITY throttle."""
        if REQUEST_MIN_INTERVAL <= 0:
            return
        async with lock:
            now = self._loop.time()
            wait = self._last_request_at + REQUEST_MIN_INTERVAL - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = self._loop.time()

    async def _do_api_request(self, url_path, body, captcha_action, method, timeout, meta):
        req_id = str(uuid.uuid4())
        future = self._loop.create_future()
        self._pending[req_id] = future
        self._remember_request(req_id, {
            "captcha_action": captcha_action,
            "url_path": url_path,
            **(meta or {}),
        })

        target_ws, target_entry = self._get_target_ws_with_entry()

        # Auto-fill projectId from target extension instance if missing or set to 'auto'
        if isinstance(body, dict) and "clientContext" in body:
            current_pid = (body["clientContext"].get("projectId") or "").strip()
            if (not current_pid or current_pid == "auto" or current_pid == DEFAULT_PROJECT) and target_entry and target_entry.get("project_id"):
                body = json.loads(json.dumps(body))
                body["clientContext"]["projectId"] = target_entry["project_id"]

        act_pid = (body.get("clientContext", {}).get("projectId") if isinstance(body, dict) else None) or (target_entry.get("project_id") if target_entry else None) or "auto"
        act_name = (target_entry.get("name") if target_entry else None) or "Chrome Extension"
        log.info("🌐 [Flow Project: %s | %s] Sending %s", act_pid, act_name, url_path)

        url = f"{API_BASE}{url_path}?key={API_KEY}"
        ua = random.choice(USER_AGENTS)
        platform = '"macOS"' if "Macintosh" in ua else '"Windows"'

        msg = {
            "id": req_id,
            "method": "api_request",
            "params": {
                "url": url,
                "method": method,
                "headers": {
                    "accept": "*/*",
                    "content-type": "text/plain;charset=UTF-8",
                    "origin": CLIENT_CTX["origin"],
                    "referer": CLIENT_CTX["origin"] + "/",
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": platform,
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "cross-site",
                    "user-agent": ua,
                },
                "body": body,
                "captchaAction": captcha_action,
            },
        }
        if target_ws:
            try:
                if hasattr(target_ws, "send_text"):
                    await target_ws.send_text(json.dumps(msg))
                else:
                    await target_ws.send(json.dumps(msg))
            except Exception as e:
                log.warning("Failed to send message to target ws: %s", e)
        else:
            await self.send_message(msg)

        try:
            result = await asyncio.wait_for(future, timeout=timeout or API_REQUEST_TIMEOUT)
            return result
        except asyncio.TimeoutError:
            return {"error": "TIMEOUT"}
        finally:
            self._pending.pop(req_id, None)

    async def trpc_request(self, url, method="POST", headers=None, body=None, timeout=20):
        if not self._ws:
            return {"error": "Extension not connected"}
        req_id = str(uuid.uuid4())
        future = self._loop.create_future()
        self._pending[req_id] = future
        msg = {
            "id": req_id,
            "method": "trpc_request",
            "params": {"url": url, "method": method, "headers": headers or {}, "body": body},
        }
        target_ws, _ = self._get_target_ws_with_entry()
        try:
            if target_ws:
                await target_ws.send(json.dumps(msg))
            else:
                await self.send_message(msg)
        except Exception as e:
            self._pending.pop(req_id, None)
            return {"error": str(e)}
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": "TIMEOUT"}
        finally:
            self._pending.pop(req_id, None)

    async def create_flow_project(self, title="Affilia Auto"):
        result = await self.trpc_request(
            url="https://labs.google/fx/api/trpc/createProject",
            method="POST",
            body={"title": title},
            timeout=15,
        )
        if result.get("error"):
            return result
        data = result.get("data", {})
        project_id = data.get("result", {}).get("data", {}).get("id") or data.get("id") or data.get("projectId")
        if project_id:
            self.record_instance_project_id(self.active_instance_id, project_id)
            log.info("Auto-created Flow project: %s (id=%s)", title, project_id)
            return {"project_id": project_id}
        return {"error": "Could not extract project ID from response", "raw": data}

    def _start_http_server(self):
        """Start HTTP server for extension callbacks (runs in thread)."""
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == "/api/ext/callback":
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    bridge.handle_http_callback(body)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "ok",
                        "extension_connected": bridge._ws is not None,
                    }).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", HTTP_PORT), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

    async def close(self):
        self._ws_server.close()
        await self._ws_server.wait_closed()
