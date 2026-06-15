"""
WeaveSimulator v2
"""
from __future__ import annotations
import logging

from app.models import WorkfrontSimplePayload, GenerationResult
from dam.selector import resolve_brief
from prompts.builder import build_firefly_prompt_v2, enrich_prompt_with_llm
from firefly.client import generate_image_firefly
from workfront_mock.client import upload_result_to_workfront

logger = logging.getLogger(__name__)


async def run_pipeline(payload: WorkfrontSimplePayload) -> GenerationResult:
    logger.info(
        f"[WeaveSimulator] Start — task={payload.task_id} "
        f"product={payload.product_id} season={payload.season} scope={payload.scope}"
    )

    # Step 1: Risolvi brief dal DAM
    brief = resolve_brief(payload)
    logger.info(
        f"[WeaveSimulator] Brief resolved — "
        f"product='{brief.product.name}' bg='{brief.background.name}'"
    )

    # Step 2: Prompt
    base_prompt = build_firefly_prompt_v2(brief)
    final_prompt = enrich_prompt_with_llm(base_prompt)

    # Step 3: Genera immagine
    generated_image_url = await generate_image_firefly(prompt=final_prompt)
    logger.info(f"[WeaveSimulator] Image → {generated_image_url}")

    # Step 4: Copy dal catalogo
    generated_copy = brief.product.description

    # Step 5: Risultato
    result = GenerationResult(
        task_id=payload.task_id,
        generated_image_url=generated_image_url,
        generated_copy=generated_copy,
        prompt_used=final_prompt,
        product_id=brief.product.product_id,
        background_id=brief.background.background_id,
        season=payload.season.value,
        scope=payload.scope.value,
        status="ready_for_review",
    )

    # Step 6: Upload Workfront
    await upload_result_to_workfront(payload, result)
    logger.info(f"[WeaveSimulator] Done — task={payload.task_id}")
    return result