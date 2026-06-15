import os, httpx
from app.models import WorkfrontTaskPayload, GenerationResult

WORKFRONT_BASE = os.getenv("WORKFRONT_BASE_URL", "")
API_KEY = os.getenv("WORKFRONT_API_KEY", "")

async def upload_result_to_workfront(
    task: WorkfrontTaskPayload,
    result: GenerationResult,
) -> None:
    """
    In APP_MODE=demo: simula l'upload stampando a console.
    In live: carica l'immagine come allegato e aggiorna lo stato in 'Review'.
    """
    if os.getenv("APP_MODE", "demo") == "demo":
        print(f"[WorkfrontClient][DEMO] Would upload to task {task.task_id}")
        print(f"  Image: {result.generated_image_url}")
        print(f"  Copy:  {result.generated_copy[:80]}...")
        print(f"  Status → Review")
        return

    headers = {"apiKey": API_KEY, "Content-Type": "application/json"}
    base = WORKFRONT_BASE

    async with httpx.AsyncClient(timeout=30) as client:
        # Upload attachment
        await client.post(
            f"{base}/attask/api/v18.0/document",
            headers=headers,
            json={
                "objID": task.task_id,
                "objCode": "TASK",
                "name": f"generated_{task.task_id}.jpg",
                "downloadURL": result.generated_image_url,
            },
        )
        # Update task status to Review
        await client.put(
            f"{base}/attask/api/v18.0/task/{task.task_id}",
            headers=headers,
            json={"status": "INP", "customField_review_note": result.generated_copy},
        )