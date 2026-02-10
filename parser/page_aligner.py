#!/usr/bin/env python3
"""
Page Aligner - matches pages between different language versions of manga chapters.

Handles:
- Color vs B&W pages (converts to grayscale)
- Extra pages in one version (sequence alignment)
- Different resolutions/compression

Uses perceptual hashing (pHash) - no neural networks.

Usage:
    python3 page_aligner.py chapter_en.zip chapter_es.zip
    python3 page_aligner.py chapter_en.zip chapter_es.zip --output aligned/
    python3 page_aligner.py chapter_en.zip chapter_es.zip --threshold 15
"""

import argparse
import logging
import zipfile
import tempfile
import shutil
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import io

import imagehash
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Default similarity threshold (lower = more strict)
# pHash difference: 0 = identical, <10 = very similar, <15 = similar, <25 = same page different scan
# For manga from different scanlation groups, use 20-25
DEFAULT_THRESHOLD = 20


@dataclass
class PageInfo:
    """Information about a single page."""
    index: int
    filename: str
    phash: str
    width: int
    height: int


@dataclass
class PageMatch:
    """A matched pair of pages."""
    page_a: Optional[PageInfo]
    page_b: Optional[PageInfo]
    distance: Optional[int]  # pHash distance, None if no match
    match_type: str  # "match", "insert_a", "insert_b"


@dataclass
class AlignmentResult:
    """Result of aligning two chapters."""
    file_a: str
    file_b: str
    pages_a: int
    pages_b: int
    matches: list[PageMatch]
    matched_count: int
    insert_a_count: int  # Pages only in A
    insert_b_count: int  # Pages only in B
    avg_distance: float


def compute_phash(image_data: bytes, hash_size: int = 8) -> tuple[imagehash.ImageHash, int, int]:
    """Compute perceptual hash of an image.

    Returns (hash, width, height).
    """
    img = Image.open(io.BytesIO(image_data))
    width, height = img.size

    # Convert to grayscale (handles color vs B&W)
    img = img.convert('L')

    # Resize to standard size for consistent hashing across different resolutions
    # This helps when comparing scans from different sources
    img = img.resize((256, 256), Image.Resampling.LANCZOS)

    # Compute perceptual hash
    phash = imagehash.phash(img, hash_size=hash_size)

    return phash, width, height


def extract_pages(zip_path: Path) -> list[tuple[str, bytes]]:
    """Extract all image pages from a ZIP archive.

    Returns list of (filename, image_data) tuples, sorted by filename.
    """
    pages = []
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in sorted(zf.namelist()):
            ext = Path(name).suffix.lower()
            if ext in image_extensions:
                data = zf.read(name)
                pages.append((name, data))

    return pages


def analyze_chapter(zip_path: Path) -> list[PageInfo]:
    """Analyze all pages in a chapter ZIP."""
    pages = extract_pages(zip_path)
    result = []

    for idx, (filename, data) in enumerate(pages):
        try:
            phash, width, height = compute_phash(data)
            result.append(PageInfo(
                index=idx,
                filename=filename,
                phash=str(phash),
                width=width,
                height=height
            ))
        except Exception as e:
            logger.warning(f"Failed to process {filename}: {e}")

    return result


def hash_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hash strings."""
    h1 = imagehash.hex_to_hash(hash1)
    h2 = imagehash.hex_to_hash(hash2)
    return h1 - h2


def build_distance_matrix(pages_a: list[PageInfo], pages_b: list[PageInfo]) -> list[list[int]]:
    """Build a distance matrix between all pages."""
    matrix = []
    for pa in pages_a:
        row = []
        for pb in pages_b:
            dist = hash_distance(pa.phash, pb.phash)
            row.append(dist)
        matrix.append(row)
    return matrix


def align_sequences(
    pages_a: list[PageInfo],
    pages_b: list[PageInfo],
    threshold: int = DEFAULT_THRESHOLD
) -> list[PageMatch]:
    """Align two sequences of pages using Needleman-Wunsch dynamic programming.

    This is similar to DNA sequence alignment - finds optimal alignment
    that minimizes total cost while respecting page order.
    """
    n = len(pages_a)
    m = len(pages_b)

    if n == 0 and m == 0:
        return []

    if n == 0:
        return [PageMatch(None, pb, None, "insert_b") for pb in pages_b]

    if m == 0:
        return [PageMatch(pa, None, None, "insert_a") for pa in pages_a]

    # Build distance matrix
    dist = build_distance_matrix(pages_a, pages_b)

    # Gap penalty - cost of inserting a page (unmatched)
    GAP_PENALTY = threshold + 5

    # DP table: dp[i][j] = minimum cost to align A[0:i] with B[0:j]
    # INF placeholder
    INF = float('inf')
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0

    # Initialize: gaps at the beginning
    for i in range(1, n + 1):
        dp[i][0] = i * GAP_PENALTY
    for j in range(1, m + 1):
        dp[0][j] = j * GAP_PENALTY

    # Fill DP table
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            # Option 1: Match A[i-1] with B[j-1]
            match_cost = dist[i-1][j-1]
            if match_cost <= threshold:
                # Good match
                dp[i][j] = min(dp[i][j], dp[i-1][j-1] + match_cost)
            else:
                # Bad match - still allow but with penalty
                dp[i][j] = min(dp[i][j], dp[i-1][j-1] + GAP_PENALTY * 2)

            # Option 2: Insert A[i-1] (gap in B)
            dp[i][j] = min(dp[i][j], dp[i-1][j] + GAP_PENALTY)

            # Option 3: Insert B[j-1] (gap in A)
            dp[i][j] = min(dp[i][j], dp[i][j-1] + GAP_PENALTY)

    # Traceback to find alignment
    matches = []
    i, j = n, m

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            match_cost = dist[i-1][j-1]
            came_from_match = (match_cost <= threshold and
                               dp[i][j] == dp[i-1][j-1] + match_cost)
            came_from_bad_match = (match_cost > threshold and
                                   dp[i][j] == dp[i-1][j-1] + GAP_PENALTY * 2)

            if came_from_match:
                # Good match
                match_type = "match" if match_cost <= threshold // 2 else "weak_match"
                matches.append(PageMatch(pages_a[i-1], pages_b[j-1], match_cost, match_type))
                i -= 1
                j -= 1
                continue
            elif came_from_bad_match:
                # Bad match (mismatch) - treat as both insertions
                matches.append(PageMatch(pages_a[i-1], None, None, "insert_a"))
                matches.append(PageMatch(None, pages_b[j-1], None, "insert_b"))
                i -= 1
                j -= 1
                continue

        if i > 0 and dp[i][j] == dp[i-1][j] + GAP_PENALTY:
            # Gap in B (A only)
            matches.append(PageMatch(pages_a[i-1], None, None, "insert_a"))
            i -= 1
        elif j > 0:
            # Gap in A (B only)
            matches.append(PageMatch(None, pages_b[j-1], None, "insert_b"))
            j -= 1
        else:
            break

    # Reverse since we traced back
    matches.reverse()

    return matches


def align_chapters(
    zip_a: Path,
    zip_b: Path,
    threshold: int = DEFAULT_THRESHOLD
) -> AlignmentResult:
    """Align pages between two chapter ZIPs."""
    logger.info(f"Analyzing {zip_a.name}...")
    pages_a = analyze_chapter(zip_a)
    logger.info(f"  Found {len(pages_a)} pages")

    logger.info(f"Analyzing {zip_b.name}...")
    pages_b = analyze_chapter(zip_b)
    logger.info(f"  Found {len(pages_b)} pages")

    logger.info("Aligning sequences...")
    matches = align_sequences(pages_a, pages_b, threshold)

    # Calculate stats
    matched = sum(1 for m in matches if m.match_type == "match")
    insert_a = sum(1 for m in matches if m.match_type == "insert_a")
    insert_b = sum(1 for m in matches if m.match_type == "insert_b")

    distances = [m.distance for m in matches if m.distance is not None]
    avg_dist = sum(distances) / len(distances) if distances else 0

    return AlignmentResult(
        file_a=str(zip_a),
        file_b=str(zip_b),
        pages_a=len(pages_a),
        pages_b=len(pages_b),
        matches=matches,
        matched_count=matched,
        insert_a_count=insert_a,
        insert_b_count=insert_b,
        avg_distance=avg_dist
    )


def print_alignment(result: AlignmentResult):
    """Print alignment result in a readable format."""
    print(f"\n{'='*60}")
    print(f"ALIGNMENT RESULT")
    print(f"{'='*60}")
    print(f"File A: {Path(result.file_a).name} ({result.pages_a} pages)")
    print(f"File B: {Path(result.file_b).name} ({result.pages_b} pages)")
    print(f"{'='*60}")
    print(f"Matched:    {result.matched_count}")
    print(f"Only in A:  {result.insert_a_count}")
    print(f"Only in B:  {result.insert_b_count}")
    print(f"Avg distance: {result.avg_distance:.1f}")
    print(f"{'='*60}\n")

    print(f"{'#':<4} {'A':<15} {'B':<15} {'Dist':<6} {'Status'}")
    print("-" * 50)

    for idx, match in enumerate(result.matches, 1):
        a_name = match.page_a.filename if match.page_a else "---"
        b_name = match.page_b.filename if match.page_b else "---"
        dist = str(match.distance) if match.distance is not None else "-"

        status_icons = {
            "match": "✓",
            "mismatch": "?",
            "insert_a": "← A only",
            "insert_b": "→ B only"
        }
        status = status_icons.get(match.match_type, match.match_type)

        # Truncate filenames
        a_name = a_name[:13] + ".." if len(a_name) > 15 else a_name
        b_name = b_name[:13] + ".." if len(b_name) > 15 else b_name

        print(f"{idx:<4} {a_name:<15} {b_name:<15} {dist:<6} {status}")


def save_alignment(result: AlignmentResult, output_path: Path):
    """Save alignment result to JSON."""
    # Convert to serializable format
    data = {
        "file_a": result.file_a,
        "file_b": result.file_b,
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved alignment to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Align pages between two manga chapter ZIPs"
    )
    parser.add_argument("zip_a", type=Path, help="First ZIP file (e.g., chapter_en.zip)")
    parser.add_argument("zip_b", type=Path, help="Second ZIP file (e.g., chapter_es.zip)")
    parser.add_argument("-t", "--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Similarity threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output JSON file for alignment result")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Don't print alignment table")

    args = parser.parse_args()

    if not args.zip_a.exists():
        logger.error(f"File not found: {args.zip_a}")
        return 1

    if not args.zip_b.exists():
        logger.error(f"File not found: {args.zip_b}")
        return 1

    result = align_chapters(args.zip_a, args.zip_b, args.threshold)

    if not args.quiet:
        print_alignment(result)

    if args.output:
        save_alignment(result, args.output)

    return 0


if __name__ == "__main__":
    exit(main())
