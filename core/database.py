import sqlite3
from pathlib import Path
from datetime import datetime
import json
import os

# Put database file in the .logs directory or a dedicated data directory
from config import SHARED_FOLDER
DB_DIR = SHARED_FOLDER / ".data"
DB_DIR.mkdir(exist_ok=True, parents=True)
DB_PATH = DB_DIR / "streamdrop.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Jobs table for compression/HLS worker
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Audit logs for document edits
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            file_path TEXT,
            action TEXT
        )
    """)
    
    # Folder settings (Optimization toggles)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folder_settings (
            folder_path TEXT PRIMARY KEY,
            optimization_enabled BOOLEAN DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

def log_audit(ip_address: str, file_path: str, action: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_logs (ip_address, file_path, action) VALUES (?, ?, ?)",
        (ip_address, file_path, action)
    )
    conn.commit()
    conn.close()

def set_folder_optimization(folder_path: str, enabled: bool):
    conn = get_db()
    conn.execute(
        "INSERT INTO folder_settings (folder_path, optimization_enabled) VALUES (?, ?) ON CONFLICT(folder_path) DO UPDATE SET optimization_enabled = ?",
        (folder_path, enabled, enabled)
    )
    conn.commit()
    conn.close()

def get_folder_optimization(folder_path: str) -> bool:
    conn = get_db()
    cursor = conn.execute("SELECT optimization_enabled FROM folder_settings WHERE folder_path = ?", (folder_path,))
    row = cursor.fetchone()
    conn.close()
    return bool(row["optimization_enabled"]) if row else False

def add_video_job(file_path: str):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO video_jobs (file_path, status) VALUES (?, 'pending')",
            (file_path,)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already exists
    finally:
        conn.close()

def update_job_status(job_id: int, status: str):
    conn = get_db()
    conn.execute(
        "UPDATE video_jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, job_id)
    )
    conn.commit()
    conn.close()

def get_pending_jobs():
    conn = get_db()
    cursor = conn.execute("SELECT id, file_path FROM video_jobs WHERE status = 'pending'")
    jobs = cursor.fetchall()
    conn.close()
    return [dict(row) for row in jobs]

init_db()
