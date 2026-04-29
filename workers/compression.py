import asyncio
import logging
import subprocess
from pathlib import Path
from core.database import update_job_status, get_pending_jobs

logger = logging.getLogger("streamdrop.compression")

# Global queue for jobs
job_queue = asyncio.Queue()

async def process_video_job(job_id: int, file_path_str: str):
    file_path = Path(file_path_str)
    if not file_path.exists():
        update_job_status(job_id, "failed_not_found")
        return

    hls_dir = file_path.parent / f"{file_path.name}.hls"
    hls_dir.mkdir(exist_ok=True)
    m3u8_path = hls_dir / "index.m3u8"
    
    if m3u8_path.exists():
        update_job_status(job_id, "completed")
        return

    logger.info(f"Starting HLS generation for {file_path.name}")
    update_job_status(job_id, "processing")
    
    cmd = [
        "ffmpeg", "-y", "-i", str(file_path),
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-hls_time", "10",
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", str(hls_dir / "segment_%03d.ts"),
        str(m3u8_path)
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    await process.wait()
    
    if process.returncode == 0:
        logger.info(f"Successfully generated HLS for {file_path.name}")
        update_job_status(job_id, "completed")
    else:
        logger.error(f"Failed to generate HLS for {file_path.name}")
        update_job_status(job_id, "failed")

async def worker_loop():
    logger.info("Compression worker started. Re-queuing pending jobs...")
    
    # On startup, load pending jobs from SQLite into the queue
    pending_jobs = get_pending_jobs()
    for job in pending_jobs:
        await job_queue.put(job)
        
    while True:
        job = await job_queue.get()
        try:
            await process_video_job(job["id"], job["file_path"])
        except Exception as e:
            logger.error(f"Error processing job {job['id']}: {e}")
            update_job_status(job["id"], "failed")
        finally:
            job_queue.task_done()

def start_worker():
    asyncio.create_task(worker_loop())
