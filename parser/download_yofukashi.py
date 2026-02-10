#!/usr/bin/env python3
"""
Download Yofukashi no Uta (Call of the Night).

Sources:
- Spanish (es-la): MangaDex
- English: callofthenight.space

Usage:
    python3 download_yofukashi.py
    python3 download_yofukashi.py --start 1 --end 50
    python3 download_yofukashi.py --english-only
    python3 download_yofukashi.py --spanish-only
"""

import asyncio
import argparse
import logging
import ssl
import random
from pathlib import Path

import aiohttp
import certifi

# MangaDex imports
from mangadex_client import get_manga_by_title, get_all_manga_chapters, get_manga_cover
from downloader import download_chapter_to_zip, download_cover

# CallOfTheNight imports
from callofthenight_client import get_all_chapters, get_chapter_info, build_image_url, COTNChapter, BASE_URL
from callofthenight_downloader import download_chapter, download_image

# Common imports
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
        logging.FileHandler("download_yofukashi.log")
    ]
)
logger = logging.getLogger(__name__)

# Config
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
OUTPUT_DIR = Path(__file__).parent.parent / "backup_downloads"
TEMP_DIR = Path(__file__).parent / "temp"
MANGA_SLUG = "yofukashi-no-uta"

# MangaDex ID for Yofukashi no Uta
MANGADEX_ID = "259dfd8a-f06a-4825-8fa6-a2dcd7274230"

# Image server base
IMAGE_BASE = "https://official.lowee.us/manga/Yofukashi-no-Uta"


async def probe_and_download_chapter(
    session: aiohttp.ClientSession,
    chapter_num: str,
    output_dir: Path,
    temp_dir: Path
) -> tuple[Path | None, int]:
    """Probe image server and download chapter directly.

    Returns (zip_path, page_count) or (None, 0) if chapter doesn't exist.
    """
    import zipfile
    from stealth import page_delay, STEALTH_LIMITER, get_image_headers

    # Format chapter number for filename
    ch_padded = chapter_num.zfill(3)
    zip_name = f"{ch_padded}_en.zip"
    zip_path = output_dir / zip_name

    # Skip if already exists on disk
    if zip_path.exists():
        logger.info(f"Already exists: {zip_name}")
        # Count pages in existing zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            return zip_path, len(zf.namelist())

    # Probe first page to check if chapter exists
    first_page_url = build_image_url(chapter_num, 1)

    async with STEALTH_LIMITER:
        headers = get_image_headers(BASE_URL)
        try:
            async with session.head(first_page_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.debug(f"Chapter {chapter_num} not found on server")
                    return None, 0
        except Exception as e:
            logger.error(f"Error probing chapter {chapter_num}: {e}")
            return None, 0

    # Chapter exists, find page count by probing
    logger.info(f"Chapter {chapter_num} found, probing pages...")

    page = 1
    max_pages = 80  # Safety limit

    while page <= max_pages:
        url = build_image_url(chapter_num, page)
        async with STEALTH_LIMITER:
            try:
                async with session.head(url, headers=headers) as resp:
                    if resp.status == 200:
                        page += 1
                    else:
                        break
            except:
                break

    page_count = page - 1
    if page_count == 0:
        logger.error(f"Chapter {chapter_num}: no pages found")
        return None, 0

    logger.info(f"Chapter {chapter_num}: {page_count} pages")

    # Download all pages
    chapter_temp = temp_dir / f"ch{chapter_num}_en"
    chapter_temp.mkdir(parents=True, exist_ok=True)

    downloaded_files = []
    referer = BASE_URL

    for p in range(1, page_count + 1):
        url = build_image_url(chapter_num, p)
        page_file = chapter_temp / f"{p:03d}.png"

        if page_file.exists():
            downloaded_files.append(page_file)
            continue

        if p % 10 == 1:
            logger.info(f"  Downloading pages {p}-{min(p+9, page_count)}/{page_count}")

        if await download_image(session, url, page_file, referer):
            downloaded_files.append(page_file)
        else:
            logger.error(f"  Failed page {p}")

        await page_delay()

    if not downloaded_files:
        logger.error(f"No pages downloaded for chapter {chapter_num}")
        return None, 0

    # Create ZIP
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for page_file in sorted(downloaded_files):
            zf.write(page_file, page_file.name)

    logger.info(f"Created {zip_name} ({len(downloaded_files)} pages)")
    return zip_path, len(downloaded_files)


async def download_spanish_from_mangadex(
    session: aiohttp.ClientSession,
    start_chapter: int = 1,
    end_chapter: int = None
) -> int:
    """Download Spanish chapters from MangaDex."""
    logger.info("\n" + "="*60)
    logger.info("SPANISH from MangaDex (es-la)")
    logger.info("="*60)

    # Get manga info
    await human_delay()
    manga = await get_manga_by_title(session, "Yofukashi no Uta")

    if not manga:
        logger.error("Manga not found on MangaDex!")
        return 0

    manga_id = manga["id"]
    title = manga["attributes"]["title"].get("en", "Yofukashi no Uta")

    # Add to database
    mangadex_url = f"https://mangadex.org/title/{manga_id}"
    add_manga(manga_id, title, mangadex_url, status="downloading")
    db_manga = get_manga_by_mangadex_id(manga_id)

    # Get chapters (Spanish only - es-la will be normalized to es)
    await human_delay()
    logger.info("Fetching Spanish chapters...")
    all_chapters = await get_all_manga_chapters(session, manga_id, languages=["es-la", "es"])

    # Filter by language (already normalized to "es")
    es_chapters = [ch for ch in all_chapters if ch.language == "es"]
    logger.info(f"Found {len(es_chapters)} Spanish chapters")

    # Update DB
    if db_manga:
        update_manga_chapter_counts(db_manga.id, 0, len(es_chapters))

    # Filter by range
    if start_chapter or end_chapter:
        def in_range(ch):
            try:
                num = float(ch.chapter_number)
                if start_chapter and num < start_chapter:
                    return False
                if end_chapter and num > end_chapter:
                    return False
                return True
            except ValueError:
                return True

        es_chapters = [ch for ch in es_chapters if in_range(ch)]
        logger.info(f"After range filter: {len(es_chapters)} chapters")

    # Sort by chapter number
    es_chapters.sort(key=lambda x: float(x.chapter_number) if x.chapter_number.replace('.', '').isdigit() else 0)

    # Setup directories
    chapters_output = OUTPUT_DIR / "chapters" / MANGA_SLUG
    covers_output = OUTPUT_DIR / "covers" / MANGA_SLUG
    chapters_output.mkdir(parents=True, exist_ok=True)
    covers_output.mkdir(parents=True, exist_ok=True)

    # Download cover
    await human_delay()
    cover_filename = await get_manga_cover(session, manga_id)
    if cover_filename:
        cover_path = covers_output / "cover.jpg"
        await download_cover(session, manga_id, cover_filename, cover_path)

    # Download chapters
    downloaded = 0
    for idx, chapter in enumerate(es_chapters, 1):
        ch_num = chapter.chapter_number
        logger.info(f"\n--- Chapter {ch_num} ES ({idx}/{len(es_chapters)}) ---")

        # Check if already downloaded
        if db_manga and is_chapter_downloaded(db_manga.id, ch_num, "es"):
            logger.info("Already downloaded, skipping")
            continue

        zip_path = await download_chapter_to_zip(
            session,
            chapter,
            chapters_output,
            TEMP_DIR / MANGA_SLUG,
            data_saver=False
        )

        if zip_path and db_manga:
            add_downloaded_chapter(
                manga_id=db_manga.id,
                chapter_number=ch_num,
                language="es",
                zip_path=str(zip_path),
                page_count=chapter.page_count
            )
            downloaded += 1

        await chapter_delay()

        # Random longer break
        if random.random() < 0.15:
            pause = random.uniform(15, 45)
            logger.info(f"Taking a break... ({pause:.0f}s)")
            await asyncio.sleep(pause)

    logger.info(f"\nSpanish: downloaded {downloaded} new chapters")
    return downloaded


async def download_english_from_cotn(
    session: aiohttp.ClientSession,
    start_chapter: int = 1,
    end_chapter: int = None
) -> int:
    """Download English chapters from callofthenight.space (direct probe)."""
    logger.info("\n" + "="*60)
    logger.info("ENGLISH from callofthenight.space (direct probe)")
    logger.info("="*60)

    # Get database record (use MangaDex ID)
    db_manga = get_manga_by_mangadex_id(MANGADEX_ID)
    if not db_manga:
        # Create record if doesn't exist
        add_manga(MANGADEX_ID, "Yofukashi no Uta",
                  f"https://mangadex.org/title/{MANGADEX_ID}", status="downloading")
        db_manga = get_manga_by_mangadex_id(MANGADEX_ID)

    # Generate chapter list 1-200 (site doesn't show all, but images exist)
    if end_chapter is None:
        end_chapter = 200

    all_chapters = [str(i) for i in range(start_chapter, end_chapter + 1)]
    logger.info(f"Will check chapters {start_chapter}-{end_chapter}")

    # Filter out already downloaded
    chapters_to_dl = []
    for ch in all_chapters:
        if not is_chapter_downloaded(db_manga.id, ch, "en"):
            chapters_to_dl.append(ch)

    logger.info(f"Already downloaded: {len(all_chapters) - len(chapters_to_dl)}")
    logger.info(f"Chapters to download: {len(chapters_to_dl)}")

    # Setup directories
    chapters_output = OUTPUT_DIR / "chapters" / MANGA_SLUG
    chapters_output.mkdir(parents=True, exist_ok=True)

    # Download chapters
    downloaded = 0
    for idx, ch_num in enumerate(chapters_to_dl, 1):
        logger.info(f"\n--- Chapter {ch_num} EN ({idx}/{len(chapters_to_dl)}) ---")

        # Probe and download directly from image server
        zip_path, page_count = await probe_and_download_chapter(
            session,
            ch_num,
            chapters_output,
            TEMP_DIR / MANGA_SLUG
        )

        if zip_path and db_manga:
            add_downloaded_chapter(
                manga_id=db_manga.id,
                chapter_number=ch_num,
                language="en",
                zip_path=str(zip_path),
                page_count=page_count
            )
            downloaded += 1

        await chapter_delay()

        # Random longer break
        if random.random() < 0.15:
            pause = random.uniform(15, 45)
            logger.info(f"Taking a break... ({pause:.0f}s)")
            await asyncio.sleep(pause)

    logger.info(f"\nEnglish: downloaded {downloaded} new chapters")
    return downloaded


async def main():
    parser = argparse.ArgumentParser(description="Download Yofukashi no Uta")
    parser.add_argument("--start", type=int, default=1, help="Start chapter")
    parser.add_argument("--end", type=int, default=None, help="End chapter")
    parser.add_argument("--english-only", action="store_true", help="Only download English")
    parser.add_argument("--spanish-only", action="store_true", help="Only download Spanish")
    args = parser.parse_args()

    logger.info("="*60)
    logger.info("YOFUKASHI NO UTA DOWNLOADER")
    logger.info("="*60)
    logger.info(f"Output: {OUTPUT_DIR}")
    logger.info(f"Range: {args.start} - {args.end or 'latest'}")
    logger.info("="*60)

    # Initialize database
    init_database()

    # Setup session
    timeout = aiohttp.ClientTimeout(total=120, connect=30)
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT, limit=2)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        total_downloaded = 0

        # Download Spanish from MangaDex
        if not args.english_only:
            try:
                count = await download_spanish_from_mangadex(
                    session, args.start, args.end
                )
                total_downloaded += count
            except Exception as e:
                logger.error(f"Error downloading Spanish: {e}")

            # Pause between sources
            if not args.spanish_only:
                pause = random.uniform(30, 60)
                logger.info(f"\nSwitching source, pausing... ({pause:.0f}s)\n")
                await asyncio.sleep(pause)

        # Download English from callofthenight.space
        if not args.spanish_only:
            try:
                count = await download_english_from_cotn(
                    session, args.start, args.end
                )
                total_downloaded += count
            except Exception as e:
                logger.error(f"Error downloading English: {e}")

    logger.info("\n" + "="*60)
    logger.info(f"DONE! Total downloaded: {total_downloaded} files")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
