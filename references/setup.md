# Setup & Troubleshooting

## Manual Dependency Install

If auto-install fails, run these manually:

```bash
pip install requests Pillow icrawler
```

Or with pip3:

```bash
pip3 install requests Pillow icrawler
```

---

## Folder Location

Images are saved to:
```
~/Pictures/ImageExtractor/{topic}/
```

On different OS:
- **macOS/Linux**: `/Users/yourname/Pictures/ImageExtractor/`
- **Windows**: `C:\Users\yourname\Pictures\ImageExtractor\`

---

## Google Rate Limiting

Google may throttle requests if you run many searches quickly.
If you get 0 results or errors:
- Wait 30–60 seconds before retrying
- Try a slightly different topic keyword
- The script fetches up to 25 candidates to give ratio filter room to work

---

## Metadata File

Each topic folder contains `metadata.json`:
```json
{
  "hashes": ["md5hash1", "md5hash2", ...],
  "urls": [],
  "files": ["image_1.jpg", "image_2.jpg", ...]
}
```

This file prevents re-downloading duplicates on future runs.
Delete it to reset deduplication for a topic.

---

## Aspect Ratio Notes

- **9:16 (portrait)**: Best for TikTok, Instagram Reels, YouTube Shorts
- **16:9 (landscape)**: Best for YouTube, desktop wallpapers, presentations

The script fetches up to 25 candidates and picks the first 5 that match.
If fewer than 5 match, it reports how many were found.
