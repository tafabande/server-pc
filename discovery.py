"""
StreamDrop — Network Discovery & Utilities
Zeroconf service registration, IP detection, and QR code generation.
"""

import io
import socket
import logging
from zeroconf import ServiceInfo, Zeroconf
import qrcode
from qrcode.image.styledpil import StyledPilImage
from config import PORT, SERVICE_NAME

logger = logging.getLogger("streamdrop.discovery")


def get_local_ip() -> str:
    """
    Get the machine's LAN IP address reliably.
    Connects a UDP socket to a public address (no data sent)
    to determine which interface the OS would route through.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        # Fallback to hostname resolution
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def get_server_url(ip: str | None = None) -> str:
    """Build the full server URL."""
    ip = ip or get_local_ip()
    return f"http://{ip}:{PORT}"


# ── Zeroconf Service Registration ──────────────────────


class ServiceDiscovery:
    """Manages Zeroconf/mDNS service registration."""

    def __init__(self):
        self.zeroconf: Zeroconf | None = None
        self.info: ServiceInfo | None = None

    def register(self):
        """Register the StreamDrop service on the local network."""
        try:
            self.zeroconf = Zeroconf()
            ip = get_local_ip()
            hostname = socket.gethostname()

            self.info = ServiceInfo(
                type_="_http._tcp.local.",
                name=f"{SERVICE_NAME}._http._tcp.local.",
                addresses=[socket.inet_aton(ip)],
                port=PORT,
                properties={
                    "version": "1.0.0",
                    "description": "StreamDrop LAN Hub",
                    "path": "/",
                },
                server=f"{hostname}.local.",
            )

            self.zeroconf.register_service(self.info)
            logger.info(
                f"✅ Zeroconf: Registered as '{SERVICE_NAME}' at {ip}:{PORT}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Zeroconf registration failed (non-fatal): {e}")

    def unregister(self):
        """Unregister the service and close Zeroconf."""
        try:
            if self.zeroconf and self.info:
                self.zeroconf.unregister_service(self.info)
                self.zeroconf.close()
                logger.info("🛑 Zeroconf: Service unregistered.")
        except Exception as e:
            logger.warning(f"⚠️ Zeroconf cleanup error: {e}")


# ── QR Code Generation ─────────────────────────────────


def generate_qr_code(url: str | None = None) -> bytes:
    """
    Generate a QR code PNG for the server URL.
    Returns raw PNG bytes.
    """
    url = url or get_server_url()

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()
