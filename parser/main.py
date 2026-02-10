#!/usr/bin/env python3
"""MangaOff parser - downloads manga chapters from MangaDex."""

import asyncio
import argparse
import logging
import ssl
from pathlib import Path

import aiohttp
import certifi

from mangadex_client import (
    get_manga_by_title, get_all_manga_chapters, get_manga_cover, Chapter
)
from downloader import download_chapter_to_zip, download_cover
from manifest import generate_manifest, save_manifest
from stealth import chapter_delay, human_delay
from database import (
    init_database, add_manga, add_downloaded_chapter,
    get_manga_by_mangadex_id, update_manga_chapter_counts,
    update_manga_status, is_chapter_downloaded
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# SSL context using certifi certificates
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Default output directory
DEFAULT_OUTPUT = Path("./output")
DEFAULT_TEMP = Path("./temp")


def filter_bilingual_chapters(chapters: list[Chapter]) -> dict[str, dict[str, Chapter]]:
    """Group chapters by number and filter to only those with both EN and ES.

    Returns dict: {chapter_number: {"en": Chapter, "es": Chapter}}
    """
    # Group by chapter number
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


async def download_manga(
    manga_title: str,
    output_dir: Path,
    temp_dir: Path,
    chapter_range: tuple[int, int] = None,
    data_saver: bool = False
):
    """Download manga chapters with both EN and ES translations."""

    # Initialize database
    init_database()

    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Find manga
        logger.info(f"Searching for: {manga_title}")
        manga = await get_manga_by_title(session, manga_title)

        if not manga:
            logger.error(f"Manga not found: {manga_title}")
            return

        manga_id = manga["id"]
        title = manga["attributes"]["title"].get("en", manga_title)
        manga_slug = title.lower().replace(" ", "-")

        # Add/update manga in database
        mangadex_url = f"https://mangadex.org/title/{manga_id}"
        add_manga(manga_id, title, mangadex_url, status="downloading")
        db_manga = get_manga_by_mangadex_id(manga_id)

        logger.info(f"Found: {title} ({manga_id})")

        # Get all chapters
        logger.info("Fetching chapter list...")
        all_chapters = await get_all_manga_chapters(session, manga_id)
        logger.info(f"Total chapters found: {len(all_chapters)}")

        # Filter to bilingual only
        bilingual = filter_bilingual_chapters(all_chapters)
        logger.info(f"Bilingual chapters (EN+ES): {len(bilingual)}")

        # Count total chapters per language and update database
        en_count = len([c for c in all_chapters if c.language == "en"])
        es_count = len([c for c in all_chapters if c.language == "es"])
        if db_manga:
            update_manga_chapter_counts(db_manga.id, en_count, es_count)

        if not bilingual:
            logger.error("No bilingual chapters found!")
            return

        # Apply chapter range filter if specified
        if chapter_range:
            start, end = chapter_range
            bilingual = {
                num: langs for num, langs in bilingual.items()
                if start <= float(num) <= end
            }
            logger.info(f"After range filter ({start}-{end}): {len(bilingual)} chapters")

        # Create output directories
        chapters_output = output_dir / "chapters" / manga_slug
        covers_output = output_dir / "covers" / manga_slug
        chapters_output.mkdir(parents=True, exist_ok=True)
        covers_output.mkdir(parents=True, exist_ok=True)

        # Download cover
        logger.info("Downloading cover...")
        cover_filename = await get_manga_cover(session, manga_id)
        if cover_filename:
            cover_path = covers_output / "cover.jpg"
            await download_cover(session, manga_id, cover_filename, cover_path)

        # Download chapters
        downloaded_count = 0
        for ch_num in sorted(bilingual.keys(), key=lambda x: float(x) if x.replace('.', '').isdigit() else 0):
            langs = bilingual[ch_num]
            logger.info(f"\n=== Chapter {ch_num} ===")

            for lang in ["en", "es"]:
                chapter = langs[lang]

                # Check if already downloaded in database
                if db_manga and is_chapter_downloaded(db_manga.id, ch_num, lang):
                    logger.info(f"Skipping {lang.upper()} (already in database)")
                    continue

                logger.info(f"Processing {lang.upper()}...")

                zip_path = await download_chapter_to_zip(
                    session,
                    chapter,
                    chapters_output,
                    temp_dir / manga_slug,
                    data_saver=data_saver
                )

                # Record download in database
                if zip_path and db_manga:
                    add_downloaded_chapter(
                        manga_id=db_manga.id,
                        chapter_number=ch_num,
                        language=lang,
                        zip_path=str(zip_path),
                        page_count=chapter.page_count
                    )
                    downloaded_count += 1

                # Random delay between chapters (stealth)
                await chapter_delay()

        # Generate manifest
        logger.info("\nGenerating manifest...")
        manifest = generate_manifest(
            manga_slug,
            title,
            chapters_output,
            f"covers/{manga_slug}/cover.jpg"
        )

        manifest_path = output_dir / manga_slug / "manifest.json"
        save_manifest(manifest, manifest_path)
        logger.info(f"Manifest saved: {manifest_path}")

        # Update manga status in database
        if db_manga:
            # Check if all bilingual chapters downloaded
            from database import get_downloaded_chapters
            dl_chapters = get_downloaded_chapters(db_manga.id)
            unique_bilingual = set()
            for dc in dl_chapters:
                unique_bilingual.add(dc["chapter_number"])

            if len(unique_bilingual) >= len(bilingual):
                update_manga_status(db_manga.id, "completed")
                logger.info("Manga marked as completed in database")

        logger.info(f"\nDone! Downloaded {downloaded_count} new chapters")
        logger.info(f"Total bilingual chapters available: {len(manifest.chapters)}")


def main():
    parser = argparse.ArgumentParser(description="Download manga from MangaDex")
    parser.add_argument("title", help="Manga title to search for")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output directory")
    parser.add_argument("-t", "--temp", type=Path, default=DEFAULT_TEMP,
                        help="Temp directory for downloads")
    parser.add_argument("--start", type=int, default=1,
                        help="Start chapter number")
    parser.add_argument("--end", type=int, default=None,
                        help="End chapter number")
    parser.add_argument("--data-saver", action="store_true",
                        help="Use data saver (lower quality) images")

    args = parser.parse_args()

    chapter_range = None
    if args.end:
        chapter_range = (args.start, args.end)

    asyncio.run(download_manga(
        args.title,
        args.output,
        args.temp,
        chapter_range=chapter_range,
        data_saver=args.data_saver
    ))


if __name__ == "__main__":
    main()
