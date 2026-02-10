"""MangaDex API client with rate limiting and stealth."""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

import aiohttp

from stealth import STEALTH_LIMITER, get_api_headers, human_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://api.mangadex.org"

# Legacy alias for compatibility
RATE_LIMITER = STEALTH_LIMITER

# Language normalization (treat regional variants as main language)
LANGUAGE_ALIASES = {
    "es-la": "es",  # Latin America Spanish -> Spanish
    "pt-br": "pt",  # Brazilian Portuguese -> Portuguese
}


def normalize_language(lang: str) -> str:
    """Normalize language code (e.g., es-la -> es)."""
    return LANGUAGE_ALIASES.get(lang, lang)


@dataclass
class Chapter:
    """Chapter metadata."""
    id: str
    chapter_number: str
    title: str
    language: str
    page_count: int
    volume: Optional[str] = None


@dataclass
class ChapterPages:
    """Chapter pages data from at-home endpoint."""
    base_url: str
    hash: str
    data: list[str]  # High quality filenames
    data_saver: list[str]  # Low quality filenames


async def get_manga_by_title(session: aiohttp.ClientSession, title: str) -> Optional[dict]:
    """Search manga by title."""
    async with STEALTH_LIMITER:
        params = {"title": title, "limit": 10}
        headers = get_api_headers()
        async with session.get(f"{BASE_URL}/manga", params=params, headers=headers) as resp:
            if resp.status != 200:
                logger.error(f"Failed to search manga: {resp.status}")
                return None
            data = await resp.json()
            if data["data"]:
                return data["data"][0]
            return None


async def get_manga_chapters(
    session: aiohttp.ClientSession,
    manga_id: str,
    languages: list[str] = None,
    limit: int = 100,
    offset: int = 0
) -> list[Chapter]:
    """Get chapters for a manga with pagination."""
    if languages is None:
        # Include regional variants
        languages = ["en", "es", "es-la"]

    chapters = []
    async with STEALTH_LIMITER:
        params = {
            "manga": manga_id,
            "translatedLanguage[]": languages,
            "limit": limit,
            "offset": offset,
            "order[chapter]": "asc",
            "includes[]": ["scanlation_group"]
        }
        headers = get_api_headers()
        async with session.get(f"{BASE_URL}/chapter", params=params, headers=headers) as resp:
            if resp.status != 200:
                logger.error(f"Failed to get chapters: {resp.status}")
                return chapters

            data = await resp.json()
            for ch in data["data"]:
                attrs = ch["attributes"]
                raw_lang = attrs["translatedLanguage"]
                # Normalize language (es-la -> es)
                normalized_lang = normalize_language(raw_lang)
                chapters.append(Chapter(
                    id=ch["id"],
                    chapter_number=attrs.get("chapter") or "0",
                    title=attrs.get("title") or "",
                    language=normalized_lang,
                    page_count=attrs.get("pages", 0),
                    volume=attrs.get("volume")
                ))

    return chapters


async def get_all_manga_chapters(
    session: aiohttp.ClientSession,
    manga_id: str,
    languages: list[str] = None
) -> list[Chapter]:
    """Get all chapters for a manga with auto-pagination."""
    if languages is None:
        languages = ["en", "es", "es-la"]

    all_chapters = []
    offset = 0
    limit = 100

    while True:
        chapters = await get_manga_chapters(
            session, manga_id, languages, limit, offset
        )
        if not chapters:
            break
        all_chapters.extend(chapters)
        if len(chapters) < limit:
            break
        offset += limit
        await human_delay()  # Random delay between pagination

    return all_chapters


async def get_chapter_pages(
    session: aiohttp.ClientSession,
    chapter_id: str
) -> Optional[ChapterPages]:
    """Get chapter page URLs from at-home endpoint."""
    async with STEALTH_LIMITER:
        headers = get_api_headers()
        async with session.get(f"{BASE_URL}/at-home/server/{chapter_id}", headers=headers) as resp:
            if resp.status != 200:
                logger.error(f"Failed to get chapter pages: {resp.status}")
                return None

            data = await resp.json()
            ch = data["chapter"]
            return ChapterPages(
                base_url=data["baseUrl"],
                hash=ch["hash"],
                data=ch["data"],
                data_saver=ch.get("dataSaver", [])
            )


def build_page_url(pages: ChapterPages, filename: str, data_saver: bool = False) -> str:
    """Build full URL for a page image."""
    quality = "data-saver" if data_saver else "data"
    return f"{pages.base_url}/{quality}/{pages.hash}/{filename}"


async def get_manga_cover(
    session: aiohttp.ClientSession,
    manga_id: str
) -> Optional[str]:
    """Get manga cover filename."""
    async with STEALTH_LIMITER:
        params = {"manga[]": manga_id, "limit": 1}
        headers = get_api_headers()
        async with session.get(f"{BASE_URL}/cover", params=params, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if data["data"]:
                return data["data"][0]["attributes"]["fileName"]
            return None
