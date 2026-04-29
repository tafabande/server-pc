"""
StreamDrop — Celery Application
Configures Celery with Redis as both broker and result backend.
Auto-discovers tasks in the 'workers' package.
"""

from celery import Celery
from config import REDIS_URL

celery_app = Celery(
    "streamdrop",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "workers.hls_worker",
        "workers.ffprobe_worker",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behavior
    task_acks_late=True,           # Only ack after task completes (retry on crash)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time per worker (CPU-bound encoding)
    # Result TTL
    result_expires=3600,           # Keep results for 1 hour
    # Beat schedule: re-probe files that failed indexing
    beat_schedule={
        "retry-failed-probes": {
            "task": "workers.ffprobe_worker.probe_pending_files",
            "schedule": 300.0,   # Every 5 minutes
        },
    },
)
