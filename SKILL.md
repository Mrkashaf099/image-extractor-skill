---
name: image-extractor
description: >
  Downloads images from Bing, DuckDuckGo, and Unsplash for any topic directly to the local filesystem.
  Use this skill whenever the user asks to: search and download images, fetch images
  for a topic, grab reference photos, collect images from Google, or says anything like
  "get me images of X", "download photos of X", "find and save images of X".
  Automatically creates a dedicated folder, downloads 5 images per topic, detects
  duplicates, and supports 9:16 (portrait/vertical) or 16:9 (landscape/horizontal)
  aspect ratio filtering based on user preference.
---

# Image Extractor Skill

Downloads images from Bing, DuckDuckGo, and Unsplash for a given topic, saves them to a dedicated
local folder, detects duplicates, and filters by aspect ratio (9:16 or 16:9).

---

## Workflow

### Step 1 — Collect Parameters

Ask the user (if not already provided):
1. **Topic** — what to search for (e.g. "northern lights", "lions in savanna")
2. **Aspect ratio** — `9:16` (portrait / vertical) or `16:9` (landscape / horizontal)

If the user already specified both in their message, skip asking and proceed immediately.

---

### Step 2 — Run the Downloader Script

Once you have topic + aspect ratio, run:

```bash
python3 /path/to/image-extractor-skill/scripts/download_images.py \
  --topic "TOPIC_HERE" \
  --ratio "9:16 or 16:9"
```

> Replace `/path/to/image-extractor-skill/` with the actual skill path on disk.
> The script handles folder creation, downloading, deduplication, and saving.

---

### Step 3 — Report to User

After the script completes, tell the user:
- Folder path where images were saved
- How many images were downloaded
- How many duplicates were skipped (if any)
- Any errors or failures

---

## Folder Structure

The script automatically creates:

```
~/Pictures/ImageExtractor/
└── {topic-slug}/
    ├── image_1.jpg
    ├── image_2.jpg
    ├── image_3.jpg
    ├── image_4.jpg
    ├── image_5.jpg
    └── metadata.json     ← source URLs + hash log for dedup
```

- `topic-slug` is the topic lowercased with spaces replaced by underscores
- `metadata.json` tracks source URLs and file hashes to prevent re-downloading duplicates

---

## Aspect Ratio Behavior

| User says       | Behavior                                      |
|----------------|-----------------------------------------------|
| `9:16`         | Filters for portrait images (height > width)  |
| `16:9`         | Filters for landscape images (width > height) |
| Not specified  | Ask before proceeding                         |

Images that don't match the target ratio are skipped and replaced until 5 valid ones are collected (up to 20 candidates fetched total).

---

## Duplicate Detection

- Each downloaded image is hashed (MD5)
- Hash is checked against `metadata.json` in the topic folder
- Duplicate files (same content, different URL) are skipped automatically
- Already-downloaded URLs are also skipped on re-runs

---

## Dependencies

The script installs missing dependencies automatically on first run.
Required packages: `requests`, `Pillow`, `google-images-search` (or `icrawler`)

See `references/setup.md` for manual install instructions if auto-install fails.
