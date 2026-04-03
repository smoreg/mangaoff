# MangaOff Project Instructions

## CRITICAL: LONG-RUNNING SCRIPTS

**NEVER without explicit user permission:**
- ❌ Run `download_all.py`, `upload_all.py` or similar long scripts
- ❌ Kill/stop running processes (`pkill`, `kill`, Ctrl+C)
- ❌ Start background tasks that take more than 30 seconds

**ALWAYS ask first:**
- "Запустить скрипт X?" / "Run script X?"
- "Остановить процесс Y?" / "Stop process Y?"

**WHY:** Downloads take hours, killing them loses progress and wastes time.

---

## CRITICAL: BACKUP DOWNLOADS FOLDER

**Directory: `/Users/smoreg/code/mangaoff/backup_downloads/`**

### ABSOLUTELY FORBIDDEN OPERATIONS:
- ❌ `rm` - NEVER delete any files
- ❌ `mv` - NEVER move any files
- ❌ `rename` - NEVER rename any files
- ❌ Any modification to file contents
- ❌ Any destructive operation

### ALLOWED OPERATIONS:
- ✅ `cp` - Copy files to other locations
- ✅ `ls` - List files
- ✅ `cat` / Read - Read file contents
- ✅ Generate manifests from existing files

### WHY:
Downloaded chapters from MangaDex are expensive to re-download:
- Strict rate limits (4-5 req/sec)
- Hours of download time
- Risk of getting rate-limited/blocked

### IF RESTRUCTURING NEEDED:
1. Create new target directory
2. COPY (not move) files from backup_downloads
3. Work with copies
4. Keep backup_downloads intact

## Project Structure

- `parser/` - Python MangaDex downloader
- `server/` - Go API server
- `android/` - Android app
- `backup_downloads/` - **READ-ONLY** downloaded chapters

## Parser Usage

### Installation

```bash
cd parser
pip install -r requirements.txt
```

### Download Manga

```bash
# Basic usage - download by title
python3 main.py "Chainsaw Man" -o ../backup_downloads

# Download specific chapter range
python3 main.py "Chainsaw Man" -o ../backup_downloads --start 1 --end 20

# Use data-saver mode (lower quality, faster download)
python3 main.py "SPY×FAMILY" -o ../backup_downloads --data-saver

# Custom temp directory
python3 main.py "One Piece" -o ../backup_downloads -t ./my_temp
```

### Arguments

| Argument | Description |
|----------|-------------|
| `title` | Manga title to search on MangaDex |
| `-o, --output` | Output directory (default: ./output) |
| `-t, --temp` | Temp directory for downloads (default: ./temp) |
| `--start` | Start chapter number (default: 1) |
| `--end` | End chapter number (optional) |
| `--data-saver` | Use lower quality images |

### What Parser Does

1. Searches manga on MangaDex by title
2. Fetches all chapters with EN and ES translations
3. Filters to **bilingual only** (chapters with BOTH languages)
4. Downloads pages and creates ZIP archives: `001_en.zip`, `001_es.zip`
5. Records each download in `manga_tracker.db`
6. Generates `manifest.json` for the manga

### Output Structure

```
backup_downloads/
├── chapters/
│   └── chainsaw-man/
│       ├── 001_en.zip
│       ├── 001_es.zip
│       ├── 002_en.zip
│       └── ...
├── covers/
│   └── chainsaw-man/
│       └── cover.jpg
└── chainsaw-man/
    └── manifest.json
```

### Rate Limits

MangaDex has strict rate limits (4-5 req/sec). The parser:
- Uses `aiolimiter` for automatic rate limiting
- Adds delays between chapter downloads
- Retries on 429 (rate limit) errors

## Manga Tracker Database

SQLite database at `manga_tracker.db` tracks all manga downloads.

**IMPORTANT:** Database location is `/Users/smoreg/code/mangaoff/manga_tracker.db` (project root, NOT parser/)!

### Database Backup

```bash
# Create backup
cp manga_tracker.db manga_tracker.db.backup

# Restore from backup
cp manga_tracker.db.backup manga_tracker.db
```

**Always backup before running long downloads!**

### Database Schema

```sql
-- manga: All manga in wishlist
CREATE TABLE manga (
    id INTEGER PRIMARY KEY,
    mangadex_id TEXT UNIQUE,      -- MangaDex UUID
    title TEXT,                    -- Manga title
    slug TEXT,                     -- URL-friendly slug
    mangadex_url TEXT,             -- Full MangaDex URL
    total_chapters_en INTEGER,     -- Available EN chapters
    total_chapters_es INTEGER,     -- Available ES chapters
    status TEXT,                   -- wishlist/downloading/completed
    created_at TEXT,
    updated_at TEXT
);

-- downloaded_chapters: Downloaded chapter files
CREATE TABLE downloaded_chapters (
    id INTEGER PRIMARY KEY,
    manga_id INTEGER,              -- FK to manga
    chapter_number TEXT,           -- "1", "2.5", etc.
    language TEXT,                 -- "en" or "es"
    zip_path TEXT,                 -- Path to zip file
    page_count INTEGER,
    downloaded_at TEXT
);
```

### Commands

```bash
cd parser

# Initialize database with wishlist (run once)
python3 init_wishlist.py

# View stats
python3 init_wishlist.py --stats

# Add Chainsaw Man downloaded chapters (if needed)
python3 init_wishlist.py --add-chainsaw
```

### How Parser Uses Database

- Automatically tracks downloaded chapters
- Skips already-downloaded chapters (checks database first)
- Updates chapter counts from MangaDex API
- Marks manga as "completed" when all bilingual chapters downloaded

### Wishlist Manga (29 titles)

| Status | Manga |
|--------|-------|
| downloading | Chainsaw Man (5 ch) |
| wishlist | One Piece, Fullmetal Alchemist, Attack on Titan, SPY×FAMILY, Jujutsu Kaisen, Hellsing, Beelzebub, Bakuman, Dr.STONE, Kaiju No. 8, and more... |

## Page Alignment & Upload

Different translation groups have different page counts (credits, covers, etc.).
The alignment tools synchronize page numbering between EN and ES versions.

### Page Aligner (Analysis)

```bash
cd parser

# Analyze alignment between two chapter ZIPs
python3 page_aligner.py chapter_en.zip chapter_es.zip

# Custom similarity threshold (lower = stricter)
python3 page_aligner.py chapter_en.zip chapter_es.zip -t 20

# Save result to JSON
python3 page_aligner.py chapter_en.zip chapter_es.zip -o alignment.json
```

### Prepare Chapter for Upload

Creates aligned ZIPs ready for server upload. Pages are renumbered so that
`001.jpg` in EN corresponds to `001.jpg` in ES.

```bash
cd parser

# Prepare single chapter
python3 prepare_chapter.py chainsaw-man 001_en.zip 001_es.zip

# Custom output directory
python3 prepare_chapter.py chainsaw-man 001_en.zip 001_es.zip -o ../upload/

# With custom threshold
python3 prepare_chapter.py beelzebub 005_en.zip 005_es.zip -t 20
```

### Output Structure

```
upload/
└── chainsaw-man/
    └── chapters/
        ├── 001_en.zip           # Aligned EN pages (001.jpg, 002.jpg, ...)
        ├── 001_es.zip           # Aligned ES pages (001.jpg, 002.jpg, ...)
        └── 001_alignment.json   # Alignment manifest
```

### Alignment Manifest

The `*_alignment.json` file documents which pages matched:

```json
{
  "chapter": "001",
  "total_pages": 57,
  "matched": 51,
  "en_only": 2,
  "es_only": 4,
  "pages": [
    {"index": 1, "en": null, "es": "001.png", "type": "es_only"},
    {"index": 2, "en": "001.jpg", "es": null, "type": "en_only"},
    {"index": 5, "en": "003.jpg", "es": "003.png", "type": "matched", "distance": 14}
  ]
}
```

### Upload to Server

Server: `smoreg.dev`
User: `root`
Data path: `/opt/mangaoff/data/`

#### Server Structure (IMPORTANT!)

```
/opt/mangaoff/data/
├── chainsaw-man/          <- manifest.json here (API reads from here!)
│   └── manifest.json
├── beelzebub/
│   └── manifest.json
├── chapters/              <- nginx /chapters/ alias points here
│   ├── chainsaw-man/
│   │   ├── 001_en.zip
│   │   ├── 001_es.zip
│   │   └── ...
│   └── beelzebub/
│       └── ...
└── covers/                <- nginx /covers/ alias points here
    ├── chainsaw-man/
    │   └── cover.jpg
    └── beelzebub/
        └── cover.jpg
```

**CRITICAL:** The Go API reads `manifest.json` from `/opt/mangaoff/data/{manga-slug}/manifest.json`!
Without manifests, manga won't appear in the app!

#### Upload All Manga (Recommended)

```bash
cd parser

# Upload all manga (chapters + covers + manifests)
python3 upload_all.py

# Dry run first
python3 upload_all.py --dry-run

# List available manga
python3 upload_all.py --list

# Specific manga only
python3 upload_all.py --manga chainsaw-man beelzebub

# Only regenerate and upload manifests (skip chapters)
python3 upload_all.py --manifest-only
```

The `upload_all.py` script automatically:
1. Aligns and uploads chapters
2. Uploads covers
3. Generates and uploads `manifest.json`

#### Single Chapter Upload

```bash
cd parser

# Single chapter (align + upload)
python3 upload_chapter.py chainsaw-man 001

# Multiple chapters
python3 upload_chapter.py chainsaw-man 001 002 003 004 005

# Chapter range
python3 upload_chapter.py beelzebub --range 1-50

# All available bilingual chapters
python3 upload_chapter.py chainsaw-man --all

# Dry run (prepare only, don't upload)
python3 upload_chapter.py chainsaw-man 001 --dry-run

# Keep unpaired pages (pages that exist only in EN or ES)
python3 upload_chapter.py chainsaw-man 001 --keep-unpaired
```

**Note:** `upload_chapter.py` does NOT upload manifests! Use `upload_all.py` or manually upload.

#### Generate Manifest Only

```bash
cd parser

# Generate manifest from uploaded chapters
python3 generate_manifest.py chainsaw-man "Chainsaw Man"

# Then upload manually:
ssh root@smoreg.dev "mkdir -p /opt/mangaoff/data/chainsaw-man"
scp tmp/upload/chainsaw-man/manifest.json root@smoreg.dev:/opt/mangaoff/data/chainsaw-man/
```

#### Manual rsync

```bash
# Chapters:
rsync -avz tmp/upload/chainsaw-man/chapters/ root@smoreg.dev:/opt/mangaoff/data/chapters/chainsaw-man/

# Covers:
rsync -avz ../backup_downloads/covers/chainsaw-man/ root@smoreg.dev:/opt/mangaoff/data/covers/chainsaw-man/

# Manifest:
scp tmp/upload/chainsaw-man/manifest.json root@smoreg.dev:/opt/mangaoff/data/chainsaw-man/
```

### How Alignment Works

1. **Perceptual hashing (pHash)** - converts images to 64-bit fingerprints
2. **Grayscale + resize** - handles color vs B&W and different resolutions
3. **Needleman-Wunsch DP** - sequence alignment algorithm (like DNA alignment)
4. **Threshold filtering** - distance ≤12 = good match, 13-25 = weak match

### Threshold Guide

| Threshold | Use Case |
|-----------|----------|
| 12-15 | Same scan source, minor differences |
| 20-25 | Different scanlation groups (recommended) |
| 30+ | Very different scans, may have false positives |
