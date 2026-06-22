import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

import config

DB_PATH = config.DATA_DIR / "jobs.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            video_mode TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'queued',
            max_clips INTEGER DEFAULT 5,
            clip_urls TEXT,
            error TEXT,
            webhook_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_job(job_id: str, source_url: str, video_mode: str, max_clips: int, webhook_url: str | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO jobs (id, source_url, video_mode, max_clips, webhook_url, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, source_url, video_mode, max_clips, webhook_url, now, now),
        )


def update_job(job_id: str, status: str, clip_urls: list[str] | None = None, error: str | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status=?, clip_urls=?, error=?, updated_at=? WHERE id=?",
            (status, json.dumps(clip_urls) if clip_urls else None, error, now, job_id),
        )


def get_job(job_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d["clip_urls"]:
            d["clip_urls"] = json.loads(d["clip_urls"])
        return d


def list_jobs(limit: int = 50, offset: int = 0) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d["clip_urls"]:
                d["clip_urls"] = json.loads(d["clip_urls"])
            result.append(d)
        return result
