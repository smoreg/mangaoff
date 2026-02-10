#!/usr/bin/env python3
"""
Prepare aligned chapter for server upload.

Takes EN and ES chapter ZIPs, aligns pages, and creates new ZIPs
with synchronized page numbering (001_en.jpg matches 001_es.jpg).

Usage:
    python3 prepare_chapter.py manga-slug chapter_en.zip chapter_es.zip
    python3 prepare_chapter.py chainsaw-man 001_en.zip 001_es.zip --output ../upload/
    python3 prepare_chapter.py beelzebub 005_en.zip 005_es.zip -t 20

Output structure:
    output/
    └── manga-slug/
        └── chapters/
            ├── 001_en.zip   (aligned pages: 001.jpg, 002.jpg, ...)
            └── 001_es.zip   (aligned pages: 001.jpg, 002.jpg, ...)
"""

import argparse
import logging
import zipfile
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import io

from PIL import Image

from page_aligner import align_chapters, AlignmentResult, PageMatch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path(__file__).parent.parent / "upload"
DEFAULT_THRESHOLD = 25


@dataclass
class AlignedPage:
    """A page in the aligned output."""
    index: int  # 1-based index in output
    en_source: Optional[str]  # Original filename in EN zip, or None
    es_source: Optional[str]  # Original filename in ES zip, or None
    match_type: str  # "matched", "en_only", "es_only"
    distance: Optional[int]


def extract_chapter_number(zip_path: Path) -> str:
    """Extract chapter number from filename like '001_en.zip' -> '001'."""
    stem = zip_path.stem  # "001_en"
    match = re.match(r'^([\d.]+)', stem)
    if match:
        return match.group(1)
    # Fallback: remove language suffix
    parts = stem.rsplit('_', 1)
    return parts[0] if len(parts) == 2 else stem


def get_image_extension(filename: str) -> str:
    """Get lowercase extension."""
    return Path(filename).suffix.lower()


def align_and_prepare(
    en_zip: Path,
    es_zip: Path,
    threshold: int = DEFAULT_THRESHOLD
) -> tuple[AlignmentResult, list[AlignedPage]]:
    """Align chapters and prepare page mapping."""

    result = align_chapters(en_zip, es_zip, threshold)

    aligned_pages = []
    page_idx = 1

    for match in result.matches:
        if match.match_type in ("match", "weak_match"):
            # Both languages have this page
            aligned_pages.append(AlignedPage(
                index=page_idx,
                en_source=match.page_a.filename if match.page_a else None,
                es_source=match.page_b.filename if match.page_b else None,
                match_type="matched",
                distance=match.distance
            ))
            page_idx += 1
        elif match.match_type == "insert_a":
            # EN only - include with placeholder for ES
            aligned_pages.append(AlignedPage(
                index=page_idx,
                en_source=match.page_a.filename,
                es_source=None,
                match_type="en_only",
                distance=None
            ))
            page_idx += 1
        elif match.match_type == "insert_b":
            # ES only - include with placeholder for EN
            aligned_pages.append(AlignedPage(
                index=page_idx,
                en_source=None,
                es_source=match.page_b.filename,
                match_type="es_only",
                distance=None
            ))
            page_idx += 1

    return result, aligned_pages


def create_aligned_zip(
    source_zip: Path,
    aligned_pages: list[AlignedPage],
    output_path: Path,
    lang: str  # "en" or "es"
):
    """Create a new ZIP with aligned page numbering."""

    source_field = "en_source" if lang == "en" else "es_source"

    # Read source images
    source_images = {}
    with zipfile.ZipFile(source_zip, 'r') as zf:
        for name in zf.namelist():
            if Path(name).suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}:
                source_images[name] = zf.read(name)

    # Create output ZIP
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for page in aligned_pages:
            source_name = getattr(page, source_field)

            if source_name and source_name in source_images:
                # Get extension from source
                ext = get_image_extension(source_name)
                # New name with aligned index
                new_name = f"{page.index:03d}{ext}"
                zf.writestr(new_name, source_images[source_name])

    return output_path


def create_alignment_manifest(
    aligned_pages: list[AlignedPage],
    result: AlignmentResult,
    chapter_num: str
) -> dict:
    """Create a manifest describing the alignment."""
    return {
        "chapter": chapter_num,
        "total_pages": len(aligned_pages),
        "matched": sum(1 for p in aligned_pages if p.match_type == "matched"),
        "en_only": sum(1 for p in aligned_pages if p.match_type == "en_only"),
        "es_only": sum(1 for p in aligned_pages if p.match_type == "es_only"),
        "avg_distance": result.avg_distance,
        "pages": [
            {
                "index": p.index,
                "en": p.en_source,
                "es": p.es_source,
                "type": p.match_type,
                "distance": p.distance
            }
            for p in aligned_pages
        ]
    }


def prepare_chapter(
    manga_slug: str,
    en_zip: Path,
    es_zip: Path,
    output_dir: Path,
    threshold: int = DEFAULT_THRESHOLD
) -> dict:
    """Prepare aligned chapter for upload."""

    chapter_num = extract_chapter_number(en_zip)
    logger.info(f"Preparing chapter {chapter_num} for {manga_slug}")

    # Align pages
    logger.info("Aligning pages...")
    result, aligned_pages = align_and_prepare(en_zip, es_zip, threshold)

    logger.info(f"  Total aligned pages: {len(aligned_pages)}")
    logger.info(f"  Matched: {sum(1 for p in aligned_pages if p.match_type == 'matched')}")
    logger.info(f"  EN only: {sum(1 for p in aligned_pages if p.match_type == 'en_only')}")
    logger.info(f"  ES only: {sum(1 for p in aligned_pages if p.match_type == 'es_only')}")

    # Output paths
    chapters_dir = output_dir / manga_slug / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    en_output = chapters_dir / f"{chapter_num}_en.zip"
    es_output = chapters_dir / f"{chapter_num}_es.zip"

    # Create aligned ZIPs
    logger.info(f"Creating {en_output.name}...")
    create_aligned_zip(en_zip, aligned_pages, en_output, "en")

    logger.info(f"Creating {es_output.name}...")
    create_aligned_zip(es_zip, aligned_pages, es_output, "es")

    # Save alignment manifest
    manifest = create_alignment_manifest(aligned_pages, result, chapter_num)
    manifest_path = chapters_dir / f"{chapter_num}_alignment.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved alignment manifest to {manifest_path.name}")

    return {
        "chapter": chapter_num,
        "manga": manga_slug,
        "en_zip": str(en_output),
        "es_zip": str(es_output),
        "manifest": str(manifest_path),
        "pages": len(aligned_pages),
        "matched": manifest["matched"],
        "en_only": manifest["en_only"],
        "es_only": manifest["es_only"]
    }


def main():
    parser = argparse.ArgumentParser(
        description="Prepare aligned chapter for server upload"
    )
    parser.add_argument("manga_slug", help="Manga identifier (e.g., chainsaw-man)")
    parser.add_argument("en_zip", type=Path, help="English chapter ZIP")
    parser.add_argument("es_zip", type=Path, help="Spanish chapter ZIP")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output directory (default: {DEFAULT_OUTPUT})")
    parser.add_argument("-t", "--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Similarity threshold (default: {DEFAULT_THRESHOLD})")

    args = parser.parse_args()

    if not args.en_zip.exists():
        logger.error(f"File not found: {args.en_zip}")
        return 1

    if not args.es_zip.exists():
        logger.error(f"File not found: {args.es_zip}")
        return 1

    result = prepare_chapter(
        args.manga_slug,
        args.en_zip,
        args.es_zip,
        args.output,
        args.threshold
    )

    print(f"\n{'='*50}")
    print("CHAPTER PREPARED FOR UPLOAD")
    print(f"{'='*50}")
    print(f"Manga:    {result['manga']}")
    print(f"Chapter:  {result['chapter']}")
    print(f"Pages:    {result['pages']} ({result['matched']} matched, "
          f"{result['en_only']} EN-only, {result['es_only']} ES-only)")
    print(f"{'='*50}")
    print(f"EN ZIP:   {result['en_zip']}")
    print(f"ES ZIP:   {result['es_zip']}")
    print(f"Manifest: {result['manifest']}")
    print(f"{'='*50}")
    print(f"\nTo upload: rsync -avz {args.output}/{args.manga_slug}/ user@server:/opt/mangaoff/data/{args.manga_slug}/")

    return 0


if __name__ == "__main__":
    exit(main())
