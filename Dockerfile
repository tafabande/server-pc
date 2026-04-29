FROM python:3.12-slim

# Install system dependencies: FFmpeg for media processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories that must exist at runtime
# Note: /shared (media) and /transcodes are mounted as Docker volumes
RUN mkdir -p /app/.cache/transcodes /app/.data /app/.logs

# Expose the FastAPI port
EXPOSE 8000

# Default: run the FastAPI web server
# Override CMD in docker-compose.yml for the Celery worker service
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
