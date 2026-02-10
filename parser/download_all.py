#!/usr/bin/env python3
"""
Download all bilingual manga from wishlist.

Uses stealth mode and database tracking.
Spanish: es and es-la (saved as es)
English: en

Only downloads chapters with BOTH languages available.

Usage:
    python3 download_all.py --scan          # Scan and show stats only
    python3 download_all.py                 # Download everything
    python3 download_all.py --manga "Title" # Download specific manga
"""

import asyncio
import argparse
import logging
import ssl
import random
from pathlib import Path
from dataclasses import dataclass

import aiohttp
import certifi

from mangadex_client import (
    get_all_manga_chapters, get_manga_cover, Chapter
)
from downloader import download_chapter_to_zip, download_cover
from database import (
    init_database, get_all_manga, add_downloaded_chapter,
    update_manga_chapter_counts, update_manga_status,
    is_chapter_downloaded, get_manga_by_mangadex_id
)
from stealth import chapter_delay, human_delay

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("download_all.log")
    ]
)
logger = logging.getLogger(__name__)

# Config
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
OUTPUT_DIR = Path(__file__).parent.parent / "backup_downloads"
TEMP_DIR = Path(__file__).parent / "temp"

# Excluded manga (currently downloading or special handling)
EXCLUDED_SLUGS = ["beelzebub", "yofukashi-no-uta"]


@dataclass
class MangaStats:
    """Stats for a single manga."""
    title: str
    mangadex_id: str
    slug: str
    total_en: int = 0
    total_es: int = 0
    bilingual_count: int = 0
    already_downloaded: int = 0
    to_download: int = 0
    bilingual_chapters: dict = None  # {chapter_num: {"en": Chapter, "es": Chapter}}

    def __post_init__(self):
        if self.bilingual_chapters is None:
            self.bilingual_chapters = {}


def make_slug(title: str) -> str:
    """Create URL-friendly slug from title."""
    return title.lower().replace(" ", "-").replace(":", "").replace("!", "")


def filter_bilingual_chapters(chapters: list[Chapter]) -> dict[str, dict[str, Chapter]]:
    """Group chapters by number and filter to only those with both EN and ES.

    Returns dict: {chapter_number: {"en": Chapter, "es": Chapter}}
    """
    by_number: dict[str, dict[str, Chapter]] = {}

    for ch in chapters:
        num = ch.chapter_number
        if num not in by_number:
            by_number[num] = {}

        # Keep the first (or best) version for each language
        if ch.language not in by_number[num]:
            by_number[num][ch.language] = ch

    # Filter to only bilingual chapters
    bilingual = {
        num: langs for num, langs in by_number.items()
        if "en" in langs and "es" in langs
    }

    return bilingual


async def scan_manga(
    session: aiohttp.ClientSession,
    mangadex_id: str,
    title: str,
    db_manga_id: int
) -> MangaStats:
    """Scan a single manga and return stats."""
    slug = make_slug(title)
    stats = MangaStats(
        title=title,
        mangadex_id=mangadex_id,
        slug=slug
    )

    try:
        # Get all chapters
        await human_delay()
        chapters = await get_all_manga_chapters(session, mangadex_id)

        # Count by language
        stats.total_en = len([c for c in chapters if c.language == "en"])
        stats.total_es = len([c for c in chapters if c.language == "es"])

        # Filter bilingual
        bilingual = filter_bilingual_chapters(chapters)
        stats.bilingual_count = len(bilingual)
        stats.bilingual_chapters = bilingual

        # Count already downloaded
        for ch_num in bilingual.keys():
            en_dl = is_chapter_downloaded(db_manga_id, ch_num, "en")
            es_dl = is_chapter_downloaded(db_manga_id, ch_num, "es")
            if en_dl and es_dl:
                stats.already_downloaded += 1

        stats.to_download = stats.bilingual_count - stats.already_downloaded

    except Exception as e:
        logger.error(f"Error scanning {title}: {e}")

    return stats


async def scan_all_manga(session: aiohttp.ClientSession) -> list[MangaStats]:
    """Scan all manga in wishlist and return stats."""
    all_manga = get_all_manga()

    # Filter out excluded
    manga_to_scan = [
        m for m in all_manga
        if make_slug(m.title) not in EXCLUDED_SLUGS
    ]

    logger.info(f"Scanning {len(manga_to_scan)} manga...")
    logger.info(f"(Excluded: {EXCLUDED_SLUGS})")

    all_stats = []
    for idx, manga in enumerate(manga_to_scan, 1):
        logger.info(f"\n[{idx}/{len(manga_to_scan)}] Scanning: {manga.title}")

        stats = await scan_manga(
            session,
            manga.mangadex_id,
            manga.title,
            manga.id
        )
        all_stats.append(stats)

        # Update DB with chapter counts
        update_manga_chapter_counts(manga.id, stats.total_en, stats.total_es)

        # Random longer break occasionally
        if random.random() < 0.1:
            pause = random.uniform(5, 15)
            logger.info(f"Taking a short break... ({pause:.0f}s)")
            await asyncio.sleep(pause)

    return all_stats


def print_stats(all_stats: list[MangaStats]):
    """Print statistics table."""
    print("\n" + "=" * 80)
    print("SCAN RESULTS")
    print("=" * 80)

    # Sort by chapters to download (most first)
    sorted_stats = sorted(all_stats, key=lambda x: x.to_download, reverse=True)

    total_to_dl = 0
    total_bilingual = 0

    print(f"\n{'Manga':<40} {'EN':>6} {'ES':>6} {'Both':>6} {'Done':>6} {'TODO':>6}")
    print("-" * 80)

    for s in sorted_stats:
        print(f"{s.title[:39]:<40} {s.total_en:>6} {s.total_es:>6} {s.bilingual_count:>6} {s.already_downloaded:>6} {s.to_download:>6}")
        total_to_dl += s.to_download
        total_bilingual += s.bilingual_count

    print("-" * 80)
    print(f"{'TOTAL':<40} {'':<6} {'':<6} {total_bilingual:>6} {'':<6} {total_to_dl:>6}")
    print("=" * 80)

    # Estimate time (very rough: ~30 sec per chapter with both languages)
    if total_to_dl > 0:
        est_minutes = (total_to_dl * 30) / 60
        est_hours = est_minutes / 60
        print(f"\nEstimated time: ~{est_hours:.1f} hours ({est_minutes:.0f} minutes)")
        print(f"Chapters to download: {total_to_dl} x 2 languages = {total_to_dl * 2} archives")

    return sorted_stats


async def download_manga(
    session: aiohttp.ClientSession,
    stats: MangaStats,
    db_manga_id: int
) -> int:
    """Download all bilingual chapters for a manga."""
    if stats.to_download == 0:
        logger.info(f"Nothing to download for {stats.title}")
        return 0

    logger.info(f"\n{'=' * 60}")
    logger.info(f"DOWNLOADING: {stats.title}")
    logger.info(f"Chapters: {stats.to_download} to download")
    logger.info(f"{'=' * 60}")

    # Setup directories
    chapters_output = OUTPUT_DIR / "chapters" / stats.slug
    covers_output = OUTPUT_DIR / "covers" / stats.slug
    chapters_output.mkdir(parents=True, exist_ok=True)
    covers_output.mkdir(parents=True, exist_ok=True)

    # Download cover
    await human_delay()
    try:
        from mangadex_client import get_manga_cover
        cover_filename = await get_manga_cover(session, stats.mangadex_id)
        if cover_filename:
            cover_path = covers_output / "cover.jpg"
            if not cover_path.exists():
                await download_cover(session, stats.mangadex_id, cover_filename, cover_path)
    except Exception as e:
        logger.warning(f"Failed to download cover: {e}")

    # Sort chapters by number
    sorted_chapters = sorted(
        stats.bilingual_chapters.keys(),
        key=lambda x: float(x) if x.replace('.', '').isdigit() else 0
    )

    downloaded = 0
    for ch_num in sorted_chapters:
        langs = stats.bilingual_chapters[ch_num]

        # Check if already downloaded
        en_done = is_chapter_downloaded(db_manga_id, ch_num, "en")
        es_done = is_chapter_downloaded(db_manga_id, ch_num, "es")

        if en_done and es_done:
            continue

        logger.info(f"\n--- Chapter {ch_num} ---")

        # Download EN
        if not en_done:
            en_ch = langs["en"]
            logger.info(f"Downloading EN ({en_ch.page_count} pages)...")
            try:
                zip_path = await download_chapter_to_zip(
                    session, en_ch, chapters_output,
                    TEMP_DIR / stats.slug, data_saver=False
                )
                if zip_path:
                    add_downloaded_chapter(
                        manga_id=db_manga_id,
                        chapter_number=ch_num,
                        language="en",
                        zip_path=str(zip_path),
                        page_count=en_ch.page_count
                    )
                    downloaded += 1
            except Exception as e:
                logger.error(f"Failed EN: {e}")

            await chapter_delay()

        # Download ES
        if not es_done:
            es_ch = langs["es"]
            logger.info(f"Downloading ES ({es_ch.page_count} pages)...")
            try:
                zip_path = await download_chapter_to_zip(
                    session, es_ch, chapters_output,
                    TEMP_DIR / stats.slug, data_saver=False
                )
                if zip_path:
                    add_downloaded_chapter(
                        manga_id=db_manga_id,
                        chapter_number=ch_num,
                        language="es",
                        zip_path=str(zip_path),
                        page_count=es_ch.page_count
                    )
                    downloaded += 1
            except Exception as e:
                logger.error(f"Failed ES: {e}")

            await chapter_delay()

        # Random longer break
        if random.random() < 0.15:
            pause = random.uniform(15, 45)
            logger.info(f"Taking a break... ({pause:.0f}s)")
            await asyncio.sleep(pause)

    return downloaded


async def main():
    parser = argparse.ArgumentParser(description="Download all bilingual manga")
    parser.add_argument("--scan", action="store_true", help="Only scan and show stats")
    parser.add_argument("--manga", type=str, help="Download specific manga by title")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MANGAOFF - BATCH DOWNLOADER")
    logger.info("=" * 60)
    logger.info(f"Output: {OUTPUT_DIR}")
    logger.info(f"Mode: {'SCAN ONLY' if args.scan else 'DOWNLOAD'}")
    logger.info("=" * 60)

    # Initialize database
    init_database()

    # Setup session
    timeout = aiohttp.ClientTimeout(total=120, connect=30)
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT, limit=2)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Scan all manga
        all_stats = await scan_all_manga(session)

        # Print stats
        sorted_stats = print_stats(all_stats)

        if args.scan:
            logger.info("\nScan complete. Use without --scan to download.")
            return

        # Filter by specific manga if requested
        if args.manga:
            sorted_stats = [s for s in sorted_stats if args.manga.lower() in s.title.lower()]
            if not sorted_stats:
                logger.error(f"Manga not found: {args.manga}")
                return

        # Download
        total_downloaded = 0
        for stats in sorted_stats:
            if stats.to_download == 0:
                continue

            db_manga = get_manga_by_mangadex_id(stats.mangadex_id)
            if not db_manga:
                continue

            count = await download_manga(session, stats, db_manga.id)
            total_downloaded += count

            # Update status
            if stats.to_download == count // 2:  # Divided by 2 because we count both langs
                update_manga_status(db_manga.id, "completed")
            else:
                update_manga_status(db_manga.id, "downloading")

            # Break between manga
            if stats != sorted_stats[-1]:
                pause = random.uniform(30, 90)
                logger.info(f"\nSwitching to next manga, pausing... ({pause:.0f}s)\n")
                await asyncio.sleep(pause)

    logger.info("\n" + "=" * 60)
    logger.info(f"DONE! Total downloaded: {total_downloaded} archives")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
