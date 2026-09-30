from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.analysis import Anomaly, MissingData, FinancialValue
from app.schemas.document import DashboardStatsOut

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc_ids = [d.id for d in db.query(Document.id).filter(Document.owner_id == current_user.id).all()]

    documents_analyzed = (
        db.query(func.count(Document.id))
        .filter(Document.owner_id == current_user.id, Document.status == "completed")
        .scalar() or 0
    )

    severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    if doc_ids:
        rows = (
            db.query(Anomaly.severity, func.count(Anomaly.id))
            .filter(Anomaly.document_id.in_(doc_ids))
            .group_by(Anomaly.severity)
            .all()
        )
        for severity, count in rows:
            severity_counts[severity] = count

    critical_issues = severity_counts.get("critical", 0) + severity_counts.get("high", 0)
    warnings = severity_counts.get("medium", 0) + severity_counts.get("low", 0)

    missing_data_count = (
        db.query(func.count(MissingData.id)).filter(MissingData.document_id.in_(doc_ids)).scalar()
        if doc_ids else 0
    ) or 0

    total_financial_value = 0.0
    if doc_ids:
        total_financial_value = (
            db.query(func.coalesce(func.sum(FinancialValue.value), 0.0))
            .filter(FinancialValue.document_id.in_(doc_ids), FinancialValue.label == "stated_total")
            .scalar() or 0.0
        )

    documents_by_type: dict = {}
    if doc_ids:
        rows = (
            db.query(Document.document_type, func.count(Document.id))
            .filter(Document.owner_id == current_user.id)
            .group_by(Document.document_type)
            .all()
        )
        documents_by_type = {t: c for t, c in rows}

    return DashboardStatsOut(
        documents_analyzed=documents_analyzed,
        critical_issues=critical_issues,
        warnings=warnings,
        upcoming_deadlines=0,  # requires resolving relative deadlines to dates — future work
        missing_data_count=missing_data_count,
        total_financial_value=float(total_financial_value),
        documents_by_type=documents_by_type,
        findings_by_severity=severity_counts,
    )
