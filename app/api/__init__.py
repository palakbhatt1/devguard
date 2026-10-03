"""API routes package."""

from app.api.dashboard import router as dashboard_router
from app.api.explain import router as explain_router
from app.api.rag import router as rag_router
from app.api.scan import router as scan_router
from app.api.webhooks import router as webhooks_router

__all__ = [
    "dashboard_router",
    "explain_router",
    "rag_router",
    "scan_router",
    "webhooks_router",
]
