"""Manifest generation for manga data."""

import json
import zipfile
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class LanguageInfo:
    """Info about chapter in specific language."""
    archive: str
    page_count: int


@dataclass
class ChapterManifest:
    """Chapter entry in manifest."""
    number: str
    title: str
    languages: dict[str, LanguageInfo] = field(default_factory=dict)


@dataclass
class MangaInfo:
    """Manga metadata."""
    id: str
    title: str
    cover: str


@dataclass
class Manifest:
    """Full manifest structure."""
    version: int
    manga: MangaInfo
    chapters: list[ChapterManifest] = field(default_factory=list)


def count_pages_in_zip(zip_path: Path) -> int:
    """Count image files in a ZIP archive."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
            return sum(
                1 for name in zf.namelist()
                if Path(name).suffix.lower() in image_exts
            )
    except Exception:
        return 0


def generate_manifest(
    manga_id: str,
    manga_title: str,
    chapters_dir: Path,
    cover_path: Optional[str] = None
) -> Manifest:
    """Generate manifest from downloaded chapter ZIPs.

    Expects ZIP files named like: 001_en.zip, 001_es.zip
    Only includes chapters that have BOTH en and es versions.
    """
    manifest = Manifest(
        version=1,
        manga=MangaInfo(
            id=manga_id,
            title=manga_title,
            cover=cover_path or f"covers/{manga_id}/cover.jpg"
        ),
        chapters=[]
    )

    # Group ZIP files by chapter number
    chapter_files: dict[str, dict[str, Path]] = {}

    for zip_file in chapters_dir.glob("*.zip"):
        # Parse filename: 001_en.zip -> number=001, lang=en
        stem = zip_file.stem
        if "_" not in stem:
            continue

        parts = stem.rsplit("_", 1)
        if len(parts) != 2:
            continue

        ch_num, lang = parts
        if ch_num not in chapter_files:
            chapter_files[ch_num] = {}
        chapter_files[ch_num][lang] = zip_file

    # Build chapters list - only include if both EN and ES exist
    for ch_num in sorted(chapter_files.keys()):
        langs = chapter_files[ch_num]

        # Skip if missing either language
        if "en" not in langs or "es" not in langs:
            continue

        chapter = ChapterManifest(
            number=ch_num.lstrip("0") or "0",
            title="",  # Could be fetched from API if needed
            languages={}
        )

        for lang, zip_path in langs.items():
            page_count = count_pages_in_zip(zip_path)
            chapter.languages[lang] = LanguageInfo(
                archive=f"chapters/{manga_id}/{zip_path.name}",
                page_count=page_count
            )

        manifest.chapters.append(chapter)

    return manifest


def save_manifest(manifest: Manifest, output_path: Path) -> None:
    """Save manifest to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict with proper structure
    data = {
        "version": manifest.version,
        "manga": asdict(manifest.manga),
        "chapters": []
    }

    for ch in manifest.chapters:
        ch_dict = {
            "number": ch.number,
            "title": ch.title,
            "languages": {}
        }
        for lang, info in ch.languages.items():
            ch_dict["languages"][lang] = asdict(info)
        data["chapters"].append(ch_dict)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
