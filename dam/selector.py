"""
DAM Selector v2 — selezione basata su product_id, season, scope.

Flusso:
  1. Carica catalog.json
  2. Lookup prodotto per product_id (hard match, errore se non trovato)
  3. Scoring sfondi: season match + scope match + mood compatibility con tone prodotto
  4. Ritorna prodotto + sfondo migliore + path assoluti delle immagini locali
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional

from app.models import (
    DAMCatalog, ProductEntry, BackgroundEntry,
    ResolvedBrief, WorkfrontSimplePayload, Season, Scope
)

DAM_PATH      = Path(os.getenv("DAM_LOCAL_PATH", "./dam"))
CATALOG_PATH  = DAM_PATH / "catalog.json"
PRODUCTS_DIR  = DAM_PATH / "products"
BACKGROUNDS_DIR = DAM_PATH / "backgrounds"


def _load_catalog() -> DAMCatalog:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return DAMCatalog(**data)


def _get_product(catalog: DAMCatalog, product_id: str) -> ProductEntry:
    for p in catalog.products:
        if p.product_id == product_id:
            return p
    raise ValueError(
        f"Product '{product_id}' not found in DAM catalog. "
        f"Available: {[p.product_id for p in catalog.products]}"
    )


# Compatibilità mood-tone: quale mood di sfondo funziona meglio per ogni tone prodotto
TONE_MOOD_AFFINITY: dict[str, list[str]] = {
    "luxury":      ["neutral", "calm", "dark"],
    "warm":        ["bright", "vibrant", "calm"],
    "energetic":   ["vibrant", "bright"],
    "informative": ["neutral", "calm", "bright"],
}


def _score_background(
    bg: BackgroundEntry,
    season: Season,
    scope: Scope,
    product_tone: str,
) -> float:
    score = 0.0

    # Season match (più importante)
    if bg.season == season.value:
        score += 5
    elif bg.season == "evergreen":
        score += 2

    # Scope match
    if scope.value in bg.scope or "all" in bg.scope:
        score += 3

    # Mood / tone affinity
    preferred_moods = TONE_MOOD_AFFINITY.get(product_tone, ["neutral"])
    if bg.mood in preferred_moods:
        score += 2

    return score


def resolve_brief(
    payload: WorkfrontSimplePayload,
    catalog_path: Optional[Path] = None,
) -> ResolvedBrief:
    """
    Risolve un payload semplice Workfront in un brief completo
    con prodotto + sfondo selezionati dal DAM locale.
    """
    cat_path = catalog_path or CATALOG_PATH
    catalog = _load_catalog() if catalog_path is None else DAMCatalog(
        **json.loads(cat_path.read_text())
    )

    # 1. Lookup prodotto
    product = _get_product(catalog, payload.product_id)

    # 2. Scoring sfondi
    scored = []
    for bg in catalog.backgrounds:
        s = _score_background(bg, payload.season, payload.scope, product.tone)
        scored.append((s, bg))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        raise ValueError("No backgrounds found in DAM catalog.")

    best_bg = scored[0][1]

    # 3. Percorsi assoluti immagini locali
    product_path = str(PRODUCTS_DIR / product.image_file)
    bg_path      = str(BACKGROUNDS_DIR / best_bg.image_file)

    return ResolvedBrief(
        task_id=payload.task_id,
        product=product,
        background=best_bg,
        season=payload.season,
        scope=payload.scope,
        product_image_path=product_path,
        background_image_path=bg_path,
    )