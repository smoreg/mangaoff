"""
Downloader for callofthenight.space chapters.
"""

import asyncio
import logging
import zipfile
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles

from callofthenight_client import COTNChapter, get_chapter_info, BASE_URL
from stealth import (
    STEALTH_LIMITER, get_image_headers,
    page_delay, rate_limit_backoff
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


async def download_image(
    session: aiohttp.ClientSession,
    url: str,
    dest: Path,
    referer: str,
    retries: int = MAX_RETRIES
) -> bool:
    """Download a single image with retries."""
    for attempt in range(retries):
        try:
            async with STEALTH_LIMITER:
                headers = get_image_headers(referer)
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 429:
                        await rate_limit_backoff(attempt)
                        continue

                    if resp.status == 503:
                        await rate_limit_backoff(attempt + 1)
                        continue

                    if resp.status != 200:
                        if attempt < retries - 1:
                            await rate_limit_backoff(attempt)
                            continue
                        logger.error(f"Failed: {url} -> {resp.status}")
                        return False

                    content = await resp.read()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    async with aiofiles.open(dest, "wb") as f:
                        await f.write(content)
                    return True

        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {url} (attempt {attempt + 1})")
            if attempt < retries - 1:
                await rate_limit_backoff(attempt)
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            if attempt < retries - 1:
                await rate_limit_backoff(attempt)

    return False


async def download_chapter(
    session: aiohttp.ClientSession,
    chapter: COTNChapter,
    output_dir: Path,
    temp_dir: Path
) -> Optional[Path]:
    """Download chapter and create ZIP archive.

    Returns path to ZIP file or None if failed.
    """
    # Format chapter number for filename (e.g., "1" -> "001", "200.8" -> "200.8")
    if '.' in chapter.number:
        ch_padded = chapter.number.zfill(5)  # "200.8" -> "200.8"
    else:
        ch_padded = chapter.number.zfill(3)  # "1" -> "001"

    zip_name = f"{ch_padded}_en.zip"
    zip_path = output_dir / zip_name

    # Skip if already exists
    if zip_path.exists():
        logger.info(f"Already exists: {zip_name}")
        return zip_path

    # Create temp directory
    chapter_temp = temp_dir / f"ch{chapter.number}_en"
    chapter_temp.mkdir(parents=True, exist_ok=True)

    # Download all pages
    downloaded_files = []
    referer = chapter.url

    for idx, url in enumerate(chapter.image_urls, 1):
        # Determine extension from URL
        ext = Path(url).suffix or ".png"
        page_file = chapter_temp / f"{idx:03d}{ext}"

        if page_file.exists():
            downloaded_files.append(page_file)
            continue

        logger.info(f"  Page {idx}/{len(chapter.image_urls)}")

        if await download_image(session, url, page_file, referer):
            downloaded_files.append(page_file)
        else:
            logger.error(f"  Failed page {idx}")

        await page_delay()

    if not downloaded_files:
        logger.error(f"No pages downloaded for chapter {chapter.number}")
        return None

    # Create ZIP
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for page_file in sorted(downloaded_files):
            zf.write(page_file, page_file.name)

    logger.info(f"Created {zip_name} ({len(downloaded_files)} pages)")
    return zip_path


async def download_chapter_by_number(
    session: aiohttp.ClientSession,
    chapter_num: str,
    output_dir: Path,
    temp_dir: Path
) -> Optional[Path]:
    """Download a chapter by its number."""
    logger.info(f"Fetching chapter {chapter_num} info...")

    chapter = await get_chapter_info(session, chapter_num)
    if not chapter:
        return None

    logger.info(f"Chapter {chapter_num}: {chapter.page_count} pages")
    return await download_chapter(session, chapter, output_dir, temp_dir)
