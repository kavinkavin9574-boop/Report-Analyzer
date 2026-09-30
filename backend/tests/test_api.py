import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"
os.environ["STORAGE_PATH"] = "./storage_test_api"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.analysis import AIModelLog, ChatMessage, ChatSession, Evidence, Finding
from app.models.document import Document
from app.models.user import User
from app.services.pipeline import process_document


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True, scope="module")
def cleanup():
    for f in ["test_api.db", "test_api.db-journal"]:
        if os.path.exists(f):
            os.remove(f)
    yield
    for f in ["test_api.db", "test_api.db-journal"]:
        if os.path.exists(f):
            os.remove(f)


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_register_and_login_flow(client):
    res = client.post("/api/auth/register", json={
        "name": "Test User", "email": "test@example.com", "password": "testpass123",
    })
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert token

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"


def test_cannot_register_duplicate_email(client):
    client.post("/api/auth/register", json={
        "name": "Dup", "email": "dup@example.com", "password": "testpass123",
    })
    res = client.post("/api/auth/register", json={
        "name": "Dup2", "email": "dup@example.com", "password": "testpass123",
    })
    assert res.status_code == 400


def test_documents_require_auth(client):
    res = client.get("/api/documents")
    assert res.status_code == 401


def test_dashboard_stats_require_auth(client):
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 401


def test_delete_document_cleans_up_references(client):
    auth = client.post("/api/auth/register", json={
        "name": "Delete Test", "email": "delete@example.com", "password": "testpass123",
    })
    token = auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "delete@example.com").one()
        doc = Document(
            owner_id=user.id,
            filename="delete.pdf",
            storage_path="delete.pdf",
            file_size=1,
            mime_type="application/pdf",
        )
        db.add(doc)
        db.flush()
        evidence = Evidence(document_id=doc.id, page_number=1, source_text="text")
        db.add(evidence)
        db.flush()
        db.add(Finding(
            document_id=doc.id,
            category="general",
            field_name="test",
            evidence_id=evidence.id,
        ))
        chat_session = ChatSession(document_id=doc.id)
        db.add(chat_session)
        db.flush()
        chat_session_id = chat_session.id
        db.add(ChatMessage(
            session_id=chat_session.id,
            role="user",
            content="test",
            evidence_id=evidence.id,
        ))
        db.add(AIModelLog(document_id=doc.id, task="test", model="test"))
        db.commit()
        document_id = doc.id

    response = client.delete(f"/api/documents/{document_id}", headers=headers)
    assert response.status_code == 200

    with SessionLocal() as db:
        assert db.query(Document).filter(Document.id == document_id).first() is None
        assert db.query(Evidence).filter(Evidence.document_id == document_id).first() is None
        assert db.query(ChatMessage).filter(ChatMessage.session_id == chat_session_id).first() is None
        usage_log = db.query(AIModelLog).filter(AIModelLog.task == "test").one()
        assert usage_log.document_id is None


def test_openai_key_updates_at_runtime_without_being_returned(client):
    from app.core import runtime_config

    auth = client.post("/api/auth/register", json={
        "name": "Settings Test", "email": "settings@example.com", "password": "testpass123",
    })
    headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}

    try:
        response = client.put(
            "/api/settings/ai-models",
            headers=headers,
            json={"api_key": "runtime-test-key"},
        )
        assert response.status_code == 200
        assert response.json()["api_key_configured"] is True
        assert "api_key" not in response.json()
        assert "runtime-test-key" not in response.text
        assert runtime_config.get_api_key() == "runtime-test-key"

        response = client.delete("/api/settings/ai-models/api-key", headers=headers)
        assert response.status_code == 200
        assert response.json()["api_key_configured"] is False
        assert runtime_config.get_api_key() == ""
    finally:
        runtime_config.set_api_key(None)


def test_cancel_document_stops_queued_processing(client):
    auth = client.post("/api/auth/register", json={
        "name": "Cancel Test", "email": "cancel@example.com", "password": "testpass123",
    })
    headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "cancel@example.com").one()
        doc = Document(
            owner_id=user.id,
            filename="cancel.pdf",
            storage_path="cancel.pdf",
            file_size=1,
            mime_type="application/pdf",
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        document_id = doc.id

    response = client.post(f"/api/documents/{document_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelling"

    with SessionLocal() as db:
        doc = db.query(Document).filter(Document.id == document_id).one()
        asyncio.run(process_document(db, doc))
        db.refresh(doc)
        assert doc.status == "cancelled"

    response = client.post(f"/api/documents/{document_id}/cancel", headers=headers)
    assert response.status_code == 409


def test_nvidia_settings_route_to_nvidia_endpoint(client):
    from app.ai import router as ai_router
    from app.core import runtime_config

    auth = client.post("/api/auth/register", json={
        "name": "NVIDIA Test", "email": "nvidia@example.com", "password": "testpass123",
    })
    headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}
    original = client.get("/api/settings/ai-models", headers=headers).json()
    try:
        response = client.put("/api/settings/ai-models", headers=headers, json={
            "ai_provider": "nvidia",
            "default_model": "meta/llama-3.3-70b-instruct",
            "fast_model": "meta/llama-3.3-70b-instruct",
            "reasoning_model": "meta/llama-3.3-70b-instruct",
            "api_key": "test-nvidia-key",
        })
        assert response.status_code == 200
        assert response.json()["ai_provider"] == "nvidia"

        response = client.get("/api/settings/ai-models", headers=headers)
        assert response.status_code == 200
        assert response.json()["default_model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"

        provider = ai_router.get_provider()
        assert str(provider._client.base_url) == "https://integrate.api.nvidia.com/v1/"
        assert provider._tier_to_model["primary"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    finally:
        client.put("/api/settings/ai-models", headers=headers, json={
            "ai_provider": original["ai_provider"],
            "default_model": original["default_model"],
            "fast_model": original["fast_model"],
            "reasoning_model": original["reasoning_model"],
        })
        runtime_config.set_api_key(None)
