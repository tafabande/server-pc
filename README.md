# 🚀 MediaHub — Professional LAN Media Ecosystem

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Material 3](https://img.shields.io/badge/UI-Material_3-7C4DFF.svg)](https://m3.material.io/)

**MediaHub** is a premium, self-hosted media and document ecosystem designed for high-performance LAN environments. It combines a cinematic PWA frontend with a robust FastAPI backend and a native Windows control panel for real-time monitoring.

---

## ✨ Key Features

- **🎬 Cinematic Streaming**: HLS-ready transcoding for instant seeking and "Netflix-style" scrubbing on any device.
- **📄 Document Hub**: Collaborative, browser-based editor for `.txt` and `.md` files with full RBAC protection.
- **🛡️ Enterprise Security**: Role-Based Access Control (RBAC) with JWT authentication and persistent security auditing.
- **🖥️ Native Desktop Panel**: Windows GUI for hardware monitoring (CPU/RAM) and one-click server management.
- **📱 Mobile-First PWA**: Installable app experience for iOS and Android with zero App Store requirement.
- **📊 Real-time Telemetry**: Detailed play events and audit trails for system transparency.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python, FastAPI, SQLAlchemy (Async) |
| **Frontend** | Vanilla JS, Material 3 CSS, PWA |
| **Database** | SQLite / PostgreSQL (UUID identifiers) |
| **Media** | FFmpeg, ffprobe |
| **Desktop** | CustomTkinter, psutil |
| **Auth** | JWT, bcrypt, Redis-ready sessions |

---

## 🚦 Quick Start

1. **Install Prerequisites**: Ensure Python 3.10 and **FFmpeg** are installed.
2. **Setup Environment**:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env  # Configure your paths and admin login
   ```
3. **Launch Control Panel**:
   ```bash
   python server_manager.py
   ```

> [!TIP]
> For a full production deployment guide, including building a Windows Installer (.exe), see [GUIDE.md](./GUIDE.md).

---

## 🏗️ Architecture Summary

MediaHub follows a strict **Stateless Core** architecture. The `core/` directory houses the engine (Database, Workers, Security), while the `routers/` handle the API surface. The desktop panel acts as a process orchestrator, isolating the web server from the management UI for maximum stability.

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.

---

*Built with ❤️ for the LAN streaming community.*
