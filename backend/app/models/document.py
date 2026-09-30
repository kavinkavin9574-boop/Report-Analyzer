from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    filename = Column(String(500), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)

    document_type = Column(String(50), default="other")  # invoice | contract | financial_report | compliance | po | other
    document_type_confirmed_by_user = Column(String(50), nullable=True)

    status = Column(String(50), default="uploaded")
    # uploaded -> processing -> extracting_text -> analyzing -> validating -> completed -> failed

    page_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="document", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="document", cascade="all, delete-orphan")
    deadlines = relationship("Deadline", back_populates="document", cascade="all, delete-orphan")
    obligations = relationship("Obligation", back_populates="document", cascade="all, delete-orphan")
    financial_values = relationship("FinancialValue", back_populates="document", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="document", cascade="all, delete-orphan")
    missing_data = relationship("MissingData", back_populates="document", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=True)
    used_ocr = Column(String(10), default="false")
    image_path = Column(String(1000), nullable=True)  # rendered page image, for evidence highlighting

    document = relationship("Document", back_populates="pages")
    chunks = relationship("DocumentChunk", back_populates="page", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Normalized text chunks, ready for future semantic/vector search."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("document_pages.id"), nullable=False)
    section = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # placeholder until a vector column/index is added

    page = relationship("DocumentPage", back_populates="chunks")
