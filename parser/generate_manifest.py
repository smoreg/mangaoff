#!/usr/bin/env python3
"""
Generate manifest.json from uploaded chapter files.

Usage:
    python3 generate_manifest.py chainsaw-man "Chainsaw Man"
    python3 generate_manifest.py beelzebub "Beelzebub"
    python3 generate_manifest.py yofukashi-no-uta "Yofukashi no Uta"
"""

import argparse
import json
import zipfile
from pathlib import Path

# Local upload directory (after alignment)
UPLOAD_DIR = Path(__file__).parent / "tmp" / "upload"


def count_pages_in_zip(zip_path: Path) -> int:
    """Count image files in a ZIP."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            return sum(1 for name in zf.namelist()
                      if Path(name).suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'})
    except Exception:
        return 0


def generate_manifest(manga_slug: str, title: str, output_dir: Path = None) -> dict:
    """Generate manifest from uploaded chapter files."""

    chapters_dir = UPLOAD_DIR / manga_slug / "chapters"

    if not chapters_dir.exists():
        raise FileNotFoundError(f"Chapters directory not found: {chapters_dir}")

    # Find all chapter numbers
    chapter_nums = set()
    for f in chapters_dir.glob("*_en.zip"):
        ch_num = f.stem.rsplit('_', 1)[0]
        chapter_nums.add(ch_num)

    # Sort chapters
    def sort_key(ch):
        try:
            return float(ch)
        except (ValueError, TypeError):
            return float('inf')

    chapters = []
    for ch_num in sorted(chapter_nums, key=sort_key):
        en_zip = chapters_dir / f"{ch_num}_en.zip"
        es_zip = chapters_dir / f"{ch_num}_es.zip"

        languages = {}

        if en_zip.exists():
            languages["en"] = {
                "archive": f"chapters/{manga_slug}/{ch_num}_en.zip",
                "page_count": count_pages_in_zip(en_zip)
            }

        if es_zip.exists():
            languages["es"] = {
                "archive": f"chapters/{manga_slug}/{ch_num}_es.zip",
                "page_count": count_pages_in_zip(es_zip)
            }

        if languages:
            chapters.append({
                "number": ch_num.lstrip('0') or "0",
                "title": "",
                "languages": languages
            })

    manifest = {
        "version": 1,
        "manga": {
            "id": manga_slug,
            "title": title,
            "cover": f"covers/{manga_slug}/cover.jpg"
        },
        "chapters": chapters
    }

    # Save manifest
    if output_dir is None:
        output_dir = UPLOAD_DIR / manga_slug

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Generated manifest: {manifest_path}")
    print(f"  Manga: {title}")
    print(f"  Chapters: {len(chapters)}")

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate manifest.json from uploaded chapters")
    parser.add_argument("manga_slug", help="Manga identifier (e.g., chainsaw-man)")
    parser.add_argument("title", help="Manga title (e.g., 'Chainsaw Man')")
    parser.add_argument("-o", "--output", type=Path, help="Output directory")

    args = parser.parse_args()

    try:
        manifest = generate_manifest(args.manga_slug, args.title, args.output)
        print(f"\nManifest generated successfully!")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
