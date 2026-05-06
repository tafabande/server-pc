"""
StreamDrop — Redis Session Client
Stores JWT token hashes in Redis so all FastAPI instances share session state.

Graceful degradation:
  If Redis is unavailable (dev mode without Docker), falls back to an in-memory
  dict. Sessions will still work but won't survive restarts or span instances.
"""

import hashlib
import logging
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("streamdrop.redis")

# ── In-memory fallback ────────────────────────────────────────────────────────
# Used when Redis is unreachable. Thread-safe enough for single-instance dev.
_memory_store: dict[str, tuple[str, datetime]] = {}  # token_hash -> (user_id, expires_at)

# ── Circuit Breaker ───────────────────────────────────────────────────────────
_redis_failures = 0
_last_failure_time: float = 0
MAX_FAILURES = 3
FAILURE_RESET_TIME = 300  # 5 minutes
SESSION_TTL = 86400  # 24 hours


def _hash_token(token: str) -> str:
    """SHA-256 hash the JWT so we never store raw tokens in Redis."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Redis client (lazy init) ──────────────────────────────────────────────────
_redis_client = None
_redis_available = False


async def _get_redis_connection():
    """Internal: Attempt to connect to Redis."""
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client if _redis_available else None
    try:
        import redis.asyncio as aioredis
        from config import REDIS_URL
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis_client.ping()
        _redis_available = True
        logger.info("✅ Redis connected for multi-instance session sync.")
    except Exception as e:
        _redis_available = False
        logger.warning(f"⚠️  Redis unavailable — using in-memory sessions (single-instance mode): {e}")
    return _redis_client if _redis_available else None


async def get_redis():
    """Get Redis connection with circuit breaker pattern."""
    global _redis_failures, _last_failure_time

    # Circuit breaker reset logic
    if _redis_failures >= MAX_FAILURES:
        # Check if we should retry (5 minutes have passed)
        if time.time() - _last_failure_time > FAILURE_RESET_TIME:
            logger.info("⚡ Circuit breaker timeout reached, attempting Redis reconnect...")
            _redis_failures = 0  # Reset counter
            _last_failure_time = 0
        else:
            logger.warning(f"Redis circuit breaker OPEN ({_redis_failures} failures). Using memory fallback.")
            return None

    try:
        redis = await _get_redis_connection()
        if redis:
            _redis_failures = 0  # Reset on success
            _last_failure_time = 0
        return redis
    except Exception as e:
        _redis_failures += 1
        _last_failure_time = time.time()  # Track when failure occurred
        logger.error(f"Redis connection failed ({_redis_failures}/{MAX_FAILURES}): {e}")
        if _redis_failures >= MAX_FAILURES:
            logger.critical("⚠️ Redis circuit breaker OPENED. Will use memory fallback and retry in 5 minutes.")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

async def store_session(token: str, user_id: int, ttl_seconds: int = SESSION_TTL):
    """
    Persist a token → user_id mapping with TTL.
    All FastAPI instances can validate this session via check_session().
    """
    key = _hash_token(token)
    value = str(user_id)
    r = await get_redis()
    if r:
        await r.setex(key, ttl_seconds, value)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        _memory_store[key] = (value, expires_at)


async def get_session_user_id(token: str) -> Optional[int]:
    """
    Look up user_id for a given token. Returns None if invalid/expired.
    """
    key = _hash_token(token)
    r = await get_redis()
    if r:
        value = await r.get(key)
        return int(value) if value else None
    else:
        # Check memory store with TTL
        entry = _memory_store.get(key)
        if entry:
            user_id, expires_at = entry
            if datetime.now(timezone.utc) < expires_at:
                return int(user_id)
            else:
                # Expired, remove it
                del _memory_store[key]
        return None


async def invalidate_session(token: str):
    """Remove a session (logout)."""
    key = _hash_token(token)
    r = await get_redis()
    if r:
        await r.delete(key)
    else:
        _memory_store.pop(key, None)


async def invalidate_all_user_sessions(user_id: int):
    """
    Invalidate all sessions for a user (admin force-logout).
    NOTE: With in-memory fallback this scans all entries; with Redis this
    requires a SCAN which is O(N). For large deployments, use a user→tokens
    reverse index. Acceptable at this scale.
    """
    target = str(user_id)
    r = await get_redis()
    if r:
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, count=100)
            for key in keys:
                val = await r.get(key)
                if val == target:
                    await r.delete(key)
            if cursor == 0:
                break
    else:
        # For memory store, check tuple format
        to_delete = [k for k, v in _memory_store.items() if v[0] == target]
        for k in to_delete:
            del _memory_store[k]


async def _cleanup_memory_store():
    """Remove expired entries from memory store."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes

        now = datetime.now(timezone.utc)
        expired = [k for k, (_, exp) in _memory_store.items() if exp < now]

        for key in expired:
            del _memory_store[key]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired session(s) from memory store")


# Start cleanup task
try:
    asyncio.create_task(_cleanup_memory_store())
except RuntimeError:
    # No event loop running yet, will be started later
    pass
