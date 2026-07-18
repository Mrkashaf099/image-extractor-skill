---
name: image-extractor
description: >
  Downloads images for a topic directly to the local filesystem. Also supports a
  documentary workflow where Claude can generate a professional script and then
  extract image prompts from it for downloading reference images.
  Use this skill whenever the user asks to: search and download images, fetch images
  for a topic, grab reference photos, collect images for a script, or says anything like
  "get me images of X", "download photos of X", "find and save images of X", or
  "write a script and download matching images".
  Automatically creates a dedicated folder, downloads images per topic, detects
  duplicates, and supports 9:16 (portrait/vertical) or 16:9 (landscape/horizontal)
  aspect ratio filtering based on user preference.
---

# Image Extractor Skill

Downloads images for a given topic, saves them to a dedicated local folder, detects duplicates,
and filters by aspect ratio (9:16 or 16:9).

The repository can also be used as the image layer inside a larger documentary workflow:
Claude generates a script, extracts scene image prompts, and then calls this skill to download
matching reference images.

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
/storage/emulated/0/DCIM/manga/
└── {topic}/
    ├── 001.jpg
    ├── 002.jpg
    ├── 003.jpg
    ├── 004.jpg
    ├── 005.jpg
    └── metadata.json     ← source URLs + hash log for dedup
```

- `{topic}` is the topic name sanitized for Android storage paths
- `metadata.json` tracks source URLs and file hashes to prevent re-downloading duplicates

---

## Aspect Ratio Behavior

| User says       | Behavior                                      |
|----------------|-----------------------------------------------|
| `9:16`         | Filters for portrait images (height > width)  |
| `16:9`         | Filters for landscape images (width > height) |
| Not specified  | Ask before proceeding                         |

Images that don't match the target ratio are skipped and replaced until the requested count is collected.

---

## Duplicate Detection

- Each downloaded image is hashed (MD5)
- Hash is checked against `metadata.json` in the topic folder
- Duplicate files (same content, different URL) are skipped automatically
- Already-downloaded URLs are also skipped on re-runs

---

## Dependencies

The script installs or expects only the runtime packages actually used by the downloader.
Recommended packages: `requests`, `Pillow`

For the documentary workflow, a separate script can be added later to call the Gemini API and generate
professional scripts before handing image prompts off to this downloader.
