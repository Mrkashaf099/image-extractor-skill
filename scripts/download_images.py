#!/usr/bin/env python3
"""
Image Extractor - Claude Code Skill

Termux-friendly downloader using SerpAPI image results.
Requires:
  - requests
  - Pillow
API key:
  - SERPAPI_API_KEY environment variable

Saves to /storage/emulated/0/DCIM/manga/<topic>/ when available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    )
}

TARGET_COUNT = 5
METADATA_FILE = "metadata.json"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def android_storage_base() -> Path:
    candidates = [
        Path("/storage/emulated/0/DCIM/manga"),
        Path("/sdcard/DCIM/manga"),
        Path.home() / "storage" / "shared" / "DCIM" / "manga",
        Path.home() / "DCIM" / "manga",
    ]
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_test"
            probe.write_text("1", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue
    fallback = Path.home() / "DCIM" / "manga"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DEFAULT_BASE_DIR = android_storage_base()


def slugify_folder_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", " ", text)
    return text[:120] if len(text) > 120 else text


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


def detect_extension(url: str, data: bytes) -> str:
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if ext == ".jpeg" else ext
    try:
        from io import BytesIO
        img = Image.open(BytesIO(data))
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


def serpapi_image_urls(topic: str, api_key: str, count: int):
    params = {
        "engine": "google_images",
        "q": topic,
        "api_key": api_key,
        "ijn": 0,
    }
    urls = []
    seen = set()

    while len(urls) < count:
        resp = requests.get(SERPAPI_ENDPOINT, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        images = data.get("images_results", []) or []
        if not images:
            break

        for item in images:
            url = item.get("original") or item.get("thumbnail") or item.get("link")
            if not url or not isinstance(url, str):
                continue
            if not url.startswith("http"):
                continue
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= count:
                break

        next_page = data.get("serpapi_pagination", {}).get("next")
        if not next_page:
            break
        params = None
        if len(urls) < count:
            resp2 = requests.get(next_page, headers=HEADERS, timeout=30)
            resp2.raise_for_status()
            data = resp2.json()
            images = data.get("images_results", []) or []
            if not images:
                break
            for item in images:
                url = item.get("original") or item.get("thumbnail") or item.get("link")
                if not url or not isinstance(url, str):
                    continue
                if not url.startswith("http"):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                urls.append(url)
                if len(urls) >= count:
                    break
            if not data.get("serpapi_pagination", {}).get("next"):
                break
            params = None
            break

    return urls[:count]


def download_url(url: str, timeout: int = 25) -> bytes | None:
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


def download_images(topic: str, ratio: str, base_dir: Path, count: int, api_key: str):
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

    urls = serpapi_image_urls(topic, api_key, max(count * 5, 25))

    accepted = 0
    skipped_ratio = 0
    skipped_dedup = 0
    skipped_errors = 0

    print("\n  ⬇️  Downloading images...\n")

    def fetch_and_validate(url: str):
        data = None
        for _ in range(3):
            data = download_url(url)
            if data:
                break
        if not data:
            return url, None, None, "error", None
        file_hash, reason, dims = validate_image(data, ratio_check, known_hashes)
        return url, data, file_hash, reason, dims

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for url in urls:
            if accepted >= count:
                break
            if url in known_urls:
                skipped_dedup += 1
                continue
            futures.append(executor.submit(fetch_and_validate, url))

        for future in as_completed(futures):
            if accepted >= count:
                break
            try:
                url, data, file_hash, reason, dims = future.result()
            except Exception:
                skipped_errors += 1
                continue

            if reason == "error" or not data:
                skipped_errors += 1
                continue
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
    parser = argparse.ArgumentParser(description="Search the web for images and download them directly.")
    parser.add_argument("--topic", required=True, help="Search topic")
    parser.add_argument("--ratio", required=True, choices=["9:16", "16:9"], help="Aspect ratio")
    parser.add_argument("--output-dir", default=str(DEFAULT_BASE_DIR), help="Output base directory")
    parser.add_argument("--count", type=int, default=TARGET_COUNT, help="Number of images to save")
    args = parser.parse_args()

    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is not set in the environment.")

    result = download_images(args.topic, args.ratio, Path(args.output_dir), args.count, api_key)

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
