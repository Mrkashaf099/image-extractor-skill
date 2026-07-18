#!/usr/bin/env python3
"""
Image Extractor - Claude Code Skill

Termux-friendly version:
- No icrawler / lxml dependency
- Downloads images using requests only
- Saves to /storage/emulated/0/DCIM/manga/<topic>/ by default
- Works on Python 3.14
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


try:
    import requests
except ImportError:
    print("Missing dependency: requests")
    print("Install it with: pip install requests")
    raise

try:
    from PIL import Image
except ImportError:
    print("Missing dependency: Pillow")
    print("Install it with: pip install Pillow")
    raise

try:
    from duckduckgo_search import DDGS
except ImportError:
    print("Missing dependency: duckduckgo-search")
    print("Install it with: pip install duckduckgo-search")
    raise


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    )
}

TARGET_COUNT = 5
MAX_CANDIDATES = 40
METADATA_FILE = "metadata.json"

DEFAULT_BASE_DIR = Path("/storage/emulated/0/DCIM/manga")
if not DEFAULT_BASE_DIR.exists():
    DEFAULT_BASE_DIR = Path.home() / "DCIM" / "manga"


def slugify_folder_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", " ", text)
    return text[:120] if len(text) > 120 else text


def slugify_filename(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "_", text)
    return text.strip("_") or "image"


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def get_ratio_check(ratio: str):
    if ratio == "9:16":
        return lambda w, h: h > w
    if ratio == "16:9":
        return lambda w, h: w > h
    raise ValueError("Unknown ratio. Use 9:16 or 16:9.")


def load_metadata(folder: Path):
    path = folder / METADATA_FILE
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"hashes": [], "files": [], "urls": []}


def save_metadata(folder: Path, meta: dict) -> None:
    (folder / METADATA_FILE).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def search_image_urls(topic: str, count: int = MAX_CANDIDATES):
    query = f"{topic} high quality photo"
    print(f'  🔍 Searching web for: "{query}"')
    urls = []
    seen = set()

    try:
        with DDGS() as ddgs:
            results = ddgs.images(keywords=query, max_results=count)
            for r in results:
                url = r.get("image") or r.get("thumbnail") or r.get("url")
                if not url or not isinstance(url, str):
                    continue
                if not url.startswith("http"):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                urls.append(url)
    except Exception as e:
        print(f"  ⚠️  Search error: {e}")

    print(f"  📋 Found {len(urls)} candidate URLs")
    return urls


def download_url(url: str, timeout: int = 20) -> bytes | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type.lower():
            return None
        data = resp.content
        if len(data) < 4096:
            return None
        return data
    except Exception:
        return None


def detect_extension(url: str, data: bytes) -> str:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if ext == ".jpeg" else ext

    try:
        img = Image.open(sys.modules["io"].BytesIO(data))
        fmt = (img.format or "JPEG").upper()
        img.close()
        return {
            "JPEG": ".jpg",
            "JPG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp",
            "GIF": ".gif",
        }.get(fmt, ".jpg")
    except Exception:
        return ".jpg"


def validate_image(data: bytes, ratio_check, known_hashes: set[str]):
    try:
        from io import BytesIO
        img = Image.open(BytesIO(data))
        w, h = img.size
        img.close()
    except Exception:
        return None, "corrupt", None

    if not ratio_check(w, h):
        return None, "ratio", (w, h)

    file_hash = md5_bytes(data)
    if file_hash in known_hashes:
        return None, "duplicate", (w, h)

    return file_hash, "ok", (w, h)


def download_images(topic: str, ratio: str, base_dir: Path, count: int):
    ratio_check = get_ratio_check(ratio)
    folder = base_dir / slugify_folder_name(topic)
    folder.mkdir(parents=True, exist_ok=True)

    meta = load_metadata(folder)
    known_hashes = set(meta.get("hashes", []))
    known_urls = set(meta.get("urls", []))

    print(f"\n{'─'*52}")
    print("🖼️  Image Extractor")
    print(f"   Topic  : {topic}")
    print(f"   Ratio  : {ratio}")
    print(f"   Folder : {folder}")
    print(f"{'─'*52}\n")

    urls = search_image_urls(topic)

    accepted = 0
    skipped_ratio = 0
    skipped_dedup = 0
    skipped_errors = 0

    print("\n  ⬇️  Downloading images...\n")

    for idx, url in enumerate(urls, start=1):
        if accepted >= count:
            break
        if url in known_urls:
            skipped_dedup += 1
            continue

        data = None
        for _ in range(3):
            data = download_url(url)
            if data:
                break
            time.sleep(0.5)

        if not data:
            skipped_errors += 1
            continue

        file_hash, reason, dims = validate_image(data, ratio_check, known_hashes)
        if reason == "ratio":
            skipped_ratio += 1
            continue
        if reason == "duplicate":
            skipped_dedup += 1
            continue
        if reason == "corrupt":
            skipped_errors += 1
            continue

        ext = detect_extension(url, data)
        next_num = len(meta.get("files", [])) + 1
        filename = f"{next_num:03d}{ext}"
        path = folder / filename
        path.write_bytes(data)

        accepted += 1
        known_hashes.add(file_hash)
        known_urls.add(url)
        meta.setdefault("hashes", []).append(file_hash)
        meta.setdefault("files", []).append(filename)
        meta.setdefault("urls", []).append(url)

        w, h = dims or (0, 0)
        print(f"  ✅ {filename}  ({w}×{h}px)")

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


def main():
    parser = argparse.ArgumentParser(
        description="Search the web for images and download them directly."
    )
    parser.add_argument("--topic", required=True, help="Search topic")
    parser.add_argument(
        "--ratio", required=True, choices=["9:16", "16:9"],
        help="Aspect ratio: 9:16 (portrait) or 16:9 (landscape)"
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_BASE_DIR),
        help="Output base directory (default: /storage/emulated/0/DCIM/manga)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=TARGET_COUNT,
        help="Number of images to save (default: 5)",
    )
    args = parser.parse_args()

    result = download_images(
        topic=args.topic,
        ratio=args.ratio,
        base_dir=Path(args.output_dir),
        count=args.count,
    )

    print(f"\n{'─'*52}")
    print("✅ Complete!")
    print(f"   Downloaded : {result['downloaded']} / {args.count} images")
    print(
        f"   Skipped    : {result['skipped_ratio']} wrong ratio  |  "
        f"{result['skipped_duplicate']} duplicates  |  "
        f"{result['skipped_errors']} errors"
    )
    print(f"   Saved to   : {result['folder']}")
    print(f"{'─'*52}\n")

    if result["downloaded"] < args.count:
        print(f"⚠️  Only {result['downloaded']} image(s) found. Try a broader topic.\n")


if __name__ == "__main__":
    main()
