import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"
os.environ["STORAGE_PATH"] = "./storage_test_api"

from datetime import datetime

import pytest
import httpx
from openai import APIConnectionError
from fastapi.testclient import TestClient

from app.ai import router as ai_router
from app.ai.providers import openai_provider
from app.api.chat import _ground_chat_answer
from app.main import app
from app.schemas.document import DocumentAnalysisOut, DocumentOut
from app.core.database import SessionLocal
from app.api.documents import _build_report_text
from app.models.analysis import AIModelLog, ChatMessage, ChatSession, Evidence, Finding
from app.models.document import Document
from app.models.user import User
from app.rules.financial_validation import validate_invoice_totals
from app.services.pipeline import (
    _normalize_extraction,
    _parse_numeric_value,
    _parse_summary,
    _summary_from_extraction,
    process_document,
)


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


def test_ocr_runtime_disables_problematic_paddle_flags():
    assert os.environ.get("FLAGS_enable_pir_api") == "0"
    assert os.environ.get("FLAGS_use_onednn") == "0"
    assert os.environ.get("FLAGS_use_mkldnn") == "0"


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_chat_returns_not_found_when_answer_has_no_evidence():
    answer, evidence = _ground_chat_answer(
        {"answer": "The payment is due in 30 days.", "evidence": None},
        {1: "Invoice issued on June 1."},
    )

    assert answer == "Not found in the document."
    assert evidence is None


def test_chat_returns_not_found_when_evidence_is_not_in_cited_page():
    answer, evidence = _ground_chat_answer(
        {
            "answer": "The payment is due in 30 days.",
            "evidence": {"page": 1, "section": None, "text": "Payment due in 30 days."},
        },
        {1: "Invoice issued on June 1."},
    )

    assert answer == "Not found in the document."
    assert evidence is None


def test_chat_returns_answer_when_evidence_matches_cited_page():
    parsed = {
        "answer": "The payment is due in 30 days.",
        "evidence": {
            "page": 1,
            "section": "Payment terms",
            "text": "Payment is due within 30 days of the invoice date.",
        },
    }
    answer, evidence = _ground_chat_answer(
        parsed,
        {1: "Payment is due within 30 days of the invoice date."},
    )

    assert answer == parsed["answer"]
    assert evidence == parsed["evidence"]


def test_chat_accepts_numeric_string_page_numbers_and_whitespace_variants():
    parsed = {
        "answer": "The payment is due in 30 days.",
        "evidence": {
            "page": "1",
            "section": "Payment terms",
            "text": "  Payment is due within 30 days\n of the invoice date.  ",
        },
    }
    answer, evidence = _ground_chat_answer(
        parsed,
        {1: "Payment is due within 30 days of the invoice date."},
    )

    assert answer == parsed["answer"]
    assert evidence == parsed["evidence"]


def test_normalize_extraction_unwraps_values_and_preserves_evidence():
    extraction = {
        "revenue": {
            "value": 1250.5,
            "evidence": {"page": 2, "text": "Revenue: $1,250.50"},
        },
        "reporting_period": "Q1 2026",
        "financial_ratios": {
            "value": [{"name": "margin", "value": 0.25}],
            "evidence": {"page": 3, "text": "Margin was 25%."},
        },
    }

    values, evidence = _normalize_extraction(extraction)

    assert values == {
        "revenue": 1250.5,
        "reporting_period": "Q1 2026",
        "financial_ratios": [{"name": "margin", "value": 0.25}],
    }
    assert evidence == {
        "revenue": {"page": 2, "text": "Revenue: $1,250.50"},
        "financial_ratios": {"page": 3, "text": "Margin was 25%."},
    }


def test_parse_summary_returns_report_key_points():
    parsed = _parse_summary(
        '{"text":"","key_points":["Revenue: $1,250.50","Reporting period: Q1 2026"]}'
    )

    assert parsed == {
        "text": "",
        "key_points": ["Revenue: $1,250.50", "Reporting period: Q1 2026"],
    }


def test_parse_summary_rejects_missing_key_points():
    with pytest.raises(ValueError, match="key_points"):
        _parse_summary('{"text":"Report summary"}')


def test_summary_fallback_uses_extracted_report_facts():
    summary = _summary_from_extraction({
        "reporting_period": "Q1 2026",
        "revenue": 1250.5,
        "empty_field": None,
        "financial_ratios": [{"name": "margin", "value": 0.25}],
    })

    assert summary == {
        "text": "",
        "key_points": [
            "Reporting Period: Q1 2026",
            "Revenue: 1250.5",
            'Financial Ratios: [{"name": "margin", "value": 0.25}]',
        ],
    }


def test_build_report_text_returns_page_order_and_skips_empty_pages():
    class Page:
        def __init__(self, id, page_number, raw_text):
            self.id = id
            self.page_number = page_number
            self.raw_text = raw_text

    class DocumentWithPages:
        pages = [
            Page(3, 3, "Third page"),
            Page(1, 1, "First page"),
            Page(2, 2, "  "),
            Page(4, 1, "Latest first page"),
        ]

    assert _build_report_text(DocumentWithPages()) == (
        "[PAGE 1]\nLatest first page\n\n[PAGE 3]\nThird page"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("$1,234.56", 1234.56),
        ("1.234,56 EUR", 1234.56),
        ("(€1,234.56)", -1234.56),
        ("Q1 2026", None),
        (None, None),
        (True, None),
    ],
)
def test_parse_numeric_value_handles_currency_and_invalid_values(value, expected):
    assert _parse_numeric_value(value) == expected


def test_invoice_total_validation_accepts_currency_formatted_extraction():
    amounts = {
        "subtotal": _parse_numeric_value("$1,200.00"),
        "tax": _parse_numeric_value("$96.00"),
        "discount": _parse_numeric_value("$0.00"),
        "total": _parse_numeric_value("$1,296.00"),
    }

    result = validate_invoice_totals(
        subtotal=amounts["subtotal"],
        tax=amounts["tax"],
        discount=amounts["discount"],
        shipping=None,
        stated_total=amounts["total"],
    )

    assert result.expected_total == 1296.0
    assert result.difference == 0.0


def test_ai_connection_error_includes_provider_task_and_root_cause(monkeypatch):
    class FailingProvider:
        async def complete(self, **kwargs):
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            raise APIConnectionError(
                message="Connection error",
                request=request,
            ) from OSError("network unreachable")

    monkeypatch.setattr(ai_router, "get_provider", lambda: FailingProvider())
    with pytest.raises(ai_router.AIProviderConnectionError) as exc_info:
        asyncio.run(ai_router.run_task("classification", "system", "user"))

    assert "OpenAI (api.openai.com)" in str(exc_info.value)
    assert "'classification'" in str(exc_info.value)
    assert "OSError: network unreachable" in str(exc_info.value)


def test_openai_provider_retries_transient_connection_errors(monkeypatch):
    captured = {}

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(openai_provider, "AsyncOpenAI", FakeAsyncOpenAI)
    openai_provider.OpenAIProvider(api_key="test-key")

    assert captured["max_retries"] == 5
    assert captured["api_key"] == "test-key"


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


def test_original_document_can_be_viewed_inline_by_owner(client, tmp_path):
    auth = client.post("/api/auth/register", json={
        "name": "Original Viewer", "email": "original-viewer@example.com", "password": "testpass123",
    })
    token = auth.json()["access_token"]
    original_path = tmp_path / "original.pdf"
    original_path.write_bytes(b"%PDF-test")

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "original-viewer@example.com").one()
        doc = Document(
            owner_id=user.id,
            filename="original.pdf",
            storage_path=str(original_path),
            file_size=original_path.stat().st_size,
            mime_type="application/pdf",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        document_id = doc.id
        try:
            response = client.get(
                f"/api/documents/{document_id}/original",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/pdf")
            assert response.headers["content-disposition"].startswith("inline")
            assert response.content == b"%PDF-test"
        finally:
            db.delete(doc)
            db.commit()


def test_dashboard_stats_require_auth(client):
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 401


def test_analysis_response_supports_structured_summary_and_fields():
    doc = DocumentOut(
        id=1,
        filename="invoice.pdf",
        mime_type="application/pdf",
        document_type="invoice",
        status="completed",
        page_count=1,
        file_size=1024,
        error_message=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    analysis = DocumentAnalysisOut(
        document=doc,
        summary={"text": "Invoice paid in full.", "key_points": ["Vendor: Acme", "Total: $1,250.00"]},
        extracted_fields={"invoice_number": "INV-1001", "total": 1250.0},
        findings=[],
        deadlines=[],
        obligations=[],
        financial_values=[],
        anomalies=[],
        missing_data=[],
    )

    assert analysis.model_dump()["summary"]["text"] == "Invoice paid in full."
    assert analysis.extracted_fields["invoice_number"] == "INV-1001"
    assert analysis.extracted_fields["total"] == 1250.0


def test_normalize_json_summary_string_into_structured_summary():
    from app.api.documents import _normalize_summary

    summary = '{"text": "Invoice paid in full.", "key_points": ["Vendor: Acme", "Total: $1,250.00"]}'
    normalized = _normalize_summary(summary)

    assert normalized is not None
    assert normalized.text == "Invoice paid in full."
    assert normalized.key_points == ["Vendor: Acme", "Total: $1,250.00"]


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


def test_openrouter_settings_route_to_openrouter_endpoint(client):
    from app.ai import router as ai_router
    from app.core import runtime_config

    auth = client.post("/api/auth/register", json={
        "name": "OpenRouter Test", "email": "openrouter@example.com", "password": "testpass123",
    })
    headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}
    original = client.get("/api/settings/ai-models", headers=headers).json()
    try:
        response = client.put("/api/settings/ai-models", headers=headers, json={
            "ai_provider": "openrouter",
            "default_model": "openai/gpt-4o-mini",
            "fast_model": "openai/gpt-4o-mini",
            "reasoning_model": "anthropic/claude-3.7-sonnet",
            "api_key": "test-openrouter-key",
        })
        assert response.status_code == 200
        assert response.json()["ai_provider"] == "openrouter"

        provider = ai_router.get_provider()
        assert str(provider._client.base_url) == "https://openrouter.ai/api/v1/"
        assert provider._tier_to_model["primary"] == "openai/gpt-4o-mini"
        assert provider._tier_to_model["reasoning"] == "anthropic/claude-3.7-sonnet"
    finally:
        client.put("/api/settings/ai-models", headers=headers, json={
            "ai_provider": original["ai_provider"],
            "default_model": original["default_model"],
            "fast_model": original["fast_model"],
            "reasoning_model": original["reasoning_model"],
        })
        runtime_config.set_api_key(None)
