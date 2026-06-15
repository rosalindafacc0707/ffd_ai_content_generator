"""
DAM Asset Selector — riutilizzato e adattato dal progetto Rituals.

Logica di scoring multi-dimensionale per selezionare i copy asset e le immagini
più adeguate a partire dai metadati del brief Workfront.

Scoring weights (tunable):
  - exact match on channel/audience/market/age_segment: +3 each
  - 'all' wildcard match: +1 each
  - performancetag high: +2, medium: +1
  - approvalstatus approved: required (hard filter)
  - collection match: +2
  - ritual_occasion match: +1
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional

from app.models import (
    AgeSegment, Audience, Channel,
    SelectedAsset, SelectedImage, WorkfrontTaskPayload
)

DAM_PATH = Path(os.getenv("DAM_LOCAL_PATH", "./dam"))
ASSETS_JSON = DAM_PATH / "assets_seed.json"
IMAGES_JSON = DAM_PATH / "images_seed.json"


def _load_json(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _score_asset(asset: dict, task: WorkfrontTaskPayload) -> float:
    """Score a copy asset against the task brief."""
    # Hard filter: only approved assets
    if asset.get("approvalstatus") != "approved":
        return -1.0

    score = 0.0

    # Channel match
    a_channel = asset.get("channel", "")
    if a_channel == task.channel.value:
        score += 3
    elif a_channel == "all":
        score += 1

    # Audience match
    a_audience = asset.get("audience", "")
    if a_audience == task.audience.value:
        score += 3
    elif a_audience == "all":
        score += 1

    # Market match
    a_market = asset.get("market", "")
    if a_market.lower() == task.market.lower():
        score += 3
    elif a_market == "all":
        score += 1

    # Collection match
    if task.collection.lower() in asset.get("collection", "").lower():
        score += 2

    # Ritual occasion
    if task.ritual_occasion and asset.get("ritualoccasion", "") == task.ritual_occasion:
        score += 1

    # Performance boost
    perf = asset.get("performancetag", "")
    if perf == "high":
        score += 2
    elif perf == "medium":
        score += 1

    return score


def _score_image(image: dict, task: WorkfrontTaskPayload) -> float:
    """Score an image asset against the task brief — ported from Rituals selector."""
    if image.get("approvalstatus") != "approved":
        return -1.0

    score = 0.0

    # Channel match
    i_channel = image.get("channel", "")
    if i_channel == task.channel.value:
        score += 3
    elif i_channel == "all":
        score += 1

    # Age segment match (key differentiator for images)
    i_age = image.get("agesegment", "")
    if i_age == task.age_segment.value:
        score += 4   # images are strongly age-targeted
    elif i_age == "all":
        score += 1

    # Audience match
    i_audience = image.get("audience", "")
    if i_audience == task.audience.value:
        score += 2
    elif i_audience == "all":
        score += 1

    # Market match
    i_market = image.get("market", "")
    if i_market.lower() == task.market.lower():
        score += 2
    elif i_market == "all":
        score += 1

    # Collection match
    if task.collection.lower() in image.get("collection", "").lower():
        score += 2

    # Visual mood match (tone)
    if task.visual_mood and image.get("tone", "") == task.visual_mood:
        score += 2

    # Performance boost
    perf = image.get("performancetag", "")
    if perf == "high":
        score += 2
    elif perf == "medium":
        score += 1

    # Placement hint for channel coherence
    placement = image.get("placementhint", "")
    channel_placement_map = {
        "email": "hero",
        "landing": "hero",
        "social": "social-feed",
    }
    if task.channel.value in channel_placement_map:
        if channel_placement_map[task.channel.value] in placement:
            score += 1

    return score


def select_assets(
    task: WorkfrontTaskPayload,
    top_k: int = 5,
    assets_path: Optional[Path] = None,
) -> list[SelectedAsset]:
    """Return top-k copy assets ranked by score."""
    path = assets_path or ASSETS_JSON
    raw = _load_json(path)
    scored = []
    for item in raw:
        s = _score_asset(item, task)
        if s >= 0:
            scored.append((s, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    result = []
    for score, item in scored[:top_k]:
        result.append(SelectedAsset(
            id=item["id"],
            title=item["title"],
            body=item["body"],
            score=score,
            channel=item.get("channel", ""),
            collection=item.get("collection", ""),
            tone=item.get("tone", ""),
        ))
    return result


def select_images(
    task: WorkfrontTaskPayload,
    top_k: int = 3,
    images_path: Optional[Path] = None,
) -> list[SelectedImage]:
    """Return top-k images ranked by score."""
    path = images_path or IMAGES_JSON
    raw = _load_json(path)
    scored = []
    for item in raw:
        s = _score_image(item, task)
        if s >= 0:
            scored.append((s, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    result = []
    for score, item in scored[:top_k]:
        result.append(SelectedImage(
            id=item["id"],
            title=item["title"],
            image_url=item.get("imageurl", ""),
            alt_text=item.get("alttext", ""),
            visual_description=item.get("visualdescription", ""),
            placement_hint=item.get("placementhint", ""),
            score=score,
        ))
    return result