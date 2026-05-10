import os
import aiosqlite
import logging
from datetime import datetime, date
from pathlib import Path

log = logging.getLogger(__name__)
DB_PATH = os.getenv("DB_PATH", "/app/data/pluto.db")


class Database:
    async def init(self):
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    registered_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_usage (
                    uid TEXT NOT NULL,
                    day TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (uid, day)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    bvid TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await db.commit()
        log.info("Database initialized")

    async def save_user_email(self, uid: str, email: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (uid, email, registered_at) VALUES (?, ?, ?)",
                (uid, email, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def get_user_email(self, uid: str) -> str | None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT email FROM users WHERE uid = ?", (uid,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else None

    async def get_transcript(self, bvid: str) -> tuple[str, str] | None:
        """命中返回 (text, source)；未命中返回 None。source ∈ {'subtitle', 'asr'}"""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT text, source FROM transcripts WHERE bvid = ?", (bvid,)
            ) as cur:
                row = await cur.fetchone()
                return (row[0], row[1]) if row else None

    async def save_transcript(self, bvid: str, text: str, source: str) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO transcripts (bvid, text, source, created_at) VALUES (?, ?, ?, ?)",
                (bvid, text, source, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def check_and_increment_usage(self, uid: str, limit: int) -> bool:
        today = date.today().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT count FROM daily_usage WHERE uid = ? AND day = ?", (uid, today)
            ) as cur:
                row = await cur.fetchone()
            count = row[0] if row else 0
            if count >= limit:
                return False
            await db.execute(
                "INSERT INTO daily_usage (uid, day, count) VALUES (?, ?, 1) "
                "ON CONFLICT(uid, day) DO UPDATE SET count = count + 1",
                (uid, today),
            )
            await db.commit()
            return True
