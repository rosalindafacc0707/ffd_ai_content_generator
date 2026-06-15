"""
Image Generation Client v3

Modalità (APP_MODE in .env):
  demo  → placeholder picsum.photos, nessuna dipendenza
  sd    → AUTOMATIC1111 locale su SD_API_URL (default http://localhost:7860)
  live  → Adobe Firefly API reale
"""
from __future__ import annotations
import os
import base64
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FIREFLY_BASE = "https://firefly-api.adobe.io"

# Cartella dove salvare le immagini generate localmente
OUTPUT_DIR = Path(os.getenv("DAM_LOCAL_PATH", "./dam")) / "generated"


def _ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


async def generate_image_firefly(
    prompt: str,
    reference_image_url: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
) -> str:
    app_mode = os.getenv("APP_MODE", "demo")

    if app_mode == "demo":
        return await _demo_mode(prompt, width, height)
    elif app_mode == "sd":
        return await _sd_mode(prompt, width, height)
    else:
        return await _firefly_mode(prompt, reference_image_url, width, height)


# ── DEMO MODE ─────────────────────────────────────────────────────────────────

async def _demo_mode(prompt: str, width: int, height: int) -> str:
    seed = prompt[:40].replace(" ", "-").lower()
    url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
    logger.info(f"[ImageClient][DEMO] → {url}")
    return url


# ── STABLE DIFFUSION MODE (AUTOMATIC1111 locale) ──────────────────────────────

async def _sd_mode(prompt: str, width: int, height: int) -> str:
    sd_url = os.getenv("SD_API_URL", "http://localhost:7860")
    endpoint = f"{sd_url}/sdapi/v1/txt2img"

    payload = {
        "prompt": prompt,
        "negative_prompt": (
            "text, watermark, logo, signature, low quality, blurry, "
            "distorted, oversaturated, ugly, bad anatomy, worst quality"
        ),
        "width": width,
        "height": height,
        "steps": 28,
        "cfg_scale": 7.5,
        "sampler_name": "DPM++ 2M Karras",
        "batch_size": 1,
        "n_iter": 1,
        "seed": -1,
    }

    logger.info(f"[ImageClient][SD] Calling {endpoint}")
    logger.info(f"[ImageClient][SD] Prompt: {prompt[:100]}...")

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(endpoint, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # AUTOMATIC1111 restituisce l'immagine come base64
    image_b64 = data["images"][0]
    image_bytes = base64.b64decode(image_b64)

    # Salva l'immagine localmente nel DAM
    out_dir = _ensure_output_dir()
    timestamp = int(time.time())
    filename = f"generated_{timestamp}.png"
    filepath = out_dir / filename
    filepath.write_bytes(image_bytes)

    logger.info(f"[ImageClient][SD] Image saved → {filepath}")

    # Restituisce path locale come URL file://
    return filepath.as_uri()


# ── ADOBE FIREFLY MODE (live) ─────────────────────────────────────────────────

async def _firefly_mode(
    prompt: str,
    reference_image_url: Optional[str],
    width: int,
    height: int,
) -> str:
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