import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import router as ai_router
from app.ai.router import AIProviderNotConfigured
from app.ai.prompts import chat as chat_prompts
from app.core.database import get_db
from app.core.security import get_current_user
from app.document_processing.extractor import build_full_text_with_page_markers, PageResult
from app.models.user import User
from app.models.document import Document
from app.models.analysis import ChatSession, ChatMessage, Evidence
from app.schemas.document import ChatRequest, ChatResponseOut, EvidenceOut
from app.services.pipeline import _safe_json_loads

router = APIRouter(prefix="/api/documents", tags=["chat"])


def _normalize_grounding_text(value: str | None) -> str:
    if value is None:
        return ""
    value = str(value)
    value = value.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value.casefold()


def _ground_chat_answer(
    parsed: dict, page_text_by_number: dict[int, str]
) -> tuple[str, dict | None]:
    answer = parsed.get("answer")
    evidence = parsed.get("evidence")
    if not isinstance(answer, str) or not answer.strip():
        return chat_prompts.NOT_FOUND_ANSWER, None

    if answer.strip().casefold() == chat_prompts.NOT_FOUND_ANSWER.casefold():
        return chat_prompts.NOT_FOUND_ANSWER, None

    if not isinstance(evidence, dict):
        return chat_prompts.NOT_FOUND_ANSWER, None

    raw_page_number = evidence.get("page")
    source_text = evidence.get("text")
    section = evidence.get("section")

    page_number = None
    if isinstance(raw_page_number, bool):
        page_number = None
    elif isinstance(raw_page_number, int):
        page_number = raw_page_number
    elif isinstance(raw_page_number, str):
        normalized_page = raw_page_number.strip()
        if normalized_page and normalized_page.lstrip("-").isdigit():
            page_number = int(normalized_page)

    if (
        page_number is None
        or not isinstance(source_text, str)
        or not source_text.strip()
        or (section is not None and not isinstance(section, str))
    ):
        return chat_prompts.NOT_FOUND_ANSWER, None

    page_text = page_text_by_number.get(page_number)
    normalized_source = _normalize_grounding_text(source_text)
    normalized_page = _normalize_grounding_text(page_text)
    if not normalized_page or not normalized_source or normalized_source not in normalized_page:
        return chat_prompts.NOT_FOUND_ANSWER, None

    return answer.strip(), evidence


@router.post("/{document_id}/chat", response_model=ChatResponseOut)
async def chat_with_document(
    document_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "completed":
        raise HTTPException(status_code=400, detail="Document is still processing")

    pages = [PageResult(page_number=p.page_number, text=p.raw_text or "", used_ocr=False) for p in doc.pages]
    full_text = build_full_text_with_page_markers(pages)

    session = db.query(ChatSession).filter(ChatSession.document_id == doc.id).first()
    if not session:
        session = ChatSession(document_id=doc.id)
        db.add(session)
        db.commit()
        db.refresh(session)

    db.add(ChatMessage(session_id=session.id, role="user", content=payload.question))
    db.commit()

    try:
        response = await ai_router.run_task(
            "chat", chat_prompts.SYSTEM_PROMPT, chat_prompts.build_user_prompt(full_text, payload.question)
        )
    except AIProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    parsed = _safe_json_loads(response.text)
    if not isinstance(parsed, dict):
        parsed = {}

    page_text_by_number = {page.page_number: page.text for page in pages}
    answer, ev_info = _ground_chat_answer(parsed, page_text_by_number)
    evidence_out = None
    if ev_info:
        ev = Evidence(
            document_id=doc.id,
            page_number=ev_info["page"],
            section=ev_info.get("section"),
            source_text=ev_info["text"],
        )
        db.add(ev)
        db.flush()
        evidence_out = EvidenceOut.model_validate(ev)

    db.add(ChatMessage(session_id=session.id, role="assistant", content=answer))
    db.commit()

    return ChatResponseOut(answer=answer, evidence=evidence_out)
