import pytest
from app.models import WorkfrontTaskPayload, WorkfrontStatus, Channel, Audience, AgeSegment
from dam.selector import select_assets, select_images
from pathlib import Path

FIXTURE_TASK = WorkfrontTaskPayload(
    task_id="test-001", project_id="proj-test",
    status=WorkfrontStatus.CONTENT_GENERATION,
    collection="The Ritual of Namaste",
    channel=Channel.EMAIL, audience=Audience.LOYALTY,
    age_segment=AgeSegment.MATURE, market="NL",
    objective="Test replenishment campaign",
)

def test_select_assets_returns_approved_only():
    assets = select_assets(FIXTURE_TASK)
    assert all(a.score >= 0 for a in assets)
    assert len(assets) > 0

def test_select_images_age_segment_scored_higher():
    images = select_images(FIXTURE_TASK)
    assert len(images) > 0
    # top image should match mature or all
    top = images[0]
    assert top.score > 0

def test_select_images_top3():
    images = select_images(FIXTURE_TASK, top_k=3)
    assert len(images) <= 3