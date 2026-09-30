from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from app.core.database import Base


class SystemSettings(Base):
    """
    Single-row table holding the AI configuration that's safe to expose in
    the UI (provider choice + model names per tier). The API key itself is
    never stored here — it stays server-side, in the environment, only.
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, default=1)
    ai_provider = Column(String(20), default="openai")
    default_model = Column(String(100), default="gpt-4o")
    fast_model = Column(String(100), default="gpt-4o-mini")
    reasoning_model = Column(String(100), default="gpt-4o")
    ocr_enabled = Column(String(10), default="true")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
