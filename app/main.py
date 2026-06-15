from fastapi import FastAPI, HTTPException, Header
from app.models import WorkfrontSimplePayload, WorkfrontStatus, GenerationResult
from app.config import settings
import logging

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FullForce Content Generation PoC",
    description="AI content pipeline: Workfront → DAM → Firefly → Review",
    version="0.2.0",
)


@app.post("/webhook/workfront", response_model=GenerationResult)
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
        return {"skipped": True, "reason": f"Status '{payload.status}' not handled"}

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