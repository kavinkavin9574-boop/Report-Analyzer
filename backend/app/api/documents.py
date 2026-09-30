import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.analysis import (
    AIModelLog, Analysis, ChatMessage, ChatSession, Deadline, Evidence, Finding,
    Obligation, FinancialValue, Anomaly, MissingData,
)
from app.schemas.document import DocumentOut, DocumentAnalysisOut
from app.services.pipeline import process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()

ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}


def _get_owned_document(db: Session, document_id: int, user: User) -> Document:
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, PNG or JPG.")

    contents = await file.read()
    if len(contents) > settings.max_file_size:
        raise HTTPException(status_code=400, detail="Document too large")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    user_dir = os.path.join(settings.storage_path, f"user_{current_user.id}")
    os.makedirs(user_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    storage_path = os.path.join(user_dir, safe_name)
    with open(storage_path, "wb") as f:
        f.write(contents)

    document = Document(
        owner_id=current_user.id,
        filename=file.filename,
        storage_path=storage_path,
        file_size=len(contents),
        mime_type=file.content_type,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Kick off the pipeline in the background so the upload responds immediately.
    background_tasks.add_task(_run_pipeline_sync_wrapper, document.id)

    return DocumentOut.model_validate(document)


def _run_pipeline_sync_wrapper(document_id: int):
    import asyncio
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            asyncio.run(process_document(db, document))
    finally:
        db.close()


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    docs = db.query(Document).filter(Document.owner_id == current_user.id).order_by(Document.created_at.desc()).all()
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return DocumentOut.model_validate(_get_owned_document(db, document_id, current_user))


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)

    # Remove evidence references before deleting evidence rows, which are not
    # covered by the document's ORM cascades.
    for model in (Finding, Deadline, Obligation, FinancialValue):
        db.query(model).filter(model.document_id == doc.id).delete(synchronize_session=False)
    chat_session_ids = db.query(ChatSession.id).filter(ChatSession.document_id == doc.id)
    db.query(ChatMessage).filter(ChatMessage.session_id.in_(chat_session_ids)).delete(synchronize_session=False)
    db.query(Evidence).filter(Evidence.document_id == doc.id).delete(synchronize_session=False)
    db.query(AIModelLog).filter(AIModelLog.document_id == doc.id).update(
        {AIModelLog.document_id: None}, synchronize_session=False
    )

    db.delete(doc)
    db.commit()
    return {"detail": "Document deleted"}


@router.post("/{document_id}/cancel")
def cancel_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    active_statuses = {"uploaded", "processing", "extracting_text", "analyzing", "validating"}
    if doc.status == "cancelling":
        return {"detail": "Cancellation already requested", "status": doc.status}
    if doc.status not in active_statuses:
        raise HTTPException(status_code=409, detail="Document is not being processed")

    doc.status = "cancelling"
    db.commit()
    return {"detail": "Cancellation requested", "status": doc.status}


@router.post("/{document_id}/analyze")
def reanalyze_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = _get_owned_document(db, document_id, current_user)
    # Clear previous analysis artifacts before re-running
    db.query(Finding).filter(Finding.document_id == doc.id).delete()
    db.query(Deadline).filter(Deadline.document_id == doc.id).delete()
    db.query(Obligation).filter(Obligation.document_id == doc.id).delete()
    db.query(FinancialValue).filter(FinancialValue.document_id == doc.id).delete()
    db.query(Anomaly).filter(Anomaly.document_id == doc.id).delete()
    db.query(MissingData).filter(MissingData.document_id == doc.id).delete()
    db.query(Analysis).filter(Analysis.document_id == doc.id).delete()
    doc.status = "uploaded"
    db.commit()

    background_tasks.add_task(_run_pipeline_sync_wrapper, doc.id)
    return {"detail": "Re-analysis started"}


@router.get("/{document_id}/analysis", response_model=DocumentAnalysisOut)
def get_analysis(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    latest_analysis = (
        db.query(Analysis).filter(Analysis.document_id == doc.id).order_by(Analysis.created_at.desc()).first()
    )
    return DocumentAnalysisOut(
        document=DocumentOut.model_validate(doc),
        summary=latest_analysis.summary if latest_analysis else None,
        model_used=latest_analysis.model_used if latest_analysis else None,
        findings=doc.findings,
        deadlines=doc.deadlines,
        obligations=doc.obligations,
        financial_values=doc.financial_values,
        anomalies=doc.anomalies,
        missing_data=doc.missing_data,
    )


@router.get("/{document_id}/findings")
def get_findings(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    return doc.findings


@router.get("/{document_id}/deadlines")
def get_deadlines(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    return doc.deadlines


@router.get("/{document_id}/obligations")
def get_obligations(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    return doc.obligations


@router.get("/{document_id}/anomalies")
def get_anomalies(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    return doc.anomalies


@router.get("/{document_id}/pages/{page_number}")
def get_page(document_id: int, page_number: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    page = next((p for p in doc.pages if p.page_number == page_number), None)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"page_number": page.page_number, "raw_text": page.raw_text, "image_path": page.image_path}


@router.get("/{document_id}/pages/{page_number}/image")
def get_page_image(document_id: int, page_number: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = _get_owned_document(db, document_id, current_user)
    page = next((p for p in doc.pages if p.page_number == page_number), None)
    if not page or not page.image_path or not os.path.exists(page.image_path):
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(page.image_path, media_type="image/png")
