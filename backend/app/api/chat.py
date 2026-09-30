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

    answer = parsed.get("answer") or response.text
    evidence_out = None
    ev_info = parsed.get("evidence")
    if ev_info and ev_info.get("text"):
        ev = Evidence(
            document_id=doc.id,
            page_number=ev_info.get("page", 1),
            section=ev_info.get("section"),
            source_text=ev_info.get("text", ""),
        )
        db.add(ev)
        db.flush()
        evidence_out = EvidenceOut.model_validate(ev)

    db.add(ChatMessage(session_id=session.id, role="assistant", content=answer))
    db.commit()

    return ChatResponseOut(answer=answer, evidence=evidence_out)
