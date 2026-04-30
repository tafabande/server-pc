"""
StreamDrop — ASR Manager
Local Automatic Speech Recognition using Faster-Whisper.
Processes audio chunks from the stream and broadcasts transcriptions.
"""

import threading
import queue
import logging
import time
import numpy as np
from faster_whisper import WhisperModel
import asyncio

logger = logging.getLogger("streamdrop.asr")

class ASRManager:
    def __init__(self, model_size="tiny"):
        self.model_size = model_size
        self.model = None
        self.audio_queue = queue.Queue()
        self._running = False
        self._thread = None
        self._loop = None
        
        # Audio config
        self.target_sample_rate = 16000
        self.buffer = np.array([], dtype=np.float32)
        
    def start(self, loop):
        """Start the ASR processing thread."""
        if self._running:
            return
        
        self._loop = loop
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info(f"🎙️ ASR initialized with model: {self.model_size}")

    def stop(self):
        """Stop the ASR processing thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("🎙️ ASR stopped.")

    def add_audio(self, pcm_bytes: bytes, source_rate: int, channels: int):
        """Add raw PCM audio bytes to the processing queue."""
        if not self._running:
            return
            
        # Convert bytes to numpy array (int16 to float32)
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Convert stereo to mono if needed
        if channels == 2:
            audio_data = audio_data.reshape(-1, 2).mean(axis=1)
            
        # Basic downsampling (every Nth sample) if source is 44.1k or 48k
        # For production, we'd use a proper resampler like librosa or scipy,
        # but to keep dependencies low and offline, we'll do simple decimation.
        step = source_rate // self.target_sample_rate
        if step > 1:
            audio_data = audio_data[::step]
            
        self.audio_queue.put(audio_data)

    def _worker(self):
        """Background thread for transcription."""
        last_audio_time = time.time()
        model_loaded = False

        chunk_duration = 3  # Process in 3-second chunks for better context
        samples_needed = self.target_sample_rate * chunk_duration
        local_buffer = np.array([], dtype=np.float32)

        while self._running:
            try:
                # Check for idle timeout (unload model after 60s of silence)
                if model_loaded and (time.time() - last_audio_time > 60):
                    logger.info("🎙️ ASR Idle: Unloading model to save memory.")
                    self.model = None
                    model_loaded = False
                    import gc
                    gc.collect()

                # Accumulate enough audio for a chunk
                while len(local_buffer) < samples_needed and self._running:
                    try:
                        # Wait for data with timeout to check for idle
                        data = self.audio_queue.get(timeout=1.0)
                        local_buffer = np.append(local_buffer, data)
                        last_audio_time = time.time()
                        
                        # Load model on demand
                        if not model_loaded and self._running:
                            logger.info(f"🎙️ ASR Activity: Loading model ({self.model_size})...")
                            self.model = WhisperModel(
                                self.model_size, 
                                device="cpu", 
                                compute_type="int8",
                                cpu_threads=4
                            )
                            model_loaded = True
                    except queue.Empty:
                        if not self._running: break
                        # If idle, we break to the outer loop to check timeout
                        if len(local_buffer) == 0: break
                        continue
                
                if not self._running or not model_loaded or len(local_buffer) < samples_needed:
                    continue

                # Transcribe
                segments, info = self.model.transcribe(
                    local_buffer, 
                    beam_size=1,  # Beam size 1 is much faster and uses less RAM
                    language="en", 
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=1000)
                )
                
                for segment in segments:
                    text = segment.text.strip()
                    if text:
                        logger.info(f"📝 ASR: {text}")
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._broadcast_transcription(text), 
                                self._loop
                            )
                
                # Clear ONLY the processed part of the buffer
                # This ensures we don't leak memory and stay synchronized
                local_buffer = np.array([], dtype=np.float32)
                
            except Exception as e:
                logger.error(f"ASR Worker error: {e}")
                time.sleep(1)
        
        # Final cleanup
        self.model = None
        local_buffer = None
        import gc
        gc.collect()

    async def _broadcast_transcription(self, text: str):
        """Helper to broadcast via ws_manager."""
        from websocket_hub import ws_manager
        await ws_manager.broadcast({
            "type": "transcription",
            "text": text,
            "timestamp": time.time()
        })

# Global singleton
asr_manager = ASRManager()
