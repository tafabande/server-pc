"""
StreamDrop — Redis Session Client
Stores JWT token hashes in Redis so all FastAPI instances share session state.

Graceful degradation:
  If Redis is unavailable (dev mode without Docker), falls back to an in-memory
  dict. Sessions will still work but won't survive restarts or span instances.
"""

import hashlib
import logging
from typing import Optional

logger = logging.getLogger("streamdrop.redis")

# ── In-memory fallback ────────────────────────────────────────────────────────
# Used when Redis is unreachable. Thread-safe enough for single-instance dev.
_memory_store: dict[str, str] = {}  # token_hash -> user_id str


def _hash_token(token: str) -> str:
    """SHA-256 hash the JWT so we never store raw tokens in Redis."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Redis client (lazy init) ──────────────────────────────────────────────────
_redis_client = None
_redis_available = False


async def _get_redis():
    """Lazily connect to Redis. Returns None if Redis is unavailable."""
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


# ── Public API ────────────────────────────────────────────────────────────────

async def store_session(token: str, user_id: int, ttl_seconds: int = 86400):
    """
    Persist a token → user_id mapping.
    All FastAPI instances can validate this session via check_session().
    """
    key = _hash_token(token)
    value = str(user_id)
    r = await _get_redis()
    if r:
        await r.setex(key, ttl_seconds, value)
    else:
        _memory_store[key] = value


async def get_session_user_id(token: str) -> Optional[int]:
    """
    Look up user_id for a given token. Returns None if invalid/expired.
    """
    key = _hash_token(token)
    r = await _get_redis()
    if r:
        value = await r.get(key)
    else:
        value = _memory_store.get(key)
    return int(value) if value else None


async def invalidate_session(token: str):
    """Remove a session (logout)."""
    key = _hash_token(token)
    r = await _get_redis()
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
    r = await _get_redis()
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
        to_delete = [k for k, v in _memory_store.items() if v == target]
        for k in to_delete:
            del _memory_store[k]
