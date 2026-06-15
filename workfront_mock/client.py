"""
Workfront Mock Client v2
"""
from __future__ import annotations
import os
import logging

import httpx

from app.models import WorkfrontSimplePayload, GenerationResult

logger = logging.getLogger(__name__)

WORKFRONT_BASE = os.getenv("WORKFRONT_BASE_URL", "")
API_KEY = os.getenv("WORKFRONT_API_KEY", "")
STATUS_REVIEW = "INP"


async def upload_result_to_workfront(
    task: WorkfrontSimplePayload,
    result: GenerationResult,
) -> None:
    app_mode = os.getenv("APP_MODE", "demo")

    if app_mode == "demo":
        logger.info(f"[WorkfrontClient][DEMO] task={task.task_id}")
        logger.info(f"  → Product    : {result.product_id}")
        logger.info(f"  → Background : {result.background_id}")
        logger.info(f"  → Image URL  : {result.generated_image_url}")
        logger.info(f"  → Copy       : {result.generated_copy[:80]}...")
        logger.info(f"  → Status     : Content Generation → Review")
        return

    headers = {"apiKey": API_KEY, "Content-Type": "application/json"}
    base = WORKFRONT_BASE.rstrip("/")

    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{base}/attask/api/v18.0/document",
            headers=headers,
            json={
                "objID": task.task_id,
                "objCode": "TASK",
                "name": f"ai_generated_{task.task_id}.jpg",
                "downloadURL": result.generated_image_url,
            },
        )
        await client.put(
            f"{base}/attask/api/v18.0/task/{task.task_id}",
            headers=headers,
            json={
                "status": STATUS_REVIEW,
                "description": (
                    f"[AI Generated]\n"
                    f"Product: {result.product_id}\n"
                    f"Background: {result.background_id}\n"
                    f"Season: {result.season} | Scope: {result.scope}\n\n"
                    f"Copy:\n{result.generated_copy}\n\n"
                    f"Prompt:\n{result.prompt_used[:500]}..."
                ),
            },
        )
        logger.info(f"[WorkfrontClient] Task {task.task_id} → Review")