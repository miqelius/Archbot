"""
workers/celery_app.py - Celery application factory with Redis broker
Handles background task processing for translation pipeline
"""

from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from kombu import Exchange, Queue
from typing import Optional
import logging

from core.core_config import settings

logger = logging.getLogger(__name__)


class CeleryManager:
    """
    Singleton Celery application manager.
    Configures broker, backend, and task routing.
    """
    
    _instance: Optional[Celery] = None
    
    @classmethod
    def get_app(cls) -> Celery:
        """Get or create Celery app instance"""
        if cls._instance is not None:
            return cls._instance
        
        cls._instance = Celery(settings.app_name)
        cls._configure_app()
        return cls._instance
    
    @classmethod
    def _configure_app(cls) -> None:
        """Configure Celery with all settings"""
        app = cls._instance
        celery_config = settings.celery
        redis_config = settings.redis
        
        # Broker and result backend URLs
        broker_url = celery_config.broker_url or redis_config.url
        result_backend_url = celery_config.result_backend_url or redis_config.url
        
        logger.info(f"Configuring Celery broker: {broker_url}")
        logger.info(f"Configuring Celery result backend: {result_backend_url}")
        
        # Core broker settings
        app.conf.update(
            # Broker configuration
            broker_url=broker_url,
            broker_connection_retry_on_startup=True,
            broker_connection_retry=True,
            broker_connection_max_retries=5,
            broker_pool_limit=10,
            broker_transport_options={
                "master_name": "mymaster",  # For Sentinel
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                "retry_on_timeout": True,
                "health_check_interval": 30,
            },
            
            # Result backend
            result_backend=result_backend_url,
            result_expires=3600,  # 1 hour
            result_compression="gzip",
            
            # Task serialization
            task_serializer="json",
            accept_content=["json", "msgpack"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            
            # Worker pool configuration
            worker_prefetch_multiplier=celery_config.worker_prefetch_multiplier,
            worker_max_tasks_per_child=celery_config.worker_max_tasks_per_child,
            worker_disable_rate_limits=False,  # Enable rate limiting
            
            # Task configuration
            task_soft_time_limit=celery_config.task_soft_time_limit,
            task_time_limit=celery_config.task_time_limit,
            task_acks_late=celery_config.task_acks_late,
            task_reject_on_worker_lost=True,
            
            # Retry configuration
            task_autoretry_for={
                "exc": (TimeoutError, ConnectionError),
                "max_retries": 5,
                "jitter": True,
            },
            task_default_retry_delay=celery_config.task_default_retry_delay,
            
            # Default queue routing
            task_default_queue="default",
            task_default_exchange="tasks",
            task_default_routing_key="task.default",
            
            # Event configuration
            worker_send_task_events=True,
            task_send_sent_event=True,
        )
        
        # Queue definitions with priority routing
        app.conf.task_queues = (
            Queue(
                "default",
                Exchange("tasks", type="direct"),
                routing_key="task.default",
                priority=5,
            ),
            Queue(
                "high_priority",
                Exchange("tasks", type="direct"),
                routing_key="task.high",
                priority=10,  # OCR tasks, small documents
            ),
            Queue(
                "low_priority",
                Exchange("tasks", type="direct"),
                routing_key="task.low",
                priority=1,  # Batch processing
            ),
            Queue(
                "llm_intensive",
                Exchange("tasks", type="direct"),
                routing_key="task.llm",
                priority=7,  # LLM agent pipeline
            ),
        )
        
        # Default task routing
        app.conf.task_routes = {
            "workers.tasks.process_translation_job": {
                "queue": "llm_intensive",
                "routing_key": "task.llm",
            },
            "workers.tasks.extract_document_text": {
                "queue": "high_priority",
                "routing_key": "task.high",
            },
            "workers.tasks.batch_process_jobs": {
                "queue": "low_priority",
                "routing_key": "task.low",
            },
        }
        
        logger.info("Celery application configured successfully")


# Get the Celery app singleton
app = CeleryManager.get_app()


# Signal handlers for task lifecycle monitoring
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Log before task execution"""
    logger.info(f"Task started: {task.name} [ID: {task_id}]")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, result=None, **kwargs):
    """Log after successful task execution"""
    logger.info(f"Task completed: {task.name} [ID: {task_id}] → {result}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Log task failures"""
    logger.error(f"Task failed: {sender.name} [ID: {task_id}] → {exception}")


# Task retry decorator with exponential backoff
def retry_with_backoff(
    max_retries: int = 5,
    base_delay: int = 60,
):
    """
    Decorator for automatic retry with exponential backoff.
    
    Usage:
        @retry_with_backoff(max_retries=5, base_delay=60)
        @app.task(bind=True)
        def my_task(self):
            ...
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                # Exponential backoff: 60s, 120s, 240s, 480s, 960s
                delay = base_delay * (2 ** (self.request.retries - 1))
                raise self.retry(exc=exc, countdown=delay, max_retries=max_retries)
        return wrapper
    return decorator


import services.workers_tasks
