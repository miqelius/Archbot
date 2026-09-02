"""
services/llm_pipeline.py - Multi-agent pipeline orchestration
Chains Translator → Stylist → Quality Control with error handling and observability
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple
import logging
import asyncio
import json

from core.core_database import DatabaseManager
from core.db_models import TranslationJobDB, AuditLogDB, PipelineMetricsDB
from schemas.schemas_translation import (
    JobStatus,
    TranslatorAgentOutput,
    StylistAgentOutput,
    QualityControlResult,
    PipelineMetrics,
)
from services.services_agents_base import (
    AgentException,
    AgentMetrics,
    AgentProvider,
)
from services.services_agents_implementations import (
    AgentFactory,
    TranslatorAgent,
    StylistAgent,
    QualityControlAgent,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Mutable state tracking through pipeline execution"""
    
    job_id: str
    original_text: str
    
    # Stage outputs
    draft_translation: Optional[str] = None
    styled_translation: Optional[str] = None
    final_translation: Optional[str] = None
    quality_report: Optional[QualityControlResult] = None
    
    # Metrics per stage
    translator_metrics: Optional[AgentMetrics] = None
    stylist_metrics: Optional[AgentMetrics] = None
    qa_metrics: Optional[AgentMetrics] = None
    
    # Timestamps
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    @property
    def total_duration_seconds(self) -> float:
        """Total pipeline execution time"""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def total_input_tokens(self) -> int:
        """Sum of input tokens across all stages"""
        return sum([
            m.input_tokens if m else 0
            for m in [self.translator_metrics, self.stylist_metrics, self.qa_metrics]
        ])
    
    @property
    def total_output_tokens(self) -> int:
        """Sum of output tokens across all stages"""
        return sum([
            m.output_tokens if m else 0
            for m in [self.translator_metrics, self.stylist_metrics, self.qa_metrics]
        ])


class TranslationPipeline:
    """
    Orchestrates multi-agent translation pipeline.
    Handles:
    - Agent chaining (Translator → Stylist → QA)
    - Error recovery (validation, retries, fallback)
    - Database persistence
    - Audit logging
    - Metrics collection
    """
    
    def __init__(
        self,
        provider: AgentProvider = AgentProvider.ANTHROPIC,
        min_quality_score: int = 75,
    ):
        self.provider = provider
        self.min_quality_score = min_quality_score
        
        # Initialize agents
        self.translator = AgentFactory.create_translator(provider=provider)
        self.stylist = AgentFactory.create_stylist(provider=provider)
        self.qa = AgentFactory.create_qa(
            provider=provider,
            min_quality_score=min_quality_score
        )
        self.validator = AgentFactory.create_validator()
        
        self.logger = logging.getLogger("Pipeline")
    
    async def execute(
        self,
        job_id: str,
        original_text: str,
        source_language: str = "ka",
        target_language: str = "en",
        context: Optional[str] = None,
        db_session=None,
    ) -> Tuple[PipelineState, bool]:
        """
        Execute complete translation pipeline.
        
        Args:
            job_id: Unique job identifier
            original_text: Text to translate
            source_language: Source language code
            target_language: Target language code
            context: Additional context (historical, domain-specific)
            db_session: Database session for persistence
        
        Returns:
            (pipeline_state, success)
            - pipeline_state: Complete execution state with all outputs
            - success: Whether pipeline completed successfully
        """
        state = PipelineState(
            job_id=job_id,
            original_text=original_text
        )
        
        try:
            self.logger.info(
                f"Starting pipeline for job {job_id}: "
                f"{source_language}→{target_language}"
            )
            
            # Stage 1: Translation
            await self._run_stage(
                stage_name="translation",
                agent=self.translator,
                input_data=original_text,
                state=state,
                agent_kwargs={
                    "source_language": source_language,
                    "target_language": target_language,
                    "context": context or "",
                },
                db_session=db_session,
                job_id=job_id,
            )
            
            if not state.draft_translation:
                raise RuntimeError("Translation stage produced no output")
            
            # Stage 2: Stylization
            await self._run_stage(
                stage_name="stylization",
                agent=self.stylist,
                input_data=state.draft_translation,
                state=state,
                agent_kwargs={
                    "original_text": original_text,
                    "context": context or "",
                },
                db_session=db_session,
                job_id=job_id,
            )
            
            if not state.styled_translation:
                raise RuntimeError("Stylization stage produced no output")
            
            # Stage 3: Quality Control
            await self._run_stage(
                stage_name="quality_control",
                agent=self.qa,
                input_data=state.styled_translation,
                state=state,
                agent_kwargs={
                    "original_text": original_text,
                    "draft_translation": state.draft_translation,
                    "context": context or "",
                },
                db_session=db_session,
                job_id=job_id,
            )
            
            # Extract final translation from QA report
            if state.quality_report:
                state.final_translation = state.quality_report.final_text
            else:
                state.final_translation = state.styled_translation
            
            state.end_time = datetime.utcnow()
            
            self.logger.info(
                f"Pipeline completed successfully for job {job_id} "
                f"({state.total_duration_seconds:.2f}s)"
            )
            
            # Persist results to database
            if db_session:
                await self._persist_results(state, db_session)
            
            return state, True
        
        except Exception as e:
            state.end_time = datetime.utcnow()
            self.logger.error(
                f"Pipeline failed for job {job_id}: {e}",
                exc_info=True
            )
            
            # Log failure
            if db_session:
                await self._log_failure(job_id, str(e), db_session)
            
            return state, False
    
    async def _run_stage(
        self,
        stage_name: str,
        agent,
        input_data: str,
        state: PipelineState,
        agent_kwargs: dict,
        db_session=None,
        job_id: str = "",
    ) -> None:
        """
        Run a single pipeline stage with error handling and logging.
        
        Args:
            stage_name: Name of the stage (translation, stylization, quality_control)
            agent: Agent instance to execute
            input_data: Input for the agent
            state: Mutable pipeline state to update
            agent_kwargs: Kwargs to pass to agent.execute()
            db_session: Database session for audit logging
            job_id: Job identifier for logging
        """
        self.logger.info(f"Starting stage: {stage_name}")
        
        try:
            # Execute agent with retries and metrics collection
            output, metrics = await agent.execute(
                input_data,
                output_type=agent.get_output_schema(),
                **agent_kwargs
            )
            
            # Store metrics based on stage
            if stage_name == "translation":
                state.translator_metrics = metrics
                if isinstance(output, TranslatorAgentOutput):
                    state.draft_translation = output.draft_translation
            
            elif stage_name == "stylization":
                state.stylist_metrics = metrics
                if isinstance(output, StylistAgentOutput):
                    state.styled_translation = output.styled_translation
            
            elif stage_name == "quality_control":
                state.qa_metrics = metrics
                if isinstance(output, QualityControlResult):
                    state.quality_report = output
            
            # Audit log
            if db_session:
                await self._log_event(
                    job_id=job_id,
                    stage=stage_name,
                    event_type="completed",
                    message=f"{stage_name} completed successfully",
                    metadata=metrics.to_dict(),
                    db_session=db_session,
                )
            
            self.logger.info(
                f"{stage_name} completed: {metrics.duration_seconds:.2f}s, "
                f"{metrics.total_tokens} tokens"
            )
        
        except Exception as e:
            self.logger.error(f"{stage_name} failed: {e}", exc_info=True)
            
            if db_session:
                await self._log_event(
                    job_id=job_id,
                    stage=stage_name,
                    event_type="failed",
                    message=f"{stage_name} failed",
                    error_type=type(e).__name__,
                    error_details=str(e),
                    db_session=db_session,
                )
            
            raise
    
    async def _persist_results(
        self,
        state: PipelineState,
        db_session,
    ) -> None:
        """Save pipeline results to database"""
        from sqlalchemy import select
        
        try:
            # Fetch existing job record
            stmt = select(TranslationJobDB).where(
                TranslationJobDB.job_id == state.job_id
            )
            result = await db_session.execute(stmt)
            job = result.scalar_one_or_none()
            
            if not job:
                self.logger.error(f"Job {state.job_id} not found in database")
                return
            
            # Update job with pipeline results
            job.draft_translation = state.draft_translation
            job.styled_translation = state.styled_translation
            job.final_translation = state.final_translation
            
            # Serialize quality report
            if state.quality_report:
                job.quality_report = state.quality_report.model_dump()
            
            job.status = (
                JobStatus.completed
                if state.quality_report and state.quality_report.approved
                else JobStatus.reviewing
            )
            job.completed_at = state.end_time
            job.translator_model = state.translator_metrics.model_name if state.translator_metrics else "unknown"
            job.stylist_model = state.stylist_metrics.model_name if state.stylist_metrics else "unknown"
            job.qa_model = state.qa_metrics.model_name if state.qa_metrics else "unknown"
            
            await db_session.commit()
            
            # Also save detailed metrics
            metrics_record = PipelineMetricsDB(
                job_id=job.id,
                total_duration_seconds=state.total_duration_seconds,
                translator_duration_seconds=(
                    state.translator_metrics.duration_seconds
                    if state.translator_metrics else 0
                ),
                stylist_duration_seconds=(
                    state.stylist_metrics.duration_seconds
                    if state.stylist_metrics else 0
                ),
                qa_duration_seconds=(
                    state.qa_metrics.duration_seconds
                    if state.qa_metrics else 0
                ),
                translator_input_tokens=(
                    state.translator_metrics.input_tokens
                    if state.translator_metrics else 0
                ),
                translator_output_tokens=(
                    state.translator_metrics.output_tokens
                    if state.translator_metrics else 0
                ),
                stylist_input_tokens=(
                    state.stylist_metrics.input_tokens
                    if state.stylist_metrics else 0
                ),
                stylist_output_tokens=(
                    state.stylist_metrics.output_tokens
                    if state.stylist_metrics else 0
                ),
                qa_input_tokens=(
                    state.qa_metrics.input_tokens
                    if state.qa_metrics else 0
                ),
                qa_output_tokens=(
                    state.qa_metrics.output_tokens
                    if state.qa_metrics else 0
                ),
                quality_score=(
                    state.quality_report.score
                    if state.quality_report else 0
                ),
                issues_found=len(
                    state.quality_report.issues
                    if state.quality_report else []
                ),
            )
            
            db_session.add(metrics_record)
            await db_session.commit()
            
            self.logger.info(f"Pipeline results persisted for job {state.job_id}")
        
        except Exception as e:
            self.logger.error(f"Failed to persist results: {e}", exc_info=True)
            await db_session.rollback()
    
    async def _log_event(
        self,
        job_id: str,
        stage: str,
        event_type: str,
        message: str,
        metadata: Optional[dict] = None,
        error_type: Optional[str] = None,
        error_details: Optional[str] = None,
        db_session=None,
    ) -> None:
        """Log audit event to database"""
        if not db_session:
            return
        
        try:
            from sqlalchemy import select
            
            # Fetch job by job_id
            stmt = select(TranslationJobDB).where(
                TranslationJobDB.job_id == job_id
            )
            result = await db_session.execute(stmt)
            job = result.scalar_one_or_none()
            
            if not job:
                return
            
            log = AuditLogDB(
                job_id=job.id,
                stage=stage,
                event_type=event_type,
                message=message,
                metadata=metadata,
                error_type=error_type,
                error_details=error_details,
            )
            
            db_session.add(log)
            await db_session.commit()
        
        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")
    
    async def _log_failure(
        self,
        job_id: str,
        error_message: str,
        db_session,
    ) -> None:
        """Log pipeline failure"""
        from sqlalchemy import select
        
        try:
            stmt = select(TranslationJobDB).where(
                TranslationJobDB.job_id == job_id
            )
            result = await db_session.execute(stmt)
            job = result.scalar_one_or_none()
            
            if job:
                job.status = JobStatus.failed
                job.error_message = error_message
                job.completed_at = datetime.utcnow()
                await db_session.commit()
        
        except Exception as e:
            self.logger.error(f"Failed to log pipeline failure: {e}")
