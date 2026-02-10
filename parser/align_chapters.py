#!/usr/bin/env python3
"""
Batch chapter alignment tool.

Finds matching EN/ES chapter pairs and aligns their pages.

Usage:
    python3 align_chapters.py ../backup_downloads/chapters/beelzebub/
    python3 align_chapters.py ../backup_downloads/chapters/chainsaw-man/ --output alignments/
"""

import argparse
import logging
import json
from pathlib import Path
from dataclasses import asdict

from page_aligner import align_chapters, print_alignment, AlignmentResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def find_chapter_pairs(chapters_dir: Path) -> list[tuple[Path, Path, str]]:
    """Find matching EN/ES chapter pairs.

    Returns list of (en_zip, es_zip, chapter_number) tuples.
    """
    pairs = []

    # Find all ZIP files
    zips = list(chapters_dir.glob("*.zip"))

    # Group by chapter number
    by_chapter = {}
    for zip_path in zips:
        # Parse filename: 001_en.zip, 001_es.zip, 200.8_en.zip
        stem = zip_path.stem  # "001_en"
        parts = stem.rsplit("_", 1)
        if len(parts) != 2:
            continue

        ch_num, lang = parts
        if ch_num not in by_chapter:
            by_chapter[ch_num] = {}
        by_chapter[ch_num][lang] = zip_path

    # Find pairs with both EN and ES
    for ch_num in sorted(by_chapter.keys(), key=lambda x: float(x) if x.replace('.', '').isdigit() else 0):
        langs = by_chapter[ch_num]
        if "en" in langs and "es" in langs:
            pairs.append((langs["en"], langs["es"], ch_num))

    return pairs


def align_all_chapters(
    chapters_dir: Path,
    output_dir: Path = None,
    threshold: int = 12
) -> dict:
    """Align all chapter pairs in a directory."""
    pairs = find_chapter_pairs(chapters_dir)
    logger.info(f"Found {len(pairs)} chapter pairs to align")

    if not pairs:
        logger.warning("No EN/ES chapter pairs found!")
        return {}

    results = {}
    summary = {
        "total_chapters": len(pairs),
        "perfect_matches": 0,
        "has_insertions": 0,
        "chapters": []
    }

    for en_zip, es_zip, ch_num in pairs:
        logger.info(f"\n{'='*40}")
        logger.info(f"Chapter {ch_num}")
        logger.info(f"{'='*40}")

        try:
            result = align_chapters(en_zip, es_zip, threshold)
            results[ch_num] = result

            # Check if perfect match
            if result.insert_a_count == 0 and result.insert_b_count == 0:
                summary["perfect_matches"] += 1
                status = "PERFECT"
            else:
                summary["has_insertions"] += 1
                status = f"DIFF (+{result.insert_a_count}A, +{result.insert_b_count}B)"

            logger.info(f"  EN: {result.pages_a} pages, ES: {result.pages_b} pages")
            logger.info(f"  Status: {status}")
            logger.info(f"  Avg distance: {result.avg_distance:.1f}")

            summary["chapters"].append({
                "chapter": ch_num,
                "pages_en": result.pages_a,
                "pages_es": result.pages_b,
                "matched": result.matched_count,
                "only_en": result.insert_a_count,
                "only_es": result.insert_b_count,
                "avg_distance": result.avg_distance,
                "status": status
            })

            # Save individual result if output dir specified
            if output_dir:
                output_path = output_dir / f"chapter_{ch_num}.json"
                output_path.parent.mkdir(parents=True, exist_ok=True)

                data = {
                    "file_a": str(result.file_a),
                    "file_b": str(result.file_b),
                    "pages_a": result.pages_a,
                    "pages_b": result.pages_b,
                    "matched_count": result.matched_count,
                    "insert_a_count": result.insert_a_count,
                    "insert_b_count": result.insert_b_count,
                    "avg_distance": result.avg_distance,
                    "matches": [
                        {
                            "page_a": asdict(m.page_a) if m.page_a else None,
                            "page_b": asdict(m.page_b) if m.page_b else None,
                            "distance": m.distance,
                            "match_type": m.match_type
                        }
                        for m in result.matches
                    ]
                }

                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"  Error: {e}")
            summary["chapters"].append({
                "chapter": ch_num,
                "error": str(e)
            })

    # Save summary
    if output_dir:
        summary_path = output_dir / "summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        logger.info(f"\nSaved summary to {summary_path}")

    return summary


def print_summary(summary: dict):
    """Print alignment summary."""
    print(f"\n{'='*60}")
    print("ALIGNMENT SUMMARY")
    print(f"{'='*60}")
    print(f"Total chapters:   {summary['total_chapters']}")
    print(f"Perfect matches:  {summary['perfect_matches']}")
    print(f"Has differences:  {summary['has_insertions']}")
    print(f"{'='*60}\n")

    if summary.get("chapters"):
        print(f"{'Ch':<8} {'EN':<6} {'ES':<6} {'Match':<6} {'+EN':<5} {'+ES':<5} {'Status'}")
        print("-" * 55)

        for ch in summary["chapters"]:
            if "error" in ch:
                print(f"{ch['chapter']:<8} ERROR: {ch['error']}")
            else:
                print(f"{ch['chapter']:<8} {ch['pages_en']:<6} {ch['pages_es']:<6} "
                      f"{ch['matched']:<6} {ch['only_en']:<5} {ch['only_es']:<5} {ch['status']}")


def main():
    parser = argparse.ArgumentParser(
        description="Align all EN/ES chapter pairs in a directory"
    )
    parser.add_argument("chapters_dir", type=Path,
                        help="Directory containing chapter ZIPs")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output directory for alignment results")
    parser.add_argument("-t", "--threshold", type=int, default=12,
                        help="Similarity threshold (default: 12)")

    args = parser.parse_args()

    if not args.chapters_dir.exists():
        logger.error(f"Directory not found: {args.chapters_dir}")
        return 1

    summary = align_all_chapters(args.chapters_dir, args.output, args.threshold)
    print_summary(summary)

    return 0


if __name__ == "__main__":
    exit(main())
