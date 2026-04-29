"""
StreamDrop — Compression Worker (Celery Shim)
Previously held an asyncio.Queue-based worker.
Now delegates to the Celery task system for distributed encoding.

Kept for backwards compatibility: routers/file_api.py imports start_worker() and job_queue.
"""

import asyncio
import logging

logger = logging.getLogger("streamdrop.compression")

# Dummy queue shim — consumed by file_api.py, but now Celery handles dispatch
job_queue: asyncio.Queue = asyncio.Queue()


def start_worker():
    """
    Legacy entrypoint called from core/main.py lifespan.
    No-ops here — the Celery worker process handles transcoding separately.
    Logs a warning if Celery broker is unreachable so the operator knows.
    """
    try:
        from workers.celery_app import celery_app
        celery_app.control.ping(timeout=1)
        logger.info("✅ Celery broker reachable — HLS transcoding active.")
    except Exception:
        logger.warning(
            "⚠️  Celery broker unreachable. HLS transcoding will be disabled. "
            "Start Redis and run: celery -A workers.celery_app worker -l info"
        )
