"""
Helpers for turning the minimal Workfront webhook payload into the richer
internal task brief used by the orchestration pipeline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models import (
    AgeSegment,
    Audience,
    Channel,
    WorkfrontBriefPayload,
    WorkfrontStatus,
    WorkfrontTaskPayload,
)

DAM_PATH = Path("./dam")
ASSETS_JSON = DAM_PATH / "assets_seed.json"
IMAGES_JSON = DAM_PATH / "images_seed.json"


def _load_seed_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in (ASSETS_JSON, IMAGES_JSON):
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                items.extend(json.load(f))
    return items


def _normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _field(item: dict[str, Any], *names: str, default: str = "") -> str:
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return default


def _season_to_occasion(season: str) -> str:
    normalized = season.lower()
    if any(token in normalized for token in ("gift", "holiday", "christmas", "xmas")):
        return "gifting"
    if any(token in normalized for token in ("replen", "retention", "loyal")):
        return "replenishment"
    return "self-care"


def _score_metadata_match(item: dict[str, Any], payload: WorkfrontBriefPayload) -> int:
    score = 0
    product_id = _normalize(payload.product_id)
    product = _normalize(_field(item, "product"))
    item_id = _normalize(_field(item, "id"))
    title = _normalize(_field(item, "title"))

    if product_id == item_id:
        score += 8
    if product_id == product:
        score += 6
    elif product_id and product_id in product:
        score += 4
    elif product and product in product_id:
        score += 3
    if product_id and product_id in title:
        score += 2

    channel = _field(item, "channel")
    if channel == payload.scope.value:
        score += 3
    elif channel == Channel.ALL.value:
        score += 1

    occasion = _field(item, "ritual_occasion", "ritualoccasion")
    if occasion == _season_to_occasion(payload.season):
        score += 2

    if _field(item, "approval_status", "approvalstatus") == "approved":
        score += 1

    return score


def build_task_from_workfront_payload(
    payload: WorkfrontBriefPayload,
) -> WorkfrontTaskPayload:
    """Enrich the minimal Workfront payload using local DAM metadata."""
    seed_items = _load_seed_items()
    best_match = max(
        seed_items,
        key=lambda item: _score_metadata_match(item, payload),
        default={},
    )

    collection = _field(best_match, "collection", default="Brand collection")
    product = _field(best_match, "product", default=payload.product_id)
    occasion = _season_to_occasion(payload.season)
    tone = _field(best_match, "tone", default="luxury")
    market = _field(best_match, "market", default="all")
    language = _field(best_match, "language", default="en")
    audience = _field(best_match, "audience", default=Audience.ALL.value)
    age_segment = _field(best_match, "age_segment", "agesegment", default=AgeSegment.ALL.value)

    return WorkfrontTaskPayload(
        task_id=f"{payload.product_id}-{payload.season}-{payload.scope.value}",
        project_id="workfront",
        status=WorkfrontStatus.CONTENT_GENERATION,
        collection=collection,
        product=product,
        channel=payload.scope,
        audience=Audience(audience) if audience in Audience._value2member_map_ else Audience.ALL,
        age_segment=(
            AgeSegment(age_segment)
            if age_segment in AgeSegment._value2member_map_
            else AgeSegment.ALL
        ),
        market=market,
        language=language,
        objective=f"Create {payload.season} {payload.scope.value} content for {collection} {product}",
        visual_mood=tone,
        ritual_occasion=occasion,
    )
