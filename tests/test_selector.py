import pytest

from app.models import Scope, Season, WorkfrontSimplePayload, WorkfrontStatus
from dam.selector import resolve_brief
import os
os.environ["APP_MODE"] = "demo"

def _payload(
    product_id: str = "PROD_001",
    season: Season = Season.SPRING,
    scope: Scope = Scope.EMAIL,
) -> WorkfrontSimplePayload:
    return WorkfrontSimplePayload(
        task_id="test-001",
        project_id="proj-test",
        status=WorkfrontStatus.CONTENT_GENERATION,
        product_id=product_id,
        season=season,
        scope=scope,
    )


def test_resolve_brief_returns_matching_product():
    brief = resolve_brief(_payload(product_id="PROD_001"))

    assert brief.product.product_id == "PROD_001"
    assert brief.product.name == "Namaste Body Cream"
    assert brief.task_id == "test-001"


def test_resolve_brief_scores_season_and_scope():
    brief = resolve_brief(_payload(product_id="PROD_004", season=Season.WINTER, scope=Scope.LANDING))

    assert brief.background.season == "winter"
    assert "landing" in brief.background.scope or "all" in brief.background.scope


def test_resolve_brief_raises_for_unknown_product():
    with pytest.raises(ValueError, match="Product 'UNKNOWN' not found"):
        resolve_brief(_payload(product_id="UNKNOWN"))
