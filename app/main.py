from fastapi import FastAPI, HTTPException, Header
from app.models import WorkfrontTaskPayload, WorkfrontStatus, GenerationResult
from app.config import settings
import logging

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FullForce Content Generation PoC",
    description="AI-powered content generation layer inside the Adobe Workfront content value chain",
    version="0.1.0",
)


@app.post("/webhook/workfront", response_model=GenerationResult)
async def workfront_webhook(
    payload: WorkfrontTaskPayload,
    x_webhook_secret: str = Header(default=None),
):
    """
    Receives webhook from Adobe Workfront when a task enters 'Content Generation' status.
    Runs the full orchestration pipeline and returns the generation result.
    """
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if payload.status != WorkfrontStatus.CONTENT_GENERATION:
        return {"skipped": True, "reason": f"Status '{payload.status}' not handled"}

    from orchestrator.weave_simulator import run_pipeline
    result: GenerationResult = await run_pipeline(payload)
    logger.info(f"Pipeline complete for task {payload.task_id}")
    return result


@app.post("/generate", response_model=GenerationResult)
async def manual_generate(payload: WorkfrontTaskPayload):
    """
    Manual trigger for testing without Workfront webhook.
    Used by the Streamlit UI and for Sprint 1/2 development.
    """
    from orchestrator.weave_simulator import run_pipeline
    result: GenerationResult = await run_pipeline(payload)
    return result


@app.get("/health")
def health():
    return {"status": "ok", "mode": settings.app_mode}