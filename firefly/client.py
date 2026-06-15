"""
Adobe Firefly API Client.

In APP_MODE=demo: restituisce un'immagine placeholder (picsum.photos)
senza fare nessuna chiamata reale. Permette di sviluppare e testare
l'intera pipeline senza API key.

In APP_MODE=live: chiama la Firefly Generate Images v3 API con
autenticazione IMS Bearer token.

Documentazione: https://developer.adobe.com/firefly-services/docs/firefly-api/
"""
from __future__ import annotations
import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FIREFLY_BASE = os.getenv("ç", "https://firefly-api.adobe.io")



async def _get_ims_token() -> str:
    """
    Retrieves a short-lived IMS access token using client credentials.
    In production, this should be cached and refreshed before expiry.
    """
    client_id = os.getenv("ADOBE_FIREFLY_CLIENT_ID", "")
    client_secret = os.getenv("ADOBE_FIREFLY_API_KEY", "")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://ims-na1.adobelogin.com/ims/token/v3",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "openid,AdobeID,firefly_enterprise,firefly_api",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def generate_image_firefly(
    prompt: str,
    reference_image_url: Optional[str] = None,
    width: int = 1792,
    height: int = 1024,
    num_variations: int = 1,
) -> str:
    """
    Generates an image via Adobe Firefly and returns the presigned URL.

    Args:
        prompt: Structured text prompt for image generation
        reference_image_url: Optional DAM image URL used as visual reference
        width: Output image width in pixels
        height: Output image height in pixels
        num_variations: Number of image variants to generate (returns first)

    Returns:
        URL of the generated image (presigned in live mode, picsum in demo)
    """
    app_mode = os.getenv("APP_MODE", "demo")

    # ── DEMO MODE ────────────────────────────────────────────────────────────
    if app_mode == "demo":
        seed = prompt[:30].replace(" ", "-").lower()
        demo_url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
        logger.info(f"[FireflyClient][DEMO] Returning placeholder: {demo_url}")
        return demo_url

    # ── LIVE MODE ────────────────────────────────────────────────────────────
    # Use pre-set token if available, otherwise fetch a new one
    token = os.getenv("ADOBE_IMS_TOKEN") or await _get_ims_token()
    client_id = os.getenv("ADOBE_FIREFLY_CLIENT_ID", "")

    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": client_id,
        "Content-Type": "application/json",
    }

    body: dict = {
        "prompt": prompt,
        "negativePrompt": (
            "text, watermark, logo, low quality, blurry, "
            "distorted, oversaturated, cluttered"
        ),
        "size": {"width": width, "height": height},
        "numVariations": num_variations,
        "contentClass": "photo",
        "photoSettings": {
            "aperture": 4.0,
            "shutterSpeed": 0.005,
            "fieldOfView": 35,
        },
    }

    # Add reference image if provided (Image-to-Image / style transfer)
    if reference_image_url:
        body["referenceImage"] = {
            "source": {"url": reference_image_url},
            "strength": 40,  # 0-100: how much to blend reference
        }

    async with httpx.AsyncClient(timeout=90) as client:
        logger.info(
            f"[FireflyClient] Calling Firefly API — prompt length: {len(prompt)}"
        )
        resp = await client.post(
            f"{FIREFLY_BASE}/v3/images/generate",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    presigned_url: str = data["outputs"][0]["image"]["presignedUrl"]
    logger.info(f"[FireflyClient] Image generated: {presigned_url[:80]}...")
    return presigned_url