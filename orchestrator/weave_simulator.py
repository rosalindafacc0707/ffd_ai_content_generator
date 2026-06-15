"""
WeaveSimulator — il cuore del PoC, sostituisce Figma Weave nel backend.

Questo modulo è progettato come un layer MODULARE e SOSTITUIBILE:
quando Figma rilascerà le API di Weave, basterà sostituire questo file
con un adapter verso Weave senza toccare nulla del resto del flusso.

Pipeline:
  1. Riceve WorkfrontTaskPayload dal webhook
  2. Seleziona copy asset e immagini dal DAM locale (scoring multi-dimensionale)
  3. Costruisce il prompt arricchito per Adobe Firefly
  4. [Opzionale] Arricchisce il prompt via LLM (OpenAI)
  5. Chiama Adobe Firefly per la generazione immagine
  6. Genera il copy testuale
  7. Carica il risultato su Workfront → stato "Review"
"""
from __future__ import annotations
import logging

from app.models import (
    WorkfrontTaskPayload,
    GenerationResult,
)
from dam.selector import select_assets, select_images
from prompts.builder import build_firefly_prompt, enrich_prompt_with_llm
from firefly.client import generate_image_firefly
from workfront_mock.client import upload_result_to_workfront

logger = logging.getLogger(__name__)


async def run_pipeline(task: WorkfrontTaskPayload) -> GenerationResult:
    logger.info(f"[WeaveSimulator] Starting pipeline — task_id={task.task_id}")

    # ── Step 1: DAM Selection ────────────────────────────────────────────────
    assets = select_assets(task, top_k=5)
    images = select_images(task, top_k=3)
    logger.info(
        f"[WeaveSimulator] DAM → {len(assets)} copy assets, "
        f"{len(images)} images selected"
    )

    if not assets:
        logger.warning(
            "[WeaveSimulator] No approved copy assets found — "
            "using objective as fallback copy"
        )
    if not images:
        logger.warning(
            "[WeaveSimulator] No approved images found — "
            "Firefly will use prompt only"
        )

    # ── Step 2: Prompt Construction ──────────────────────────────────────────
    base_prompt = build_firefly_prompt(task, images, assets)
    final_prompt = enrich_prompt_with_llm(base_prompt, model="gpt-4o")
    logger.info(f"[WeaveSimulator] Prompt ready — {len(final_prompt)} chars")

    # ── Step 3: Image Generation via Adobe Firefly ───────────────────────────
    reference_url = images[0].image_url if images else None
    generated_image_url = await generate_image_firefly(
        prompt=final_prompt,
        reference_image_url=reference_url,
    )
    logger.info(f"[WeaveSimulator] Image generated → {generated_image_url}")

    # ── Step 4: Copy Generation ───────────────────────────────────────────────
    # Uses top-scored copy fragment as base.
    # In a future sprint this can be replaced with full LLM-generated copy
    # using the channel prompt templates (email.txt, social.txt, etc.)
    generated_copy = assets[0].body if assets else task.objective

    # ── Step 5: Assemble Result ───────────────────────────────────────────────
    result = GenerationResult(
        task_id=task.task_id,
        generated_image_url=generated_image_url,
        generated_copy=generated_copy,
        prompt_used=final_prompt,
        images_used=[img.id for img in images],
        assets_used=[a.id for a in assets],
        status="ready_for_review",
    )

    # ── Step 6: Upload to Workfront + set status → Review ────────────────────
    await upload_result_to_workfront(task, result)
    logger.info(f"[WeaveSimulator] Pipeline complete — task_id={task.task_id}")

    return result