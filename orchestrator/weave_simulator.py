"""
WeaveSimulator v3 — usa l'AgenticOrchestrator.
"""
from __future__ import annotations
import logging

from app.models import WorkfrontSimplePayload, GenerationResult
from orchestrator.agent import run_agentic_pipeline
from workfront_mock.client import upload_result_to_workfront

logger = logging.getLogger(__name__)


async def run_pipeline(payload: WorkfrontSimplePayload) -> GenerationResult:
    logger.info(
        f"[WeaveSimulator] Start — task={payload.task_id} "
        f"product={payload.product_id} season={payload.season} scope={payload.scope}"
    )

    # Agentic pipeline (sync dentro async — OK per PoC)
    agent_result = run_agentic_pipeline(payload)

    out_path = agent_result["output_path"]
    from pathlib import Path
    image_uri = Path(out_path).as_uri()

    result = GenerationResult(
        task_id=payload.task_id,
        generated_image_url=image_uri,
        generated_copy=agent_result.get("reasoning", ""),
        prompt_used=agent_result.get("prompt_used", ""),
        product_id=agent_result["product_id"],
        background_id=agent_result["background_id"],
        season=payload.season.value,
        scope=payload.scope.value,
        status="ready_for_review",
    )

    await upload_result_to_workfront(payload, result)
    logger.info(f"[WeaveSimulator] Done — task={payload.task_id} → {out_path}")
    return result