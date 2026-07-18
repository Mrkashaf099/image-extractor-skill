#!/usr/bin/env python3
"""
Image Extractor - Claude Code Skill
Uses web search to find image URLs, then downloads them directly.
No third-party crawlers needed.
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlparse


# ── Auto-install dependencies ──────────────────────────────────────────────────

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:
    import requests
except ImportError:
    print("Installing requests..."); install("requests"); import requests

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow..."); install("Pillow"); from PIL import Image

try:
    from duckduckgo_search import DDGS
except ImportError:
    print("Installing duckduckgo-search..."); install("duckduckgo-search"); from duckduckgo_search import DDGS


# ── Constants ──────────────────────────────────────────────────────────────────

BASE_DIR = Path.home() / "Pictures" / "ImageExtractor"
TARGET_COUNT = 5
MAX_CANDIDATES = 30
METADATA_FILE = "metadata.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def slugify(text):
    return text.lower().strip().replace(" ", "_").replace("/", "-")

def get_ratio_check(ratio):
    if ratio == "9:16":
        return lambda w, h: h > w
    elif ratio == "16:9":
        return lambda w, h: w > h
    else:
        raise ValueError(f"Unknown ratio '{ratio}'. Use '9:16' or '16:9'.")

def md5_bytes(data):
    return hashlib.md5(data).hexdigest()

def load_metadata(folder):
    p = folder / METADATA_FILE
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {"hashes": [], "files": [], "urls": []}

def save_metadata(folder, meta):
    with open(folder / METADATA_FILE, "w") as f:
        json.dump(meta, f, indent=2)


# ── Step 1: Web Search for Image URLs ─────────────────────────────────────────

def search_image_urls(topic, count=MAX_CANDIDATES):
    """Use DuckDuckGo image search to collect direct image URLs."""
    print(f"  🔍 Searching web for: \"{topic} high quality photo\"")
    urls = []
    try:
        with DDGS() as ddgs:
            results = ddgs.images(
                keywords=f"{topic} high quality photo",
                max_results=count,
            )
            for r in results:
                url = r.get("image", "")
                if url and url.startswith("http"):
                    urls.append(url)
    except Exception as e:
        print(f"  ⚠️  Search error: {e}")
    print(f"  📋 Found {len(urls)} candidate URLs")
    return urls


# ── Step 2: Download Each URL Directly ────────────────────────────────────────

def download_url(url, dest_path):
    """Download an image URL directly and save to dest_path. Returns bytes or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            return None
        data = resp.content
        if len(data) < 5000:  # skip tiny/broken images
            return None
        dest_path.write_bytes(data)
        return data
    except Exception:
        return None


# ── Step 3: Validate Ratio + Dedup ────────────────────────────────────────────

def validate(path, ratio_check, known_hashes, data):
    """Check ratio and duplicate. Returns hash if valid, None otherwise."""
    try:
        img = Image.open(path)
        w, h = img.size
        img.close()
    except Exception:
        return None, "corrupt"

    if not ratio_check(w, h):
        return None, "ratio"

    file_hash = md5_bytes(data)
    if file_hash in known_hashes:
        return None, "duplicate"

    return file_hash, "ok"


# ── Core Orchestrator ──────────────────────────────────────────────────────────

def download_images(topic, ratio):
    ratio_check = get_ratio_check(ratio)
    slug = slugify(topic)
    folder = BASE_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    meta = load_metadata(folder)
    known_hashes = set(meta["hashes"])
    known_urls   = set(meta["urls"])

    print(f"\n{'─'*52}")
    print(f"🖼️  Image Extractor")
    print(f"   Topic  : {topic}")
    print(f"   Ratio  : {ratio}")
    print(f"   Folder : {folder}")
    print(f"{'─'*52}\n")

    # Step 1 — Search for URLs
    urls = search_image_urls(topic)

    # Step 2 — Download and validate each URL
    accepted       = 0
    skipped_ratio  = 0
    skipped_dedup  = 0
    skipped_errors = 0

    print(f"\n  ⬇️  Downloading images...\n")

    for url in urls:
        if accepted >= TARGET_COUNT:
            break

        if url in known_urls:
            skipped_dedup += 1
            continue

        # Determine file extension
        parsed = urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        temp_path = folder / f"_temp_{accepted}{ext}"

        # Download directly
        data = download_url(url, temp_path)
        if data is None:
            skipped_errors += 1
            temp_path.unlink(missing_ok=True)
            continue

        # Validate
        file_hash, reason = validate(temp_path, ratio_check, known_hashes, data)

        if reason == "ratio":
            skipped_ratio += 1
            temp_path.unlink(missing_ok=True)
            continue
        elif reason == "duplicate":
            skipped_dedup += 1
            temp_path.unlink(missing_ok=True)
            continue
        elif reason == "corrupt":
            skipped_errors += 1
            temp_path.unlink(missing_ok=True)
            continue

        # Accept — rename to final filename
        accepted += 1
        final_path = folder / f"image_{len(meta['files']) + 1}{ext}"
        temp_path.rename(final_path)

        # Update metadata
        known_hashes.add(file_hash)
        known_urls.add(url)
        meta["hashes"].append(file_hash)
        meta["files"].append(final_path.name)
        meta["urls"].append(url)

        try:
            img = Image.open(final_path)
            w, h = img.size
            img.close()
            print(f"  ✅ image_{len(meta['files'])}{ext}  ({w}×{h}px)")
        except Exception:
            print(f"  ✅ image_{len(meta['files'])}{ext}")

    save_metadata(folder, meta)

    return {
        "topic": topic,
        "ratio": ratio,
        "folder": str(folder),
        "downloaded": accepted,
        "skipped_ratio": skipped_ratio,
        "skipped_duplicate": skipped_dedup,
        "skipped_errors": skipped_errors,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Search the web for images and download them directly."
    )
    parser.add_argument("--topic", required=True, help="Search topic")
    parser.add_argument("--ratio", required=True, choices=["9:16", "16:9"],
                        help="Aspect ratio: 9:16 (portrait) or 16:9 (landscape)")
    args = parser.parse_args()

    result = download_images(args.topic, args.ratio)

    print(f"\n{'─'*52}")
    print(f"✅ Complete!")
    print(f"   Downloaded : {result['downloaded']} / 5 images")
    print(f"   Skipped    : {result['skipped_ratio']} wrong ratio  |  "
          f"{result['skipped_duplicate']} duplicates  |  "
          f"{result['skipped_errors']} errors")
    print(f"   Saved to   : {result['folder']}")
    print(f"{'─'*52}\n")

    if result["downloaded"] < 5:
        print(f"⚠️  Only {result['downloaded']} image(s) found. Try a broader topic.\n")

if __name__ == "__main__":
    main()
