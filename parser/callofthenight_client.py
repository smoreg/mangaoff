"""
Call of the Night (callofthenight.space) parser.
English source for Yofukashi no Uta manga.

Image URL pattern: https://official.lowee.us/manga/Yofukashi-no-Uta/XXXX-YYY.png
Where XXXX = chapter number (zero-padded), YYY = page number (zero-padded)
"""

import asyncio
import re
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from stealth import STEALTH_LIMITER, get_browser_headers, human_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://callofthenight.space"
IMAGE_BASE = "https://official.lowee.us/manga/Yofukashi-no-Uta"


@dataclass
class COTNChapter:
    """Chapter from callofthenight.space."""
    number: str  # "1", "2", "200.8", etc.
    url: str
    page_count: int
    image_urls: list[str]


def format_chapter_number(chapter: str) -> str:
    """Format chapter number for image URL (e.g., '1' -> '0001', '200.8' -> '0200-8')."""
    if '.' in chapter:
        main, sub = chapter.split('.', 1)
        return f"{int(main):04d}-{sub}"
    else:
        return f"{int(float(chapter)):04d}"


def build_image_url(chapter: str, page: int) -> str:
    """Build image URL for a specific page."""
    ch_formatted = format_chapter_number(chapter)
    return f"{IMAGE_BASE}/{ch_formatted}-{page:03d}.png"


async def get_chapter_page_count(
    session: aiohttp.ClientSession,
    chapter: str
) -> int:
    """Determine page count by checking which pages exist."""
    # Start checking from page 1, increment until 404
    page = 1
    max_pages = 100  # Safety limit

    while page <= max_pages:
        url = build_image_url(chapter, page)
        async with STEALTH_LIMITER:
            headers = get_browser_headers(f"{BASE_URL}/chapters/{chapter}/")
            try:
                async with session.head(url, headers=headers, allow_redirects=True) as resp:
                    if resp.status == 200:
                        page += 1
                    else:
                        break
            except Exception:
                break

        # Check in batches to be faster
        if page % 10 == 0:
            await asyncio.sleep(0.5)

    return page - 1


async def get_chapter_info(
    session: aiohttp.ClientSession,
    chapter: str
) -> Optional[COTNChapter]:
    """Get chapter info including all image URLs."""
    # First, verify the chapter page exists
    chapter_url = f"{BASE_URL}/chapters/{chapter}/"

    async with STEALTH_LIMITER:
        headers = get_browser_headers()
        try:
            async with session.get(chapter_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Chapter {chapter} not found: {resp.status}")
                    return None
                html = await resp.text()
        except Exception as e:
            logger.error(f"Error fetching chapter {chapter}: {e}")
            return None

    # Extract page count from HTML (look for image URLs)
    # Pattern: official.lowee.us/manga/Yofukashi-no-Uta/XXXX-YYY.png
    pattern = rf'{IMAGE_BASE.replace(".", r"\.")}/[^"]+\.png'
    matches = re.findall(pattern, html)

    if matches:
        # Deduplicate and sort
        unique_urls = sorted(set(matches))
        page_count = len(unique_urls)
        logger.info(f"Chapter {chapter}: found {page_count} pages in HTML")
        return COTNChapter(
            number=chapter,
            url=chapter_url,
            page_count=page_count,
            image_urls=unique_urls
        )

    # Fallback: probe for pages
    logger.info(f"Chapter {chapter}: probing for pages...")
    page_count = await get_chapter_page_count(session, chapter)

    if page_count == 0:
        logger.error(f"Chapter {chapter}: no pages found")
        return None

    image_urls = [build_image_url(chapter, p) for p in range(1, page_count + 1)]

    return COTNChapter(
        number=chapter,
        url=chapter_url,
        page_count=page_count,
        image_urls=image_urls
    )


async def get_all_chapters(session: aiohttp.ClientSession) -> list[str]:
    """Get list of all available chapter numbers."""
    # Fetch the main page or chapter list
    async with STEALTH_LIMITER:
        headers = get_browser_headers()
        try:
            async with session.get(BASE_URL, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch main page: {resp.status}")
                    return []
                html = await resp.text()
        except Exception as e:
            logger.error(f"Error fetching main page: {e}")
            return []

    # Extract chapter links: /chapters/XXX/
    pattern = r'/chapters/([0-9]+(?:-[0-9]+)?(?:\.[0-9]+)?)'
    matches = re.findall(pattern, html)

    # Normalize: "200-8" -> "200.8" for consistency
    chapters = []
    for ch in set(matches):
        # Convert URL format to number format
        if '-' in ch and not ch.startswith('-'):
            # Check if it's like "200-8" (subchapter) vs just a number
            parts = ch.split('-')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ch = f"{parts[0]}.{parts[1]}"
        chapters.append(ch)

    # Sort numerically
    def sort_key(x):
        try:
            return float(x.replace('-', '.'))
        except ValueError:
            return 0

    chapters = sorted(set(chapters), key=sort_key)
    logger.info(f"Found {len(chapters)} chapters")

    return chapters


async def get_latest_chapter(session: aiohttp.ClientSession) -> Optional[str]:
    """Get the latest chapter number."""
    chapters = await get_all_chapters(session)
    return chapters[-1] if chapters else None
