from fastapi.testclient import TestClient

from app.main import app


def test_workfront_webhook_skips_non_generation_status():
    client = TestClient(app)

    response = client.post(
        "/webhook/workfront",
        headers={"x-webhook-secret": "changeme"},
        json={
            "task_id": "task-skip",
            "project_id": "proj-test",
            "status": "Approved",
            "product_id": "PROD_001",
            "season": "spring",
            "scope": "email",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "skipped": True,
        "reason": "Status 'Approved' not handled",
    }
