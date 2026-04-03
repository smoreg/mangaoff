#!/usr/bin/env python3
"""
Upload all downloaded manga to server.

Usage:
    python3 upload_all.py
    python3 upload_all.py --dry-run
    python3 upload_all.py --manga chainsaw-man beelzebub
"""

import argparse
import subprocess
import sys
from pathlib import Path

from generate_manifest import generate_manifest

BACKUP_DIR = Path(__file__).parent.parent / "backup_downloads" / "chapters"
COVERS_DIR = Path(__file__).parent.parent / "backup_downloads" / "covers"
UPLOAD_DIR = Path(__file__).parent / "tmp" / "upload"

# Server config
SERVER_HOST = "smoreg.dev"
SERVER_USER = "root"
SERVER_DATA_PATH = "/opt/mangaoff/data"

# Manga to upload (slug -> title)
ALL_MANGA = {
    "chainsaw-man": "Chainsaw Man",
    "beelzebub": "Beelzebub",
    "yofukashi-no-uta": "Yofukashi no Uta",
    "saotome-senshu,-hitakakusu": "Saotome Senshu, Hitakakusu",
    "vagabond": "Vagabond",
}


def count_chapters(manga_slug: str) -> int:
    """Count bilingual chapters for a manga."""
    manga_dir = BACKUP_DIR / manga_slug
    if not manga_dir.exists():
        return 0

    en_files = set(f.stem.rsplit('_', 1)[0] for f in manga_dir.glob("*_en.zip"))
    es_files = set(f.stem.rsplit('_', 1)[0] for f in manga_dir.glob("*_es.zip"))
    return len(en_files & es_files)


def upload_manga(manga_slug: str, dry_run: bool = False, keep_unpaired: bool = True) -> bool:
    """Upload all chapters for a manga."""
    cmd = [
        sys.executable, "upload_chapter.py",
        manga_slug, "--all"
    ]

    if dry_run:
        cmd.append("--dry-run")

    if keep_unpaired:
        cmd.append("--keep-unpaired")

    print(f"\n{'='*60}")
    print(f"UPLOADING CHAPTERS: {manga_slug}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd)
    return result.returncode == 0


def upload_manifest(manga_slug: str, title: str, dry_run: bool = False) -> bool:
    """Generate and upload manifest for a manga."""
    print(f"\n--- Generating manifest for {manga_slug}...")

    try:
        generate_manifest(manga_slug, title)
    except Exception as e:
        print(f"Failed to generate manifest: {e}")
        return False

    manifest_path = UPLOAD_DIR / manga_slug / "manifest.json"
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return False

    remote_dir = f"{SERVER_USER}@{SERVER_HOST}:{SERVER_DATA_PATH}/{manga_slug}/"

    # Create remote directory
    mkdir_cmd = ["ssh", f"{SERVER_USER}@{SERVER_HOST}", f"mkdir -p {SERVER_DATA_PATH}/{manga_slug}"]
    if not dry_run:
        subprocess.run(mkdir_cmd, check=True)

    # Upload manifest
    scp_cmd = ["scp", str(manifest_path), remote_dir]
    print(f"Uploading manifest: {' '.join(scp_cmd)}")

    if dry_run:
        print("  [DRY RUN] Skipping upload")
        return True

    result = subprocess.run(scp_cmd)
    return result.returncode == 0


def upload_cover(manga_slug: str, dry_run: bool = False) -> bool:
    """Upload cover if exists locally."""
    cover_dir = COVERS_DIR / manga_slug
    if not cover_dir.exists():
        print(f"  No local cover for {manga_slug}")
        return True  # Not an error

    remote_dir = f"{SERVER_USER}@{SERVER_HOST}:{SERVER_DATA_PATH}/covers/{manga_slug}/"

    rsync_cmd = ["rsync", "-avz", f"{cover_dir}/", remote_dir]
    print(f"Uploading cover: {' '.join(rsync_cmd)}")

    if dry_run:
        print("  [DRY RUN] Skipping upload")
        return True

    result = subprocess.run(rsync_cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Upload all downloaded manga")
    parser.add_argument("--manga", "-m", nargs="+", default=None,
                        help="Specific manga to upload (default: all)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Prepare but don't upload")
    parser.add_argument("--no-keep-unpaired", action="store_true",
                        help="Drop pages that exist only in one language")
    parser.add_argument("--list", "-l", action="store_true",
                        help="Just list available manga and chapter counts")
    parser.add_argument("--manifest-only", action="store_true",
                        help="Only generate and upload manifests (skip chapters)")

    args = parser.parse_args()

    manga_list = args.manga or list(ALL_MANGA.keys())

    # List mode
    if args.list:
        print("Available manga:")
        print("-" * 40)
        for slug, title in ALL_MANGA.items():
            count = count_chapters(slug)
            status = "✓" if count > 0 else "✗"
            print(f"  {status} {slug}: {count} chapters")
        return 0

    # Show plan
    print("=" * 60)
    print("UPLOAD PLAN")
    print("=" * 60)

    total_chapters = 0
    for manga in manga_list:
        count = count_chapters(manga)
        total_chapters += count
        title = ALL_MANGA.get(manga, manga)
        print(f"  {manga} ({title}): {count} chapters")

    print("-" * 60)
    print(f"  TOTAL: {total_chapters} chapters")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Keep unpaired: {not args.no_keep_unpaired}")
    print(f"  Manifest only: {args.manifest_only}")
    print("=" * 60)

    if total_chapters == 0 and not args.manifest_only:
        print("No chapters to upload!")
        return 1

    # Upload each manga
    success = 0
    failed = 0

    for manga in manga_list:
        title = ALL_MANGA.get(manga, manga.replace("-", " ").title())

        if not args.manifest_only:
            if count_chapters(manga) == 0:
                print(f"Skipping {manga} - no chapters found")
                continue

            if not upload_manga(manga, args.dry_run, not args.no_keep_unpaired):
                failed += 1
                continue

        # Upload cover
        print(f"\n--- Uploading cover for {manga}...")
        upload_cover(manga, args.dry_run)

        # Generate and upload manifest
        if not upload_manifest(manga, title, args.dry_run):
            print(f"WARNING: Failed to upload manifest for {manga}")
            failed += 1
            continue

        success += 1

    # Summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"  Manga processed: {success + failed}")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
