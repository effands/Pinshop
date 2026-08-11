"""Omni Flash — Image to Video (I2V) generator + image upload."""

import base64
import logging
import os
import random

from ..config import CLIENT_CTX, ENDPOINTS
from .. import media_store
from .common import build_client_context, build_generation_context

log = logging.getLogger("omniflash.generators.i2v")


def _api_error_message(result: dict) -> str:
    """Extract errors from both extension-level and Google API responses."""
    raw_err = ""
    top_level = result.get("error")
    if top_level:
        raw_err = str(top_level)
    else:
        data = result.get("data")
        if isinstance(data, dict):
            nested = data.get("error")
            if isinstance(nested, dict) and nested.get("message"):
                raw_err = str(nested["message"])
            elif isinstance(nested, str) and nested:
                raw_err = nested
            elif data.get("message"):
                raw_err = str(data["message"])
        elif data:
            raw_err = str(data)

    if not raw_err:
        status = result.get("status", 0)
        return f"HTTP {status} tanpa detail error" if status else "Extension tidak mengembalikan status atau detail error"

    if "Cannot access contents" in raw_err or "Extension manifest must request permission" in raw_err or "FLOW_LOGIN_REQUIRED" in raw_err:
        return (
            "Google Flow belum login di Chrome. Silakan buka tab https://labs.google/fx/tools/flow "
            "di Chrome dan pastikan akun Google sudah posisi Login."
        )

    return raw_err


async def upload_image(bridge, image_path: str, project_id: str = None) -> str | None:
    """Upload a local image to Flow. Returns media_id.

    Auto-saves filename  media_id to media-id.js.
    """
    from ..config import DEFAULT_PROJECT
    project_id = project_id or DEFAULT_PROJECT

    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode()

    body = {
        "clientContext": {"tool": CLIENT_CTX["tool"], "projectId": project_id},
        "imageBytes": img_data,
    }

    log.info("Uploading image: %s", os.path.basename(image_path))
    result = await bridge.api_request(ENDPOINTS["upload_image"], body)

    status = result.get("status", 0)
    data = result.get("data", {})
    if status != 200:
        err = _api_error_message(result)
        err_msg = f"Image upload failed: {err}"
        log.error("%s", err_msg)
        raise ValueError(err_msg)

    media_id = data.get("mediaId") or data.get("name")
    if not media_id and isinstance(data.get("media"), dict):
        media_id = data["media"].get("name")
    log.info("Image uploaded! media_id=%s", media_id)

    return media_id


async def generate_video_i2v(bridge, prompt: str, aspect: str, project_id: str,
                              image_media_id: str, duration: int = 8, count: int = 1,
                              reference_media_ids: list[str] = None) -> list[str] | None:
    """Generate video from a start image (storyboard). Optional reference_media_ids. Returns list of media_ids."""
    model_key = f"abra_t2v_{duration}s"

    requests = []
    for _ in range(count):
        req_item = {
            "aspectRatio": aspect,
            "textInput": {"structuredPrompt": {"parts": [{"text": prompt}]}},
            "videoModelKey": model_key,
            "seed": random.randint(1, 9999),
            "metadata": {},
            "startImage": {"mediaId": image_media_id},
        }
        requests.append(req_item)

    body = {
        "mediaGenerationContext": build_generation_context(),
        "clientContext": build_client_context(project_id),
        "requests": requests,
    }

    log.info('I2V: "%s" [%s] image=%s count=%d', prompt[:50], model_key, image_media_id[:12], count)
    result = await bridge.api_request(ENDPOINTS["generate_i2v"], body)

    status = result.get("status", 0)
    if status != 200:
        err = result.get("data", {})
        reason = ""
        if isinstance(err, dict):
            details = err.get("error", {}).get("details", [])
            for detail in details:
                if isinstance(detail, dict) and "reason" in detail:
                    reason = f" ({detail['reason']})"
                    break
            err = err.get("error", {}).get("message", result.get("error", "Unknown"))
        err_msg = f"{err}{reason}"
        log.error("I2V failed (%s): %s", status, err_msg)
        raise ValueError(err_msg)

    data = result.get("data", {})
    media = data.get("media", [])
    if not media:
        log.error("No media in response")
        return None

    media_ids = [m.get("name") for m in media]
    credits = data.get("remainingCredits", "?")
    if credits != "?" and bridge and hasattr(bridge, "update_last_credits"):
        bridge.update_last_credits(credits)
    log.info("I2V submitted! %d video(s), credits=%s", len(media_ids), credits)
    return media_ids


async def generate_video_fl(bridge, prompt: str, aspect: str, project_id: str,
                             start_image_id: str, end_image_id: str,
                             duration: int = 8) -> list[str] | None:
    """Generate video with First+Last frame control.

    Video transitions smoothly from start_image to end_image.
    """
    model_key = f"abra_t2v_{duration}s"

    request = {
        "aspectRatio": aspect,
        "textInput": {"structuredPrompt": {"parts": [{"text": prompt}]}},
        "videoModelKey": model_key,
        "seed": random.randint(1, 9999),
        "metadata": {},
        "startImage": {"mediaId": start_image_id},
        "endImage": {"mediaId": end_image_id},
    }

    body = {
        "mediaGenerationContext": build_generation_context(),
        "clientContext": build_client_context(project_id),
        "requests": [request],
        "useV2ModelConfig": True,
    }

    log.info('FL: "%s" start=%s end=%s', prompt[:40], start_image_id[:12], end_image_id[:12])
    result = await bridge.api_request(ENDPOINTS["generate_fl"], body)

    status = result.get("status", 0)
    if status != 200:
        err = result.get("data", {})
        reason = ""
        if isinstance(err, dict):
            details = err.get("error", {}).get("details", [])
            for detail in details:
                if isinstance(detail, dict) and "reason" in detail:
                    reason = f" ({detail['reason']})"
                    break
            err = err.get("error", {}).get("message", result.get("error", "Unknown"))
        err_msg = f"{err}{reason}"
        log.error("FL failed (%s): %s", status, err_msg)
        raise ValueError(err_msg)

    data = result.get("data", {})
    media = data.get("media", [])
    if not media:
        log.error("No media in response")
        return None

    media_ids = [m.get("name") for m in media]
    credits = data.get("remainingCredits", "?")
    log.info("FL submitted! %d video(s), credits=%s", len(media_ids), credits)
    return media_ids


async def generate_video_r2v(bridge, prompt: str, aspect: str, project_id: str,
                              ref_media_ids: list[str],
                              duration: int = 8, count: int = 1) -> list[str] | None:
    """Generate video from reference images (character/style consistency)."""
    model_key = f"abra_t2v_{duration}s"

    ref_images = [
        {"mediaId": mid, "imageUsageType": "IMAGE_USAGE_TYPE_ASSET"}
        for mid in ref_media_ids
    ]

    requests = []
    for _ in range(count):
        requests.append({
            "aspectRatio": aspect,
            "textInput": {"structuredPrompt": {"parts": [{"text": prompt}]}},
            "videoModelKey": model_key,
            "seed": random.randint(1, 9999),
            "metadata": {},
            "referenceImages": ref_images,
        })

    body = {
        "mediaGenerationContext": build_generation_context(),
        "clientContext": build_client_context(project_id),
        "requests": requests,
        "useV2ModelConfig": True,
    }

    log.info('R2V: "%s" refs=%d count=%d', prompt[:50], len(ref_media_ids), count)
    result = await bridge.api_request(ENDPOINTS["generate_r2v"], body)

    status = result.get("status", 0)
    if status != 200:
        err = result.get("data", {})
        reason = ""
        if isinstance(err, dict):
            details = err.get("error", {}).get("details", [])
            for detail in details:
                if isinstance(detail, dict) and "reason" in detail:
                    reason = f" ({detail['reason']})"
                    break
            err = err.get("error", {}).get("message", result.get("error", "Unknown"))
        err_msg = f"{err}{reason}"
        log.error("R2V failed (%s): %s", status, err_msg)
        raise ValueError(err_msg)

    data = result.get("data", {})
    media = data.get("media", [])
    if not media:
        log.error("No media in response")
        return None

    media_ids = [m.get("name") for m in media]
    credits = data.get("remainingCredits", "?")
    log.info("R2V submitted! %d video(s), credits=%s", len(media_ids), credits)
    return media_ids
