"""
schemas/translation.py - Pydantic V2 schemas for multi-agent pipeline
Supports structured JSON output from LLM models via function calling
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class SourceType(str, Enum):
    """Input source type"""
    text = "text"
    photo = "photo"
    document = "document"


class JobStatus(str, Enum):
    """Job execution status"""
    pending = "pending"
    processing = "processing"
    translating = "translating"
    reviewing = "reviewing"
    completed = "completed"
    failed = "failed"


class IssueType(str, Enum):
    """Quality control issue classification"""
    grammar = "grammar"
    tone = "tone"
    context = "context"
    terminology = "terminology"
    cultural = "cultural"
    historical = "historical"
    other = "other"


# ============================================================================
# Quality Control Schemas (QA Agent Output)
# ============================================================================

class QualityIssue(BaseModel):
    """Single quality control issue found during review"""
    
    issue_type: IssueType = Field(
        description="Category of the issue"
    )
    location: str = Field(
        description="Where in the text the issue was found (phrase or context)"
    )
    description: str = Field(
        description="Detailed explanation of the issue and why it matters"
    )
    suggestion: Optional[str] = Field(
        default=None,
        description="Suggested fix or improvement"
    )
    severity: int = Field(
        ge=1,
        le=5,
        description="Severity level: 1=minor, 5=critical"
    )


class QualityControlResult(BaseModel):
    """
    Structured output from Quality Control (QA) agent.
    This is what the LLM returns via function calling.
    """
    
    score: int = Field(
        ge=0,
        le=100,
        description="Overall translation quality score (0-100)"
    )
    issues: List[QualityIssue] = Field(
        default_factory=list,
        description="List of quality issues found"
    )
    approved: bool = Field(
        description="Whether the translation meets quality standards"
    )
    final_text: str = Field(
        description="Final, corrected translation ready for delivery"
    )
    recommendations: Optional[str] = Field(
        default=None,
        description="General recommendations for improvement"
    )
    
    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if not (0 <= v <= 100):
            raise ValueError("Score must be between 0 and 100")
        return v
    
    @field_validator("issues")
    @classmethod
    def validate_issues_not_empty_if_rejected(cls, v: List[QualityIssue], info) -> List[QualityIssue]:
        """Warn if text rejected but no issues listed"""
        if len(v) == 0 and not info.data.get("approved", True):
            # Validation passes, but this should be logged
            pass
        return v


# ============================================================================
# Agent Output Schemas (Internal Pipeline)
# ============================================================================

class TranslatorAgentOutput(BaseModel):
    """Output from Translator agent"""
    
    source_text: str = Field(description="Original text provided to translator")
    draft_translation: str = Field(
        description="Initial translation without stylization"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the translation"
    )
    terminology_notes: Optional[str] = Field(
        default=None,
        description="Notes on key terminology and translation choices"
    )
    model_name: str = Field(description="Model used for translation")


class StylistAgentOutput(BaseModel):
    """Output from Stylist agent"""
    
    draft_translation: str = Field(description="Input translation from Translator")
    styled_translation: str = Field(
        description="Translation with historical-diplomatic style applied"
    )
    style_notes: Optional[str] = Field(
        default=None,
        description="Notes on stylization choices and tone adjustments"
    )
    tone_indicators: List[str] = Field(
        default_factory=list,
        description="List of stylistic elements applied (e.g., 'formal', 'archaic', 'diplomatic')"
    )
    model_name: str = Field(description="Model used for stylization")


class QAAgentOutput(BaseModel):
    """Output from Quality Control agent (includes structured QualityControlResult)"""
    
    styled_translation: str = Field(description="Input styled translation from Stylist")
    quality_report: QualityControlResult = Field(
        description="Structured quality assessment with score and issues"
    )
    review_notes: Optional[str] = Field(
        default=None,
        description="Additional notes from quality review"
    )
    model_name: str = Field(description="Model used for quality assessment")


# ============================================================================
# Job Request/Response Schemas (API)
# ============================================================================

class TranslationJobRequest(BaseModel):
    """API request to create a translation job"""
    
    telegram_user_id: str = Field(description="Telegram user ID")
    telegram_username: Optional[str] = Field(
        default=None,
        description="Telegram username (for UI purposes)"
    )
    source_type: SourceType = Field(description="Type of source input")
    source_language: Optional[str] = Field(
        default="ka",
        description="ISO 639-1 language code (default: Georgian)"
    )
    target_language: Optional[str] = Field(
        default="en",
        description="ISO 639-1 language code (default: English)"
    )
    
    # One of these must be provided
    text: Optional[str] = Field(
        default=None,
        description="Raw text to translate (if source_type=text)"
    )
    file_url: Optional[str] = Field(
        default=None,
        description="URL or local path to document/image (if source_type=document or photo)"
    )
    file_bytes: Optional[bytes] = Field(
        default=None,
        description="Raw file bytes (if uploading directly)"
    )
    
    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, v: Optional[str], info) -> Optional[str]:
        source_type = info.data.get("source_type")
        if source_type == SourceType.text and not v:
            raise ValueError("text is required when source_type=text")
        if v and len(v.strip()) < 10:
            raise ValueError("Text must be at least 10 characters")
        return v
    
    @field_validator("file_url", mode="before")
    @classmethod
    def validate_file_url(cls, v: Optional[str], info) -> Optional[str]:
        source_type = info.data.get("source_type")
        if source_type != SourceType.text and not v:
            raise ValueError(f"file_url is required when source_type={source_type}")
        return v


class TranslationJobResponse(BaseModel):
    """API response after job creation"""
    
    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Current job status")
    created_at: datetime = Field(description="Job creation timestamp")
    message: str = Field(description="Status message for user")


class TranslationJobStatus(BaseModel):
    """Current status of a translation job"""
    
    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Current execution status")
    progress_percent: int = Field(
        ge=0,
        le=100,
        description="Overall progress percentage"
    )
    created_at: datetime = Field(description="Job creation timestamp")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Job completion timestamp"
    )


class TranslationJobResult(BaseModel):
    """Complete translation result"""
    
    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Final status")
    
    # Input information
    source_type: SourceType = Field(description="Type of source")
    source_language: str = Field(description="Source language code")
    target_language: str = Field(description="Target language code")
    original_text: Optional[str] = Field(
        default=None,
        description="Original input text (or excerpt if large document)"
    )
    
    # Pipeline outputs
    draft_translation: Optional[str] = Field(
        default=None,
        description="Raw translation before styling"
    )
    styled_translation: Optional[str] = Field(
        default=None,
        description="Translation with historical-diplomatic style"
    )
    final_translation: Optional[str] = Field(
        default=None,
        description="Final translation after quality control"
    )
    
    # Quality metrics
    quality_report: Optional[QualityControlResult] = Field(
        default=None,
        description="Detailed quality assessment and corrections"
    )
    
    # Metadata
    created_at: datetime = Field(description="Job creation time")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Job completion time"
    )
    pipeline_version: str = Field(
        default="1.0.0",
        description="Version of the translation pipeline used"
    )


class PipelineMetrics(BaseModel):
    """Metrics for pipeline performance tracking"""
    
    job_id: str = Field(description="Job identifier")
    total_duration_seconds: float = Field(description="Total pipeline execution time")
    translator_duration_seconds: float = Field(description="Translator agent time")
    stylist_duration_seconds: float = Field(description="Stylist agent time")
    qa_duration_seconds: float = Field(description="Quality control agent time")
    input_tokens: int = Field(description="Total input tokens used across all agents")
    output_tokens: int = Field(description="Total output tokens generated")
    translator_model: str = Field(description="Model used by translator")
    stylist_model: str = Field(description="Model used by stylist")
    qa_model: str = Field(description="Model used by QA agent")
    quality_score: int = Field(description="Final quality score (0-100)")


# ============================================================================
# Batch Processing Schemas
# ============================================================================

class BatchJobRequest(BaseModel):
    """Request for batch translation of multiple documents"""
    
    telegram_user_id: str = Field(description="User requesting batch job")
    jobs: List[TranslationJobRequest] = Field(
        min_items=1,
        max_items=100,
        description="List of translation jobs"
    )
    priority: str = Field(
        default="normal",
        description="Queue priority: low, normal, high"
    )


class BatchJobResult(BaseModel):
    """Result of batch translation"""
    
    batch_id: str = Field(description="Batch identifier")
    total_jobs: int = Field(description="Total jobs in batch")
    completed_jobs: int = Field(description="Successfully completed jobs")
    failed_jobs: int = Field(description="Failed jobs")
    results: List[TranslationJobResult] = Field(
        description="Individual job results"
    )
