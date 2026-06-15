"""
Adobe Firefly API Client v2
"""
from __future__ import annotations
import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)
FIREFLY_BASE = "https://firefly-api.adobe.io"


async def generate_image_firefly(
    prompt: str,
    reference_image_url: Optional[str] = None,
    width: int = 1792,
    height: int = 1024,
) -> str:
    app_mode = os.getenv("APP_MODE", "demo")

    if app_mode == "demo":
        seed = prompt[:40].replace(" ", "-").lower()
        url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
        logger.info(f"[FireflyClient][DEMO] → {url}")
        return url

    token = os.getenv("ADOBE_IMS_TOKEN") or await _get_ims_token()
    client_id = os.getenv("ADOBE_FIREFLY_CLIENT_ID", "")
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": client_id,
        "Content-Type": "application/json",
    }
    body: dict = {
        "prompt": prompt,
        "negativePrompt": "text, watermark, logo, blurry, distorted",
        "size": {"width": width, "height": height},
        "numVariations": 1,
        "contentClass": "photo",
    }
    if reference_image_url and reference_image_url.startswith("http"):
        body["referenceImage"] = {
            "source": {"url": reference_image_url},
            "strength": 40,
        }

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{FIREFLY_BASE}/v3/images/generate",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()

    return resp.json()["outputs"][0]["image"]["presignedUrl"]


async def _get_ims_token() -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://ims-na1.adobelogin.com/ims/token/v3",
            data={
                "grant_type": "client_credentials",
                "client_id": os.getenv("ADOBE_FIREFLY_CLIENT_ID", ""),
                "client_secret": os.getenv("ADOBE_FIREFLY_API_KEY", ""),
                "scope": "openid,AdobeID,firefly_enterprise,firefly_api",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]