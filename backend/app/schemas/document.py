from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, SecretStr


class DocumentOut(BaseModel):
    id: int
    filename: str
    document_type: str
    status: str
    page_count: int
    file_size: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvidenceOut(BaseModel):
    id: int
    page_number: int
    section: Optional[str] = None
    source_text: str
    bbox: Optional[list[float]] = None

    class Config:
        from_attributes = True


class FindingOut(BaseModel):
    id: int
    category: str
    field_name: str
    field_value: Optional[str] = None
    confidence: float
    source: str
    evidence: Optional[EvidenceOut] = None

    class Config:
        from_attributes = True


class DeadlineOut(BaseModel):
    id: int
    event: str
    value: Optional[str] = None
    absolute_date: Optional[datetime] = None
    confidence: float
    evidence: Optional[EvidenceOut] = None

    class Config:
        from_attributes = True


class ObligationOut(BaseModel):
    id: int
    responsible_party: Optional[str] = None
    action: str
    frequency: Optional[str] = None
    deadline: Optional[str] = None
    condition: Optional[str] = None
    consequence: Optional[str] = None
    confidence: float
    evidence: Optional[EvidenceOut] = None

    class Config:
        from_attributes = True


class FinancialValueOut(BaseModel):
    id: int
    label: str
    value: Optional[float] = None
    currency: Optional[str] = None
    is_calculated: bool
    evidence: Optional[EvidenceOut] = None

    class Config:
        from_attributes = True


class AnomalyOut(BaseModel):
    id: int
    title: str
    severity: str
    description: Optional[str] = None
    detection_type: str
    pages: Optional[list[int]] = None
    confidence: float

    class Config:
        from_attributes = True


class MissingDataOut(BaseModel):
    id: int
    field_name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class StructuredSummary(BaseModel):
    text: str
    key_points: list[str] = []


class DocumentAnalysisOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    document: DocumentOut
    summary: Optional[StructuredSummary | str] = None
    extracted_fields: dict[str, Any] = {}
    model_used: Optional[str] = None
    findings: list[FindingOut] = []
    deadlines: list[DeadlineOut] = []
    obligations: list[ObligationOut] = []
    financial_values: list[FinancialValueOut] = []
    anomalies: list[AnomalyOut] = []
    missing_data: list[MissingDataOut] = []


class DashboardStatsOut(BaseModel):
    documents_analyzed: int
    critical_issues: int
    warnings: int
    upcoming_deadlines: int
    missing_data_count: int
    total_financial_value: float
    documents_by_type: dict
    findings_by_severity: dict


class ChatRequest(BaseModel):
    question: str


class ChatResponseOut(BaseModel):
    answer: str
    evidence: Optional[EvidenceOut] = None


class AIModelSettingsOut(BaseModel):
    ai_provider: str
    default_model: str
    fast_model: str
    reasoning_model: str
    api_key_configured: bool  # whether an in-memory key is configured; never the key itself


class AIModelSettingsIn(BaseModel):
    ai_provider: Optional[str] = None       # "openai" or "nvidia"
    default_model: Optional[str] = None
    fast_model: Optional[str] = None
    reasoning_model: Optional[str] = None
    api_key: Optional[SecretStr] = None
