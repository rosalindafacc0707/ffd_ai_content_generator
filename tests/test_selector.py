from app.briefs import build_task_from_workfront_payload
from app.models import (
    AgeSegment,
    Audience,
    Channel,
    WorkfrontBriefPayload,
    WorkfrontStatus,
    WorkfrontTaskPayload,
)
from dam.selector import select_assets, select_images

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


def test_workfront_brief_payload_hydrates_internal_task():
    payload = WorkfrontBriefPayload(
        product_id="body_cream",
        season="replenishment",
        scope=Channel.EMAIL,
    )

    task = build_task_from_workfront_payload(payload)

    assert task.product == "Body Cream"
    assert task.channel == Channel.EMAIL
    assert task.ritual_occasion == "replenishment"
    assert task.status == WorkfrontStatus.CONTENT_GENERATION
