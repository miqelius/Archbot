from celery import Celery
import os

# Redis-ის URL-ის აღება გარემოს ცვლადებიდან, ან ლოკალური სტანდარტულის გამოყენება
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "archbot",
    broker=redis_url,
    backend=redis_url
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
