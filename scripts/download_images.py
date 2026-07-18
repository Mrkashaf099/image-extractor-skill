#!/usr/bin/env python3
"""
Image Extractor - Claude Code Skill
Downloads 5 images from Google for a topic with aspect ratio filtering and dedup.
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlparse, quote_plus


# ── Auto-install dependencies ──────────────────────────────────────────────────

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:
    import requests
except ImportError:
    print("Installing requests...")
    install("requests")
    import requests

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow...")
    install("Pillow")
    from PIL import Image

try:
    from icrawler.builtin import GoogleImageCrawler
except ImportError:
    print("Installing icrawler...")
    install("icrawler")
    from icrawler.builtin import GoogleImageCrawler


# ── Constants ──────────────────────────────────────────────────────────────────

BASE_DIR = Path.home() / "Pictures" / "ImageExtractor"
TARGET_COUNT = 5
MAX_CANDIDATES = 25   # fetch extra to account for ratio/dedup filtering
METADATA_FILE = "metadata.json"


# ── Helpers ────────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert topic to safe folder name."""
    return text.lower().strip().replace(" ", "_").replace("/", "-")


def get_ratio_filter(ratio: str):
    """Return a function that checks if an image matches the target ratio."""
    if ratio == "9:16":
        return lambda w, h: h > w   # portrait: height > width
    elif ratio == "16:9":
        return lambda w, h: w > h   # landscape: width > height
    else:
        raise ValueError(f"Unknown ratio '{ratio}'. Use '9:16' or '16:9'.")


def md5_file(path: Path) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_metadata(folder: Path) -> dict:
    """Load existing metadata (hashes + URLs already downloaded)."""
    meta_path = folder / METADATA_FILE
    if meta_path.exists():
        with open(meta_path) as f:
            return json.load(f)
    return {"hashes": [], "urls": [], "files": []}


def save_metadata(folder: Path, meta: dict):
    """Save metadata to disk."""
    with open(folder / METADATA_FILE, "w") as f:
        json.dump(meta, f, indent=2)


# ── Core Download Logic ────────────────────────────────────────────────────────

def download_images(topic: str, ratio: str) -> dict:
    """
    Main function: search Google, filter by ratio, dedup, save 5 images.
    Returns a result summary dict.
    """
    ratio_check = get_ratio_filter(ratio)
    slug = slugify(topic)
    folder = BASE_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    meta = load_metadata(folder)
    known_hashes = set(meta["hashes"])
    known_urls   = set(meta["urls"])

    # ── Use icrawler to fetch candidates into a temp subfolder ──────────────
    temp_dir = folder / "_temp"
    temp_dir.mkdir(exist_ok=True)

    print(f"\n🔍 Searching Google Images for: \"{topic}\"")
    print(f"📐 Aspect ratio filter: {ratio}")
    print(f"📁 Output folder: {folder}\n")

    crawler = GoogleImageCrawler(
        storage={"root_dir": str(temp_dir)},
        log_level=50,          # silence icrawler logs
    )
    crawler.crawl(
        keyword=topic,
        max_num=MAX_CANDIDATES,
        file_idx_offset=0,
    )

    # ── Filter, dedup, and move accepted images ──────────────────────────────
    candidates = sorted(temp_dir.glob("*.*"))
    accepted = 0
    skipped_ratio = 0
    skipped_dedup = 0

    for candidate in candidates:
        if accepted >= TARGET_COUNT:
            break

        # Validate it's a real image
        try:
            img = Image.open(candidate)
            w, h = img.size
            img.close()
        except Exception:
            candidate.unlink(missing_ok=True)
            continue

        # Ratio filter
        if not ratio_check(w, h):
            skipped_ratio += 1
            candidate.unlink(missing_ok=True)
            continue

        # Duplicate detection via MD5
        file_hash = md5_file(candidate)
        if file_hash in known_hashes:
            skipped_dedup += 1
            candidate.unlink(missing_ok=True)
            continue

        # Accept: move to final folder
        accepted += 1
        ext = candidate.suffix.lower() or ".jpg"
        dest = folder / f"image_{len(meta['files']) + 1}{ext}"
        candidate.rename(dest)

        # Update metadata
        known_hashes.add(file_hash)
        meta["hashes"].append(file_hash)
        meta["files"].append(dest.name)
        print(f"  ✅ Saved: {dest.name}  ({w}×{h}px)")

    # Cleanup temp dir
    for leftover in temp_dir.glob("*"):
        leftover.unlink(missing_ok=True)
    temp_dir.rmdir()

    save_metadata(folder, meta)

    return {
        "topic": topic,
        "ratio": ratio,
        "folder": str(folder),
        "downloaded": accepted,
        "skipped_ratio": skipped_ratio,
        "skipped_duplicate": skipped_dedup,
    }


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download images from Google for a topic."
    )
    parser.add_argument("--topic", required=True, help="Search topic")
    parser.add_argument(
        "--ratio",
        required=True,
        choices=["9:16", "16:9"],
        help="Target aspect ratio: 9:16 (portrait) or 16:9 (landscape)",
    )
    args = parser.parse_args()

    result = download_images(args.topic, args.ratio)

    print("\n" + "─" * 50)
    print(f"✅ Done!")
    print(f"   Topic      : {result['topic']}")
    print(f"   Ratio      : {result['ratio']}")
    print(f"   Downloaded : {result['downloaded']} / {TARGET_COUNT} images")
    print(f"   Skipped    : {result['skipped_ratio']} (wrong ratio)  |  "
          f"{result['skipped_duplicate']} (duplicates)")
    print(f"   Saved to   : {result['folder']}")
    print("─" * 50 + "\n")

    if result["downloaded"] < TARGET_COUNT:
        print(f"⚠️  Only {result['downloaded']} image(s) found matching criteria.")
        print("   Try a broader topic or run again for more results.\n")


if __name__ == "__main__":
    main()
