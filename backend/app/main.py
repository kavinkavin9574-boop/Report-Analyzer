import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.database import Base, engine, SessionLocal, close_db_connections
from app.core import runtime_config
from app.api import auth, documents, dashboard, chat, settings as settings_api
import app.models  # noqa: ensures all models are registered before create_all

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(title="Intelligent Business Document Analysis API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the real frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.storage_path, exist_ok=True)


@app.on_event("startup")
def on_startup():
    # For a real deployment, replace with Alembic migrations.
    Base.metadata.create_all(bind=engine)

    # Seed / load the runtime AI config from the DB so a model change made
    # from the Settings page survives a restart.
    from app.models.system_settings import SystemSettings

    db = SessionLocal()
    try:
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
    finally:
        db.close()


@app.on_event("shutdown")
def on_shutdown():
    close_db_connections()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak stack traces to clients — log server-side, return a generic message.
    print(f"[unhandled error] {request.method} {request.url}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. Please try again."})


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(chat.router)
app.include_router(settings_api.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
