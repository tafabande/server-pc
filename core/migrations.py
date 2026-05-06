"""
StreamDrop — Database Migration System
Handles schema versioning and safe database updates.
"""
import logging
import json
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, select, func
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
        for sql in sql_commands:
            await db.execute(sql)
        
        record = MigrationRecord(version=version, description=description)
        db.add(record)
        await db.commit()
        logger.info(f"✅ Migration {version} applied successfully.")
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Failed to apply migration {version}: {e}")
        raise

async def run_migrations():
    """Main entry point to run all pending migrations."""
    await init_migration_table()
    
    async with AsyncSessionFactory() as db:
        applied = await get_applied_migrations(db)
        
        # Define migrations here
        migrations = [
            {
                "version": "20240504_init",
                "description": "Initial schema with user_id in audit_logs",
                "sql": [
                    # This is handled by Base.metadata.create_all in bootstrap_system
                    # but we can add specific ALTER statements here if needed for existing DBs
                ]
            },
            {
                "version": "20240504_add_rls_support",
                "description": "Add owner_id to media_metadata for RLS-like behavior",
                "sql": [
                    "ALTER TABLE media_metadata ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
                ]
            }
        ]
        
        for m in migrations:
            if m["version"] not in applied:
                # For SQLite, we might need special handling for ALTER TABLE
                # but simple ADD COLUMN usually works.
                try:
                    await apply_migration(db, m["version"], m["description"], m["sql"])
                except Exception as e:
                    logger.warning(f"Skipping migration {m['version']} due to error (it might already be applied): {e}")

