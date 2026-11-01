import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import dashboard_router, explain_router, rag_router, scan_router, webhooks_router
from app.config import get_settings
from app.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("devguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting AI DevGuard service...")
    init_db()
    logger.info("Database tables initialized.")
    yield
    logger.info("Shutting down AI DevGuard service...")


settings = get_settings()

app = FastAPI(
    title="AI DevGuard",
    description="Automated Secret Scanner, Error Explainer, and CI Failure Analyzer",
    version="0.1.0",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Include routers
app.include_router(dashboard_router)
app.include_router(scan_router)
app.include_router(explain_router)
app.include_router(rag_router)
app.include_router(webhooks_router)

# Mount static files
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")


@app.get("/health")
def health_check():
    """Service health check endpoint."""
    return {"status": "ok", "env": settings.APP_ENV, "llm_provider": settings.LLM_PROVIDER}
