"""
Orchestrates the full pipeline described in the product spec:

Upload -> validation -> storage -> type detection -> text extraction -> OCR
-> segmentation -> normalization -> classification -> extraction ->
rule-based validation -> anomaly detection -> missing-data detection ->
evidence mapping -> confidence scoring -> DB storage.

Runs synchronously here for clarity; wire this into a background task queue
(e.g. FastAPI BackgroundTasks or Celery/RQ) for production so uploads return
immediately while processing continues.
"""
import json
import os
import time

from sqlalchemy.orm import Session

from app.ai import router as ai_router
from app.ai.prompts import classification as classification_prompts
from app.ai.prompts import extraction as extraction_prompts
from app.ai.prompts import anomaly as anomaly_prompts
from app.ai.prompts import summarization as summarization_prompts
from app.ai.schemas.extraction_schemas import InvoiceExtraction, AnomalyList
from app.core.config import get_settings
from app.document_processing import extractor
from app.models.document import Document, DocumentPage
from app.models.analysis import (
    Analysis, Evidence, Finding, FinancialValue, Anomaly, MissingData, AIModelLog,
)
from app.rules import financial_validation, missing_data as missing_data_rules

settings = get_settings()


def _safe_json_loads(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        return {}


def _log_model_use(db: Session, document_id: int, task: str, response, started_at: float):
    db.add(AIModelLog(
        document_id=document_id,
        task=task,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        estimated_cost=0.0,  # wire up real per-model pricing table here
        processing_time_ms=int((time.time() - started_at) * 1000),
    ))


def _create_evidence(db: Session, document_id: int, page: int, section: str | None, text: str) -> Evidence:
    ev = Evidence(document_id=document_id, page_number=page, section=section, source_text=text or "")
    db.add(ev)
    db.flush()
    return ev


class ProcessingCancelled(Exception):
    pass


def _raise_if_cancelled(db: Session, document_id: int) -> None:
    status = db.query(Document.status).filter(Document.id == document_id).scalar()
    if status == "cancelling":
        raise ProcessingCancelled()


async def process_document(db: Session, document: Document) -> None:
    try:
        _raise_if_cancelled(db, document.id)
        document.status = "processing"
        db.commit()

        storage_dir = os.path.dirname(document.storage_path)
        image_dir = os.path.join(storage_dir, f"doc_{document.id}_pages")

        # --- 1. Text extraction / OCR ---
        document.status = "extracting_text"
        db.commit()

        if document.mime_type == "application/pdf":
            pages = extractor.extract_pdf(document.storage_path, image_dir)
        else:
            pages = extractor.extract_image(document.storage_path, image_dir)

        _raise_if_cancelled(db, document.id)
        for p in pages:
            db.add(DocumentPage(
                document_id=document.id,
                page_number=p.page_number,
                raw_text=p.text,
                used_ocr="true" if p.used_ocr else "false",
                image_path=p.image_path,
            ))
        document.page_count = len(pages)
        db.commit()

        full_text = extractor.build_full_text_with_page_markers(pages)

        # --- 2. Classification ---
        _raise_if_cancelled(db, document.id)
        document.status = "analyzing"
        db.commit()

        started = time.time()
        classification_resp = await ai_router.run_task(
            "classification",
            classification_prompts.SYSTEM_PROMPT,
            classification_prompts.build_user_prompt(full_text),
        )
        _raise_if_cancelled(db, document.id)
        _log_model_use(db, document.id, "classification", classification_resp, started)
        classification = _safe_json_loads(classification_resp.text)

        if not document.document_type_confirmed_by_user:
            document.document_type = classification.get("document_type", "other")
        db.commit()

        doc_type = document.document_type

        # --- 3. Extraction ---
        _raise_if_cancelled(db, document.id)
        started = time.time()
        extraction_resp = await ai_router.run_task(
            "extraction",
            extraction_prompts.get_system_prompt(doc_type),
            extraction_prompts.build_user_prompt(full_text),
        )
        _raise_if_cancelled(db, document.id)
        _log_model_use(db, document.id, "extraction", extraction_resp, started)
        extracted = _safe_json_loads(extraction_resp.text)

        # Validate extraction shape for invoices with Pydantic (extend per type as needed)
        if doc_type == "invoice":
            try:
                extracted = InvoiceExtraction(**extracted).model_dump()
            except Exception as exc:
                print(f"[pipeline] invoice extraction failed schema validation: {exc}")

        # Store each extracted field as a Finding with evidence where available
        for field_name, field_value in extracted.items():
            if field_value in (None, "", [], {}):
                continue
            evidence_obj = None
            ev_info = None
            if isinstance(field_value, dict):
                ev_info = field_value.get("evidence")
            if ev_info:
                evidence_obj = _create_evidence(
                    db, document.id, ev_info.get("page", 1), None, ev_info.get("text", "")
                )
            db.add(Finding(
                document_id=document.id,
                category="extraction",
                field_name=field_name,
                field_value=str(field_value)[:2000],
                confidence=0.8,
                evidence_id=evidence_obj.id if evidence_obj else None,
                source="ai",
            ))
        db.commit()

        # --- 4. Deterministic financial validation (invoices only, for now) ---
        _raise_if_cancelled(db, document.id)
        document.status = "validating"
        db.commit()

        rule_anomalies: list[dict] = []
        if doc_type == "invoice":
            check = financial_validation.validate_invoice_totals(
                subtotal=extracted.get("subtotal"),
                tax=extracted.get("tax"),
                discount=extracted.get("discount"),
                shipping=None,
                stated_total=extracted.get("total"),
            )
            rule_anomalies.extend(check.anomalies)

            for label, is_calc, value in [
                ("subtotal", False, extracted.get("subtotal")),
                ("tax", False, extracted.get("tax")),
                ("discount", False, extracted.get("discount")),
                ("stated_total", False, extracted.get("total")),
                ("calculated_total", True, check.expected_total),
            ]:
                if value is not None:
                    db.add(FinancialValue(
                        document_id=document.id, label=label, value=value,
                        currency=extracted.get("currency"), is_calculated=is_calc,
                    ))

            rule_anomalies.extend(
                financial_validation.detect_line_item_issues(extracted.get("line_items") or [])
            )

        for a in rule_anomalies:
            db.add(Anomaly(
                document_id=document.id,
                title=a["title"],
                severity=a["severity"],
                description=a.get("description"),
                detection_type="rule",
                pages=a.get("pages", []),
                confidence=a.get("confidence", 1.0),
            ))
        db.commit()

        # --- 5. AI-based semantic anomaly detection ---
        _raise_if_cancelled(db, document.id)
        started = time.time()
        anomaly_resp = await ai_router.run_task(
            "anomaly_explanation",
            anomaly_prompts.SYSTEM_PROMPT,
            anomaly_prompts.build_user_prompt(full_text),
        )
        _raise_if_cancelled(db, document.id)
        _log_model_use(db, document.id, "anomaly_explanation", anomaly_resp, started)
        try:
            ai_anomalies = AnomalyList(**_safe_json_loads(anomaly_resp.text)).anomalies
        except Exception:
            ai_anomalies = []

        for a in ai_anomalies:
            db.add(Anomaly(
                document_id=document.id,
                title=a.title,
                severity=a.severity,
                description=a.description,
                detection_type="ai",
                pages=a.pages,
                confidence=a.confidence,
            ))
        db.commit()

        # --- 6. Missing data detection ---
        _raise_if_cancelled(db, document.id)
        missing = missing_data_rules.find_missing_fields(doc_type, extracted)
        for m in missing:
            db.add(MissingData(document_id=document.id, field_name=m["field_name"], description=m["description"]))
        db.commit()

        # --- 7. Summarization ---
        _raise_if_cancelled(db, document.id)
        started = time.time()
        summary_resp = await ai_router.run_task(
            "summarization",
            summarization_prompts.SYSTEM_PROMPT,
            summarization_prompts.build_user_prompt(full_text, doc_type),
            json_mode=False,
        )
        _raise_if_cancelled(db, document.id)
        _log_model_use(db, document.id, "summarization", summary_resp, started)

        db.add(Analysis(document_id=document.id, summary=summary_resp.text, model_used=summary_resp.model))

        document.status = "completed"
        db.commit()

    except ProcessingCancelled:
        db.rollback()
        document.status = "cancelled"
        document.error_message = None
        db.commit()
    except Exception as exc:
        db.rollback()
        status = db.query(Document.status).filter(Document.id == document.id).scalar()
        document.status = "cancelled" if status == "cancelling" else "failed"
        document.error_message = None if status == "cancelling" else str(exc)
        db.commit()
        if document.status == "failed":
            print(f"[pipeline] document {document.id} failed: {exc}")
