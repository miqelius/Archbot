"""
core/redis_client.py - Async Redis client with connection pooling
Used for Celery broker, result backend, and caching layer
"""

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from typing import Optional, Any
import logging

from core.core_config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Singleton Redis async client with connection pooling.
    Handles both Celery broker operations and caching.
    """
    
    _instance: Optional['RedisClient'] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def initialize(cls) -> None:
        """Initialize Redis connection pool (call on app startup)"""
        instance = cls()
        
        if instance._client is not None:
            logger.warning("RedisClient already initialized, skipping re-initialization")
            return
        
        redis_config = settings.redis
        logger.info(f"Initializing Redis connection pool: {redis_config.host}:{redis_config.port}")
        
        try:
            # Create connection pool
            instance._pool = ConnectionPool.from_url(
                redis_config.url,
                max_connections=getattr(redis_config, 'max_connections', 50),
                socket_timeout=getattr(redis_config, 'socket_timeout', 5.0),
                socket_connect_timeout=getattr(redis_config, 'socket_connect_timeout', 5.0),
                decode_responses=False,
                retry_on_timeout=True,
            )
            
            # Create async Redis client from pool
            instance._client = redis.Redis(connection_pool=instance._pool)
            
            logger.info("Redis connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    @classmethod
    def get_client(cls) -> redis.Redis:
        """Get the Redis client instance"""
        instance = cls()
        if instance._client is None:
            raise RuntimeError("RedisClient not initialized. Call initialize() first.")
        return instance._client
    
    @classmethod
    async def ping(cls) -> bool:
        """Health check for Redis connectivity"""
        try:
            client = cls.get_client()
            response = await client.ping()
            return response
        except RedisConnectionError as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    @classmethod
    async def set(
        cls,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Set a key with optional expiration.
        
        Args:
            key: Redis key
            value: Value (string or bytes)
            ex: Expiration in seconds
            px: Expiration in milliseconds
            nx: Only set if not exists
            xx: Only set if exists
        """
        try:
            client = cls.get_client()
            result = await client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
            return result is not None
        except RedisError as e:
            logger.error(f"Redis SET failed for key '{key}': {e}")
            return False
    
    @classmethod
    async def get(cls, key: str) -> Optional[bytes]:
        """Get value by key"""
        try:
            client = cls.get_client()
            return await client.get(key)
        except RedisError as e:
            logger.error(f"Redis GET failed for key '{key}': {e}")
            return None
    
    @classmethod
    async def delete(cls, *keys: str) -> int:
        """Delete one or more keys"""
        try:
            client = cls.get_client()
            return await client.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis DELETE failed: {e}")
            return 0
    
    @classmethod
    async def exists(cls, key: str) -> bool:
        """Check if key exists"""
        try:
            client = cls.get_client()
            result = await client.exists(key)
            return result > 0
        except RedisError as e:
            logger.error(f"Redis EXISTS failed for key '{key}': {e}")
            return False
    
    @classmethod
    async def lpush(cls, key: str, *values: Any) -> int:
        """Push to left of list (for job queues)"""
        try:
            client = cls.get_client()
            return await client.lpush(key, *values)
        except RedisError as e:
            logger.error(f"Redis LPUSH failed for key '{key}': {e}")
            return 0
    
    @classmethod
    async def rpush(cls, key: str, *values: Any) -> int:
        """Push to right of list"""
        try:
            client = cls.get_client()
            return await client.rpush(key, *values)
        except RedisError as e:
            logger.error(f"Redis RPUSH failed for key '{key}': {e}")
            return 0
    
    @classmethod
    async def lpop(cls, key: str) -> Optional[bytes]:
        """Pop from left of list"""
        try:
            client = cls.get_client()
            return await client.lpop(key)
        except RedisError as e:
            logger.error(f"Redis LPOP failed for key '{key}': {e}")
            return None
    
    @classmethod
    async def llen(cls, key: str) -> int:
        """Get list length"""
        try:
            client = cls.get_client()
            return await client.llen(key)
        except RedisError as e:
            logger.error(f"Redis LLEN failed for key '{key}': {e}")
            return 0
    
    @classmethod
    async def hset(cls, key: str, mapping: dict[str, Any]) -> int:
        """Set hash fields (useful for job metadata)"""
        try:
            client = cls.get_client()
            return await client.hset(key, mapping=mapping)
        except RedisError as e:
            logger.error(f"Redis HSET failed for key '{key}': {e}")
            return 0
    
    @classmethod
    async def hgetall(cls, key: str) -> dict:
        """Get all hash fields"""
        try:
            client = cls.get_client()
            result = await client.hgetall(key)
            return result if result else {}
        except RedisError as e:
            logger.error(f"Redis HGETALL failed for key '{key}': {e}")
            return {}
    
    @classmethod
    async def expire(cls, key: str, seconds: int) -> bool:
        """Set expiration on a key"""
        try:
            client = cls.get_client()
            result = await client.expire(key, seconds)
            return result > 0
        except RedisError as e:
            logger.error(f"Redis EXPIRE failed for key '{key}': {e}")
            return False
    
    @classmethod
    async def close(cls) -> None:
        """Close Redis connection (call on app shutdown)"""
        instance = cls()
        if instance._client is not None:
            await instance._client.close()
            logger.info("Redis client closed")
        if instance._pool is not None:
            await instance._pool.disconnect()
            logger.info("Redis connection pool disconnected")


# Convenience exports
redis_client = RedisClient()


async def get_redis() -> redis.Redis:
    """Dependency for FastAPI to inject Redis client"""
    return RedisClient.get_client()
