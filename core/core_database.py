"""
core/database.py - Async SQLAlchemy 2.0 engine & session factory
Handles both FastAPI dependency injection and Celery worker context
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
    async_scoped_session,
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import logging

from core.core_config import settings

logger = logging.getLogger(__name__)

# Base class for all ORM models
Base = declarative_base()


class DatabaseManager:
    """
    Singleton database manager for connection pooling and session lifecycle.
    Works with both FastAPI (async context) and Celery (sync context via run_async).
    """
    
    _instance: Optional['DatabaseManager'] = None
    _engine: Optional[AsyncEngine] = None
    _async_session_factory: Optional[async_sessionmaker] = None
    _scoped_session: Optional[async_scoped_session] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def initialize(cls) -> None:
        """Initialize database engine and session factory (call on app startup)"""
        instance = cls()
        
        if instance._engine is not None:
            logger.warning("DatabaseManager already initialized, skipping re-initialization")
            return
        
        db_config = settings.database
        logger.info(
            f"Initializing async database connection pool: {db_config.hostname}:{db_config.port}/{db_config.database}"
        )
        
        # Determine pool strategy based on environment
        if settings.environment == "production":
            poolclass = QueuePool
            pool_kwargs = {
                "pool_size": db_config.pool_size,
                "max_overflow": db_config.max_overflow,
                "pool_recycle": db_config.pool_recycle,
                "pool_pre_ping": db_config.pool_pre_ping,
            }
        else:
            # Development: NullPool for simpler lifecycle
            poolclass = NullPool
            pool_kwargs = {}
        
        instance._engine = create_async_engine(
            db_config.async_url,
            echo=db_config.echo,
            poolclass=poolclass,
            **pool_kwargs,
            # Statement compilation caching for performance
            connect_args={
                "server_settings": {
                    "jit": "off",  # Disable JIT in PostgreSQL
                },
                "timeout": 30,
                "ssl": "prefer",  # Use SSL if available
            }
        )
        
        instance._async_session_factory = async_sessionmaker(
            instance._engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Prevent lazy-load issues after commit
            autoflush=False,
            autocommit=False,
        )
        
        # Scoped session for thread-local context (Celery workers)
        instance._scoped_session = async_scoped_session(
            instance._async_session_factory,
            scopefunc=lambda: "celery_worker"  # Simple scope for now
        )
    
    @classmethod
    def get_engine(cls) -> AsyncEngine:
        """Get the async engine instance"""
        instance = cls()
        if instance._engine is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return instance._engine
    
    @classmethod
    def get_async_session_factory(cls) -> async_sessionmaker:
        """Get the async session factory"""
        instance = cls()
        if instance._async_session_factory is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return instance._async_session_factory
    
    @classmethod
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI dependency for obtaining an async session.
        
        Usage in FastAPI route:
            async def get_users(session: AsyncSession = Depends(get_db)):
                result = await session.execute(select(User))
                return result.scalars().all()
        """
        instance = cls()
        factory = instance.get_async_session_factory()
        
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @classmethod
    @asynccontextmanager
    async def session_context(cls) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for async sessions (useful in services/agents).
        
        Usage:
            async with DatabaseManager.session_context() as session:
                result = await session.execute(select(User))
        """
        instance = cls()
        factory = instance.get_async_session_factory()
        
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @classmethod
    async def create_all_tables(cls) -> None:
        """Create all tables (idempotent, use Alembic in production)"""
        engine = cls.get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    
    @classmethod
    async def drop_all_tables(cls) -> None:
        """Drop all tables (DANGER: testing only)"""
        engine = cls.get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All database tables dropped")
    
    @classmethod
    async def close(cls) -> None:
        """Close database connections (call on app shutdown)"""
        instance = cls()
        if instance._engine is not None:
            await instance._engine.dispose()
            logger.info("Database engine disposed")


# Convenience exports for FastAPI dependency injection
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency function.
    
    Usage:
        @app.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async for session in DatabaseManager.get_session():
        yield session


# For Celery workers (sync context with asyncio.run wrapper)
class CelerySessionManager:
    """Helper for Celery tasks to get async sessions in sync context"""
    
    @staticmethod
    def get_session():
        """
        Returns the async session factory for Celery tasks.
        
        Usage in Celery task:
            import asyncio
            from db.models import TranslationJobDB
            from sqlalchemy import text, select
            
            @app.task(bind=True)
            def process_translation(self, job_id: str):
                async def _task():
                    async with CelerySessionManager.get_session_context() as session:
                        stmt = select(TranslationJobDB).where(TranslationJobDB.job_id == job_id)
                        result = await session.execute(stmt)
                        job = result.scalar_one_or_none()
                        if job:
                            job.status = JobStatus.processing
                            await session.commit()
                
                return asyncio.run(_task())
        """
        return DatabaseManager.get_async_session_factory()
    
    @staticmethod
    @asynccontextmanager
    async def session_context():
        """Async context manager for Celery task database access"""
        async for session in DatabaseManager.get_session():
            yield session


# Health check function
async def check_database_health() -> bool:
    from sqlalchemy import text
    """
    Verify database connectivity.
    
    Usage in startup checks:
        if not await check_database_health():
            raise RuntimeError("Database connection failed")
    """
    try:
        engine = DatabaseManager.get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database health check passed")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
