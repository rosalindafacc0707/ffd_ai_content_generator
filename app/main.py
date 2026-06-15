import logging
from typing import Union

from fastapi import FastAPI, HTTPException, Header

from app.config import settings
from app.models import GenerationResult, SkippedResult, WorkfrontSimplePayload, WorkfrontStatus

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FullForce Content Generation PoC",
    description="AI content pipeline: Workfront → DAM → Firefly → Review",
    version="0.2.0",
)


@app.post("/webhook/workfront", response_model=Union[GenerationResult, SkippedResult])
async def workfront_webhook(
    payload: WorkfrontSimplePayload,
    x_webhook_secret: str = Header(default=None),
):
    """
    Webhook da Adobe Workfront.
    Riceve product_id, season, scope e lancia la pipeline completa.
    """
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if payload.status != WorkfrontStatus.CONTENT_GENERATION:
        return SkippedResult(reason=f"Status '{payload.status.value}' not handled")

    from orchestrator.weave_simulator import run_pipeline
    return await run_pipeline(payload)


@app.post("/generate", response_model=GenerationResult)
async def manual_generate(payload: WorkfrontSimplePayload):
    """Trigger manuale — usato dalla Streamlit UI e per test."""
    from orchestrator.weave_simulator import run_pipeline
    return await run_pipeline(payload)


@app.get("/health")
def health():
    return {"status": "ok", "mode": settings.app_mode}
