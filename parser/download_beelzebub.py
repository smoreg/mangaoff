#!/usr/bin/env python3
"""
Download Beelzebub from MangaDex.

Usage:
    python3 download_beelzebub.py
    python3 download_beelzebub.py --start 1 --end 50
"""

import asyncio
import argparse
import logging
import ssl
import random
from pathlib import Path

import aiohttp
import certifi

from mangadex_client import (
    get_manga_by_title, get_all_manga_chapters, get_manga_cover, Chapter
)
from downloader import download_chapter_to_zip, download_cover
from manifest import generate_manifest, save_manifest
from database import (
    init_database, add_manga, add_downloaded_chapter,
    get_manga_by_mangadex_id, update_manga_chapter_counts,
    update_manga_status, is_chapter_downloaded, get_downloaded_chapters
)
from stealth import chapter_delay, human_delay

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("download_beelzebub.log")
    ]
)
logger = logging.getLogger(__name__)

# Config
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
OUTPUT_DIR = Path(__file__).parent.parent / "backup_downloads"
TEMP_DIR = Path(__file__).parent / "temp"


def filter_bilingual_chapters(chapters: list[Chapter]) -> dict[str, dict[str, Chapter]]:
    """Filter to chapters with both EN and ES."""
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


async def main():
    parser = argparse.ArgumentParser(description="Download Beelzebub")
    parser.add_argument("--start", type=int, default=1, help="Start chapter")
    parser.add_argument("--end", type=int, default=None, help="End chapter")
    parser.add_argument("--data-saver", action="store_true", help="Lower quality images")
    args = parser.parse_args()

    logger.info("="*60)
    logger.info("BEELZEBUB DOWNLOADER")
    logger.info("="*60)
    logger.info(f"Output: {OUTPUT_DIR}")
    logger.info(f"Range: {args.start} - {args.end or 'all'}")
    logger.info("="*60)

    # Initialize database
    init_database()

    # Setup session
    timeout = aiohttp.ClientTimeout(total=120, connect=30)
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT, limit=2)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Find manga
        await human_delay()
        logger.info("Searching for Beelzebub...")
        manga = await get_manga_by_title(session, "Beelzebub")

        if not manga:
            logger.error("Manga not found!")
            return

        manga_id = manga["id"]
        title = manga["attributes"]["title"].get("en", "Beelzebub")
        manga_slug = title.lower().replace(" ", "-")

        logger.info(f"Found: {title}")
        logger.info(f"ID: {manga_id}")

        # Add to database
        mangadex_url = f"https://mangadex.org/title/{manga_id}"
        add_manga(manga_id, title, mangadex_url, status="downloading")
        db_manga = get_manga_by_mangadex_id(manga_id)

        # Get chapters
        await human_delay()
        logger.info("Fetching chapters...")
        all_chapters = await get_all_manga_chapters(session, manga_id)
        logger.info(f"Total chapters: {len(all_chapters)}")

        # Count by language
        en_count = len([c for c in all_chapters if c.language == "en"])
        es_count = len([c for c in all_chapters if c.language == "es"])
        logger.info(f"EN: {en_count}, ES: {es_count}")

        if db_manga:
            update_manga_chapter_counts(db_manga.id, en_count, es_count)

        # Filter bilingual
        bilingual = filter_bilingual_chapters(all_chapters)
        logger.info(f"Bilingual (EN+ES): {len(bilingual)}")

        if not bilingual:
            logger.error("No bilingual chapters found!")
            return

        # Apply range filter
        if args.start or args.end:
            def in_range(num):
                try:
                    n = float(num)
                    if args.start and n < args.start:
                        return False
                    if args.end and n > args.end:
                        return False
                    return True
                except ValueError:
                    return True

            bilingual = {n: l for n, l in bilingual.items() if in_range(n)}
            logger.info(f"After range filter: {len(bilingual)}")

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
            await download_cover(session, manga_id, cover_filename, covers_output / "cover.jpg")

        # Sort chapters
        chapter_nums = sorted(
            bilingual.keys(),
            key=lambda x: float(x) if x.replace('.', '').isdigit() else 0
        )

        # Download chapters
        downloaded = 0
        total = len(chapter_nums)

        for idx, ch_num in enumerate(chapter_nums, 1):
            langs = bilingual[ch_num]
            logger.info(f"\n{'='*40}")
            logger.info(f"Chapter {ch_num} ({idx}/{total})")
            logger.info(f"{'='*40}")

            for lang in ["en", "es"]:
                chapter = langs[lang]

                # Check if already downloaded
                if db_manga and is_chapter_downloaded(db_manga.id, ch_num, lang):
                    logger.info(f"  {lang.upper()}: already downloaded")
                    continue

                logger.info(f"  {lang.upper()}: downloading...")

                zip_path = await download_chapter_to_zip(
                    session,
                    chapter,
                    chapters_output,
                    TEMP_DIR / manga_slug,
                    data_saver=args.data_saver
                )

                if zip_path and db_manga:
                    add_downloaded_chapter(
                        manga_id=db_manga.id,
                        chapter_number=ch_num,
                        language=lang,
                        zip_path=str(zip_path),
                        page_count=chapter.page_count
                    )
                    downloaded += 1
                    logger.info(f"  {lang.upper()}: done!")

                await chapter_delay()

            # Random longer break (20% chance)
            if random.random() < 0.2:
                pause = random.uniform(20, 60)
                logger.info(f"\nTaking a break... ({pause:.0f}s)")
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

        logger.info("\n" + "="*60)
        logger.info(f"DONE! Downloaded {downloaded} new files")
        logger.info(f"Bilingual chapters available: {len(bilingual)}")
        logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
