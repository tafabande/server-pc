"""
StreamDrop — WebSocket Hub
Central real-time messaging layer for clipboard sync, file events,
remote control, and adaptive bitrate negotiation.
"""

import json
import logging
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("streamdrop.ws")


# ── State Objects ──────────────────────────────────────

@dataclass
class NowPlaying:
    """Shared media playback state across all clients."""
    url: str = ""
    filename: str = ""
    playing: bool = False
    current_time: float = 0.0
    duration: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def reset(self):
        self.url = ""
        self.filename = ""
        self.playing = False
        self.current_time = 0.0
        self.duration = 0.0


# ── Connection Manager ─────────────────────────────────

class ConnectionManager:
    """
    Manages WebSocket connections and message routing.

    Message protocol (JSON):
        { "type": "clipboard",       "text": "..." }
        { "type": "file_event",      "action": "uploaded"|"deleted", "file": {...} }
        { "type": "remote_control",  "action": "play"|"pause"|"seek"|"set"|"stop", ... }
        { "type": "bitrate",         "quality": 30-95 }
        { "type": "ping" }
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

        # Shared state
        self.clipboard_text: str = ""
        self.now_playing: NowPlaying = NowPlaying()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection and send initial state."""
        async with self._lock:
            await websocket.accept()
            self.active_connections.append(websocket)

        client = f"{websocket.client.host}:{websocket.client.port}"
        logger.info(f"🔌 WS connected: {client} (total: {len(self.active_connections)})")

        # Send current state to the new client
        await self._send_initial_state(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

        client = f"{websocket.client.host}:{websocket.client.port}"
        logger.info(f"🔌 WS disconnected: {client} (total: {len(self.active_connections)})")

    async def _send_initial_state(self, websocket: WebSocket):
        """Send current clipboard and now-playing state to a new connection."""
        try:
            # Current clipboard
            if self.clipboard_text:
                await websocket.send_json({
                    "type": "clipboard",
                    "text": self.clipboard_text,
                    "source": "server",
                })

            # Current now-playing
            if self.now_playing.url:
                await websocket.send_json({
                    "type": "remote_control",
                    "action": "state",
                    **self.now_playing.to_dict(),
                })

            # Connection count
            await self._broadcast_connection_count()
        except Exception:
            pass

    async def broadcast(self, message: dict, exclude: WebSocket | None = None):
        """Send a message to all connected clients, optionally excluding one."""
        disconnected = []
        async with self._lock:
            connections = list(self.active_connections)

        for conn in connections:
            if conn is exclude:
                continue
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.append(conn)

        # Clean up any broken connections
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception:
            await self.disconnect(websocket)

    async def _broadcast_connection_count(self):
        """Notify all clients of the current connection count."""
        await self.broadcast({
            "type": "connections",
            "count": len(self.active_connections),
        })

    # ── Message Handlers ────────────────────────────────

    async def handle_message(self, websocket: WebSocket, data: dict):
        """Route an incoming message to the appropriate handler."""
        msg_type = data.get("type", "")

        handlers = {
            "clipboard": self._handle_clipboard,
            "remote_control": self._handle_remote_control,
            "bitrate": self._handle_bitrate,
            "ping": self._handle_ping,
        }

        handler = handlers.get(msg_type)
        if handler:
            await handler(websocket, data)
        else:
            logger.warning(f"Unknown WS message type: {msg_type}")

    async def _handle_clipboard(self, websocket: WebSocket, data: dict):
        """Handle clipboard sync messages."""
        text = data.get("text", "")
        self.clipboard_text = text

        # Broadcast to all OTHER clients
        await self.broadcast(
            {"type": "clipboard", "text": text, "source": "peer"},
            exclude=websocket,
        )
        logger.debug(f"📋 Clipboard synced: {text[:50]}...")

    async def _handle_remote_control(self, websocket: WebSocket, data: dict):
        """Handle remote control messages (play/pause/seek/set/stop)."""
        action = data.get("action", "")

        if action == "set":
            # Set a new media file as "Now Playing"
            self.now_playing.url = data.get("url", "")
            self.now_playing.filename = data.get("filename", "")
            self.now_playing.playing = True
            self.now_playing.current_time = 0.0
            self.now_playing.duration = data.get("duration", 0.0)

        elif action == "play":
            self.now_playing.playing = True

        elif action == "pause":
            self.now_playing.playing = False

        elif action == "seek":
            self.now_playing.current_time = data.get("time", 0.0)

        elif action == "timeupdate":
            # Periodic time sync from the player
            self.now_playing.current_time = data.get("time", 0.0)
            self.now_playing.duration = data.get("duration", self.now_playing.duration)

        elif action == "stop":
            self.now_playing.reset()

        # Broadcast updated state to all clients
        await self.broadcast(
            {
                "type": "remote_control",
                "action": action,
                **self.now_playing.to_dict(),
            },
            exclude=websocket if action == "timeupdate" else None,
        )

    async def _handle_bitrate(self, websocket: WebSocket, data: dict):
        """Handle adaptive bitrate requests from clients."""
        from streaming import stream_manager

        quality = data.get("quality", 75)
        quality = max(20, min(95, int(quality)))
        stream_manager.quality = quality

        # Acknowledge to all clients
        await self.broadcast({
            "type": "bitrate",
            "quality": quality,
            "source": "server",
        })
        logger.info(f"📊 Stream quality adjusted to {quality}")

    async def _handle_ping(self, websocket: WebSocket, _data: dict):
        """Respond to a keepalive ping."""
        await self.send_personal(websocket, {"type": "pong"})

    # ── Server-side event helpers ───────────────────────

    async def broadcast_file_event(self, action: str, file_info: dict):
        """Broadcast a file upload/delete event to all clients."""
        await self.broadcast({
            "type": "file_event",
            "action": action,
            "file": file_info,
        })

    async def broadcast_update(self):
        """Send a signal to trigger a full client-side refresh."""
        await self.broadcast({"type": "update"})

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


# ── Module-level singleton ──────────────────────────────
manager = ConnectionManager()
