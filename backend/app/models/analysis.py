from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Float, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    summary = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="analyses")


class Evidence(Base):
    """Shared evidence pointer, reused by findings/deadlines/obligations/anomalies."""

    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    section = Column(String(255), nullable=True)
    source_text = Column(Text, nullable=False)
    bbox = Column(JSON, nullable=True)  # [x0, y0, x1, y1]


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    category = Column(String(100), nullable=False)  # extraction | compliance | general
    field_name = Column(String(255), nullable=False)
    field_value = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True)
    source = Column(String(50), default="ai")  # ai | calculated | rule

    document = relationship("Document", back_populates="findings")


class Deadline(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    event = Column(String(255), nullable=False)
    value = Column(String(255), nullable=True)         # e.g. "30 days"
    absolute_date = Column(DateTime, nullable=True)     # only when a reference date is known
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True)
    confidence = Column(Float, default=0.0)

    document = relationship("Document", back_populates="deadlines")


class Obligation(Base):
    __tablename__ = "obligations"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    responsible_party = Column(String(255), nullable=True)
    action = Column(Text, nullable=False)
    frequency = Column(String(100), nullable=True)
    deadline = Column(String(255), nullable=True)
    condition = Column(Text, nullable=True)
    consequence = Column(Text, nullable=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True)
    confidence = Column(Float, default=0.0)

    document = relationship("Document", back_populates="obligations")


class FinancialValue(Base):
    __tablename__ = "financial_values"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    label = Column(String(255), nullable=False)   # e.g. "subtotal", "total", "revenue"
    value = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True)
    is_calculated = Column(Boolean, default=False)  # True = deterministic Python calc, False = extracted
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True)

    document = relationship("Document", back_populates="financial_values")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    title = Column(String(500), nullable=False)
    severity = Column(String(20), default="medium")  # low | medium | high | critical
    description = Column(Text, nullable=True)
    detection_type = Column(String(20), default="rule")  # rule | ai
    pages = Column(JSON, nullable=True)          # list[int]
    evidence_ids = Column(JSON, nullable=True)   # list[int]
    confidence = Column(Float, default=0.0)

    document = relationship("Document", back_populates="anomalies")


class MissingData(Base):
    __tablename__ = "missing_data"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    field_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    document = relationship("Document", back_populates="missing_data")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class AIModelLog(Base):
    __tablename__ = "ai_model_logs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    task = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    processing_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
