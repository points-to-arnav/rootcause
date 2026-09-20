import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data

def test_settings_get():
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "active_provider" in data
    assert "openrouter_model" in data

def test_sample_dataset_and_semantic():
    # Load sample dataset
    response = client.post("/api/datasets/sample")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    ds_id = data["dataset_id"]
    assert ds_id == "ds_retail_sample"

    # Get semantic info
    sem_resp = client.get(f"/api/datasets/{ds_id}/semantic")
    assert sem_resp.status_code == 200
    sem = sem_resp.json()
    assert "tables" in sem
    assert "sales" in sem["tables"]

    # Get quality info
    qual_resp = client.get(f"/api/datasets/{ds_id}/quality")
    assert qual_resp.status_code == 200
    qual = qual_resp.json()
    assert "issues" in qual
    assert len(qual["issues"]) > 0

    # Create session
    sess_resp = client.post("/api/sessions", json={"dataset_id": ds_id})
    assert sess_resp.status_code == 200
    session_id = sess_resp.json()["session_id"]
    assert session_id.startswith("s_")
