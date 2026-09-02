"""
db/models.py - SQLAlchemy 2.0 async ORM models
Full type hints, JSON fields for structured data, and proper indexing
"""

from sqlalchemy import (
    DateTime, Integer, String, Text, Enum as SQLEnum, JSON, Float,
    Index, UniqueConstraint, CheckConstraint, ForeignKey,
    event, Column
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone
from typing import Optional, List, Any
import json

from core.core_database import Base
from schemas.schemas_translation import SourceType, JobStatus


# ============================================================================
# Core Translation Job Model
# ============================================================================

class TranslationJobDB(Base):
    """
    Main translation job record.
    Tracks a document/text through the entire multi-agent pipeline.
    """
    
    __tablename__ = "translation_jobs"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Identifiers (indexed for fast lookup)
    job_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        comment="UUID for external API references"
    )
    telegram_user_id: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        comment="Telegram user ID"
    )
    telegram_username: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Telegram username for UI"
    )
    
    # Input metadata
    source_type: Mapped[SourceType] = mapped_column(
        SQLEnum(SourceType),
        nullable=False,
        comment="text, photo, or document"
    )
    source_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="ka",
        comment="ISO 639-1 language code"
    )
    target_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="ISO 639-1 language code"
    )
    
    # Pipeline stage outputs (nullable until completed)
    original_text: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Extracted or provided original text"
    )
    draft_translation: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Raw translation from Translator agent"
    )
    styled_translation: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Stylized translation from Stylist agent"
    )
    final_translation: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Final translation after QA agent corrections"
    )
    
    # Quality Control report (structured JSON)
    quality_report: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="QA agent output: score, issues, approved flag, recommendations"
    )
    
    # Job status and progress
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus),
        default=JobStatus.pending,
        nullable=False,
        index=True,
        comment="pending → processing → translating → reviewing → completed/failed"
    )
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Error details if job failed"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of retries attempted"
    )
    
    # Model and version tracking (for A/B testing)
    translator_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="claude-3-5-sonnet-20241022",
        comment="Model used by Translator agent"
    )
    stylist_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="claude-3-5-sonnet-20241022",
        comment="Model used by Stylist agent"
    )
    qa_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="claude-3-5-sonnet-20241022",
        comment="Model used by QA agent"
    )
    pipeline_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Pipeline version for tracking changes"
    )
    
    # Timing and metrics
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Job creation timestamp"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Pipeline execution start time"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True,
        comment="Job completion timestamp"
    )
    
    # Computed fields (for query optimization)
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Total pipeline execution duration"
    )
    
    # Relationships
    audit_logs: Mapped[List["AuditLogDB"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    pipeline_metrics: Mapped[Optional["PipelineMetricsDB"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin"
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_user_status", "telegram_user_id", "status"),
        Index("idx_created_status", "created_at", "status"),
        Index("idx_job_id_status", "job_id", "status"),
        UniqueConstraint("job_id", name="uq_job_id"),
    )
    
    def __repr__(self) -> str:
        return f"<TranslationJob job_id={self.job_id} status={self.status}>"


# ============================================================================
# Audit and Metrics Models
# ============================================================================

class AuditLogDB(Base):
    """
    Audit trail for each step of the pipeline.
    Enables debugging and tracing of issues.
    """
    
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("translation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Stage and status information
    stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="extraction, translation, stylization, qa"
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="started, completed, failed, retried"
    )
    
    # Details
    message: Mapped[str] = mapped_column(
        Text,
        comment="Event description"
    )
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        comment="Additional structured data (tokens used, latency, etc)"
    )
    
    # Error tracking
    error_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Exception type if event_type=failed"
    )
    error_details: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Full traceback if failure"
    )
    
    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationship
    job: Mapped[TranslationJobDB] = relationship(
        back_populates="audit_logs"
    )
    
    __table_args__ = (
        Index("idx_job_stage", "job_id", "stage"),
        Index("idx_job_event", "job_id", "event_type"),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog job_id={self.job_id} stage={self.stage} event={self.event_type}>"


class PipelineMetricsDB(Base):
    """
    Performance metrics for the complete pipeline.
    Used for monitoring and optimization.
    """
    
    __tablename__ = "pipeline_metrics"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("translation_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Execution times (in seconds)
    total_duration_seconds: Mapped[float] = mapped_column(Float)
    extraction_duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    translator_duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    stylist_duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    qa_duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    
    # Token usage (for cost tracking and optimization)
    extraction_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    extraction_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    translator_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    translator_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    stylist_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    stylist_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    qa_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    qa_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Quality metrics
    quality_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Final quality score (0-100)"
    )
    issues_found: Mapped[int] = mapped_column(Integer, default=0)
    issues_critical: Mapped[int] = mapped_column(Integer, default=0)
    
    # Cost estimate (assuming per-token pricing)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Relationship
    job: Mapped[TranslationJobDB] = relationship(
        back_populates="pipeline_metrics"
    )
    
    @property
    def total_input_tokens(self) -> int:
        """Calculate total input tokens across all stages"""
        return (
            self.extraction_input_tokens
            + self.translator_input_tokens
            + self.stylist_input_tokens
            + self.qa_input_tokens
        )
    
    @property
    def total_output_tokens(self) -> int:
        """Calculate total output tokens across all stages"""
        return (
            self.extraction_output_tokens
            + self.translator_output_tokens
            + self.stylist_output_tokens
            + self.qa_output_tokens
        )
    
    def __repr__(self) -> str:
        return (
            f"<PipelineMetrics job_id={self.job_id} "
            f"duration={self.total_duration_seconds:.2f}s cost=${self.estimated_cost_usd:.4f}>"
        )


# ============================================================================
# Event listeners for automatic computations
# ============================================================================

@event.listens_for(TranslationJobDB, "before_update")
def update_duration_on_completion(mapper, connection, target):
    """Automatically compute duration when job completes"""
    if target.status == JobStatus.completed and target.completed_at and target.started_at:
        delta = target.completed_at - target.started_at
        target.duration_seconds = delta.total_seconds()


# ============================================================================
# User Activity Tracking (Optional)
# ============================================================================

class UserStatsDB(Base):
    """
    Aggregated user statistics for analytics and rate limiting.
    """
    
    __tablename__ = "user_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    telegram_user_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )
    
    # Counters
    total_jobs: Mapped[int] = mapped_column(Integer, default=0)
    successful_jobs: Mapped[int] = mapped_column(Integer, default=0)
    failed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    
    # Aggregated metrics
    total_characters_translated: Mapped[int] = mapped_column(Integer, default=0)
    avg_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Timing
    first_job_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_job_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_last_job", "last_job_at"),
    )
    
    def __repr__(self) -> str:
        return f"<UserStats user_id={self.telegram_user_id} jobs={self.total_jobs}>"
