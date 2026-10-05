from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core import runtime_config
from app.models.user import User
from app.models.system_settings import SystemSettings
from app.schemas.document import AIModelSettingsOut, AIModelSettingsIn

router = APIRouter(prefix="/api/settings", tags=["settings"])
settings = get_settings()

VALID_PROVIDERS = {"openai", "nvidia", "openrouter"}

# A curated list the frontend can suggest — not enforced server-side, since
# OpenAI adds models faster than this list could stay accurate. Any string
# is accepted; this is just for a helpful dropdown.
SUGGESTED_MODELS = [
    "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o4-mini", "o3",
]


def _get_or_create_row(db: Session) -> SystemSettings:
    row = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not row:
        row = SystemSettings(
            id=1,
            ai_provider=settings.ai_provider,
            default_model=settings.openai_default_model,
            fast_model=settings.openai_fast_model,
            reasoning_model=settings.openai_reasoning_model,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    if runtime_config.migrate_retired_nvidia_models(row):
        db.commit()
        db.refresh(row)
        runtime_config.load_from_row(row)
    return row


@router.get("/ai-models", response_model=AIModelSettingsOut)
def get_ai_model_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _get_or_create_row(db)
    return AIModelSettingsOut(
        ai_provider=row.ai_provider,
        default_model=row.default_model,
        fast_model=row.fast_model,
        reasoning_model=row.reasoning_model,
        api_key_configured=bool(runtime_config.get_api_key()),
    )


@router.put("/ai-models", response_model=AIModelSettingsOut)
def update_ai_model_settings(
    payload: AIModelSettingsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # NOTE: in production, gate this behind `current_user.role == "admin"` —
    # left open here so the Settings page is usable without a separate admin
    # bootstrap step.
    row = _get_or_create_row(db)
    provider_changed = payload.ai_provider is not None and payload.ai_provider != row.ai_provider

    if payload.ai_provider is not None and payload.ai_provider in VALID_PROVIDERS:
        row.ai_provider = payload.ai_provider
    if payload.default_model:
        row.default_model = payload.default_model
    if payload.fast_model:
        row.fast_model = payload.fast_model
    if payload.reasoning_model:
        row.reasoning_model = payload.reasoning_model

    db.commit()
    db.refresh(row)

    # Apply immediately — no restart needed.
    runtime_config.load_from_row(row)
    if "api_key" in payload.model_fields_set:
        key = payload.api_key.get_secret_value().strip() if payload.api_key else ""
        runtime_config.set_api_key(key or None)
    elif provider_changed:
        runtime_config.set_api_key(None)

    return AIModelSettingsOut(
        ai_provider=row.ai_provider,
        default_model=row.default_model,
        fast_model=row.fast_model,
        reasoning_model=row.reasoning_model,
        api_key_configured=bool(runtime_config.get_api_key()),
    )


@router.delete("/ai-models/api-key", response_model=AIModelSettingsOut)
def remove_api_key(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _get_or_create_row(db)
    runtime_config.set_api_key(None)
    return AIModelSettingsOut(
        ai_provider=row.ai_provider,
        default_model=row.default_model,
        fast_model=row.fast_model,
        reasoning_model=row.reasoning_model,
        api_key_configured=False,
    )


@router.get("/ai-models/suggestions")
def get_model_suggestions(current_user: User = Depends(get_current_user)):
    return {"models": SUGGESTED_MODELS}
