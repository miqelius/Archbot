import os
from functools import lru_cache
from urllib.parse import urlparse
from typing import Optional

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings


class DatabaseConfig:
    def __init__(self, url: str):
        self.url = url
        self.async_url = url
        parsed = urlparse(url)
        self.hostname = parsed.hostname
        self.port = parsed.port or 5432
        self.database = (parsed.path or "/postgres").lstrip("/")
        self.username = parsed.username
        self.password = parsed.password
        self.pool_size = 5
        self.max_overflow = 10
        self.pool_recycle = 3600
        self.pool_pre_ping = True
        self.echo = False
        self.poolclass = None
        self.connect_args = {}


class RedisConfig:
    def __init__(self, url: str):
        self.url = url
        parsed = urlparse(url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.db = int(parsed.path.lstrip("/") or "0")
        self.password = parsed.password
        self.username = parsed.username
        self.ssl = parsed.scheme == "rediss"
        self.decode_responses = True


class CeleryConfig:
    def __init__(self, redis_url: str):
        self.broker_url = redis_url
        self.result_backend_url = redis_url
        self.worker_prefetch_multiplier = 1
        self.worker_max_tasks_per_child = 100
        self.task_soft_time_limit = 300
        self.task_time_limit = 600
        self.task_acks_late = True
        self.task_default_retry_delay = 60


class LLMConfig:
    def __init__(self, provider: str, api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key
        if provider == "deepseek":
            self.model_name = "deepseek-chat"
        elif provider == "gemini":
            self.model_name = "gemini-pro"
        else:
            self.model_name = provider
        self.temperature = 0.3
        self.max_tokens = 4096


class AppConfig(BaseSettings):
    app_name: str = "archbot"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api"

    telegram_bot_token: str = Field("", validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "telegram_bot_token"))
    deepseek_api_key: str = Field("", validation_alias=AliasChoices("DEEPSEEK_API_KEY", "deepseek_api_key"))
    gemini_api_key: str = Field("", validation_alias=AliasChoices("GEMINI_API_KEY", "gemini_api_key"))
    database_url: str = Field("postgresql+asyncpg://user:pass@localhost:5432/archbot", validation_alias=AliasChoices("DATABASE_URL", "database_url"))
    redis_url: str = Field("redis://localhost:6379/0", validation_alias=AliasChoices("REDIS_URL", "redis_url"))

    llm_provider: str = Field("deepseek", validation_alias=AliasChoices("LLM_PROVIDER", "llm_provider"))

    @property
    def database(self):
        return DatabaseConfig(self.database_url)

    @property
    def celery(self):
        return CeleryConfig(self.redis_url)

    @property
    def redis(self):
        return RedisConfig(self.redis_url)

    @property
    def llm(self):
        api_key = self.deepseek_api_key if self.llm_provider.lower() == "deepseek" else self.gemini_api_key
        return LLMConfig(self.llm_provider.lower(), api_key)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


@lru_cache()
def get_config() -> AppConfig:
    return AppConfig()


settings: AppConfig = get_config()
