"""
StreamDrop — pytest Fixtures
Shared test infrastructure for all test modules.

Key fixtures:
  - engine / db_session: In-memory SQLite async DB (no PostgreSQL required for CI)
  - override_db: Overrides FastAPI get_db() dependency with test DB
  - client: TestClient with full app + in-memory DB
  - admin_token / guest_token: Pre-authenticated session cookies
  - test_video: 1-second ~50KB blank H.264 video (created via FFmpeg)
  - test_audio: 1-second silent WAV (no FFmpeg required)
"""

import os
import io
import subprocess
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Force in-memory SQLite for all tests BEFORE importing app modules
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-not-production")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("SHARED_FOLDER", str(Path(tempfile.mkdtemp(prefix="streamdrop_test_"))))
os.environ.setdefault("TRANSCODE_DIR", str(Path(tempfile.mkdtemp(prefix="streamdrop_transcode_"))))

from core.database import Base, get_db


# ── In-memory DB Engine ────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create an in-memory SQLite async engine for the test session."""
    e = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session that rolls back after each test."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ── FastAPI Test Client ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(engine, db_session):
    """
    FastAPI async test client with the DB dependency overridden to use
    the in-memory test database. Auth middleware is active.
    """
    from core.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Seed admin user before tests
    from core.database import User, UserRole
    from core.security import hash_password
    from sqlalchemy import select

    result = await db_session.execute(select(User).where(User.username == "admin"))
    if not result.scalar_one_or_none():
        admin = User(
            username="admin",
            hashed_password=hash_password("testpassword123"),
            role=UserRole.admin,
        )
        guest = User(
            username="guest",
            hashed_password=hash_password("guestpass"),
            role=UserRole.guest,
        )
        family = User(
            username="family",
            hashed_password=hash_password("familypass"),
            role=UserRole.family,
        )
        db_session.add_all([admin, guest, family])
        await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Auth Token Fixtures ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    """Log in as admin and return the session cookie value."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpassword123"},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.cookies.get("streamdrop_session", "")


@pytest_asyncio.fixture
async def guest_token(client: AsyncClient) -> str:
    """Log in as guest and return the session cookie value."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "guest", "password": "guestpass"},
    )
    assert resp.status_code == 200, f"Guest login failed: {resp.text}"
    return resp.cookies.get("streamdrop_session", "")


@pytest_asyncio.fixture
async def family_token(client: AsyncClient) -> str:
    """Log in as family user and return the session cookie value."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "family", "password": "familypass"},
    )
    assert resp.status_code == 200, f"Family login failed: {resp.text}"
    return resp.cookies.get("streamdrop_session", "")


# ── Media Test Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_video(tmp_path_factory) -> Path:
    """
    Create a 1-second, ~50KB blank H.264 video using FFmpeg.
    This is the canonical 'small test video' for all pipeline tests.
    Skips if FFmpeg is not installed.
    """
    out = tmp_path_factory.mktemp("media") / "test_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "color=c=black:size=320x240:rate=24",  # Black frame, 320x240, 24fps
        "-f", "lavfi",
        "-i", "aevalsrc=0:c=stereo:r=44100",          # Silent stereo audio
        "-t", "1",                                      # 1 second duration
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "64k",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        pytest.skip("FFmpeg not available — skipping media pipeline tests")
    assert out.exists() and out.stat().st_size < 200_000, "Test video should be < 200KB"
    return out


@pytest.fixture(scope="session")
def test_audio(tmp_path_factory) -> Path:
    """Create a 1-second silent WAV file using Python only (no FFmpeg needed)."""
    import wave, struct
    out = tmp_path_factory.mktemp("media") / "test_audio.wav"
    sample_rate = 44100
    num_channels = 1
    num_samples = sample_rate  # 1 second

    with wave.open(str(out), "w") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{num_samples}h", *([0] * num_samples)))

    return out
