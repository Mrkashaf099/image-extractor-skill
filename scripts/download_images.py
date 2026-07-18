#!/usr/bin/env python3
"""
Image Extractor - Claude Code Skill
Downloads 5 images from Bing, DuckDuckGo, and Unsplash
with aspect ratio filtering and duplicate detection.
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path


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
    from icrawler.builtin import BingImageCrawler
except ImportError:
    print("Installing icrawler..."); install("icrawler"); from icrawler.builtin import BingImageCrawler

from icrawler.builtin import BingImageCrawler


# ── Constants ──────────────────────────────────────────────────────────────────

BASE_DIR = Path.home() / "Pictures" / "ImageExtractor"
TARGET_COUNT = 5
MAX_PER_SOURCE = 10
METADATA_FILE = "metadata.json"
UNSPLASH_ACCESS_KEY = "client-id"   # Public demo key (rate limited); user can replace


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

def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def load_metadata(folder):
    p = folder / METADATA_FILE
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {"hashes": [], "files": [], "sources": []}

def save_metadata(folder, meta):
    with open(folder / METADATA_FILE, "w") as f:
        json.dump(meta, f, indent=2)

def try_accept(path, ratio_check, known_hashes):
    """Validate image: readable, correct ratio, not a duplicate. Returns hash or None."""
    try:
        img = Image.open(path)
        w, h = img.size
        img.close()
    except Exception:
        return None
    if not ratio_check(w, h):
        return None
    file_hash = md5_file(path)
    if file_hash in known_hashes:
        return None
    return file_hash


# ── Source: Bing ───────────────────────────────────────────────────────────────

def fetch_bing(topic, temp_dir, count):
    try:
        crawler = BingImageCrawler(
            storage={"root_dir": str(temp_dir)},
            log_level=50,
        )
        crawler.crawl(keyword=topic, max_num=count, file_idx_offset=0)
        return sorted(temp_dir.glob("*.*"))
    except Exception as e:
        print(f"  ⚠️  Bing error: {e}")
        return []


# ── Source: DuckDuckGo ─────────────────────────────────────────────────────────

def fetch_duckduckgo(topic, temp_dir, count):
    try:
        # duckduckgo_search package
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            install("duckduckgo-search")
            from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.images(topic, max_results=count):
                results.append(r.get("image", ""))

        saved = []
        for i, url in enumerate(results):
            if not url:
                continue
            try:
                resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    ext = ".jpg"
                    dest = temp_dir / f"ddg_{i}{ext}"
                    dest.write_bytes(resp.content)
                    saved.append(dest)
            except Exception:
                continue
        return saved
    except Exception as e:
        print(f"  ⚠️  DuckDuckGo error: {e}")
        return []


# ── Source: Unsplash ───────────────────────────────────────────────────────────

def fetch_unsplash(topic, temp_dir, count):
    try:
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": topic,
            "per_page": count,
            "client_id": UNSPLASH_ACCESS_KEY,
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️  Unsplash API error: {resp.status_code}")
            return []

        results = resp.json().get("results", [])
        saved = []
        for i, item in enumerate(results):
            img_url = item.get("urls", {}).get("regular", "")
            if not img_url:
                continue
            try:
                img_resp = requests.get(img_url, timeout=15)
                if img_resp.status_code == 200:
                    dest = temp_dir / f"unsplash_{i}.jpg"
                    dest.write_bytes(img_resp.content)
                    saved.append(dest)
            except Exception:
                continue
        return saved
    except Exception as e:
        print(f"  ⚠️  Unsplash error: {e}")
        return []


# ── Core Logic ─────────────────────────────────────────────────────────────────

def download_images(topic, ratio):
    ratio_check = get_ratio_check(ratio)
    slug = slugify(topic)
    folder = BASE_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    meta = load_metadata(folder)
    known_hashes = set(meta["hashes"])

    print(f"\n🔍 Topic     : \"{topic}\"")
    print(f"📐 Ratio     : {ratio}")
    print(f"📁 Folder    : {folder}")
    print(f"🌐 Sources   : Bing → DuckDuckGo → Unsplash\n")

    accepted = 0
    skipped_ratio = 0
    skipped_dedup = 0
    source_counts = {"Bing": 0, "DuckDuckGo": 0, "Unsplash": 0}

    sources = [
        ("Bing",       fetch_bing),
        ("DuckDuckGo", fetch_duckduckgo),
        ("Unsplash",   fetch_unsplash),
    ]

    for source_name, fetch_fn in sources:
        if accepted >= TARGET_COUNT:
            break

        needed = TARGET_COUNT - accepted
        temp_dir = folder / f"_temp_{source_name.lower()}"
        temp_dir.mkdir(exist_ok=True)

        print(f"  🔎 Trying {source_name}...")
        candidates = fetch_fn(topic, temp_dir, MAX_PER_SOURCE)

        for candidate in candidates:
            if accepted >= TARGET_COUNT:
                break
            if not candidate.exists():
                continue

            file_hash = try_accept(candidate, ratio_check, known_hashes)

            if file_hash is None:
                # Figure out why it was skipped
                try:
                    img = Image.open(candidate)
                    w, h = img.size
                    img.close()
                    if not ratio_check(w, h):
                        skipped_ratio += 1
                    else:
                        skipped_dedup += 1
                except Exception:
                    pass
                candidate.unlink(missing_ok=True)
                continue

            # Accept it
            accepted += 1
            ext = candidate.suffix.lower() or ".jpg"
            dest = folder / f"image_{len(meta['files']) + 1}{ext}"
            candidate.rename(dest)

            known_hashes.add(file_hash)
            meta["hashes"].append(file_hash)
            meta["files"].append(dest.name)
            meta["sources"].append(source_name)
            source_counts[source_name] += 1

            try:
                img = Image.open(dest)
                w, h = img.size
                img.close()
                print(f"     ✅ {dest.name}  ({w}×{h}px)  [{source_name}]")
            except Exception:
                print(f"     ✅ {dest.name}  [{source_name}]")

        # Cleanup temp
        for f in temp_dir.glob("*"):
            f.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except Exception:
            pass

    save_metadata(folder, meta)

    return {
        "topic": topic,
        "ratio": ratio,
        "folder": str(folder),
        "downloaded": accepted,
        "skipped_ratio": skipped_ratio,
        "skipped_duplicate": skipped_dedup,
        "by_source": source_counts,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download images from Bing, DuckDuckGo & Unsplash.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--ratio", required=True, choices=["9:16", "16:9"])
    args = parser.parse_args()

    result = download_images(args.topic, args.ratio)

    print("\n" + "─" * 52)
    print(f"✅ Done!")
    print(f"   Downloaded : {result['downloaded']} / {TARGET_COUNT} images")
    print(f"   Skipped    : {result['skipped_ratio']} (wrong ratio)  |  {result['skipped_duplicate']} (duplicates)")
    print(f"   By source  : Bing={result['by_source']['Bing']}  DDG={result['by_source']['DuckDuckGo']}  Unsplash={result['by_source']['Unsplash']}")
    print(f"   Saved to   : {result['folder']}")
    print("─" * 52 + "\n")

    if result["downloaded"] < TARGET_COUNT:
        print(f"⚠️  Only {result['downloaded']} image(s) matched. Try a broader topic.\n")

if __name__ == "__main__":
    main()
