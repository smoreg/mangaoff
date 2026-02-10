#!/usr/bin/env python3
"""Initialize manga wishlist database with all titles."""

import asyncio
import logging
import ssl
from pathlib import Path
from typing import Optional

import aiohttp
import certifi

from database import (
    init_database, add_manga, add_downloaded_chapter,
    get_manga_by_mangadex_id, extract_mangadex_id, get_all_manga, get_download_stats
)
from mangadex_client import RATE_LIMITER, BASE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Wishlist manga URLs
WISHLIST = [
    "https://mangadex.org/title/d90ea6cb-7bc3-4d80-8af0-28557e6c4e17/delicious-in-dungeon",
    "https://mangadex.org/title/a1c7c817-4e59-43b7-9365-09675a149a6f/one-piece",
    "https://mangadex.org/title/dd8a907a-3850-4f95-ba03-ba201a8399e3/fullmetal-alchemist",
    "https://mangadex.org/title/d773c8be-8e82-4ff1-a4e9-46171395319b/youjo-senki",
    "https://mangadex.org/title/a77742b1-befd-49a4-bff5-1ad4e6b0ef7b/chainsaw-man",
    "https://mangadex.org/title/6b958848-c885-4735-9201-12ee77abcb3c/spy-family",
    "https://mangadex.org/title/aa6c76f7-5f5f-46b6-a800-911145f81b9b/sono-bisque-doll-wa-koi-o-suru",
    "https://mangadex.org/title/259dfd8a-f06a-4825-8fa6-a2dcd7274230/yofukashi-no-uta",
    "https://mangadex.org/title/6da0b34b-db19-491a-b85c-6e31e0986f15/black-lagoon",
    "https://mangadex.org/title/7aee516e-4633-47e9-bf15-49196ce2d195/ore-monogatari",
    "https://mangadex.org/title/53ef1720-7a5d-40ad-90b0-2f9ca0a1ab01/soul-eater",
    "https://mangadex.org/title/fa442671-f5ef-4397-93c4-0560b9a3a278/make-heroine-o-katasetai",
    "https://mangadex.org/title/8e44a10a-8116-430a-9e17-ba4dd58b4137/akagi-yami-ni-oritatta-tensai",
    "https://mangadex.org/title/304ceac3-8cdb-4fe7-acf7-2b6ff7a60613/attack-on-titan",
    "https://mangadex.org/title/bcfa196d-d162-45f5-a224-61d26b04a077/kono-subarashii-sekai-ni-shukufuku-wo",
    "https://mangadex.org/title/6fcfaa0e-6023-403e-97f9-5301dd3c258c/hellsing",
    "https://mangadex.org/title/c52b2ce3-7f95-469c-96b0-479524fb7a1a/jujutsu-kaisen",
    "https://mangadex.org/title/e8799d88-d2ac-4b7d-93cd-48afb025d147/desire-for-a-reply",
    "https://mangadex.org/title/30193c1f-1569-4c2d-8c29-8a365fec322b/akuyuu-no-ore-ga-ponkotsu-kishi-o-miterarenain-da-ga-dou-sewa-o-yakya-ii-madome-gaiden",
    "https://mangadex.org/title/b9ad64a8-bf30-445b-b97d-fe3fa39c2f22/keyman-the-hand-of-judgement",
    "https://mangadex.org/title/cfc3d743-bd89-48e2-991f-63e680cc4edf/dr-stone",
    "https://mangadex.org/title/d86cf65b-5f6c-437d-a0af-19a31f94ec55/ijiranaide-nagatoro-san",
    "https://mangadex.org/title/237d527f-adb5-420e-8e6e-b7dd006fbe47/kaiju-no-8",
    "https://mangadex.org/title/cb4b4030-dc06-42a0-9830-1b7ddaff88c1/love-after-world-domination",
    "https://mangadex.org/title/ef63deb7-88bc-4942-85bb-2f32cfc72ea5/debby-the-corsifa-wa-makezugirai",
    "https://mangadex.org/title/ef25dabb-969e-4a87-b854-b15a53b9209f/sayonara-zetsubou-sensei",
    "https://mangadex.org/title/9056cf07-8190-432d-89d7-a2eeb9161155/saotome-senshu-hitakakusu",
    "https://mangadex.org/title/fa3e0b2f-4e1f-48ee-9af0-1de9dc28ca51/bakuman",
    "https://mangadex.org/title/8af3ad21-3e7e-4fb5-b344-d0044ec154fc/beelzebub",
]


async def fetch_manga_info(session: aiohttp.ClientSession, manga_id: str) -> Optional[dict]:
    """Fetch manga info from MangaDex API."""
    async with RATE_LIMITER:
        async with session.get(f"{BASE_URL}/manga/{manga_id}") as resp:
            if resp.status != 200:
                logger.error(f"Failed to fetch manga {manga_id}: {resp.status}")
                return None
            data = await resp.json()
            return data["data"]


async def count_chapters(session: aiohttp.ClientSession, manga_id: str, language: str) -> int:
    """Count available chapters for a language."""
    async with RATE_LIMITER:
        params = {
            "manga": manga_id,
            "translatedLanguage[]": [language],
            "limit": 1
        }
        async with session.get(f"{BASE_URL}/chapter", params=params) as resp:
            if resp.status != 200:
                return 0
            data = await resp.json()
            return data.get("total", 0)


async def init_wishlist():
    """Initialize database with wishlist manga."""
    init_database()

    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    async with aiohttp.ClientSession(connector=connector) as session:
        for url in WISHLIST:
            manga_id = extract_mangadex_id(url)
            logger.info(f"Processing: {url}")

            # Fetch manga info
            manga_data = await fetch_manga_info(session, manga_id)
            if not manga_data:
                logger.error(f"Skipping {url}")
                continue

            # Get title (prefer English)
            attrs = manga_data["attributes"]
            title = attrs["title"].get("en") or attrs["title"].get("ja-ro") or list(attrs["title"].values())[0]

            # Count chapters
            total_en = await count_chapters(session, manga_id, "en")
            total_es = await count_chapters(session, manga_id, "es")

            logger.info(f"  Title: {title}")
            logger.info(f"  Chapters: EN={total_en}, ES={total_es}")

            # Add to database
            add_manga(manga_id, title, url)

            # Update chapter counts
            from database import update_manga_chapter_counts, get_manga_by_mangadex_id
            manga_record = get_manga_by_mangadex_id(manga_id)
            if manga_record:
                update_manga_chapter_counts(manga_record.id, total_en, total_es)

            # Small delay
            await asyncio.sleep(0.5)

    logger.info("\n=== Wishlist initialized ===")
    print_stats()


def add_chainsaw_man_chapters():
    """Add already downloaded Chainsaw Man chapters to database."""
    from database import get_manga_by_mangadex_id, add_downloaded_chapter, update_manga_status

    chainsaw_id = "a77742b1-befd-49a4-bff5-1ad4e6b0ef7b"
    manga = get_manga_by_mangadex_id(chainsaw_id)

    if not manga:
        logger.error("Chainsaw Man not in database!")
        return

    chapters_dir = Path(__file__).parent.parent / "backup_downloads" / "chapters" / "chainsaw-man"

    if not chapters_dir.exists():
        logger.error(f"Chapters directory not found: {chapters_dir}")
        return

    # Scan existing zip files
    for zip_file in sorted(chapters_dir.glob("*.zip")):
        # Parse filename: 001_en.zip
        parts = zip_file.stem.split("_")
        if len(parts) != 2:
            continue

        chapter_num = parts[0].lstrip("0") or "0"
        language = parts[1]

        add_downloaded_chapter(
            manga_id=manga.id,
            chapter_number=chapter_num,
            language=language,
            zip_path=str(zip_file),
            page_count=0  # Could extract from zip if needed
        )
        logger.info(f"Added: Chapter {chapter_num} ({language})")

    update_manga_status(manga.id, "downloading")
    logger.info("Chainsaw Man chapters recorded!")


def print_stats():
    """Print current database stats."""
    stats = get_download_stats()
    manga_list = get_all_manga()

    print("\n" + "=" * 60)
    print("MANGA TRACKER DATABASE")
    print("=" * 60)
    print(f"Total manga:     {stats['total_manga']}")
    print(f"Completed:       {stats['completed']}")
    print(f"In progress:     {stats['in_progress']}")
    print(f"Wishlist:        {stats['wishlist']}")
    print(f"Downloaded ch:   {stats['total_downloaded_chapters']}")
    print("=" * 60)
    print()

    print(f"{'Title':<40} {'Status':<12} {'EN':<8} {'ES':<8} {'DL':<6}")
    print("-" * 80)

    for m in manga_list:
        en = m.total_chapters_en or "?"
        es = m.total_chapters_es or "?"
        dl = m.downloaded_chapters
        title = m.title[:38] + ".." if len(m.title) > 40 else m.title
        print(f"{title:<40} {m.status:<12} {en:<8} {es:<8} {dl:<6}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--add-chainsaw":
        add_chainsaw_man_chapters()
        print_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--stats":
        print_stats()
    else:
        asyncio.run(init_wishlist())
        add_chainsaw_man_chapters()
