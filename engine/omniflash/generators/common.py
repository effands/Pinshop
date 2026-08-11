"""Omni Flash — Common utilities for all generators.

Shared functions: client context builder, poll_status, download_video.
"""

import asyncio
import base64
import logging
import os
import random
import time
import uuid

from ..config import (
    CLIENT_CTX, ENDPOINTS, POLL_INTERVAL, POLL_TIMEOUT,
)

log = logging.getLogger("omniflash.generators")


def build_client_context(project_id: str) -> dict:
    """Build the clientContext dict used by all API requests."""
    return {
        "projectId": project_id,
        "tool": CLIENT_CTX["tool"],
        "userPaygateTier": CLIENT_CTX["tier"],
        "sessionId": f";{int(time.time() * 1000)}",
        "recaptchaContext": {
            "applicationType": CLIENT_CTX["recaptcha_app_type"],
            "token": "",
        },
    }


def build_generation_context(audio_pref: str = None) -> dict:
    """Build the mediaGenerationContext dict."""
    ctx = {"batchId": str(uuid.uuid4())}
    if audio_pref:
        ctx["audioFailurePreference"] = audio_pref
    return ctx


async def poll_status(
    bridge, media_id: str, project_id: str, progress_label: str = ""
) -> bool:
    """Poll until video is ready. Returns True on success."""
    body = {"media": [{"name": media_id, "projectId": project_id}]}
    start = time.time()
    prefix = f"{progress_label.strip()} " if progress_label.strip() else ""

    while time.time() - start < POLL_TIMEOUT:
        result = await bridge.api_request(ENDPOINTS["poll_status"], body, captcha_action="")
        data = result.get("data", {})
        media = data.get("media", [])
        raw_pct = None

        if media:
            media_obj = media[0]
            meta = media_obj.get("mediaMetadata", {}).get("mediaStatus", {})
            status = meta.get("mediaGenerationStatus", "")

            if status == "MEDIA_GENERATION_STATUS_SUCCESSFUL":
                elapsed = int(time.time() - start)
                log.info("%sRender selesai 100%% (%ds)", prefix, elapsed)
                return True
            elif "FAILED" in status or "BLOCKED" in status:
                log.error("%sRender gagal: %s", prefix, status)
                raise ValueError(f"MEDIA_GENERATION_STATUS_FAILED: {status}")

            raw_pct = (
                meta.get("percentComplete")
                or meta.get("progressPercent")
                or meta.get("progress")
                or media_obj.get("progress")
                or media_obj.get("percentComplete")
            )

        elapsed = int(time.time() - start)
        if raw_pct is not None:
            try:
                pct = int(raw_pct)
            except (ValueError, TypeError):
                pct = min(95, max(5, int((elapsed / 45.0) * 100)))
        else:
            pct = min(95, max(5, int((elapsed / 45.0) * 100)))

        log.info("%sRender berjalan %d%% (%ds)", prefix, pct, elapsed)
        await asyncio.sleep(POLL_INTERVAL)

    log.error("%sRender timeout setelah %ds", prefix, POLL_TIMEOUT)
    return False


async def download_video(bridge, media_id: str, output_path: str) -> bool:
    """Download video via get_media API."""
    url_path = ENDPOINTS["get_media"].format(media_id=media_id)
    result = await bridge.api_request(url_path, {}, captcha_action="", method="GET")
    data = result.get("data", result)

    video_b64 = ""
    if isinstance(data, dict):
        v = data.get("video", {})
        if isinstance(v, dict):
            video_b64 = v.get("encodedVideo", "")
        elif isinstance(v, str):
            video_b64 = v

    if not video_b64:
        log.error("No video data in response")
        return False

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    video_bytes = base64.b64decode(video_b64)
    with open(output_path, "wb") as f:
        f.write(video_bytes)

    size_mb = len(video_bytes) / (1024 * 1024)
    log.info("Saved: %s (%.1f MB)", output_path, size_mb)
    return True
