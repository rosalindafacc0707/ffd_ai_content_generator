"""
Pydantic models for the FullForce PoC.
Maps the Workfront task payload to the internal orchestration schema.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class WorkfrontStatus(str, Enum):
    CONTENT_GENERATION = "Content Generation"
    REVIEW = "Review"
    APPROVED = "Approved"


class Channel(str, Enum):
    EMAIL = "email"
    SOCIAL = "social"
    LANDING = "landing"
    ALL = "all"


class AgeSegment(str, Enum):
    YOUNG = "young"
    MATURE = "mature"
    FAMILY = "family"
    ALL = "all"


class Audience(str, Enum):
    NEW = "new"
    LOYALTY = "loyalty"
    REACTIVATION = "reactivation"
    ALL = "all"


class WorkfrontTaskPayload(BaseModel):
    """Incoming webhook payload from Adobe Workfront."""
    task_id: str = Field(..., description="Workfront task ID")
    project_id: str
    status: WorkfrontStatus
    collection: str = Field(..., description="e.g. 'The Ritual of Namaste'")
    product: Optional[str] = None
    channel: Channel
    audience: Audience
    age_segment: AgeSegment
    market: str = Field(..., description="e.g. NL, DE, UK, all")
    language: str = Field(default="en")
    objective: str = Field(..., description="Campaign objective free text")
    visual_mood: Optional[str] = None
    ritual_occasion: Optional[str] = None


class SelectedAsset(BaseModel):
    """A copy asset selected from the DAM."""
    id: str
    title: str
    body: str
    score: float
    channel: str
    collection: str
    tone: str


class SelectedImage(BaseModel):
    """An image asset selected from the DAM."""
    id: str
    title: str
    image_url: str
    alt_text: str
    visual_description: str
    placement_hint: str
    score: float


class GenerationRequest(BaseModel):
    """Internal object passed to the orchestrator."""
    task: WorkfrontTaskPayload
    selected_assets: list[SelectedAsset]
    selected_images: list[SelectedImage]
    enriched_prompt: str


class GenerationResult(BaseModel):
    """Result returned to Workfront."""
    task_id: str
    generated_image_url: str
    generated_copy: str
    prompt_used: str
    images_used: list[str]
    assets_used: list[str]
    status: str = "ready_for_review"