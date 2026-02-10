"""Chapter downloader with retry, caching, and stealth."""

import asyncio
import logging
import zipfile
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles

from mangadex_client import Chapter, ChapterPages, get_chapter_pages, build_page_url
from stealth import (
    STEALTH_LIMITER, get_image_headers, get_browser_headers,
    page_delay, chapter_delay, rate_limit_backoff
)

logger = logging.getLogger(__name__)

# Retry settings
MAX_RETRIES = 5
RETRY_DELAY = 3.0


async def download_file(
    session: aiohttp.ClientSession,
    url: str,
    dest: Path,
    referer: str = "https://mangadex.org/",
    retries: int = MAX_RETRIES
) -> bool:
    """Download a file with retries and stealth headers."""
    for attempt in range(retries):
        try:
            async with STEALTH_LIMITER:
                # Use image headers for image downloads
                headers = get_image_headers(referer)
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 429:
                        # Rate limited - exponential backoff with jitter
                        await rate_limit_backoff(attempt)
                        continue

                    if resp.status == 503:
                        # Server overloaded - wait longer
                        logger.warning(f"Server 503, waiting...")
                        await rate_limit_backoff(attempt + 1)
                        continue

                    if resp.status != 200:
                        logger.error(f"Failed to download {url}: {resp.status}")
                        if attempt < retries - 1:
                            await rate_limit_backoff(attempt)
                            continue
                        return False

                    content = await resp.read()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    async with aiofiles.open(dest, "wb") as f:
                        await f.write(content)
                    return True

        except asyncio.TimeoutError:
            logger.warning(f"Timeout downloading {url} (attempt {attempt + 1})")
            if attempt < retries - 1:
                await rate_limit_backoff(attempt)
        except Exception as e:
            logger.error(f"Download error (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                await rate_limit_backoff(attempt)

    return False


async def download_chapter_to_zip(
    session: aiohttp.ClientSession,
    chapter: Chapter,
    output_dir: Path,
    temp_dir: Path,
    data_saver: bool = False
) -> Optional[Path]:
    """Download chapter pages and create a ZIP archive.

    Returns path to created ZIP file, or None if failed.
    """
    # Create ZIP filename: 001_en.zip
    ch_num = chapter.chapter_number.zfill(3)
    zip_name = f"{ch_num}_{chapter.language}.zip"
    zip_path = output_dir / zip_name

    # Skip if already exists
    if zip_path.exists():
        logger.info(f"Chapter already exists: {zip_name}")
        return zip_path

    # Get page URLs
    pages = await get_chapter_pages(session, chapter.id)
    if not pages:
        logger.error(f"Failed to get pages for chapter {chapter.chapter_number}")
        return None

    # Create temp directory for this chapter
    chapter_temp = temp_dir / f"{ch_num}_{chapter.language}"
    chapter_temp.mkdir(parents=True, exist_ok=True)

    # Download all pages
    filenames = pages.data_saver if data_saver else pages.data
    downloaded_files = []

    for idx, filename in enumerate(filenames, 1):
        url = build_page_url(pages, filename, data_saver)
        # Normalize page filename: 001.jpg, 002.jpg, etc.
        ext = Path(filename).suffix or ".jpg"
        page_file = chapter_temp / f"{idx:03d}{ext}"

        if page_file.exists():
            downloaded_files.append(page_file)
            continue

        logger.info(f"Downloading page {idx}/{len(filenames)} for ch.{chapter.chapter_number} ({chapter.language})")

        # Use chapter page as referer for authenticity
        referer = f"https://mangadex.org/chapter/{chapter.id}"
        if await download_file(session, url, page_file, referer=referer):
            downloaded_files.append(page_file)
        else:
            logger.error(f"Failed to download page {idx}")
            # Continue anyway, might get partial chapter

        # Random delay between pages (simulates reading)
        await page_delay()

    if not downloaded_files:
        logger.error(f"No pages downloaded for chapter {chapter.chapter_number}")
        return None

    # Create ZIP archive
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for page_file in sorted(downloaded_files):
            zf.write(page_file, page_file.name)

    logger.info(f"Created {zip_name} with {len(downloaded_files)} pages")
    return zip_path


async def download_cover(
    session: aiohttp.ClientSession,
    manga_id: str,
    cover_filename: str,
    output_path: Path
) -> bool:
    """Download manga cover image."""
    if output_path.exists():
        logger.info(f"Cover already exists: {output_path}")
        return True

    url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}"
    referer = f"https://mangadex.org/title/{manga_id}"
    return await download_file(session, url, output_path, referer=referer)
