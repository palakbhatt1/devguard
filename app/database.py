from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import get_settings

settings = get_settings()

db_url = settings.DATABASE_URL
connect_args = {}
engine_kwargs = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if ":memory:" in db_url:
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    import app.models.domain  # noqa: F401
    Base.metadata.create_all(bind=engine)
