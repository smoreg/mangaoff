"""SQLite database for tracking manga downloads."""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent / "manga_tracker.db"


@dataclass
class MangaRecord:
    """Manga record from database."""
    id: int
    mangadex_id: str
    title: str
    slug: str
    mangadex_url: str
    total_chapters_en: Optional[int]
    total_chapters_es: Optional[int]
    downloaded_chapters: int
    status: str  # wishlist, downloading, completed
    created_at: str
    updated_at: str


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: Path = DEFAULT_DB_PATH):
    """Initialize database schema."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Manga table - tracks all manga we want to download
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manga (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mangadex_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            mangadex_url TEXT NOT NULL,
            total_chapters_en INTEGER,
            total_chapters_es INTEGER,
            status TEXT DEFAULT 'wishlist',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Downloaded chapters table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS downloaded_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manga_id INTEGER NOT NULL,
            chapter_number TEXT NOT NULL,
            language TEXT NOT NULL,
            zip_path TEXT,
            page_count INTEGER,
            downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manga_id) REFERENCES manga(id),
            UNIQUE(manga_id, chapter_number, language)
        )
    """)

    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_manga_mangadex_id ON manga(mangadex_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chapters_manga_id ON downloaded_chapters(manga_id)
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized: {db_path}")


def add_manga(
    mangadex_id: str,
    title: str,
    mangadex_url: str,
    status: str = "wishlist",
    db_path: Path = DEFAULT_DB_PATH
) -> int:
    """Add manga to database. Returns manga id."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    slug = title.lower().replace(" ", "-").replace(":", "").replace("!", "")

    cursor.execute("""
        INSERT INTO manga (mangadex_id, title, slug, mangadex_url, status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(mangadex_id) DO UPDATE SET
            title = excluded.title,
            mangadex_url = excluded.mangadex_url,
            updated_at = CURRENT_TIMESTAMP
    """, (mangadex_id, title, slug, mangadex_url, status))

    conn.commit()
    manga_id = cursor.lastrowid or get_manga_by_mangadex_id(mangadex_id, db_path).id
    conn.close()

    return manga_id


def get_manga_by_mangadex_id(mangadex_id: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[MangaRecord]:
    """Get manga by MangaDex ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.*,
               (SELECT COUNT(*) FROM downloaded_chapters dc WHERE dc.manga_id = m.id) as downloaded_chapters
        FROM manga m
        WHERE m.mangadex_id = ?
    """, (mangadex_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return MangaRecord(
            id=row["id"],
            mangadex_id=row["mangadex_id"],
            title=row["title"],
            slug=row["slug"],
            mangadex_url=row["mangadex_url"],
            total_chapters_en=row["total_chapters_en"],
            total_chapters_es=row["total_chapters_es"],
            downloaded_chapters=row["downloaded_chapters"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


def get_manga_by_slug(slug: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[MangaRecord]:
    """Get manga by slug."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.*,
               (SELECT COUNT(*) FROM downloaded_chapters dc WHERE dc.manga_id = m.id) as downloaded_chapters
        FROM manga m
        WHERE m.slug = ?
    """, (slug,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return MangaRecord(
            id=row["id"],
            mangadex_id=row["mangadex_id"],
            title=row["title"],
            slug=row["slug"],
            mangadex_url=row["mangadex_url"],
            total_chapters_en=row["total_chapters_en"],
            total_chapters_es=row["total_chapters_es"],
            downloaded_chapters=row["downloaded_chapters"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


def update_manga_chapter_counts(
    manga_id: int,
    total_en: int,
    total_es: int,
    db_path: Path = DEFAULT_DB_PATH
):
    """Update total chapter counts for manga."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE manga
        SET total_chapters_en = ?, total_chapters_es = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (total_en, total_es, manga_id))

    conn.commit()
    conn.close()


def update_manga_status(manga_id: int, status: str, db_path: Path = DEFAULT_DB_PATH):
    """Update manga status."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE manga SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (status, manga_id))

    conn.commit()
    conn.close()


def add_downloaded_chapter(
    manga_id: int,
    chapter_number: str,
    language: str,
    zip_path: str,
    page_count: int = 0,
    db_path: Path = DEFAULT_DB_PATH
):
    """Record a downloaded chapter."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO downloaded_chapters (manga_id, chapter_number, language, zip_path, page_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(manga_id, chapter_number, language) DO UPDATE SET
            zip_path = excluded.zip_path,
            page_count = excluded.page_count,
            downloaded_at = CURRENT_TIMESTAMP
    """, (manga_id, chapter_number, language, zip_path, page_count))

    conn.commit()
    conn.close()


def get_downloaded_chapters(manga_id: int, db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """Get all downloaded chapters for a manga."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT chapter_number, language, zip_path, page_count, downloaded_at
        FROM downloaded_chapters
        WHERE manga_id = ?
        ORDER BY CAST(chapter_number AS REAL), language
    """, (manga_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def is_chapter_downloaded(
    manga_id: int,
    chapter_number: str,
    language: str,
    db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """Check if chapter is already downloaded."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1 FROM downloaded_chapters
        WHERE manga_id = ? AND chapter_number = ? AND language = ?
    """, (manga_id, chapter_number, language))

    result = cursor.fetchone() is not None
    conn.close()
    return result


def get_all_manga(db_path: Path = DEFAULT_DB_PATH) -> list[MangaRecord]:
    """Get all manga from database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.*,
               (SELECT COUNT(*) FROM downloaded_chapters dc WHERE dc.manga_id = m.id) as downloaded_chapters
        FROM manga m
        ORDER BY m.title
    """)

    rows = cursor.fetchall()
    conn.close()

    return [MangaRecord(
        id=row["id"],
        mangadex_id=row["mangadex_id"],
        title=row["title"],
        slug=row["slug"],
        mangadex_url=row["mangadex_url"],
        total_chapters_en=row["total_chapters_en"],
        total_chapters_es=row["total_chapters_es"],
        downloaded_chapters=row["downloaded_chapters"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    ) for row in rows]


def get_download_stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """Get download statistics."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM manga")
    total_manga = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM manga WHERE status = 'completed'")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM manga WHERE status = 'wishlist'")
    wishlist = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM downloaded_chapters")
    total_chapters = cursor.fetchone()[0]

    conn.close()

    return {
        "total_manga": total_manga,
        "completed": completed,
        "wishlist": wishlist,
        "in_progress": total_manga - completed - wishlist,
        "total_downloaded_chapters": total_chapters
    }


def extract_mangadex_id(url: str) -> str:
    """Extract manga ID from MangaDex URL."""
    # URL format: https://mangadex.org/title/{uuid}/slug
    parts = url.rstrip("/").split("/")
    for i, part in enumerate(parts):
        if part == "title" and i + 1 < len(parts):
            return parts[i + 1]
    raise ValueError(f"Cannot extract manga ID from URL: {url}")
