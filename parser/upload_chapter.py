#!/usr/bin/env python3
"""
Upload aligned chapters to server.

Combines prepare_chapter.py alignment with rsync upload.

Usage:
    # Single chapter
    python3 upload_chapter.py chainsaw-man 001

    # Multiple chapters
    python3 upload_chapter.py chainsaw-man 001 002 003 004 005

    # Chapter range
    python3 upload_chapter.py beelzebub --range 1-50

    # All available chapters
    python3 upload_chapter.py chainsaw-man --all

    # Dry run (prepare only, don't upload)
    python3 upload_chapter.py chainsaw-man 001 --dry-run
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from prepare_chapter import prepare_chapter, DEFAULT_THRESHOLD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Server config
SERVER_HOST = "smoreg.dev"
SERVER_USER = "root"
SERVER_DATA_PATH = "/opt/mangaoff/data"

# Local paths
BACKUP_DIR = Path(__file__).parent.parent / "backup_downloads" / "chapters"
UPLOAD_DIR = Path(__file__).parent / "tmp" / "upload"


def find_chapter_files(manga_slug: str, chapter_num: str) -> tuple[Path, Path]:
    """Find EN and ES ZIP files for a chapter."""
    manga_dir = BACKUP_DIR / manga_slug

    # Normalize chapter number (001, 002, etc.)
    if '.' in chapter_num:
        ch_normalized = chapter_num
    else:
        ch_normalized = f"{int(chapter_num):03d}"

    en_zip = manga_dir / f"{ch_normalized}_en.zip"
    es_zip = manga_dir / f"{ch_normalized}_es.zip"

    return en_zip, es_zip


def find_all_chapters(manga_slug: str) -> list[str]:
    """Find all available chapter numbers for a manga."""
    manga_dir = BACKUP_DIR / manga_slug
    if not manga_dir.exists():
        return []

    chapters = set()
    for f in manga_dir.glob("*_en.zip"):
        ch_num = f.stem.rsplit('_', 1)[0]
        # Check if ES also exists
        es_file = manga_dir / f"{ch_num}_es.zip"
        if es_file.exists():
            chapters.add(ch_num)

    return sorted(chapters, key=lambda x: float(x) if x.replace('.', '').isdigit() else 0)


def parse_range(range_str: str) -> list[str]:
    """Parse chapter range like '1-50' or '1-10,15-20'."""
    chapters = []
    for part in range_str.split(','):
        if '-' in part:
            start, end = part.split('-', 1)
            for i in range(int(start), int(end) + 1):
                chapters.append(f"{i:03d}")
        else:
            chapters.append(f"{int(part):03d}")
    return chapters


def rsync_upload(manga_slug: str, dry_run: bool = False) -> bool:
    """Upload prepared files to server via rsync."""
    local_path = UPLOAD_DIR / manga_slug
    remote_path = f"{SERVER_USER}@{SERVER_HOST}:{SERVER_DATA_PATH}/{manga_slug}/"

    if not local_path.exists():
        logger.error(f"Upload directory not found: {local_path}")
        return False

    cmd = ["rsync", "-avz"]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend([f"{local_path}/", remote_path])

    logger.info(f"Uploading to {remote_path}...")
    logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Upload aligned chapters to server"
    )
    parser.add_argument("manga_slug", help="Manga identifier (e.g., chainsaw-man)")
    parser.add_argument("chapters", nargs="*", help="Chapter numbers (e.g., 001 002 003)")
    parser.add_argument("--range", "-r", dest="chapter_range",
                        help="Chapter range (e.g., 1-50 or 1-10,15-20)")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Process all available chapters")
    parser.add_argument("--threshold", "-t", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Similarity threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Prepare files but don't upload")
    parser.add_argument("--skip-prepare", action="store_true",
                        help="Skip alignment, just upload existing files")

    args = parser.parse_args()

    # Determine chapters to process
    if args.all:
        chapters = find_all_chapters(args.manga_slug)
        if not chapters:
            logger.error(f"No chapters found for {args.manga_slug}")
            return 1
        logger.info(f"Found {len(chapters)} chapters: {chapters[0]} - {chapters[-1]}")
    elif args.chapter_range:
        chapters = parse_range(args.chapter_range)
    elif args.chapters:
        chapters = [f"{int(c):03d}" if c.isdigit() else c for c in args.chapters]
    else:
        logger.error("Specify chapters, --range, or --all")
        return 1

    # Process each chapter
    success_count = 0
    fail_count = 0

    for ch_num in chapters:
        logger.info(f"\n{'='*50}")
        logger.info(f"Chapter {ch_num}")
        logger.info(f"{'='*50}")

        if not args.skip_prepare:
            en_zip, es_zip = find_chapter_files(args.manga_slug, ch_num)

            if not en_zip.exists():
                logger.warning(f"EN file not found: {en_zip}")
                fail_count += 1
                continue

            if not es_zip.exists():
                logger.warning(f"ES file not found: {es_zip}")
                fail_count += 1
                continue

            try:
                prepare_chapter(
                    args.manga_slug,
                    en_zip,
                    es_zip,
                    UPLOAD_DIR,
                    args.threshold
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to prepare chapter {ch_num}: {e}")
                fail_count += 1
                continue
        else:
            success_count += 1

    # Upload
    if success_count > 0:
        logger.info(f"\n{'='*50}")
        logger.info("UPLOADING TO SERVER")
        logger.info(f"{'='*50}")

        if rsync_upload(args.manga_slug, dry_run=args.dry_run):
            logger.info("Upload complete!")
        else:
            logger.error("Upload failed!")
            return 1

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"Processed: {success_count}")
    print(f"Failed:    {fail_count}")
    print(f"Dry run:   {args.dry_run}")
    print(f"{'='*50}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
