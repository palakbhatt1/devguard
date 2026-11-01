from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Repository(Base):
    """Git repository model."""

    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    findings = relationship("Finding", back_populates="repository", cascade="all, delete-orphan")
    workflow_analyses = relationship(
        "WorkflowAnalysis", back_populates="repository", cascade="all, delete-orphan"
    )


class Finding(Base):
    """Secret scanner finding table."""

    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    file_path = Column(String(512), nullable=False)
    line_number = Column(Integer, nullable=False)
    rule_name = Column(String(100), nullable=False)
    masked_value = Column(String(255), nullable=False)
    entropy_score = Column(Float, nullable=False)
    is_real_secret = Column(Boolean, default=True)
    is_false_positive = Column(Boolean, default=False)
    reasoning = Column(Text, nullable=True)
    context_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repository = relationship("Repository", back_populates="findings")


class WorkflowAnalysis(Base):
    """CI workflow log analysis table."""

    __tablename__ = "workflow_analyses"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    workflow_name = Column(String(255), nullable=False)
    job_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=True)
    failure_category = Column(String(100), nullable=False)
    root_cause = Column(Text, nullable=False)
    suggested_fix = Column(Text, nullable=False)
    confidence = Column(Float, default=0.9)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repository = relationship("Repository", back_populates="workflow_analyses")


class ErrorExplanation(Base):
    """Parsed error traceback explanation table."""

    __tablename__ = "error_explanations"

    id = Column(Integer, primary_key=True, index=True)
    exception_type = Column(String(255), nullable=False)
    summary = Column(String(512), nullable=False)
    root_cause = Column(Text, nullable=False)
    suggested_fix = Column(Text, nullable=False)
    file_path = Column(String(512), nullable=True)
    line_number = Column(Integer, nullable=True)
    fixed_code_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
