import pytest
from pydantic import ValidationError

from app.ai.prompts.summarization import SYSTEM_PROMPT, build_user_prompt
from app.schemas.document import StructuredSummary


def test_report_prompt_requires_source_grounded_categories():
    assert "Never infer a deadline from a transaction date" in SYSTEM_PROMPT
    assert "Missing information alone is not an anomaly" in SYSTEM_PROMPT
    assert '"source_type": "direct", "inference", or "not_supported"' in SYSTEM_PROMPT


def test_summary_prompt_includes_entire_document_text():
    document_text = f"{'x' * 8000}\n[PAGE 2]\nDue date: 2026-10-31"

    prompt = build_user_prompt(document_text, "invoice")

    assert document_text in prompt


def test_structured_summary_keeps_evidence_and_source_classification():
    summary = StructuredSummary.model_validate({
        "text": "Payment confirmation.",
        "sections": [{
            "heading": "2. Deadlines",
            "items": [{
                "label": "Payment date",
                "value": "2026-10-05",
                "source_type": "direct",
                "source_location": "Page 1, Transaction details",
                "evidence": "Payment date: 2026-10-05",
            }],
        }],
    })

    item = summary.sections[0].items[0]
    assert item.source_type == "direct"
    assert item.evidence == "Payment date: 2026-10-05"


def test_structured_summary_rejects_unknown_source_classification():
    with pytest.raises(ValidationError):
        StructuredSummary.model_validate({
            "sections": [{
                "heading": "1. Overview",
                "items": [{
                    "label": "Status",
                    "value": "Paid",
                    "source_type": "assumed",
                }],
            }],
        })
