"""
StreamDrop — Video Streaming
Webcam and screen capture with MJPEG streaming.
"""

import time
import threading
import logging
import cv2
import numpy as np
import mss
from config import JPEG_QUALITY, STREAM_WIDTH, STREAM_HEIGHT, STREAM_FPS

logger = logging.getLogger("streamdrop.streaming")


class WebcamStreamer:
    """Captures frames from a webcam using OpenCV."""

    def __init__(self, source: int = 0):
        self.source = source
        self.camera: cv2.VideoCapture | None = None
        self._lock = threading.Lock()

    def open(self):
        """Open the camera."""
        with self._lock:
            if self.camera is None or not self.camera.isOpened():
                self.camera = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Fix latency by disabling frame buffering
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_WIDTH)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)
                self.camera.set(cv2.CAP_PROP_FPS, STREAM_FPS)
                logger.info(f"📷 Webcam opened (source={self.source})")

    def read_frame(self) -> np.ndarray | None:
        """Read a single frame. Returns None on failure."""
        with self._lock:
            if self.camera is None or not self.camera.isOpened():
                return None
            success, frame = self.camera.read()
            if not success:
                return None
            return frame

    def release(self):
        """Release the camera."""
        with self._lock:
            if self.camera and self.camera.isOpened():
                self.camera.release()
                self.camera = None
                logger.info("📷 Webcam released")


class ScreenStreamer:
    """Captures the primary screen using mss."""

    def __init__(self):
        self.sct: mss.mss | None = None
        self._lock = threading.Lock()

    def open(self):
        """Initialize mss."""
        with self._lock:
            if self.sct is None:
                self.sct = mss.mss()
                logger.info("🖥️ Screen capture initialized")

    def read_frame(self) -> np.ndarray | None:
        """Capture the primary monitor and return as numpy array."""
        with self._lock:
            if self.sct is None:
                return None
            try:
                monitor = self.sct.monitors[1]  # Primary monitor
                screenshot = self.sct.grab(monitor)
                # Convert BGRA to BGR (OpenCV format)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                # Resize to configured resolution
                frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))
                return frame
            except Exception as e:
                logger.error(f"Screen capture error: {e}")
                return None

    def release(self):
        """Release mss resources."""
        with self._lock:
            if self.sct:
                self.sct.close()
                self.sct = None
                logger.info("🖥️ Screen capture released")


class StreamManager:
    """
    Singleton that manages the active streamer.
    Thread-safe start/stop/toggle between webcam and screen.
    """

    def __init__(self):
        self._webcam = WebcamStreamer()
        self._screen = ScreenStreamer()
        self._active_mode = "webcam"  # "webcam" or "screen"
        self._running = False
        self._lock = threading.Lock()
        self._frame_interval = 1.0 / STREAM_FPS
        self._quality = JPEG_QUALITY  # Adaptive: mutable at runtime

    @property
    def quality(self) -> int:
        return self._quality

    @quality.setter
    def quality(self, value: int):
        self._quality = max(20, min(95, int(value)))
        logger.info(f"📊 Quality set to {self._quality}")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def mode(self) -> str:
        return self._active_mode

    @property
    def _active_streamer(self):
        return self._webcam if self._active_mode == "webcam" else self._screen

    def start(self):
        """Start the active streamer."""
        with self._lock:
            if not self._running:
                self._active_streamer.open()
                self._running = True
                logger.info(f"▶️ Streaming started (mode={self._active_mode})")

    def stop(self):
        """Stop the active streamer."""
        with self._lock:
            if self._running:
                self._webcam.release()
                self._screen.release()
                self._running = False
                logger.info("⏹️ Streaming stopped")

    def toggle(self) -> str:
        """Switch between webcam and screen capture. Returns new mode."""
        with self._lock:
            was_running = self._running
            # Release current
            self._active_streamer.release()
            # Switch
            self._active_mode = (
                "screen" if self._active_mode == "webcam" else "webcam"
            )
            # Restart if was running
            if was_running:
                self._active_streamer.open()
            logger.info(f"🔄 Switched to {self._active_mode}")
            return self._active_mode

    def generate_frames(self):
        """
        Generator that yields MJPEG frames.
        Designed to be used with FastAPI StreamingResponse.
        Uses a sync generator (FastAPI runs it in a threadpool).
        Quality is read dynamically each frame for adaptive bitrate.
        """
        while self._running:
            frame_start = time.monotonic()

            frame = self._active_streamer.read_frame()
            if frame is None:
                # Yield a "no signal" placeholder
                placeholder = np.zeros((STREAM_HEIGHT, STREAM_WIDTH, 3), dtype=np.uint8)
                cv2.putText(
                    placeholder,
                    "No Signal",
                    (STREAM_WIDTH // 2 - 120, STREAM_HEIGHT // 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,
                    (100, 100, 255),
                    3,
                )
                frame = placeholder

            # Adaptive: downscale at very low quality for bandwidth savings
            q = self._quality
            if q < 40:
                h, w = frame.shape[:2]
                scale = 0.5 if q < 30 else 0.75
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

            # Encode as JPEG with current adaptive quality
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), q]
            ret, buffer = cv2.imencode(".jpg", frame, encode_params)
            if not ret:
                continue

            frame_bytes = buffer.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

            # Frame rate limiting
            elapsed = time.monotonic() - frame_start
            sleep_time = self._frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)


# ── Module-level singleton ──────────────────────────────
stream_manager = StreamManager()
