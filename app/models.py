"""
Pydantic models for the FullForce PoC.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class WorkfrontStatus(str, Enum):
    CONTENT_GENERATION = "Content Generation"
    REVIEW = "Review"
    APPROVED = "Approved"


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    EVERGREEN = "evergreen"


class Scope(str, Enum):
    EMAIL = "email"
    SOCIAL = "social"
    LANDING = "landing"
    ALL = "all"


# ── Incoming Workfront payload (simplified) ───────────────────────────────────

class WorkfrontSimplePayload(BaseModel):
    """
    Simplified webhook payload from Adobe Workfront.
    Workfront sends only product_id, season and scope —
    everything else is resolved internally from the DAM catalog.
    """
    task_id: str = Field(..., description="Workfront task ID")
    project_id: str
    status: WorkfrontStatus
    product_id: str = Field(..., description="e.g. 'PROD_001' — looked up in DAM catalog")
    season: Season = Field(..., description="Campaign season")
    scope: Scope = Field(..., description="Output channel / scope")


# ── DAM catalog models ────────────────────────────────────────────────────────

class ProductEntry(BaseModel):
    """One product entry in dam/catalog.json"""
    product_id: str
    name: str
    collection: str
    category: str                        # e.g. body, face, home
    tone: str                            # luxury | warm | energetic | informative
    seasons: list[str]                   # seasons this product is active in
    image_file: str                      # filename inside dam/products/
    description: str


class BackgroundEntry(BaseModel):
    """One background entry in dam/catalog.json"""
    background_id: str
    name: str
    season: str                          # spring | summer | autumn | winter | evergreen
    mood: str                            # calm | vibrant | dark | bright | neutral
    scope: list[str]                     # which scopes/channels it works for
    image_file: str                      # filename inside dam/backgrounds/


class DAMCatalog(BaseModel):
    products: list[ProductEntry]
    backgrounds: list[BackgroundEntry]


# ── Internal orchestration models ─────────────────────────────────────────────

class ResolvedBrief(BaseModel):
    """
    Full brief assembled by the orchestrator from the simple Workfront payload
    + DAM catalog lookup. This is what gets passed to the prompt builder.
    """
    task_id: str
    product: ProductEntry
    background: BackgroundEntry
    season: Season
    scope: Scope
    product_image_path: str              # absolute local path
    background_image_path: str          # absolute local path


class GenerationResult(BaseModel):
    """Result returned to Workfront after generation."""
    task_id: str
    generated_image_url: str
    generated_copy: str
    prompt_used: str
    product_id: str
    background_id: str
    season: str
    scope: str
    status: str = "ready_for_review"