#!/usr/bin/env python3
"""
Batch download script for multiple manga.
Downloads Beelzebub and Yofukashi No Uta with stealth settings.

Usage:
    python3 download_batch.py

All downloads go to ../backup_downloads/
"""

import asyncio
import logging
import ssl
import random
from pathlib import Path

import aiohttp
import certifi

from mangadex_client import get_manga_by_title, get_all_manga_chapters, get_manga_cover
from downloader import download_chapter_to_zip, download_cover
from manifest import generate_manifest, save_manifest
from database import (
    init_database, add_manga, add_downloaded_chapter,
    get_manga_by_mangadex_id, update_manga_chapter_counts,
    update_manga_status, is_chapter_downloaded, get_downloaded_chapters
)
from stealth import chapter_delay, human_delay

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("download.log")
    ]
)
logger = logging.getLogger(__name__)

# SSL context
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Output directories
OUTPUT_DIR = Path(__file__).parent.parent / "backup_downloads"
TEMP_DIR = Path(__file__).parent / "temp"

# Manga to download
MANGA_LIST = [
    "Beelzebub",
]


def filter_bilingual_chapters(chapters: list) -> dict:
    """Filter to chapters with both EN and ES translations."""
    by_number = {}
    for ch in chapters:
        num = ch.chapter_number
        if num not in by_number:
            by_number[num] = {}
        if ch.language not in by_number[num]:
            by_number[num][ch.language] = ch

    return {
        num: langs for num, langs in by_number.items()
        if "en" in langs and "es" in langs
    }


async def download_single_manga(
    session: aiohttp.ClientSession,
    manga_title: str,
    data_saver: bool = False
):
    """Download a single manga with stealth settings."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Starting download: {manga_title}")
    logger.info(f"{'='*60}\n")

    # Search for manga
    await human_delay()
    manga = await get_manga_by_title(session, manga_title)

    if not manga:
        logger.error(f"Manga not found: {manga_title}")
        return False

    manga_id = manga["id"]
    title = manga["attributes"]["title"].get("en", manga_title)
    manga_slug = title.lower().replace(" ", "-").replace("!", "").replace(":", "")

    # Add to database
    mangadex_url = f"https://mangadex.org/title/{manga_id}"
    add_manga(manga_id, title, mangadex_url, status="downloading")
    db_manga = get_manga_by_mangadex_id(manga_id)

    logger.info(f"Found: {title}")
    logger.info(f"MangaDex ID: {manga_id}")

    # Get chapters
    await human_delay()
    logger.info("Fetching chapter list...")
    all_chapters = await get_all_manga_chapters(session, manga_id)
    logger.info(f"Total chapters: {len(all_chapters)}")

    # Filter bilingual
    bilingual = filter_bilingual_chapters(all_chapters)
    logger.info(f"Bilingual chapters (EN+ES): {len(bilingual)}")

    # Update DB stats
    en_count = len([c for c in all_chapters if c.language == "en"])
    es_count = len([c for c in all_chapters if c.language == "es"])
    if db_manga:
        update_manga_chapter_counts(db_manga.id, en_count, es_count)

    if not bilingual:
        logger.warning(f"No bilingual chapters for {title}!")
        return False

    # Setup directories
    chapters_output = OUTPUT_DIR / "chapters" / manga_slug
    covers_output = OUTPUT_DIR / "covers" / manga_slug
    chapters_output.mkdir(parents=True, exist_ok=True)
    covers_output.mkdir(parents=True, exist_ok=True)

    # Download cover
    await human_delay()
    logger.info("Downloading cover...")
    cover_filename = await get_manga_cover(session, manga_id)
    if cover_filename:
        cover_path = covers_output / "cover.jpg"
        await download_cover(session, manga_id, cover_filename, cover_path)

    # Download chapters
    downloaded_count = 0
    total_bilingual = len(bilingual)
    chapter_nums = sorted(
        bilingual.keys(),
        key=lambda x: float(x) if x.replace('.', '').isdigit() else 0
    )

    for idx, ch_num in enumerate(chapter_nums, 1):
        langs = bilingual[ch_num]
        logger.info(f"\n--- Chapter {ch_num} ({idx}/{total_bilingual}) ---")

        for lang in ["en", "es"]:
            chapter = langs[lang]

            # Check if already downloaded
            if db_manga and is_chapter_downloaded(db_manga.id, ch_num, lang):
                logger.info(f"  {lang.upper()}: already downloaded, skipping")
                continue

            logger.info(f"  {lang.upper()}: downloading...")

            zip_path = await download_chapter_to_zip(
                session,
                chapter,
                chapters_output,
                TEMP_DIR / manga_slug,
                data_saver=data_saver
            )

            if zip_path and db_manga:
                add_downloaded_chapter(
                    manga_id=db_manga.id,
                    chapter_number=ch_num,
                    language=lang,
                    zip_path=str(zip_path),
                    page_count=chapter.page_count
                )
                downloaded_count += 1
                logger.info(f"  {lang.upper()}: done!")

            # Stealth delay between language versions
            await chapter_delay()

        # Extra delay between chapters (random break)
        if random.random() < 0.2:
            pause = random.uniform(10, 30)
            logger.info(f"Taking a break... ({pause:.0f}s)")
            await asyncio.sleep(pause)

    # Generate manifest
    logger.info("\nGenerating manifest...")
    manifest = generate_manifest(
        manga_slug,
        title,
        chapters_output,
        f"covers/{manga_slug}/cover.jpg"
    )
    manifest_path = OUTPUT_DIR / manga_slug / "manifest.json"
    save_manifest(manifest, manifest_path)

    # Update status
    if db_manga:
        dl_chapters = get_downloaded_chapters(db_manga.id)
        unique_ch = set(dc["chapter_number"] for dc in dl_chapters)
        if len(unique_ch) >= len(bilingual):
            update_manga_status(db_manga.id, "completed")
            logger.info("Marked as COMPLETED!")

    logger.info(f"\n{title}: Downloaded {downloaded_count} new files")
    return True


async def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("MangaOff Batch Downloader (Stealth Mode)")
    logger.info("="*60)
    logger.info(f"Output: {OUTPUT_DIR}")
    logger.info(f"Manga list: {', '.join(MANGA_LIST)}")
    logger.info("="*60)

    # Initialize database
    init_database()

    # Create session with timeout
    timeout = aiohttp.ClientTimeout(total=60, connect=10)
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT, limit=2)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for i, manga_title in enumerate(MANGA_LIST):
            try:
                await download_single_manga(session, manga_title)
            except Exception as e:
                logger.error(f"Error downloading {manga_title}: {e}")
                continue

            # Long pause between different manga
            if i < len(MANGA_LIST) - 1:
                pause = random.uniform(30, 60)
                logger.info(f"\nPausing before next manga... ({pause:.0f}s)\n")
                await asyncio.sleep(pause)

    logger.info("\n" + "="*60)
    logger.info("All downloads completed!")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
