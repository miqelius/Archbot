from typing import Optional
from sqlalchemy import select
from celery import shared_task
import asyncio

from core.db_models import TranslationJobDB
from core.core_database import DatabaseManager


async def _process_translation_async(
    job_id: str,
    source_language: str,
    target_language: str,
    context: Optional[str],
) -> dict:
    DatabaseManager.initialize()
    async with DatabaseManager.session_context() as db_session:
        stmt = select(TranslationJobDB).where(
            TranslationJobDB.job_id == job_id
        )
        result = await db_session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Job {job_id} not found in database")
        
        return {"job_id": job_id, "status": "processed"}


@shared_task(bind=True)
def run_translation_task(
    self,
    job_id: str,
    source_language: str,
    target_language: str,
    context: Optional[str] = None,
):
    return asyncio.run(
        _process_translation_async(
            job_id=job_id,
            source_language=source_language,
            target_language=target_language,
            context=context,
        )
    )

# ფუნქციები, რომლებსაც api_main.py მოითხოვს:
def process_translation_job(job_id: str, source_language: str, target_language: str, context: Optional[str] = None):
    return run_translation_task.delay(job_id, source_language, target_language, context)

def extract_document_text(file_path: str):
    return "extracted text placeholder"
