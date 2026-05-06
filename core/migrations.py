"""
StreamDrop — Database Migration System
Handles schema versioning and safe database updates.
"""
import logging
import json
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import Base, engine, AsyncSessionFactory

logger = logging.getLogger("streamdrop.migrations")

class MigrationRecord(Base):
    __tablename__ = "_migrations"
    version = Column(String(64), primary_key=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)

async def init_migration_table():
    """Ensure the migration tracking table exists."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_applied_migrations(db: AsyncSession) -> set[str]:
    """Fetch all applied migration versions."""
    result = await db.execute(select(MigrationRecord.version))
    return {row[0] for row in result.all()}

async def apply_migration(db: AsyncSession, version: str, description: str, sql_commands: list[str]):
    """Apply a single migration within a transaction."""
    logger.info(f"🚀 Applying migration {version}: {description}")
    try:
        # Execute each SQL command with proper text() wrapper
        for sql in sql_commands:
            if sql.strip():  # Skip empty commands
                await db.execute(text(sql))

        # Record successful migration
        record = MigrationRecord(version=version, description=description)
        db.add(record)
        await db.commit()

        logger.info(f"✅ Migration {version} applied successfully")

    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Migration {version} FAILED: {e}")
        logger.error(f"⚠️ Database may be in inconsistent state. Manual intervention required.")
        raise  # Stop on migration failure

async def add_owner_id_if_missing(db: AsyncSession):
    """Add owner_id column if it doesn't exist (SQLite compatible)."""
    try:
        # Try to select the column - if it fails, column doesn't exist
        await db.execute(text("SELECT owner_id FROM media_metadata LIMIT 1"))
        logger.info("owner_id column already exists, skipping")
    except Exception:
        # Column doesn't exist, add it
        logger.info("Adding owner_id column to media_metadata")
        await db.execute(text(
            "ALTER TABLE media_metadata ADD COLUMN owner_id INTEGER"
        ))
        await db.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_media_metadata_owner_id ON media_metadata(owner_id)"
        ))
        await db.commit()

async def run_migrations():
    """Main entry point to run all pending migrations."""
    await init_migration_table()

    async with AsyncSessionFactory() as db:
        applied = await get_applied_migrations(db)

        # Special handler for SQLite ALTER TABLE limitations
        if "20240504_add_rls_support" not in applied:
            logger.info("🔧 Running SQLite-compatible owner_id migration...")
            try:
                await add_owner_id_if_missing(db)
                # Record the migration
                record = MigrationRecord(
                    version="20240504_add_rls_support",
                    description="Add owner_id to media_metadata for RLS-like behavior"
                )
                db.add(record)
                await db.commit()
                logger.info("✅ owner_id migration completed")
            except Exception as e:
                logger.warning(f"⚠️ owner_id migration issue (may already exist): {e}")

        # Define additional migrations here
        migrations = [
            {
                "version": "20240504_init",
                "description": "Initial schema with user_id in audit_logs",
                "sql": [
                    # This is handled by Base.metadata.create_all in bootstrap_system
                    # but we can add specific ALTER statements here if needed for existing DBs
                ]
            }
        ]

        for m in migrations:
            if m["version"] not in applied and m["sql"]:
                try:
                    await apply_migration(db, m["version"], m["description"], m["sql"])
                except Exception as e:
                    logger.warning(f"Skipping migration {m['version']} due to error (it might already be applied): {e}")

