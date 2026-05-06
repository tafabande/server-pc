# 🚀 MediaHub — LAN Media Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Material 3](https://img.shields.io/badge/UI-Material_3-7C4DFF.svg)](https://m3.material.io/)

A Netflix + YouTube + Quick Share hybrid for your local network.

---

## ✨ Features

✅ **Video/Audio/Document Streaming** - HLS transcoding for smooth playback
✅ **File Management** - Upload, download, rename, delete files across devices
✅ **Live Desktop/Webcam Streaming** - Real-time streaming with WebSocket
✅ **JWT Authentication** - RBAC with admin, family, and guest roles
✅ **Modern Material 3 PWA** - Installable on any device
✅ **Database Migrations** - Safe schema updates with versioning
✅ **Real-time WebSocket Updates** - Live file changes across clients
✅ **Password Reset** - Token-based account recovery
✅ **User Profile Management** - Custom avatars and preferences
✅ **Audit Logging** - Security event tracking
✅ **Resume Playback** - Continue watching from where you left off

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | FastAPI, SQLAlchemy 2.0 (Async) |
| **Frontend** | Vanilla JS, Material 3 CSS, PWA |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Media** | FFmpeg for HLS transcoding |
| **Auth** | JWT tokens, HttpOnly cookies, Redis sessions |
| **Cache** | Redis with in-memory fallback |

---

## 🚦 Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg (for video transcoding)

### Installation

1. **Clone and install dependencies**
   ```bash
   git clone <repo-url>
   cd server-pc
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set SECRET_KEY, ADMIN_PASSWORD, etc.
   ```

3. **Run the server**
   ```bash
   uvicorn core.main:app --reload
   ```

4. **Access the app**
   - Open http://localhost:8000
   - Login with credentials from .env (default: admin/changeme)

---

## 📱 Android Access

Access from your Android device using:

- **LAN IP**: `http://<your-pc-ip>:8000`
- **USB Tethering**: `http://192.168.42.129:8000` (typical Android tethering IP)

### Find Your PC's IP

**Windows**:
```bash
ipconfig
# Look for IPv4 Address under your active network adapter
```

**Linux/Mac**:
```bash
ip addr show  # or ifconfig
```

---

## 🔐 Account Management

### Password Reset

**Request reset token**:
```bash
POST /api/auth/forgot-password
{
  "email_or_username": "your-username"
}
```

**Reset password**:
```bash
POST /api/auth/reset-password
{
  "token": "token-from-server-logs",
  "new_password": "newpassword123"
}
```

> **Note**: For LAN deployments, reset tokens are logged to console. In production, configure email sending.

### Profile Management

**Update profile**:
```bash
PATCH /api/auth/me
{
  "display_name": "John Doe",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

**Get/Update preferences**:
```bash
GET /api/auth/me/preferences
PATCH /api/auth/me/preferences
{
  "theme": "dark",
  "autoplay": true
}
```

---

## ⚡ Performance Notes

- **HLS Transcoding**: Runs in background threads to avoid blocking requests
- **Thumbnails**: Generated asynchronously with dedicated worker queue
- **Redis Caching**: Session validation with automatic fallback to in-memory store
- **HLS Cache Cleanup**: Old cache files auto-deleted after 7 days (configurable)
- **Circuit Breaker**: Redis failures trigger graceful degradation to memory storage

---

## 🛡️ Security

- **JWT Tokens**: Stored in HttpOnly cookies (XSS protection)
- **Redis Session Validation**: Multi-instance session sharing
- **RBAC**: Role-based endpoints (admin, family, guest)
- **Path Traversal Protection**: Input sanitization on all file operations
- **Auto-generated SECRET_KEY**: Falls back safely if not configured (dev mode only)
- **Password Reset Tokens**: SHA-256 hashed, 1-hour expiry, single-use
- **Audit Logging**: All sensitive actions tracked with user attribution

---

## 📊 API Reference

### Authentication
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/logout` - Invalidate session
- `POST /api/auth/register` - Self-registration (guest role)
- `GET /api/auth/verify` - Check session validity
- `POST /api/auth/forgot-password` - Request password reset
- `POST /api/auth/reset-password` - Reset password with token

### User Management (Admin Only)
- `GET /api/auth/users` - List all users
- `POST /api/auth/users` - Create new user
- `PATCH /api/auth/users/{id}` - Update user role/status
- `DELETE /api/auth/users/{id}` - Delete user
- `GET /api/auth/audit` - View audit logs
- `GET /api/auth/stats` - System statistics

### Profile
- `GET /api/auth/me` - Get current user profile
- `PATCH /api/auth/me` - Update profile
- `GET /api/auth/me/preferences` - Get preferences
- `PATCH /api/auth/me/preferences` - Update preferences

### Files
- `GET /api/files/list?path=/` - List directory contents
- `POST /api/files/upload` - Upload file
- `DELETE /api/files/delete` - Delete file
- `POST /api/files/rename` - Rename file
- `GET /api/files/download` - Download file
- `GET /api/files/stream` - Stream video (HLS)

---

## 🐳 Docker Deployment

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/mediahub
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-production-secret-key-here
    volumes:
      - ./shared_media:/app/shared_media
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: mediahub
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## 🔧 Development

### Database Migrations

The migration system automatically runs on startup:

```python
# Add a new migration in core/migrations.py
migrations = [
    {
        "version": "20240601_add_feature",
        "description": "Add new feature column",
        "sql": ["ALTER TABLE users ADD COLUMN new_field TEXT"]
    }
]
```

### Running Tests

```bash
pytest tests/ -v
```

---

## 📝 Configuration Reference

See `.env.example` for all available options:

- **SECRET_KEY**: JWT signing key (auto-generated if not set)
- **DATABASE_URL**: Database connection string
- **REDIS_URL**: Redis connection string (optional)
- **SHARED_FOLDER**: Root directory for media files
- **MAX_UPLOAD_MB**: Maximum file upload size
- **JWT_EXPIRE_HOURS**: Session duration
- **ADMIN_USERNAME/ADMIN_PASSWORD**: Initial admin credentials

---

## 🐛 Troubleshooting

### Redis Connection Failed

```
⚠️ Redis circuit breaker OPENED. Will use memory fallback.
```
**Solution**: Redis is optional. The app will use in-memory sessions. Install Redis or set `REDIS_URL=""` to suppress warnings.

### Session Expired on Restart

**Cause**: Using auto-generated SECRET_KEY or in-memory sessions.
**Solution**: Set `SECRET_KEY` in `.env` and configure Redis for persistent sessions.

### HLS Transcoding Failed

**Cause**: FFmpeg not installed or not in PATH.
**Solution**: Install FFmpeg and ensure it's accessible: `ffmpeg -version`

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

*Built with ❤️ for the LAN streaming community.*
