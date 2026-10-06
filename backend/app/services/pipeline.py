"""
Orchestrates the full pipeline described in the product spec:

Upload -> validation -> storage -> type detection -> text extraction -> OCR
-> classification -> concurrent extraction, anomaly detection, and summary
-> rule-based validation -> missing-data detection -> evidence mapping ->
DB storage.

Runs synchronously here for clarity; wire this into a background task queue
(e.g. FastAPI BackgroundTasks or Celery/RQ) for production so uploads return
immediately while processing continues.
"""
import asyncio
import json
import os
import re
import time
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai import router as ai_router
from app.ai.providers.base import AIResponse
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
from app.schemas.document import StructuredSummary
from app.rules import financial_validation, missing_data as missing_data_rules

settings = get_settings()
TimedAIResult = tuple[AIResponse, float]


def _safe_json_loads(text: str) -> dict:
    text = text.strip()
    fenced_json = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    if fenced_json:
        text = fenced_json.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        object_start = text.find("{")
        if object_start < 0:
            return {}
        try:
            parsed, _ = json.JSONDecoder().raw_decode(text, object_start)
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_extraction(extracted: dict) -> tuple[dict, dict]:
    """Unwrap value/evidence pairs while keeping evidence available for storage."""
    values: dict = {}
    evidence_by_field: dict = {}

    for field_name, field_result in extracted.items():
        if isinstance(field_result, dict) and "value" in field_result:
            values[field_name] = field_result["value"]
            evidence = field_result.get("evidence")
            if isinstance(evidence, dict):
                evidence_by_field[field_name] = evidence
            continue

        if isinstance(field_result, dict) and "evidence" in field_result:
            values[field_name] = {
                key: value for key, value in field_result.items() if key != "evidence"
            }
            evidence = field_result.get("evidence")
            if isinstance(evidence, dict):
                evidence_by_field[field_name] = evidence
            continue

        values[field_name] = field_result

    return values, evidence_by_field


def _parse_numeric_value(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value) if Decimal(str(value)).is_finite() else None
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    is_negative = text.startswith("(") and text.endswith(")")
    if is_negative:
        text = text[1:-1].strip()

    # Remove surrounding currency labels/symbols, but reject other text.
    text = re.sub(r"^[^\d+.,-]+|[^\d.,-]+$", "", text).strip()
    if not re.fullmatch(r"[+-]?\d[\d.,]*", text):
        return None

    if "," in text and "." in text:
        decimal_separator = "," if text.rfind(",") > text.rfind(".") else "."
        grouping_separator = "." if decimal_separator == "," else ","
        text = text.replace(grouping_separator, "")
        if decimal_separator == ",":
            text = text.replace(",", ".")
    elif "," in text or "." in text:
        separator = "," if "," in text else "."
        parts = text.split(separator)
        if len(parts) > 2:
            if all(len(part) == 3 for part in parts[1:]):
                text = "".join(parts)
            else:
                text = "".join(parts[:-1]) + "." + parts[-1]
        elif len(parts[1]) == 3 and len(parts[0].lstrip("+-")) <= 3:
            text = "".join(parts)
        else:
            text = text.replace(separator, ".")

    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if is_negative:
        number = -abs(number)
    return float(number) if number.is_finite() else None


def _parse_summary(text: str) -> dict:
    summary = _safe_json_loads(text)
    if not isinstance(summary, dict) or not summary:
        reason = "empty" if not text.strip() else "not a valid JSON object"
        raise ValueError(f"AI summary response was {reason}")

    summary_text = summary.get("text", "")
    key_points = summary.get("key_points", [])
    if (
        not isinstance(summary_text, str)
        or not isinstance(key_points, list)
        or any(not isinstance(point, str) for point in key_points)
    ):
        raise ValueError(
            "AI summary response fields must be a string 'text' and a list of string 'key_points'"
        )

    try:
        return StructuredSummary.model_validate(summary).model_dump()
    except ValidationError as exc:
        raise ValueError(f"AI summary response did not match the expected report shape: {exc}") from exc


def _verify_summary_sources(summary: dict, document_text: str) -> dict:
    page_matches = list(re.finditer(r"(?m)^\[PAGE\s+(\d+)\]\s*$", document_text))
    page_text: dict[int, str] = {}
    for index, match in enumerate(page_matches):
        end = page_matches[index + 1].start() if index + 1 < len(page_matches) else len(document_text)
        page_text[int(match.group(1))] = document_text[match.end():end]

    def normalize_whitespace(value: str) -> str:
        return " ".join(value.split())

    full_text = normalize_whitespace(document_text)
    for section in summary.get("sections", []):
        for item in section.get("items", []):
            if item["source_type"] == "not_supported":
                item["evidence"] = ""
                continue

            evidence = normalize_whitespace(item["evidence"])
            page_match = re.search(r"\bpage\s+(\d+)\b", item["source_location"], re.IGNORECASE)
            source_text = (
                normalize_whitespace(page_text.get(int(page_match.group(1)), ""))
                if page_match
                else full_text
            )
            if evidence and evidence in source_text:
                continue

            item["source_type"] = "not_supported"
            item["value"] = "Cannot be determined from this document."
            item["source_location"] = "The cited evidence could not be verified against the document text."
            item["evidence"] = ""

    return summary


def _summary_from_extraction(extracted: dict) -> dict:
    key_points = []
    for field_name, value in extracted.items():
        if value in (None, "", [], {}):
            continue
        display_value = (
            json.dumps(value, ensure_ascii=False)
            if isinstance(value, (dict, list))
            else str(value)
        )
        key_points.append(f"{field_name.replace('_', ' ').strip().title()}: {display_value}")
    return {"text": "", "key_points": key_points, "sections": []}


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


async def _run_timed_ai_task(task: str, system_prompt: str, user_prompt: str) -> TimedAIResult:
    started_at = time.time()
    response = await ai_router.run_task(task, system_prompt, user_prompt)
    return response, started_at


async def _run_document_analysis_tasks(
    doc_type: str, full_text: str
) -> tuple[TimedAIResult, TimedAIResult, TimedAIResult]:
    return await asyncio.gather(
        _run_timed_ai_task(
            "extraction",
            extraction_prompts.get_system_prompt(doc_type),
            extraction_prompts.build_user_prompt(full_text),
        ),
        _run_timed_ai_task(
            "anomaly_explanation",
            anomaly_prompts.SYSTEM_PROMPT,
            anomaly_prompts.build_user_prompt(full_text),
        ),
        _run_timed_ai_task(
            "summarization",
            summarization_prompts.SYSTEM_PROMPT,
            summarization_prompts.build_user_prompt(full_text, doc_type),
        ),
    )


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

        # --- 3. Independent AI analysis ---
        # Classification determines the extraction prompt; after that, the
        # extraction, anomaly review, and summary can run concurrently.
        _raise_if_cancelled(db, document.id)
        extraction_result, anomaly_result, summary_result = await _run_document_analysis_tasks(
            doc_type, full_text
        )
        _raise_if_cancelled(db, document.id)
        extraction_resp, extraction_started = extraction_result
        anomaly_resp, anomaly_started = anomaly_result
        summary_resp, summary_started = summary_result
        _log_model_use(db, document.id, "extraction", extraction_resp, extraction_started)
        _log_model_use(db, document.id, "anomaly_explanation", anomaly_resp, anomaly_started)
        _log_model_use(db, document.id, "summarization", summary_resp, summary_started)
        extracted, extraction_evidence = _normalize_extraction(
            _safe_json_loads(extraction_resp.text)
        )

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
            ev_info = extraction_evidence.get(field_name)
            if ev_info is None and isinstance(field_value, dict):
                ev_info = field_value.get("evidence")
            if ev_info:
                evidence_obj = _create_evidence(
                    db, document.id, ev_info.get("page", 1), None, ev_info.get("text", "")
                )
            display_value = (
                {key: value for key, value in field_value.items() if key != "evidence"}
                if isinstance(field_value, dict) and "evidence" in field_value
                else field_value
            )
            stored_value = (
                json.dumps(display_value, ensure_ascii=False)
                if isinstance(display_value, (dict, list))
                else str(display_value)
            )
            db.add(Finding(
                document_id=document.id,
                category="extraction",
                field_name=field_name,
                field_value=stored_value[:2000],
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
            amounts = {
                field: _parse_numeric_value(extracted.get(field))
                for field in ("subtotal", "tax", "discount", "total")
            }
            check = financial_validation.validate_invoice_totals(
                subtotal=amounts["subtotal"],
                tax=amounts["tax"],
                discount=amounts["discount"],
                shipping=None,
                stated_total=amounts["total"],
            )
            rule_anomalies.extend(check.anomalies)

            for label, is_calc, value in [
                ("subtotal", False, amounts["subtotal"]),
                ("tax", False, amounts["tax"]),
                ("discount", False, amounts["discount"]),
                ("stated_total", False, amounts["total"]),
                ("calculated_total", True, check.expected_total),
            ]:
                if value is not None:
                    db.add(FinancialValue(
                        document_id=document.id, label=label, value=value,
                        currency=extracted.get("currency"), is_calculated=is_calc,
                    ))

            rule_anomalies.extend(
                financial_validation.detect_line_item_issues([
                    {
                        **item,
                        "quantity": _parse_numeric_value(item.get("quantity")),
                        "unit_price": _parse_numeric_value(item.get("unit_price")),
                    }
                    for item in (extracted.get("line_items") or [])
                    if isinstance(item, dict)
                ])
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

        # --- 7. Extract readable key facts from the report ---
        _raise_if_cancelled(db, document.id)
        try:
            summary = _verify_summary_sources(
                _parse_summary(summary_resp.text), full_text
            )
        except ValueError as exc:
            choices = getattr(summary_resp.raw, "choices", None)
            finish_reason = getattr(choices[0], "finish_reason", None) if choices else None
            print(
                f"[pipeline] document {document.id} summary response was invalid; "
                f"using extracted report facts instead: {exc}; "
                f"response_chars={len(summary_resp.text)}; finish_reason={finish_reason or 'unknown'}"
            )
            summary = _summary_from_extraction(extracted)

        db.add(Analysis(
            document_id=document.id,
            summary=json.dumps(summary, ensure_ascii=False),
            model_used=summary_resp.model,
        ))

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
